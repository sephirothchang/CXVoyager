# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage deploy_bak – 备份服务部署（上传包、创建网络、部署并关联集群）。"""
from __future__ import annotations

import ipaddress
import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from cxvoyager.common.config import load_config
from cxvoyager.common.i18n import tr
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE, PROJECT_ROOT
from cxvoyager.core.deployment.handlers.deploy_obs import _delay_between_steps
from cxvoyager.core.deployment.login_cloudtower import login_cloudtower
from cxvoyager.core.deployment.progress import create_stage_progress_logger
from cxvoyager.core.deployment.query_cluster import query_cluster_by_name
from cxvoyager.core.deployment.query_vnet import query_vnet_by_name
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from cxvoyager.integrations.smartx.api_client import APIClient
from .app_upload import (
    _ensure_plan_loaded,
    _resolve_cloudtower_base_url,
    find_latest_package,
    normalize_base_url,
    _reset_plan_context,
)

logger = logging.getLogger(__name__)

BAK_PACKAGE_PATTERN = "smtx-backup-dr-*.tar.gz"
BAK_NAME_REGEX = re.compile(
    r"smtx-backup-dr-(?P<arch>x86_64|aarch64)-(?P<version>[\d\.]+)\.tar\.gz",
    re.IGNORECASE,
)

BAK_CREATE_UPLOAD_MUTATION = (
    "mutation createUploadTask($data: UploadTaskCreateInput!) {\n"
    "  createUploadTask(data: $data) {\n    id\n    current_chunk\n    chunk_size\n    __typename\n  }\n}\n"
)

BAK_UPLOAD_MUTATION = (
    "mutation uploadCloudTowerApplicationPackage($data: UploadCloudTowerApplicationPackageInput!) {\n"
    "  uploadCloudTowerApplicationPackage(data: $data) {\n"
    "    id\n    status\n    current_chunk\n    chunk_size\n    __typename\n  }\n}\n"
)

BAK_QUERY_PACKAGES = (
    "query cloudTowerApplicationPackages($where: CloudTowerApplicationPackageWhereInput, $orderBy: CloudTowerApplicationPackageOrderByInput, $skip: Int, $first: Int) {\n"
    "  cloudTowerApplicationPackages(where: $where, orderBy: $orderBy, skip: $skip, first: $first) {\n"
    "    id\n    filename\n    version\n    architecture\n    __typename\n  }\n"
    "  cloudTowerApplicationPackagesConnection(where: $where) {\n"
    "    aggregate { count __typename }\n    __typename\n  }\n}\n"
)

BAK_CREATE_SERVICE_MUTATION = (
    "mutation createBackupService($data: BackupServiceCreateInput!, $effect: CreateBackupServiceEffect) {\n"
    "  createBackupService(data: $data, effect: $effect) { id __typename }\n}\n"
)

BAK_QUERY_SERVICES = (
    "query getBackupServices($where: BackupServiceWhereInput) {\n"
    "  backupServices(where: $where) { id name status entityAsyncStatus application { id package { id version architecture __typename } targetPackage instanceStatuses __typename } backup_clusters { id name __typename } running_vm { id status __typename } __typename }\n}\n"
)

BAK_UPDATE_SERVICE_MUTATION = (
    "mutation updateBackupService($where: BackupServiceWhereUniqueInput!, $data: BackupServiceUpdateInput!) {\n"
    "  updateBackupService(where: $where, data: $data) { id name __typename }\n}\n"
)

BAK_GET_VDSES_ENDPOINT = "/v2/api/get-vdses"
BAK_CREATE_VLAN_ENDPOINT = "/v2/api/create-vm-vlan"
BAK_GET_TASKS_ENDPOINT = "/v2/api/get-tasks"

DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024
DEFAULT_TASK_TIMEOUT = 900  # seconds
DEFAULT_TASK_INTERVAL = 5


def _version_tuple(version: str) -> Tuple[int, ...]:
    parts: list[int] = []
    for piece in version.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _extract_version_arch(filename: str) -> Tuple[str | None, str | None]:
    m = BAK_NAME_REGEX.search(filename)
    if not m:
        return None, None
    return m.group("version"), m.group("arch").upper()


def _resolve_headers(token: str | None, cookie: str | None) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if token:
        headers["Authorization"] = token
    if cookie:
        headers["cookie"] = cookie
    return headers


def _query_packages(client: APIClient, headers: Dict[str, str]) -> list[dict]:
    payload = {
        "operationName": "cloudTowerApplicationPackages",
        "variables": {"skip": 0, "first": 50, "where": {"AND": [{"name": "iomesh-backup"}]}},
        "query": BAK_QUERY_PACKAGES,
    }
    resp = client.post("/api", payload, headers=headers)
    data = resp.get("data") if isinstance(resp, dict) else None
    items = data.get("cloudTowerApplicationPackages") if isinstance(data, dict) else None
    return items if isinstance(items, list) else []


def _should_skip_upload(packages: list[dict], package_path: Path) -> Tuple[bool, str | None, str | None]:
    local_version, local_arch = _extract_version_arch(package_path.name)
    if not local_version or not local_arch:
        return False, None, None

    best: dict | None = None
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        arch = str(pkg.get("architecture") or "").upper()
        if arch != local_arch:
            continue
        if best is None:
            best = pkg
            continue
        if _version_tuple(str(pkg.get("version") or "0")) > _version_tuple(str(best.get("version") or "0")):
            best = pkg

    if best is None:
        return False, None, None

    remote_version = str(best.get("version") or "")
    if _version_tuple(remote_version) >= _version_tuple(local_version):
        return True, remote_version, best.get("id")
    return False, remote_version, best.get("id")


def _create_upload_task(*, client: APIClient, headers: Dict[str, str], package_path: Path, chunk_size: int | None = None) -> Tuple[str, int]:
    size = package_path.stat().st_size
    payload = {
        "operationName": "createUploadTask",
        "variables": {
            "data": {
                "status": "INITIALIZING",
                "current_chunk": 1,
                "chunk_size": chunk_size or DEFAULT_CHUNK_SIZE,
                "resource_type": "CLOUDTOWER_APPLICATION_PACKAGE",
                "size": size,
                "args": {"name": package_path.name, "package_name": "iomesh-backup"},
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        },
        "query": BAK_CREATE_UPLOAD_MUTATION,
    }
    resp = client.post("/api", payload, headers=headers)
    data = resp.get("data") if isinstance(resp, dict) else None
    info = data.get("createUploadTask") if isinstance(data, dict) else None
    if not isinstance(info, dict) or not info.get("id"):
        raise RuntimeError("备份包上传初始化失败：未返回 upload_task_id")
    return str(info["id"]), int(info.get("chunk_size") or chunk_size or DEFAULT_CHUNK_SIZE)


def _upload_package_chunks(
    *,
    client: APIClient,
    headers: Dict[str, str],
    upload_task_id: str,
    package_path: Path,
    chunk_size: int,
    stage_logger,
    chunk_timeout: int | None = None,
) -> None:
    size = package_path.stat().st_size
    total_chunks = max(1, (size + chunk_size - 1) // chunk_size)
    original_timeout = getattr(client, "timeout", None)
    if chunk_timeout:
        client.timeout = chunk_timeout

    with package_path.open("rb") as f:
        chunk_index = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunk_index += 1
            operations = {
                "operationName": "uploadCloudTowerApplicationPackage",
                "variables": {
                    "data": {
                        "upload_task_id": upload_task_id,
                        "file": None,
                        "current_chunk": chunk_index,
                    }
                },
                "query": BAK_UPLOAD_MUTATION,
            }
            map_part = {"1": ["variables.data.file"]}
            data = {"operations": json.dumps(operations), "map": json.dumps(map_part)}
            files = {"1": (package_path.name, chunk, "application/octet-stream")}

            try:
                # 使用无重试的单次 POST，避免网络超时后自动重放导致同一分片重复上传
                resp = client.post_once("/api", headers=headers, files=files, data=data)
            except Exception as exc:  # pragma: no cover - surfaced
                if chunk_index == total_chunks:
                    stage_logger.warning(
                        tr("deploy.deploy_bak.chunk_timeout_last_ok"),
                        progress_extra={"chunk": chunk_index, "error": str(exc)},
                    )
                    break
                stage_logger.error(
                    tr("deploy.deploy_bak.chunk_fail"),
                    progress_extra={"chunk": chunk_index, "error": str(exc)},
                )
                raise RuntimeError(f"备份包分片上传失败: {exc}")

            if not isinstance(resp, dict):
                raise RuntimeError(f"备份包分片上传失败：响应格式无效 {resp}")

            if resp.get("errors"):
                stage_logger.error(
                    tr("deploy.deploy_bak.chunk_fail"),
                    progress_extra={"chunk": chunk_index, "error": resp.get("errors")},
                )
                raise RuntimeError(f"备份包分片上传失败: {resp.get('errors')}")

            status = resp.get("data", {}).get("uploadCloudTowerApplicationPackage")
            status_value = status.get("status") if isinstance(status, dict) else None
            stage_logger.info(
                tr("deploy.deploy_bak.chunk_done"),
                progress_extra={"chunk": chunk_index, "status": status_value},
            )

            # 如果服务端返回已完成（SUCCESSED），提前结束上传循环
            if isinstance(status_value, str) and status_value.upper() == "SUCCESSED":
                break

    if chunk_timeout and original_timeout is not None:
        client.timeout = original_timeout


def _find_package_id(packages: list[dict], package_path: Path) -> str | None:
    version, arch = _extract_version_arch(package_path.name)
    if not version or not arch:
        return None
    for pkg in packages:
        if not isinstance(pkg, dict):
            continue
        if str(pkg.get("filename") or "") == package_path.name:
            return str(pkg.get("id")) if pkg.get("id") else None
        if str(pkg.get("architecture") or "").upper() != arch.upper():
            continue
        if _version_tuple(str(pkg.get("version") or "0")) == _version_tuple(version):
            return str(pkg.get("id")) if pkg.get("id") else None
    return None


def _extract_network_record(parsed_plan: Dict[str, Any], label: str) -> Dict[str, Any] | None:
    records = parsed_plan.get("virtual_network", {}).get("records", []) if isinstance(parsed_plan, dict) else []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if str(rec.get("网络标识") or "").strip().lower() == label:
            return rec
    return None


def _netmask_from_subnet(subnet: str | None) -> str | None:
    if not subnet:
        return None
    try:
        return str(ipaddress.ip_network(subnet, strict=False).netmask)
    except Exception:
        return None


def _resolve_plan_inputs(ctx: RunContext, stage_logger) -> Dict[str, Any]:
    parsed_plan = ctx.extra.get("parsed_plan") if isinstance(ctx.extra, dict) else None
    if not isinstance(parsed_plan, dict):
        raise RuntimeError("缺少规划表解析结果，无法部署备份服务")

    mgmt_records = parsed_plan.get("mgmt", {}).get("records", []) if isinstance(parsed_plan, dict) else []
    mgmt_record = mgmt_records[0] if isinstance(mgmt_records, list) and mgmt_records else {}
    backup_ip = mgmt_record.get("备份 IP")

    net_default = _extract_network_record(parsed_plan, "default") or {}
    net_storage = _extract_network_record(parsed_plan, "storage") or {}
    net_backup = _extract_network_record(parsed_plan, "backup") or {}

    cluster_name = net_default.get("集群名称") or net_storage.get("集群名称")

    return {
        "backup_ip": backup_ip,
        "cluster_name": cluster_name,
        "mgmt_vnet": net_default.get("虚拟机网络"),
        "mgmt_gateway": net_default.get("gateway"),
        "mgmt_subnet": net_default.get("subnetwork"),
        "storage_vds": net_storage.get("虚拟交换机") or net_backup.get("虚拟交换机"),
        "storage_vnet": net_storage.get("虚拟机网络"),
        "storage_subnet": net_storage.get("subnetwork"),
        "storage_gateway": net_storage.get("gateway"),
        "backup_vnet_name": net_backup.get("虚拟机网络") or "backup-storage-network",
    }


def _query_storage_vds_id(*, client: APIClient, headers: Dict[str, str], target_name: str, stage_logger) -> str:
    resp = client.post(BAK_GET_VDSES_ENDPOINT, payload={}, headers=headers)
    vds_list = resp if isinstance(resp, list) else resp.get("data") if isinstance(resp, dict) else []
    if not isinstance(vds_list, list):
        raise RuntimeError("获取 VDS 列表失败：返回格式异常")
    for item in vds_list:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if target_name.lower() in name.lower():
            if item.get("id"):
                stage_logger.info(tr("deploy.deploy_bak.vds_found"), progress_extra={"id": item.get("id"), "name": name})
                return str(item.get("id"))
    raise RuntimeError(f"未找到包含 {target_name} 的存储 VDS")


def _create_backup_vlan(*, client: APIClient, headers: Dict[str, str], vds_id: str, name: str, stage_logger) -> str:
    payload = [{"vds_id": vds_id, "name": name}]
    resp = client.post(BAK_CREATE_VLAN_ENDPOINT, payload=payload, headers=headers)
    items = resp if isinstance(resp, list) else []
    if not items or not isinstance(items[0], dict):
        raise RuntimeError("创建备份存储网络失败：返回格式异常")
    data = items[0].get("data") if isinstance(items[0], dict) else None
    vlan_id = None
    if isinstance(data, dict):
        vlan_id = data.get("id")
    if not vlan_id:
        raise RuntimeError("创建备份存储网络失败：未返回网络 ID")
    stage_logger.info(tr("deploy.deploy_bak.storage_network_created"), progress_extra={"id": vlan_id, "name": name})
    return str(vlan_id)


def _poll_backup_service(*, client: APIClient, headers: Dict[str, str], service_id: str, interval: int, timeout: int, stage_logger) -> Dict[str, Any]:
    deadline = time.time() + timeout
    last_resp: Dict[str, Any] | None = None
    while time.time() < deadline:
        payload = {"operationName": "getBackupServices", "variables": {}, "query": BAK_QUERY_SERVICES}
        resp = client.post("/api", payload, headers=headers)
        last_resp = resp if isinstance(resp, dict) else None
        data = resp.get("data") if isinstance(resp, dict) else None
        services = data.get("backupServices") if isinstance(data, dict) else None
        if isinstance(services, list):
            target = None
            for svc in services:
                if not isinstance(svc, dict):
                    continue
                if str(svc.get("id") or "") == service_id:
                    target = svc
                    break
            if target:
                status = str(target.get("status") or "").upper()
                stage_logger.info(tr("deploy.deploy_bak.poll_service"), progress_extra={"status": status})
                if status == "RUNNING":
                    return target
                if status in {"FAILED", "ERROR"}:
                    raise RuntimeError(f"备份服务部署失败: {status}")
        time.sleep(interval)
    raise RuntimeError(tr("deploy.deploy_bak.service_timeout"))


def _wait_install_tasks(*, client: APIClient, headers: Dict[str, str], service_name: str, stage_logger, timeout: int = DEFAULT_TASK_TIMEOUT, interval: int = DEFAULT_TASK_INTERVAL) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = client.post(BAK_GET_TASKS_ENDPOINT, payload={}, headers=headers)
        except Exception:
            time.sleep(interval)
            continue
        tasks = resp if isinstance(resp, list) else resp.get("data") if isinstance(resp, dict) else []
        if isinstance(tasks, list):
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                desc = str(task.get("description") or "")
                status = str(task.get("status") or "")
                if service_name in desc and status.upper() in {"SUCCESSED", "SUCCESS"}:
                    stage_logger.info(tr("deploy.deploy_bak.task_done"), progress_extra={"task_id": task.get("id"), "status": status})
                    return
        time.sleep(interval)
    stage_logger.warning(tr("deploy.deploy_bak.task_timeout"), progress_extra={"timeout_s": timeout})


@stage_handler(Stage.deploy_bak)  # type: ignore
def handle_deploy_bak(ctx_dict):
    """上传并部署备份（BAK）服务。"""

    ctx: RunContext = ctx_dict["ctx"]  # type: ignore[index]
    stage_logger = create_stage_progress_logger(ctx, Stage.deploy_bak.value, logger=logger, prefix="[deploy_bak]")

    _reset_plan_context(ctx)
    _ensure_plan_loaded(ctx)
    _delay_between_steps(stage_logger, "plan_loaded")

    cfg = ctx.config or load_config(DEFAULT_CONFIG_FILE)
    cfg_dict = cfg if isinstance(cfg, dict) else {}
    api_cfg = cfg_dict.get("api", {}) if isinstance(cfg_dict, dict) else {}
    deploy_cfg = cfg_dict.get("deploy", {}) if isinstance(cfg_dict, dict) else {}

    timeout = int(api_cfg.get("timeout", 10)) if isinstance(api_cfg, dict) else 10
    verify_ssl = api_cfg.get("verify_ssl", False) if isinstance(api_cfg, dict) else False
    chunk_size_default = int(api_cfg.get("bak_chunk_size", DEFAULT_CHUNK_SIZE)) if isinstance(api_cfg, dict) else DEFAULT_CHUNK_SIZE

    cli_opts = ctx.extra.get("cli_options", {}) if isinstance(ctx.extra, dict) else {}
    dry_run = bool(cli_opts.get("dry_run", deploy_cfg.get("dry_run", False)))

    work_dir = ctx.work_dir if isinstance(ctx.work_dir, Path) else Path(ctx.work_dir)
    search_roots: Iterable[Path] = [work_dir, PROJECT_ROOT, PROJECT_ROOT / "release", PROJECT_ROOT / "resources", PROJECT_ROOT / "artifacts"]

    package_path = find_latest_package(
        app=type("BakSpec", (), {"package_pattern": BAK_PACKAGE_PATTERN, "name_regex": BAK_NAME_REGEX}),  # type: ignore
        search_roots=search_roots,
    )

    base_url = _resolve_cloudtower_base_url(ctx, api_cfg)
    if not base_url:
        raise RuntimeError("无法确定 CloudTower 地址，无法部署备份服务")
    base_url = normalize_base_url(base_url)

    login_result = login_cloudtower(ctx, base_url=base_url, api_cfg=api_cfg, stage_logger=stage_logger)
    cookie = login_result.get("cookie") if isinstance(login_result, dict) else None
    token = login_result.get("token") if isinstance(login_result, dict) else None

    if not cookie:
        raise RuntimeError("CloudTower 登录失败：缺少 cookie")

    headers = _resolve_headers(token, cookie)
    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    stage_logger.info(
        tr("deploy.deploy_bak.start"),
        progress_extra={"file": package_path.name, "base_url": base_url, "chunk_size": chunk_size_default, "dry_run": dry_run},
    )

    packages_before = _query_packages(client, headers)
    skip_upload, remote_version, remote_pkg_id = _should_skip_upload(packages_before, package_path)

    package_id = remote_pkg_id

    if dry_run:
        stage_logger.info(tr("deploy.deploy_bak.dry_run"))
    else:
        if not skip_upload:
            upload_task_id, chunk_size = _create_upload_task(client=client, headers=headers, package_path=package_path, chunk_size=chunk_size_default)
            stage_logger.info(tr("deploy.deploy_bak.upload_init"), progress_extra={"upload_task_id": upload_task_id, "chunk_size": chunk_size})
            _upload_package_chunks(
                client=client,
                headers=headers,
                upload_task_id=upload_task_id,
                package_path=package_path,
                chunk_size=chunk_size,
                stage_logger=stage_logger,
                chunk_timeout=deploy_cfg.get("chunk_timeout") or 30,
            )
            _delay_between_steps(stage_logger, "after_upload")
            packages_after = _query_packages(client, headers)
            package_id = _find_package_id(packages_after, package_path)
        else:
            stage_logger.info(
                tr("deploy.deploy_bak.package_exists_skip"),
                progress_extra={"remote_version": remote_version, "package": package_path.name},
            )
            if not package_id:
                package_id = _find_package_id(packages_before, package_path)

    if not package_id:
        raise RuntimeError("未找到备份安装包 ID，无法继续部署")

    plan_inputs = _resolve_plan_inputs(ctx, stage_logger)
    mgmt_ip = plan_inputs.get("backup_ip") or deploy_cfg.get("bak_management_ip")
    if not mgmt_ip:
        raise RuntimeError("规划表或配置中缺少备份管理 IP")

    mgmt_mask = _netmask_from_subnet(plan_inputs.get("mgmt_subnet"))
    storage_mask = _netmask_from_subnet(plan_inputs.get("storage_subnet"))
    if not mgmt_mask:
        raise RuntimeError("无法从管理子网解析子网掩码")
    if not storage_mask:
        stage_logger.warning(tr("deploy.deploy_bak.storage_mask_missing"))
        storage_mask = mgmt_mask

    storage_ip = deploy_cfg.get("bak_storage_ip") or mgmt_ip
    if storage_ip == mgmt_ip:
        stage_logger.warning(tr("deploy.deploy_bak.storage_ip_fallback"), progress_extra={"ip": storage_ip})

    mgmt_vlan_name = plan_inputs.get("mgmt_vnet")
    storage_vds_name = plan_inputs.get("storage_vds") or "vDS-Storage"
    backup_vnet_name = plan_inputs.get("backup_vnet_name") or "backup-storage-network"

    if not mgmt_vlan_name:
        raise RuntimeError("缺少管理网络名称，无法查询 VLAN")

    mgmt_vlan_id = query_vnet_by_name(
        base_url=base_url,
        token=token or "",
        name=str(mgmt_vlan_name),
        stage_logger=stage_logger,
        api_cfg=api_cfg,
    )

    storage_vds_id = _query_storage_vds_id(client=client, headers=headers, target_name=str(storage_vds_name), stage_logger=stage_logger)
    storage_vlan_id = _create_backup_vlan(client=client, headers=headers, vds_id=storage_vds_id, name=str(backup_vnet_name), stage_logger=stage_logger)

    cluster_name = plan_inputs.get("cluster_name") or ""
    if not cluster_name:
        raise RuntimeError("缺少集群名称，无法部署备份服务")
    cluster_info = query_cluster_by_name(
        ctx,
        base_url=base_url,
        token=token or "",
        cluster_name=str(cluster_name),
        stage_logger=stage_logger,
        api_cfg=api_cfg,
    )
    cluster_id = cluster_info.get("cluster", {}).get("id") if isinstance(cluster_info, dict) else None
    if not cluster_id:
        raise RuntimeError("无法获取集群 ID")

    service_name = deploy_cfg.get("bak_service_name", "bak")
    backup_network_gateway = plan_inputs.get("mgmt_gateway")
    storage_gateway = plan_inputs.get("storage_gateway") or backup_network_gateway

    payload_create = {
        "operationName": "createBackupService",
        "variables": {
            "data": {
                "name": service_name,
                "entityAsyncStatus": "CREATING",
                "status": "INSTALLING",
                "application": {
                    "create": {
                        "instances": {"create": []},
                        "state": "INSTALLING",
                        "instanceStatuses": [],
                        "name": f"backup-{service_name}",
                        "resourceVersion": 0,
                        "vmSpec": {},
                        "targetPackage": package_id,
                    }
                },
                "kube_config": "",
                "storage_network_type": "NEW_NIC",
                "backup_network_type": "MANAGEMENT",
                "management_network_gateway": backup_network_gateway,
                "management_network_ip": mgmt_ip,
                "management_network_subnet_mask": mgmt_mask,
                "management_network_vlan": mgmt_vlan_id,
                "storage_network_ip": storage_ip,
                "storage_network_subnet_mask": storage_mask,
                "storage_network_vlan": storage_vlan_id,
                "backup_network_gateway": backup_network_gateway,
                "backup_network_ip": mgmt_ip,
                "backup_network_subnet_mask": mgmt_mask,
                "backup_network_vlan": mgmt_vlan_id,
            },
            "effect": {"running_cluster": cluster_id, "running_host": "AUTO_SCHEDULE"},
        },
        "query": BAK_CREATE_SERVICE_MUTATION,
    }

    create_resp = client.post("/api", payload_create, headers=headers)
    service_id = None
    data_create = create_resp.get("data") if isinstance(create_resp, dict) else None
    svc = data_create.get("createBackupService") if isinstance(data_create, dict) else None
    if isinstance(svc, dict):
        service_id = svc.get("id")
    if not service_id:
        raise RuntimeError("创建备份服务失败：未返回 service id")

    _delay_between_steps(stage_logger, "after_create_service")

    if not dry_run:
        _wait_install_tasks(client=client, headers=headers, service_name=f"backup-{service_name}", stage_logger=stage_logger)
        service_status = _poll_backup_service(
            client=client,
            headers=headers,
            service_id=str(service_id),
            interval=int(deploy_cfg.get("poll_interval", DEFAULT_TASK_INTERVAL)),
            timeout=int(deploy_cfg.get("max_attempts", 120)) * int(deploy_cfg.get("poll_interval", DEFAULT_TASK_INTERVAL)),
            stage_logger=stage_logger,
        )

        payload_update = {
            "operationName": "updateBackupService",
            "variables": {
                "where": {"id": service_id},
                "data": {"backup_clusters": {"set": [{"id": cluster_id}]}},
            },
            "query": BAK_UPDATE_SERVICE_MUTATION,
        }
        client.post("/api", payload_update, headers=headers)

        ctx.extra.setdefault("deploy_results", {})["BAK"] = {
            "service_id": service_id,
            "package_id": package_id,
            "status": service_status.get("status") if isinstance(service_status, dict) else None,
        }
    else:
        ctx.extra.setdefault("deploy_results", {})["BAK"] = {
            "dry_run": True,
            "package": package_path.name,
            "base_url": base_url,
            "cluster": cluster_id,
        }

    ctx.extra["deploy_bak_result"] = ctx.extra.get("deploy_results", {}).get("BAK")
    ctx.extra["deploy_result"] = ctx.extra.get("deploy_bak_result")
