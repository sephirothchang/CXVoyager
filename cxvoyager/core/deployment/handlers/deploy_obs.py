# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage deploy_obs – 独立的 OBS 上传与校验流程。"""
from __future__ import annotations

import base64
import logging
import re
import time
import ipaddress
from urllib.parse import urlparse
from pathlib import Path

from cxvoyager.common.config import load_config
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE, PROJECT_ROOT
from cxvoyager.core.deployment.progress import create_stage_progress_logger
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from cxvoyager.core.deployment.login_cloudtower import login_cloudtower
from cxvoyager.core.deployment.query_cluster import query_cluster_by_name
from cxvoyager.core.deployment.query_vnet import query_vnet_by_name
from cxvoyager.common.i18n import tr
from cxvoyager.integrations.smartx.api_client import APIClient

from .app_upload import (
    find_latest_package,
    normalize_base_url,
    _ensure_plan_loaded,
    _resolve_cloudtower_base_url,
    _resolve_cloudtower_token,
    _reset_plan_context,
)

logger = logging.getLogger(__name__)

OBS_INIT_ENDPOINT = "/api/ovm-operator/api/v3/chunkedUploads"
OBS_CHUNK_ENDPOINT = "/api/ovm-operator/api/v1/chunkedUploads"
OBS_COMMIT_ENDPOINT = "/api/ovm-operator/api/v3/chunkedUploads/{upload_id}:commit"
OBS_TASKS_ENDPOINT = "/v2/api/get-tasks"
DEFAULT_OBS_BASIC_AUTH = "Basic bzExeTpIQyFyMGNrcw=="  # o11y:HC!r0cks
DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024  # 4MiB
DEFAULT_TASK_WAIT_TIMEOUT = 900  # seconds
DEFAULT_TASK_POLL_INTERVAL = 5  # seconds
DEFAULT_INSTANCE_WAIT_TIMEOUT = 1800  # seconds
DEFAULT_INSTANCE_POLL_INTERVAL = 10  # seconds
DEFAULT_OBS_NAME = "observability"
STEP_DELAY_SECONDS = 30
OBS_PACKAGE_PATTERN = "Observability-*-v*.tar.gz"
OBS_NAME_REGEX = re.compile(
    r"Observability-(?P<arch>X86_64|AARCH64)-v(?P<version>[\d\.]+)(?:-release\.(?P<date>\d+)(?:-(?P<build>\d+))?)?\.tar\.gz",
    re.IGNORECASE,
)

OBS_VERIFY_QUERY = (
    "query observabilityInstanceAndApps {\n  bundleApplicationPackages {\n    id\n    name\n    version\n    arch\n    application_packages {\n      id\n      architecture\n      version\n      applications {\n        id\n        name\n        __typename\n      }\n      __typename\n    }\n    host_plugin_packages {\n      id\n      arch\n      version\n      __typename\n    }\n    __typename\n  }\n  bundleApplicationInstances {\n    id\n    name\n    status\n    application {\n      id\n      instances {\n        id\n        vm {\n          id\n          status\n          cpu_usage\n          memory_usage\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    vm_spec {\n      ip\n      subnet_mask\n      gateway\n      vlan_id\n      vcpu_count\n      memory_size_bytes\n      storage_size_bytes\n      __typename\n    }\n    description\n    connected_clusters {\n      id\n      name\n      status\n      migration_status\n      cluster {\n        id\n        name\n        hosts {\n          id\n          name\n          __typename\n        }\n        type\n        __typename\n      }\n      host_plugin {\n        id\n        host_plugin_instances\n        __typename\n      }\n      observability_connected_cluster {\n        id\n        traffic_enabled\n        status\n        __typename\n      }\n      __typename\n    }\n    bundle_application_package {\n      id\n      version\n      arch\n      __typename\n    }\n    health_status\n    connected_system_services {\n      id\n      type\n      tenant_id\n      system_service {\n        id\n        name\n        __typename\n      }\n      instances {\n        state\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  bundleApplicationConnectedClusters {\n    id\n    name\n    status\n    migration_status\n    cluster {\n      id\n      name\n      local_id\n      connect_state\n      version\n      type\n      __typename\n    }\n    bundle_application_instance {\n      id\n      name\n      status\n      health_status\n      bundle_application_package {\n        id\n        version\n        __typename\n      }\n      vm_spec {\n        ip\n        __typename\n      }\n      connected_clusters {\n        id\n        name\n        cluster {\n          id\n          local_id\n          name\n          __typename\n        }\n        host_plugin {\n          id\n          host_plugin_instances\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    observability_connected_cluster {\n      id\n      traffic_enabled\n      status\n      __typename\n    }\n    __typename\n  }\n}\n"
)

OBS_ASSOCIATE_MUTATION = (
    "mutation updateBundleApplicationInstanceConnectClusters($where: BundleApplicationInstanceWhereInput!, $data: BundleApplicationInstanceConnectClustersInput!) {\n"
    "  updateBundleApplicationInstanceConnectClusters(where: $where, data: $data) {\n"
    "    id\n    name\n    status\n    error_code\n    cluster { id name __typename }\n    connected_clusters { id name cluster { id name __typename } __typename }\n    __typename\n  }\n}\n"
)

OBS_CREATE_MUTATION = (
    "mutation createBundleApplicationInstance($data: BundleApplicationInstanceCreateInput!) {\n"
    "  createBundleApplicationInstance(data: $data) {\n"
    "    id\n    name\n    status\n    __typename\n  }\n}\n"
)

OBS_ASSOCIATE_SYSTEM_SERVICE_MUTATION = (
    "mutation updateObservabilityConnectedSystemServices($ovm_name: String!, $connected_system_services: [UpdateObservabilityConnectedSystemServiceInput!]!) {\n"
    "  updateObservabilityConnectedSystemServices(ovm_name: $ovm_name, connected_system_services: $connected_system_services) {\n"
    "    connected_system_services {\n"
    "      id\n      type\n      status\n      system_service { id name version __typename }\n      instances { state __typename }\n      __typename\n    }\n"
    "    __typename\n  }\n}\n"
)

OBS_UPDATE_NTP_MUTATION = (
    "mutation updateObservabilityNtpUrl($data: NtpCommonUpdateInput!, $where: BundleApplicationInstanceWhereUniqueInput!) {\n"
    "  updateObservabilityNtpUrl(data: $data, where: $where) {\n"
    "    ntp_service_url\n"
    "    __typename\n"
    "  }\n"
    "}\n"
)


def _resolve_obs_base_url(ctx: RunContext, api_cfg) -> str:
    explicit = None
    if isinstance(api_cfg, dict):
        explicit = api_cfg.get("obs_base_url") or api_cfg.get("cloudtower_base_url") or api_cfg.get("base_url")

    base_url = explicit or _resolve_cloudtower_base_url(ctx, api_cfg)
    if not base_url:
        raise RuntimeError("无法确定 OBS 上传基址（缺少 CloudTower IP）")
    return normalize_base_url(str(base_url))


def _resolve_obs_auth(api_cfg) -> str:
    if isinstance(api_cfg, dict):
        token = api_cfg.get("obs_basic_auth")
        if token:
            return str(token)

        username = api_cfg.get("obs_username")
        password = api_cfg.get("obs_password")
        if username and password:
            raw = f"{username}:{password}"
            encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
            return f"Basic {encoded}"

    return DEFAULT_OBS_BASIC_AUTH


def _build_obs_headers(api_cfg, *, cookie: str | None = None) -> dict:
    headers = {"Authorization": _resolve_obs_auth(api_cfg)}
    if cookie:
        headers["cookie"] = cookie
    return headers


def _delay_between_steps(stage_logger, label: str | None = None) -> None:
    stage_logger.info(
        "[deploy_obs] step delay",
        progress_extra={"seconds": STEP_DELAY_SECONDS, "label": label} if label else {"seconds": STEP_DELAY_SECONDS},
    )
    time.sleep(STEP_DELAY_SECONDS)


def _normalize_server_list(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        values = list(raw)
    elif isinstance(raw, str):
        values = [item.strip() for item in raw.replace(";", ",").split(",")]
    else:
        values = [str(raw).strip()]
    return [item for item in values if item]


def _init_upload(client: APIClient, package_name: str, headers: dict, stage_logger) -> str:
    try:
        resp = client.post(OBS_INIT_ENDPOINT, {"origin_file_name": package_name}, headers=headers)
    except Exception as exc:  # pragma: no cover - surfaced
        stage_logger.error(tr("deploy.deploy_obs.init_fail"), progress_extra={"error": str(exc)})
        raise RuntimeError(f"OBS 上传初始化失败: {exc}")

    upload_id = resp.get("id")
    if not upload_id:
        raise RuntimeError("OBS 上传初始化响应缺少上传ID")

    stage_logger.info(tr("deploy.deploy_obs.upload_created"), progress_extra={"upload_id": upload_id, "status": resp.get("status")})
    return upload_id


def _upload_chunks(client: APIClient, upload_id: str, package_path: Path, headers: dict, stage_logger, chunk_size: int) -> None:
    file_size = package_path.stat().st_size
    sent = 0
    with package_path.open("rb") as f:
        chunk_index = 0
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            chunk_index += 1
            files = {"file": (package_path.name, data, "application/octet-stream")}
            form = {"id": upload_id}
            try:
                resp = client.post(OBS_CHUNK_ENDPOINT, headers=headers, files=files, data=form)
            except Exception as exc:  # pragma: no cover - surfaced
                stage_logger.error(
                    tr("deploy.deploy_obs.chunk_fail"),
                    progress_extra={"chunk": chunk_index, "sent_bytes": sent, "error": str(exc)},
                )
                raise RuntimeError(f"OBS 分片上传失败: {exc}")

            sent += len(data)
            progress = round(sent / file_size * 100, 2) if file_size else 100
            stage_logger.info(
                tr("deploy.deploy_obs.chunk_done"),
                progress_extra={
                    "chunk": chunk_index,
                    "uploaded": sent,
                    "file_size": file_size,
                    "progress_pct": progress,
                    "offset": resp.get("offset"),
                    "status": resp.get("status"),
                },
            )


def _commit_upload(client: APIClient, upload_id: str, headers: dict, stage_logger) -> dict:
    path = OBS_COMMIT_ENDPOINT.format(upload_id=upload_id)
    try:
        resp = client.post(path, headers=headers)
    except Exception as exc:  # pragma: no cover - surfaced
        stage_logger.error(tr("deploy.deploy_obs.commit_fail"), progress_extra={"upload_id": upload_id, "error": str(exc)})
        raise RuntimeError(f"OBS 上传提交失败: {exc}")

    stage_logger.info(tr("deploy.deploy_obs.commit_done"), progress_extra={"upload_id": upload_id, "status": resp.get("status")})
    return resp


def _verify_obs_pak_instance(
    ctx: RunContext,
    api_cfg,
    base_url: str,
    stage_logger,
    *,
    cookie: str | None = None,
    ct_token: str | None = None,
    log_info: bool = True,
) -> dict:
    token = ct_token or _resolve_cloudtower_token(
        ctx=ctx, api_cfg=api_cfg, cloudtower_base_url=base_url, stage_logger=stage_logger
    )
    if not token:
        raise RuntimeError("OBS 校验失败：无法获取 CloudTower token")

    verify_headers = {"Authorization": token}
    if cookie:
        verify_headers["cookie"] = cookie
    timeout = int(api_cfg.get("timeout", 10)) if isinstance(api_cfg, dict) else 10
    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False
    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    payload = {"operationName": "observabilityInstanceAndApps", "variables": {}, "query": OBS_VERIFY_QUERY}
    try:
        resp = client.post("/api", payload, headers=verify_headers)
    except Exception as exc:  # pragma: no cover - surfaced
        stage_logger.error(tr("deploy.deploy_obs.verify_fail"), progress_extra={"error": str(exc)})
        raise RuntimeError(f"OBS 校验接口调用失败: {exc}")

    data = resp.get("data") if isinstance(resp, dict) else None
    packages = data.get("bundleApplicationPackages") if isinstance(data, dict) else None
    found = False
    version = None
    if isinstance(packages, list):
        for pkg in packages:
            if isinstance(pkg, dict) and str(pkg.get("name") or "").strip().lower() == "observability":
                found = True
                version = pkg.get("version")
                break

    if log_info:
        stage_logger.info(
            tr("deploy.deploy_obs.verify_done"),
            progress_extra={"found": found, "version": version},
        )
    resp["verified"] = found
    resp["version"] = version
    return resp


def _extract_version_from_filename(filename: str) -> str | None:
    m = OBS_NAME_REGEX.search(filename)
    if not m:
        return None
    version = m.group("version")
    date = m.group("date")
    build = m.group("build")
    if date and build:
        return f"{version}-release.{date}-{build}"
    if date:
        return f"{version}-release.{date}"
    return version


def _is_package_already_present(verify_resp: dict, package_path: Path) -> tuple[bool, str | None]:
    target = _extract_version_from_filename(package_path.name)
    if not target:
        return False, None

    data = verify_resp.get("data") if isinstance(verify_resp, dict) else None
    packages = data.get("bundleApplicationPackages") if isinstance(data, dict) else None
    if not isinstance(packages, list):
        return False, None

    target_norm = target.lower().lstrip("v")
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        if str(pkg.get("name") or "").strip().lower() != "observability":
            continue
        version = str(pkg.get("version") or "").lower().lstrip("v")
        # 优先相信平台版本：只要本地文件名中的版本包含平台版本（或相等），即可视为已存在
        if version and (version == target_norm or target_norm in version or version in target_norm):
            return True, pkg.get("version")
    return False, None


def _select_obs_package_for_install(verify_resp: dict, package_path: Path) -> dict | None:
    target = _extract_version_from_filename(package_path.name)
    data = verify_resp.get("data") if isinstance(verify_resp, dict) else None
    packages = data.get("bundleApplicationPackages") if isinstance(data, dict) else None
    if not isinstance(packages, list):
        return None

    target_norm = target.lower().lstrip("v") if target else None
    for pkg in packages:
        if not isinstance(pkg, dict) or str(pkg.get("name") or "").strip().lower() != "observability":
            continue
        version = str(pkg.get("version") or "").lower().lstrip("v")
        if target_norm and (version == target_norm or target_norm in version or version in target_norm):
            return pkg
    # 未匹配到具体版本，回退取第一条 Observability 记录
    for pkg in packages:
        if isinstance(pkg, dict) and str(pkg.get("name") or "").strip().lower() == "observability":
            return pkg
    return None


def _resolve_cluster_name(ctx: RunContext) -> str | None:
    plan = getattr(ctx, "plan", None)
    # 尝试从规划表模型获取集群名称，若缺失则返回 None
    try:
        hosts = getattr(plan, "hosts", None)
        if hosts:
            name = getattr(hosts[0], "集群名称", None)
            if name:
                return str(name).strip()
        name = getattr(plan, "集群名称", None)
        if name:
            return str(name).strip()
    except Exception:  # noqa: BLE001 - 容错
        return None
    return None


def _extract_obs_instance_id(verify_resp: dict) -> str | None:
    data = verify_resp.get("data") if isinstance(verify_resp, dict) else None
    instances = data.get("bundleApplicationInstances") if isinstance(data, dict) else None
    if not isinstance(instances, list):
        return None
    for inst in instances:
        if not isinstance(inst, dict):
            continue
        name = str(inst.get("name") or "").strip().lower()
        if name in {"obs", "observability"}:
            return inst.get("id")
    return None


def _associate_obs_instance(
    *,
    base_url: str,
    cookie: str,
    token: str | None,
    instance_id: str,
    cluster_id: str,
    stage_logger,
    api_cfg,
):
    timeout = int(api_cfg.get("timeout", 10)) if isinstance(api_cfg, dict) else 10
    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False
    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    headers = {"cookie": cookie}
    if token:
        headers["Authorization"] = token

    payload = {
        "operationName": "updateBundleApplicationInstanceConnectClusters",
        "variables": {"where": {"id": instance_id}, "data": {"connected_clusters": {"id_in": [cluster_id]}}},
        "query": OBS_ASSOCIATE_MUTATION,
    }

    stage_logger.info(
        tr("deploy.deploy_obs.associate_cluster"),
        progress_extra={"instance_id": instance_id, "cluster_id": cluster_id, "base_url": base_url.rstrip("/")},
    )
    resp = client.post("/api", payload, headers=headers)
    if isinstance(resp, dict) and resp.get("errors"):
        stage_logger.error(
            tr("deploy.deploy_obs.associate_cluster_fail"),
            progress_extra={"instance_id": instance_id, "cluster_id": cluster_id, "errors": resp.get("errors")},
        )
    else:
        stage_logger.info(
            tr("deploy.deploy_obs.associate_cluster_done"),
            progress_extra={"instance_id": instance_id, "cluster_id": cluster_id},
        )
    stage_logger.debug(
        tr("deploy.deploy_obs.associate_cluster_debug"),
        progress_extra={"keys": sorted(resp.keys()) if isinstance(resp, dict) else type(resp).__name__},
    )
    return resp


def _associate_obs_system_service(
    *,
    base_url: str,
    cookie: str,
    token: str | None,
    obs_name: str,
    stage_logger,
    api_cfg,
):
    timeout = int(api_cfg.get("timeout", 10)) if isinstance(api_cfg, dict) else 10
    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False
    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    parsed = urlparse(base_url)
    host = parsed.hostname or base_url
    service_url = f"http://{host}/admin/observability/agent"

    headers = {"cookie": cookie}
    if token:
        headers["Authorization"] = token

    connected_system_services = [
        {
            "system_service_id": "CLOUDTOWER",
            "system_service_name": "CloudTower",
            "type": "CLOUDTOWER",
            "alerting_rules": [
                {
                    "name": "cluster_connect_status",
                    "type": "METRIC",
                    "metric_validator": {
                        "interval": "30s",
                        "for": "5m",
                        "query_tmpl": "cluster_connect_status * on (_tenant_id) group_left (service_name) obs_agent_info == 0",
                    },
                    "metric_descriptor": {"unit": "UNIT_UNSPECIFIED"},
                    "default_thresholds": [{"severity": "INFO", "value": "0"}],
                    "thresholds": [{"severity": "INFO", "value": "0"}],
                    "messages": [
                        {
                            "locale": "en-US",
                            "str": "CloudTower failed to connect to the {{ $labels.clusterType }} cluster {{ $labels.clusterName }}.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "CloudTower 与 {{ $labels.clusterType }} 集群 {{ $labels.clusterName }} 连接异常。",
                        },
                    ],
                    "causes": [
                        {"locale": "en-US", "str": "Network connectivity error or cluster status error."},
                        {"locale": "zh-CN", "str": "网络连接异常或集群运行状态异常。"},
                    ],
                    "impacts": [
                        {
                            "locale": "en-US",
                            "str": "This may prevent the cluster from functioning or being managed properly.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "可能导致无法正常使用或管理集群。",
                        },
                    ],
                    "solutions": [
                        {
                            "locale": "en-US",
                            "str": "Please check the network connectivity or the cluster status.",
                        },
                        {"locale": "zh-CN", "str": "请确认网络连通性或集群状态。"},
                    ],
                },
                {
                    "name": "cluster_authentication_status",
                    "type": "METRIC",
                    "metric_validator": {
                        "interval": "30s",
                        "for": "5m",
                        "query_tmpl": "cluster_authentication_status * on (_tenant_id) group_left (service_name) obs_agent_info == 0",
                    },
                    "metric_descriptor": {"unit": "UNIT_UNSPECIFIED"},
                    "default_thresholds": [{"severity": "INFO", "value": "0"}],
                    "thresholds": [{"severity": "INFO", "value": "0"}],
                    "messages": [
                        {
                            "locale": "en-US",
                            "str": "Cluster unreachable due to authentication failure for the {{ $labels.clusterType }} cluster {{ $labels.clusterName }}.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "集群无法连接，因 {{ $labels.clusterType }} 集群 {{ $labels.clusterName }} 鉴权失败。",
                        },
                    ],
                    "causes": [
                        {"locale": "en-US", "str": "Cluster authentication failed."},
                        {"locale": "zh-CN", "str": "集群鉴权失败。"},
                    ],
                    "impacts": [
                        {
                            "locale": "en-US",
                            "str": "CloudTower failed to connect to the cluster, which may result in the cluster being unavailable or unmanageable.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "CloudTower 与集群连接异常，可能无法正常使用或管理集群。",
                        },
                    ],
                    "solutions": [
                        {
                            "locale": "en-US",
                            "str": "Please confirm that the administrator username and password are correct.",
                        },
                        {"locale": "zh-CN", "str": "请确认集群管理员用户名及密码。"},
                    ],
                },
                {
                    "name": "service_cpu_usage_overload",
                    "type": "METRIC",
                    "metric_validator": {
                        "interval": "30s",
                        "for": "10m",
                        "query_tmpl": "sum without (mode) (avg without (cpu) (rate(node_cpu_seconds_total{mode!='idle'}[2m]))) * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info * 100 > {{ .threshold }}",
                    },
                    "metric_descriptor": {"unit": "PERCENT"},
                    "default_thresholds": [{"severity": "NOTICE", "value": "90"}],
                    "thresholds": [{"severity": "NOTICE", "value": "90"}],
                    "messages": [
                        {
                            "locale": "en-US",
                            "str": "The CPU usage of the virtual machine {{ $labels.vm_name }} running CloudTower is too high.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "运行 CloudTower 的虚拟机 {{ $labels.vm_name }} 的 CPU 占用过高。",
                        },
                    ],
                    "causes": [
                        {
                            "locale": "en-US",
                            "str": "The increased system load causes the vCPUs on the virtual machine running the system service to become insufficient for the service to run properly.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "因系统负载增大，当前运行系统服务的虚拟机的 vCPU 数量已不足以支持系统服务平稳运行。",
                        },
                    ],
                    "impacts": [
                        {"locale": "en-US", "str": "The system service may not run properly."},
                        {"locale": "zh-CN", "str": "可能导致系统服务无法正常提供服务。"},
                    ],
                    "solutions": [
                        {
                            "locale": "en-US",
                            "str": "Scale up the system service virtual machine, or contact technical support for assistance.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "提高该系统服务虚拟机的资源配置，或联系售后技术支持。",
                        },
                    ],
                },
                {
                    "name": "service_disk_usage_overload",
                    "type": "METRIC",
                    "metric_validator": {
                        "interval": "30s",
                        "for": "5m",
                        "query_tmpl": "100 - (node_filesystem_avail_bytes{mountpoint='/'} / node_filesystem_size_bytes{mountpoint='/'}) * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info * 100 > {{ .threshold }}",
                    },
                    "metric_descriptor": {"unit": "PERCENT"},
                    "default_thresholds": [{"severity": "NOTICE", "value": "90"}],
                    "thresholds": [{"severity": "NOTICE", "value": "90"}],
                    "messages": [
                        {
                            "locale": "en-US",
                            "str": "The storage capacity on the virtual machine {{ $labels.vm_name }} running CloudTower is insufficient.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "运行 CloudTower 的虚拟机 {{ $labels.vm_name }} 的存储空间不足。",
                        },
                    ],
                    "causes": [
                        {
                            "locale": "en-US",
                            "str": "The increased system load causes the storage capacity on the virtual machine running the system service to become insufficient for the service to run properly.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "因系统负载增大，当前运行系统服务的虚拟机的存储空间已不足以支持系统服务平稳运行。",
                        },
                    ],
                    "impacts": [
                        {"locale": "en-US", "str": "The system service may not run properly."},
                        {"locale": "zh-CN", "str": "可能导致系统服务无法正常提供服务。"},
                    ],
                    "solutions": [
                        {
                            "locale": "en-US",
                            "str": "Scale up the system service virtual machine, or contact technical support for assistance.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "提高该系统服务虚拟机的资源配置，或联系售后技术支持。",
                        },
                    ],
                },
                {
                    "name": "service_memory_usage_overload",
                    "type": "METRIC",
                    "metric_validator": {
                        "interval": "30s",
                        "for": "5m",
                        "query_tmpl": "100 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes * 100 * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info > {{ .threshold }}",
                    },
                    "metric_descriptor": {"unit": "PERCENT"},
                    "default_thresholds": [{"severity": "NOTICE", "value": "80"}],
                    "thresholds": [{"severity": "NOTICE", "value": "80"}],
                    "messages": [
                        {
                            "locale": "en-US",
                            "str": "The memory usage of the virtual machine {{ $labels.vm_name }} running CloudTower is too high.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "运行 CloudTower 的虚拟机 {{ $labels.vm_name }} 的内存使用率过高。",
                        },
                    ],
                    "causes": [
                        {
                            "locale": "en-US",
                            "str": "The increased system load causes the memory on the virtual machine running the system service to become insufficient for the service to run properly.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "因系统负载增大，当前运行系统服务的虚拟机的内存分配量已不足以支持系统服务平稳运行。",
                        },
                    ],
                    "impacts": [
                        {"locale": "en-US", "str": "The system service may not run properly."},
                        {"locale": "zh-CN", "str": "可能导致系统服务无法正常提供服务。"},
                    ],
                    "solutions": [
                        {
                            "locale": "en-US",
                            "str": "Scale up the system service virtual machine, or contact technical support for assistance.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "提高该系统服务虚拟机的资源配置，或联系售后技术支持。",
                        },
                    ],
                },
                {
                    "name": "service_vm_has_no_ntp_server",
                    "type": "METRIC",
                    "metric_validator": {
                        "interval": "30s",
                        "query_tmpl": "host_ntp_server_numbers * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info == {{ .threshold }}",
                    },
                    "default_thresholds": [{"severity": "INFO", "value": "0"}],
                    "thresholds": [{"severity": "INFO", "value": "0"}],
                    "messages": [
                        {"locale": "en-US", "str": "CloudTower is not configured with an NTP server."},
                        {"locale": "zh-CN", "str": "CloudTower 未配置 NTP 服务器。"},
                    ],
                    "causes": [
                        {"locale": "en-US", "str": "CloudTower is not configured with an NTP server."},
                        {"locale": "zh-CN", "str": "CloudTower 未配置 NTP 服务器。"},
                    ],
                    "impacts": [
                        {
                            "locale": "en-US",
                            "str": "The CloudTower time might be inaccurate, which affects the time display in task and monitoring functions. Other system services including backup and SKS might encounter exceptions. ",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "CloudTower 的时间可能不准确，影响任务、监控等功能的时间显示，或造成备份与容灾、Kubernetes 等其他系统服务的功能异常。",
                        },
                    ],
                    "solutions": [
                        {"locale": "en-US", "str": "Configure an NTP server for CloudTower."},
                        {"locale": "zh-CN", "str": "为 CloudTower 配置 NTP 服务器。"},
                    ],
                },
                {
                    "name": "service_vm_disconnect_with_each_ntp_server",
                    "type": "METRIC",
                    "metric_validator": {
                        "interval": "30s",
                        "query_tmpl": "host_can_connect_with_each_ntp_server * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info == {{ .threshold }}",
                    },
                    "metric_descriptor": {"is_boolean": True},
                    "default_thresholds": [{"severity": "NOTICE", "value": "0"}],
                    "thresholds": [{"severity": "NOTICE", "value": "0"}],
                    "messages": [
                        {
                            "locale": "en-US",
                            "str": "Failed to establish the connection between the CloudTower and the NTP server {{ $labels.ntp_server }}.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "CloudTower 无法与 NTP 服务器 {{ $labels.ntp_server }} 建立连接。",
                        },
                    ],
                    "causes": [
                        {
                            "locale": "en-US",
                            "str": "The current NTP server’s domain name or IP address might be invalid, or there might be a network exception.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "当前设置的 NTP 服务器域名、IP 地址可能无效，或存在网络异常。",
                        },
                    ],
                    "impacts": [
                        {
                            "locale": "en-US",
                            "str": "The CloudTower time might be inconsistent with the NTP server time.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "CloudTower 与 NTP 服务器的时间可能不同步。",
                        },
                    ],
                    "solutions": [
                        {
                            "locale": "en-US",
                            "str": "Check the network connection, or verify the validity of the external NTP server’s domain name and IP address. If the connection to the NTP server fails, you need to reconfigure a valid NTP server.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "检查网络连接或外部 NTP 服务器域名、IP 是否有效。若无法正常连接 NTP 服务器，则重新设置一个有效 NTP 服务器。",
                        },
                    ],
                },
                {
                    "name": "service_vm_time_offset_with_ntp_leader",
                    "type": "METRIC",
                    "metric_validator": {
                        "interval": "30s",
                        "for": "3m",
                        "query_tmpl": "host_time_offset_with_ntp_leader_seconds * on (_tenant_id) group_left (service_name, vm_name) obs_agent_info > {{ .threshold }}",
                    },
                    "metric_descriptor": {"unit": "SECOND"},
                    "default_thresholds": [
                        {"severity": "INFO", "value": "10"},
                        {"severity": "NOTICE", "value": "30"},
                        {"severity": "CRITICAL", "value": "60"},
                    ],
                    "thresholds": [
                        {"severity": "INFO", "value": "10"},
                        {"severity": "NOTICE", "value": "30"},
                        {"severity": "CRITICAL", "value": "60"},
                    ],
                    "messages": [
                        {
                            "locale": "en-US",
                            "str": "The time offset between the CloudTower and the NTP server is excessively large.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "CloudTower 与 NTP 服务器时间偏移量过大。",
                        },
                    ],
                    "causes": [
                        {
                            "locale": "en-US",
                            "str": "The time offset between the CloudTower and the NTP server is excessively large.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "CloudTower 与 NTP 服务器时间偏差过大。",
                        },
                    ],
                    "impacts": [
                        {"locale": "en-US", "str": "The CloudTower time is inaccurate, and the NTP service might stop synchronizing time."},
                        {"locale": "zh-CN", "str": "CloudTower 的时间不准确，且可能导致 NTP 服务停止同步。"},
                    ],
                    "solutions": [
                        {"locale": "en-US", "str": "Contact technical support for assistance."},
                        {"locale": "zh-CN", "str": "联系售后技术支持。"},
                    ],
                },
                {
                    "name": "cloudtower_system_service_vm_time_offset_seconds",
                    "type": "METRIC",
                    "metric_validator": {
                        "interval": "30s",
                        "for": "3m",
                        "query_tmpl": "abs(cloudtower_system_service_vm_time_offset_seconds) * on (_tenant_id) group_left (service_name) obs_agent_info > {{ .threshold }}",
                    },
                    "metric_descriptor": {"unit": "SECOND"},
                    "default_thresholds": [
                        {"severity": "NOTICE", "value": "30"},
                        {"severity": "CRITICAL", "value": "60"},
                    ],
                    "thresholds": [
                        {"severity": "NOTICE", "value": "30"},
                        {"severity": "CRITICAL", "value": "60"},
                    ],
                    "messages": [
                        {
                            "locale": "en-US",
                            "str": "The time offset between CloudTower and the system service virtual machine {{ $labels.vm_name }} is excessively large.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "CloudTower 与系统服务虚拟机 {{ $labels.vm_name }} 的时间偏移量过大。",
                        },
                    ],
                    "causes": [
                        {
                            "locale": "en-US",
                            "str": "The CloudTower time is inconsistent with the time of the system service virtual machine {{ $labels.vm_name }}.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "CloudTower 与系统服务虚拟机 {{ $labels.vm_name }} 的时间不同步。",
                        },
                    ],
                    "impacts": [
                        {
                            "locale": "en-US",
                            "str": "The system service might not be able to function properly.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "系统服务可能无法正常工作。",
                        },
                    ],
                    "solutions": [
                        {
                            "locale": "en-US",
                            "str": "Configure time-consistent NTP servers for the system service and CloudTower, and check the synchronization between the system service and its NTP server.",
                        },
                        {
                            "locale": "zh-CN",
                            "str": "为系统服务与 CloudTower 配置时间一致的 NTP 服务器，并检查系统服务与 NTP 服务器的同步情况。",
                        },
                    ],
                },
            ],
            "instances": [
                {
                    "url": service_url,
                    "info": {"service_name": "CloudTower", "vm_name": "cloudtower"},
                }
            ],
        }
    ]

    payload = {
        "operationName": "updateObservabilityConnectedSystemServices",
        "variables": {
            "ovm_name": obs_name or DEFAULT_OBS_NAME,
            "connected_system_services": connected_system_services,
        },
        "query": OBS_ASSOCIATE_SYSTEM_SERVICE_MUTATION,
    }

    stage_logger.info(
        tr("deploy.deploy_obs.associate_system_service"),
        progress_extra={"ovm_name": obs_name, "url": service_url},
    )
    resp = client.post("/api", payload, headers=headers)
    stage_logger.debug(
        tr("deploy.deploy_obs.associate_system_service_debug"),
        progress_extra={"keys": sorted(resp.keys()) if isinstance(resp, dict) else type(resp).__name__},
    )
    return resp


def _create_obs_instance(
    *,
    base_url: str,
    cookie: str,
    token: str | None,
    package_id: str,
    cluster_id: str,
    vm_spec: dict,
    name: str,
    stage_logger,
    api_cfg,
):
    timeout = int(api_cfg.get("timeout", 10)) if isinstance(api_cfg, dict) else 10
    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False
    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    headers = {"cookie": cookie}
    if token:
        headers["Authorization"] = token

    payload = {
        "operationName": "createBundleApplicationInstance",
        "variables": {
            "data": {
                "name": name,
                "description": "",
                "bundle_application_package": {"id": package_id},
                "cluster": {"id": cluster_id},
                "host_id": "",
                "vm_spec": vm_spec,
            }
        },
        "query": OBS_CREATE_MUTATION,
    }

    stage_logger.info(
        tr("deploy.deploy_obs.create_instance"),
        progress_extra={"name": name, "cluster_id": cluster_id, "package_id": package_id},
    )
    resp = client.post("/api", payload, headers=headers)
    stage_logger.debug(
        tr("deploy.deploy_obs.create_instance_debug"),
        progress_extra={"keys": sorted(resp.keys()) if isinstance(resp, dict) else type(resp).__name__},
    )
    return resp


def _wait_obs_tasks(
    *,
    base_url: str,
    token: str | None,
    stage_logger,
    api_cfg,
    package_name: str,
) -> dict | None:
    if not token:
        stage_logger.warning(tr("deploy.deploy_obs.tasks_no_token"))
        return None

    timeout = int(api_cfg.get("obs_task_wait_timeout", DEFAULT_TASK_WAIT_TIMEOUT)) if isinstance(api_cfg, dict) else DEFAULT_TASK_WAIT_TIMEOUT
    interval = int(api_cfg.get("obs_task_poll_interval", DEFAULT_TASK_POLL_INTERVAL)) if isinstance(api_cfg, dict) else DEFAULT_TASK_POLL_INTERVAL
    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False
    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    headers = {"Authorization": token, "content-type": "application/json"}
    deadline = time.monotonic() + timeout
    package_key = package_name.lower()
    last_resp: dict | None = None

    stage_logger.info(
        tr("deploy.deploy_obs.tasks_polling"),
        progress_extra={"timeout_s": timeout, "interval_s": interval, "package": package_name},
    )

    while time.monotonic() < deadline:
        try:
            resp = client.post(OBS_TASKS_ENDPOINT, payload={}, headers=headers)
        except Exception as exc:  # pragma: no cover - surfaced
            stage_logger.warning(tr("deploy.deploy_obs.tasks_query_fail_retry"), progress_extra={"error": str(exc)})
            time.sleep(interval)
            continue

        last_resp = resp if isinstance(resp, dict) else None
        tasks = resp if isinstance(resp, list) else resp.get("data") if isinstance(resp, dict) else None
        tasks_list = tasks if isinstance(tasks, list) else []

        matched = [t for t in tasks_list if isinstance(t, dict) and package_key in str(t.get("description") or "").lower()]
        if matched:
            all_done = all(str(t.get("status") or "").upper() == "SUCCESSED" for t in matched)
            if all_done:
                stage_logger.info(
                    tr("deploy.deploy_obs.tasks_done"),
                    progress_extra={"tasks": [t.get("id") for t in matched]},
                )
                return {"tasks": matched}
            has_error = any(str(t.get("status") or "").upper() in {"FAILED", "ERROR"} for t in matched)
            if has_error:
                raise RuntimeError(f"OBS 安装包处理任务失败: {[t.get('status') for t in matched]}")

        time.sleep(interval)

    stage_logger.warning(tr("deploy.deploy_obs.tasks_timeout"), progress_extra={"timeout_s": timeout})
    return last_resp


def _resolve_obs_vm_spec(ctx: RunContext, deploy_cfg: dict) -> tuple[dict | None, str | None]:
    plan = getattr(ctx, "plan", None)
    mgmt = getattr(plan, "mgmt", None)
    virtual_networks = getattr(plan, "virtual_network", []) if plan else []

    ip = getattr(mgmt, "obs_ip", None)
    subnet_mask = None
    gateway = None

    # 从规划表虚拟网络中定位 default（管理网）记录，提取 vlan/gateway/subnet
    for vn in virtual_networks:
        name = getattr(vn, "虚拟机网络", None) or getattr(vn, "network", None)
        label = str(name or "").lower()
        if label != "default":
            continue
        gateway = getattr(vn, "gateway", None)
        subnet = getattr(vn, "subnetwork", None)
        if subnet:
            try:
                net = ipaddress.ip_network(str(subnet), strict=False)
                subnet_mask = str(net.netmask)
            except Exception:
                subnet_mask = None
        break

    # 固定值
    name = DEFAULT_OBS_NAME
    vcpu_count = 16
    memory_size_bytes = 32 * 1024 * 1024 * 1024
    storage_size_bytes = 512 * 1024 * 1024 * 1024
    env_vars = {"PRODUCT_VENDOR": "SMARTX"}

    required = {"ip": ip, "subnet_mask": subnet_mask, "gateway": gateway}
    if not all(required.values()):
        return None, name

    vm_spec = {
        "ip": str(ip),
        "subnet_mask": str(subnet_mask),
        "gateway": str(gateway),
        "vcpu_count": vcpu_count,
        "memory_size_bytes": str(memory_size_bytes),
        "storage_size_bytes": str(storage_size_bytes),
        "env_vars": env_vars,
    }
    return vm_spec, name


def _resolve_ntp_servers(ctx: RunContext, api_cfg: dict, deploy_cfg: dict) -> list[str]:
    plan = getattr(ctx, "plan", None)
    mgmt = getattr(plan, "mgmt", None)

    candidates = None
    for attr in ("NTP服务器", "NTP 服务器", "ntp_servers"):
        if mgmt and getattr(mgmt, attr, None):
            candidates = getattr(mgmt, attr)
            break

    if candidates is None and isinstance(deploy_cfg, dict):
        candidates = deploy_cfg.get("ntp_servers")

    if candidates is None and isinstance(api_cfg, dict):
        candidates = api_cfg.get("ntp_servers")

    if candidates is None and isinstance(ctx.extra, dict):
        candidates = ctx.extra.get("ntp_servers")

    return _normalize_server_list(candidates)


def _update_obs_ntp(
    *,
    base_url: str,
    cookie: str,
    token: str | None,
    instance_id: str,
    servers: list[str],
    stage_logger,
    api_cfg,
) -> dict:
    timeout = int(api_cfg.get("timeout", 10)) if isinstance(api_cfg, dict) else 10
    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False
    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    headers = {"cookie": cookie}
    if token:
        headers["Authorization"] = token

    joined = ",".join(servers)
    payload = {
        "operationName": "updateObservabilityNtpUrl",
        "variables": {"data": {"ntp_service_url": joined}, "where": {"id": instance_id}},
        "query": OBS_UPDATE_NTP_MUTATION,
    }

    stage_logger.info(
        tr("deploy.deploy_obs.ntp_start"),
        progress_extra={"instance_id": instance_id, "servers": servers},
    )
    resp = client.post("/api", payload, headers=headers)
    stage_logger.debug(
        tr("deploy.deploy_obs.ntp_done"),
        progress_extra={
            "instance_id": instance_id,
            "servers": servers,
            "ntp_service_url": joined,
            "keys": sorted(resp.keys()) if isinstance(resp, dict) else type(resp).__name__,
        },
    )
    return resp


def _wait_obs_instance(
    *,
    ctx: RunContext,
    api_cfg,
    base_url: str,
    stage_logger,
    name: str,
    cookie: str | None,
    token: str | None,
    timeout: int | None = None,
    interval: int | None = None,
) -> dict | None:
    if not token:
        stage_logger.warning(tr("deploy.deploy_obs.wait_instance_no_token"))
        return None

    wait_timeout = timeout or int(api_cfg.get("obs_instance_wait_timeout", DEFAULT_INSTANCE_WAIT_TIMEOUT)) if isinstance(api_cfg, dict) else DEFAULT_INSTANCE_WAIT_TIMEOUT
    wait_interval = interval or int(api_cfg.get("obs_instance_poll_interval", DEFAULT_INSTANCE_POLL_INTERVAL)) if isinstance(api_cfg, dict) else DEFAULT_INSTANCE_POLL_INTERVAL

    deadline = time.monotonic() + wait_timeout
    stage_logger.info(
        tr("deploy.deploy_obs.wait_instance_poll"),
        progress_extra={"timeout_s": wait_timeout, "interval_s": wait_interval, "name": name},
    )

    last_resp: dict | None = None
    while time.monotonic() < deadline:
        verify_resp = _verify_obs_pak_instance(
            ctx,
            api_cfg,
            base_url,
            stage_logger,
            cookie=cookie,
            ct_token=token,
            log_info=False,
        )
        last_resp = verify_resp
        instance_id = _extract_obs_instance_id(verify_resp)
        data = verify_resp.get("data") if isinstance(verify_resp, dict) else None
        instances = data.get("bundleApplicationInstances") if isinstance(data, dict) else None
        if not isinstance(instances, list):
            time.sleep(wait_interval)
            continue
        target = None
        for inst in instances:
            if not isinstance(inst, dict):
                continue
            if str(inst.get("name") or "").strip().lower() == name.lower():
                target = inst
                break

        if not target:
            time.sleep(wait_interval)
            continue

        status = str(target.get("status") or "").upper()
        vm_info = target.get("vm") or {}
        vm_status = str(vm_info.get("status") or "").upper() if isinstance(vm_info, dict) else None

        if status in {"SUCCESS", "SUCCEEDED"} or vm_status == "RUNNING":
            stage_logger.info(
                tr("deploy.deploy_obs.wait_instance_ready"),
                progress_extra={"status": status, "vm_status": vm_status, "instance_id": instance_id},
            )
            return target
        if status in {"FAILED", "ERROR"}:
            raise RuntimeError(f"OBS 实例部署失败: {status}")

        time.sleep(wait_interval)

    stage_logger.warning(tr("deploy.deploy_obs.wait_instance_timeout"), progress_extra={"timeout_s": wait_timeout})
    return last_resp


@stage_handler(Stage.deploy_obs) # type: ignore
def handle_deploy_obs(ctx_dict):
    """独立的 OBS 上传与校验实现，不复用通用 app_upload 模块。"""

    ctx: RunContext = ctx_dict["ctx"]  # type: ignore[index]
    stage_logger = create_stage_progress_logger(ctx, Stage.deploy_obs.value, logger=logger, prefix="[deploy_obs]")

    _reset_plan_context(ctx)
    _ensure_plan_loaded(ctx)
    _delay_between_steps(stage_logger, "plan_loaded")

    cfg = ctx.config or load_config(DEFAULT_CONFIG_FILE)
    cfg_dict = cfg if isinstance(cfg, dict) else {}
    api_cfg = cfg_dict.get("api", {}) if isinstance(cfg_dict, dict) else {}
    deploy_cfg = cfg_dict.get("deploy", {}) if isinstance(cfg_dict, dict) else {}

    timeout = int(api_cfg.get("timeout", 10)) if isinstance(api_cfg, dict) else 10
    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False
    chunk_size = int(api_cfg.get("obs_chunk_size", DEFAULT_CHUNK_SIZE)) if isinstance(api_cfg, dict) else DEFAULT_CHUNK_SIZE

    cli_opts = ctx.extra.get("cli_options", {}) if isinstance(ctx.extra, dict) else {}
    dry_run = bool(cli_opts.get("dry_run", deploy_cfg.get("dry_run", False)))
    obs_name_default = DEFAULT_OBS_NAME

    work_dir = ctx.work_dir if isinstance(ctx.work_dir, Path) else Path(ctx.work_dir)
    search_roots = [work_dir, PROJECT_ROOT, PROJECT_ROOT / "release", PROJECT_ROOT / "resources", PROJECT_ROOT / "artifacts"]

    package_path = find_latest_package(
        app=type("ObsSpec", (), {"package_pattern": OBS_PACKAGE_PATTERN, "name_regex": OBS_NAME_REGEX}), # type: ignore
        search_roots=search_roots,
    )

    base_url = _resolve_obs_base_url(ctx, api_cfg)
    login_result = login_cloudtower(ctx, base_url=base_url, api_cfg=api_cfg, stage_logger=stage_logger)
    cookie = login_result.get("cookie") if isinstance(login_result, dict) else None
    ct_token = login_result.get("token") if isinstance(login_result, dict) else None

    _delay_between_steps(stage_logger, "after_login")

    if not cookie:
        stage_logger.error(
            tr("deploy.deploy_obs.login_no_cookie"),
            progress_extra={"base_url": base_url, "login_keys": sorted(login_result.keys()) if isinstance(login_result, dict) else type(login_result).__name__},
        )
        raise RuntimeError("OBS 部署中断：CloudTower 登录失败，缺少 cookie")

    headers = _build_obs_headers(api_cfg, cookie=cookie)
    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    stage_logger.info(
        tr("deploy.deploy_obs.start_upload"),
        progress_extra={"file": package_path.name, "base_url": base_url, "chunk_size": chunk_size, "dry_run": dry_run},
    )

    if dry_run:
        result = {
            "dry_run": True,
            "package": package_path.name,
            "base_url": base_url,
            "chunk_size": chunk_size,
        }
    else:
        pre_verify = _verify_obs_pak_instance(ctx, api_cfg, base_url, stage_logger, cookie=cookie, ct_token=ct_token)
        _delay_between_steps(stage_logger, "after_pre_verify")
        already_present, existing_version = _is_package_already_present(pre_verify, package_path)

        upload_id = None
        commit_resp = None
        tasks_resp = None
        install_create_resp = None
        install_wait_resp = None
        ntp_resp = None
        system_service_resp = None

        if already_present:
            stage_logger.info(
                tr("deploy.deploy_obs.package_exists_skip"),
                progress_extra={"package": package_path.name, "version": existing_version},
            )
            verify_resp = pre_verify
        else:
            upload_id = _init_upload(client, package_path.name, headers, stage_logger)
            _delay_between_steps(stage_logger, "after_init_upload")
            _upload_chunks(client, upload_id, package_path, headers, stage_logger, chunk_size)
            _delay_between_steps(stage_logger, "after_upload_chunks")
            commit_resp = _commit_upload(client, upload_id, headers, stage_logger)
            _delay_between_steps(stage_logger, "after_commit_upload")
            tasks_resp = _wait_obs_tasks(
                base_url=base_url,
                token=ct_token,
                stage_logger=stage_logger,
                api_cfg=api_cfg,
                package_name=package_path.name,
            )
            _delay_between_steps(stage_logger, "after_wait_tasks")
            verify_resp = _verify_obs_pak_instance(ctx, api_cfg, base_url, stage_logger, cookie=cookie, ct_token=ct_token)
            _delay_between_steps(stage_logger, "after_verify_post_upload")

        associate_resp = None
        try:
            cluster_name = _resolve_cluster_name(ctx)
            cluster_query = None
            cluster = None
            cluster_id = None
            if cluster_name:
                cluster_query = query_cluster_by_name(
                    ctx,
                    base_url=base_url,
                    token=ct_token or "",
                    cluster_name=cluster_name,
                    stage_logger=stage_logger,
                    api_cfg=api_cfg,
                    cache_result=True,
                )
                cluster = cluster_query.get("cluster") if isinstance(cluster_query, dict) else None
                cluster_id = cluster.get("id") if isinstance(cluster, dict) else None

            instance_id = _extract_obs_instance_id(verify_resp)

            obs_name = obs_name_default

            if not instance_id and cluster_id and cookie:
                vm_spec, obs_name = _resolve_obs_vm_spec(ctx, deploy_cfg)
                if not obs_name:
                    obs_name = DEFAULT_OBS_NAME
                package = _select_obs_package_for_install(verify_resp, package_path)
                package_id = package.get("id") if isinstance(package, dict) else None
                vnet_id = None
                if ct_token:
                    try:
                        vnet_id = query_vnet_by_name(
                            base_url=base_url,
                            token=ct_token,
                            name="default",
                            stage_logger=stage_logger,
                            api_cfg=api_cfg,
                        )
                    except Exception as exc:  # noqa: BLE001 - tolerate
                        stage_logger.warning(tr("deploy.deploy_obs.query_vnet_fail"), progress_extra={"error": str(exc)})

                if vm_spec:
                    if vnet_id:
                        vm_spec["vlan_id"] = str(vnet_id)

                if not vm_spec:
                    stage_logger.warning(
                        tr("deploy.deploy_obs.missing_vm_spec_skip"),
                        progress_extra={"cluster_id": cluster_id},
                    )
                elif not vnet_id:
                    stage_logger.warning(
                        tr("deploy.deploy_obs.missing_vnet_skip"),
                        progress_extra={"vnet_name": "default"},
                    )
                elif not package_id:
                    stage_logger.warning(
                        tr("deploy.deploy_obs.missing_package_skip"),
                        progress_extra={"package": package_path.name},
                    )
                else:
                    install_create_resp = _create_obs_instance(
                        base_url=base_url,
                        cookie=cookie,
                        token=ct_token,
                        package_id=str(package_id),
                        cluster_id=str(cluster_id),
                        vm_spec=vm_spec,
                        name=obs_name,
                        stage_logger=stage_logger,
                        api_cfg=api_cfg,
                    )
                    install_wait_resp = _wait_obs_instance(
                        ctx=ctx,
                        api_cfg=api_cfg,
                        base_url=base_url,
                        stage_logger=stage_logger,
                        name=obs_name,
                        cookie=cookie,
                        token=ct_token,
                    )
                    _delay_between_steps(stage_logger, "after_wait_instance")
                    instance_id = None
                    if isinstance(install_wait_resp, dict):
                        instance_id = install_wait_resp.get("id") or _extract_obs_instance_id(install_wait_resp)
                    if not instance_id:
                        instance_id = _extract_obs_instance_id(verify_resp)

            if instance_id and cookie:
                ntp_servers = _resolve_ntp_servers(ctx, api_cfg, deploy_cfg)
                if ntp_servers:
                    try:
                        ntp_resp = _update_obs_ntp(
                            base_url=base_url,
                            cookie=cookie,
                            token=ct_token,
                            instance_id=str(instance_id),
                            servers=ntp_servers,
                            stage_logger=stage_logger,
                            api_cfg=api_cfg,
                        )
                        _delay_between_steps(stage_logger, "after_ntp_update")
                    except Exception as exc:  # noqa: BLE001 - non-fatal
                        stage_logger.warning(
                            tr("deploy.deploy_obs.ntp_update_fail"),
                            progress_extra={"error": str(exc)},
                        )
                else:
                    stage_logger.info(
                        tr("deploy.deploy_obs.ntp_skip_no_servers"),
                        progress_extra={"instance_id": instance_id},
                    )

                try:
                    system_service_resp = _associate_obs_system_service(
                        base_url=base_url,
                        cookie=cookie,
                        token=ct_token,
                        obs_name=obs_name,
                        stage_logger=stage_logger,
                        api_cfg=api_cfg,
                    )
                    _delay_between_steps(stage_logger, "after_associate_system_service")
                except Exception as exc:  # noqa: BLE001 - non-fatal
                    stage_logger.warning(
                        tr("deploy.deploy_obs.associate_system_service_fail"),
                        progress_extra={"error": str(exc)},
                    )

                if cluster_id:
                    associate_resp = _associate_obs_instance(
                        base_url=base_url,
                        cookie=cookie,
                        token=ct_token,
                        instance_id=instance_id,
                        cluster_id=str(cluster_id),
                        stage_logger=stage_logger,
                        api_cfg=api_cfg,
                    )
                else:
                    stage_logger.info(
                        tr("deploy.deploy_obs.associate_skip_no_cluster"),
                        progress_extra={"instance_id": instance_id, "cluster_name": cluster_name, "cluster_id": cluster_id},
                    )
            else:
                stage_logger.info(
                    tr("deploy.deploy_obs.associate_skip_no_instance"),
                    progress_extra={"instance_id": instance_id, "cluster_name": cluster_name, "cluster_id": cluster_id},
                )
        except Exception as exc:  # noqa: BLE001 - 不中断主流程
            stage_logger.warning(tr("deploy.deploy_obs.install_or_associate_fail"), progress_extra={"error": str(exc)})

        result = {
            "upload_id": upload_id,
            "package": package_path.name,
            "base_url": base_url,
            "commit": commit_resp,
            "tasks": tasks_resp,
            "verify": verify_resp,
            "verified": verify_resp.get("verified") if isinstance(verify_resp, dict) else None,
            "version": verify_resp.get("version") if isinstance(verify_resp, dict) else None,
            "associate": associate_resp,
            "ntp_update": ntp_resp,
            "associate_system_service": system_service_resp,
            "install_create": install_create_resp,
            "install_wait": install_wait_resp,
            "skipped_upload": already_present,
        }

    deploy_results = ctx.extra.setdefault("deploy_results", {}) if isinstance(ctx.extra, dict) else {}
    deploy_results["OBS"] = result
    if isinstance(ctx.extra, dict):
        ctx.extra["deploy_obs_result"] = result
        ctx.extra["deploy_result"] = result

    return result
