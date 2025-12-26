# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of CXVoyager.
#
# CXVoyager is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CXVoyager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CXVoyager.  If not, see <https://www.gnu.org/licenses/>.

# Stage 7 check_cluster_healthy – 集群巡检
"""阶段 07-08：调用 CloudTower 巡检中心执行健康检查并导出报告。"""
from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from cxvoyager.common.config import load_config
from cxvoyager.utils.network_utils import check_port
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE
from cxvoyager.workflow.progress import create_stage_progress_logger
from cxvoyager.workflow.runtime_context import RunContext
from cxvoyager.workflow.stage_manager import Stage, stage_handler
from cxvoyager.integrations.smartx.api_client import APIClient
from cxvoyager.integrations.excel.planning_sheet_parser import find_plan_file, parse_plan, to_model
from cxvoyager.common.i18n import tr

from .deploy_cloudtower import (
    CLOUDTOWER_GET_CLUSTERS_ENDPOINT,
    _cloudtower_login,
    _resolve_cloudtower_ip,
)

logger = logging.getLogger(__name__)

INSPECTOR_JOB_ENDPOINT = "/api/inspector/api/v3/jobs"
INSPECTOR_EXPORT_ENDPOINT = "/api/inspector/api/v3/jobs/{job_id}:exportReport"
INSPECTOR_JOB_STATUS_ENDPOINT = "/api/inspector/api/v3/jobs/{job_id}"
INSPECTOR_EXPORT_STATUS_ENDPOINT = "/api/inspector/api/v3/export/status"
INSPECTOR_DOWNLOAD_ENDPOINT = "/api/inspector/api/v1/export/download"

DEFAULT_INSPECTOR_VERSION = "1.1.1-rc.11"
DEFAULT_EXPORT_FORMAT = "word"
DEFAULT_GRAPH_DURATION_MONTHS = 6
DEFAULT_POLL_INTERVAL = 5
DEFAULT_POLL_TIMEOUT = 10 * 60
DEFAULT_INSPECTOR_ITEMS: List[str] = [
    "master_redundancy_check",
    "cluster_mem_usage_check",
    "cluster_cpu_usage_check",
    "host_disk_remaining_life_percent",
    "host_power_is_on",
    "host_disk_is_healthy",
    "host_unhealthy_disk_is_offline",
    "event_disk_remove",
    "event_slot_disk_remove",
    "event_disk_add",
    "sensor_check",
    "power_health_check",
    "bmc_selftest",
    "fan_check",
    "ipmi_account_is_valid",
    "chassis_selftest",
    "hotfix_package_check",
    "worker_status_check",
    "worker_num_check",
    "job_duration_check",
    "failed_job_check",
    "host_service_health",
    "host_service_resident_memory_bytes",
    "host_service_is_running",
    "log_dir_usage_check",
    "host_cpu_overall_usage_percent",
    "host_memory_usage_percent",
    "host_time_diff_with_ntp_leader_seconds",
    "cluster_can_sync_time_with_external_ntp_server",
    "cluster_can_connect_to_external_ntp_server",
    "mongo_data_size_check",
    "root_disk_usage_check",
    "meta_partition_usage_check",
    "sys_partition_raid_is_normal",
    "sys_boot_health_check",
    "zk_cfg_check",
    "zk_role_check",
    "zk_primary_check",
    "primary_check",
    "status_check",
    "zk_status_check",
    "system_config_check",
    "third_party_software_check",
    "host_storage_network_can_ping",
    "host_management_network_can_ping",
    "host_access_network_can_ping",
    "host_to_host_max_ping_time_ns",
    "host_work_status_is_unknown",
    "host_bond_slave_is_normal",
    "default_gateway_check",
    "associated_nic_num_check",
    "network_loss_package_check",
    "zbs_cluster_data_space_use_rate",
    "zbs_chunk_data_space_use_rate",
    "cluster_storage_usage_check",
    "zbs_cluster_pending_migrate_bytes",
    "zbs_chunk_avg_readwrite_latency_ns",
    "zbs_chunk_connect_status",
    "zbs_chunk_maintenance_mode",
    "zbs_cluster_chunks_without_topo",
    "zbs_cluster_chunks_unsafe_failure_space",
    "zbs_chunk_dirty_cache_ratio",
    "zbs_zone_maximum_proportion_of_rack_space",
    "zbs_rack_maximum_proportion_of_brick_space",
    "disk_max_sectors_kb_check",
    "lsm2db_manifest_size_check",
    "journal_status_check",
    "dead_data_check",
    "cache_status_check",
    "recover_data_check",
    "meta_leader_check",
    "zbs_zk_hosts_cfg_check",
    "elf_cluster_cpu_model_not_recommended",
    "elf_vm_placement_expire",
    "elf_vm_placement_status",
    "elf_cluster_cpu_model_incompatible",
    "elf_host_ha_status",
    "vm_zero_page_refcount_check",
    "vm_uuid_duplicate_check",
    "without_vm_uuid_check",
]


@stage_handler(Stage.check_cluster_healthy)
def handle_check_cluster_healthy(ctx_dict: Dict[str, Any]) -> None:
    """执行 CloudTower 巡检任务并导出报告。"""

    ctx: RunContext = ctx_dict['ctx']
    stage_logger = create_stage_progress_logger(
        ctx,
        Stage.check_cluster_healthy.value,
        logger=logger,
        prefix="[check_cluster_healthy]",
    )

    cfg = ctx.config or load_config(DEFAULT_CONFIG_FILE)
    cfg_dict = cfg if isinstance(cfg, dict) else {}
    stage_cfg = dict(cfg_dict.get('cloudtower', {}).get('stage08') or {})
    if not _is_enabled(stage_cfg):
        stage_logger.info(tr("deploy.check_cluster_healthy.disabled"))
        ctx.extra['check_cluster_healthy'] = {"status": "SKIPPED", "reason": "disabled"}
        return

    plan_model, parsed_plan = _ensure_plan_for_inspector(ctx, stage_logger)

    deploy_info = ctx.extra.get('deploy_cloudtower') or {}
    if deploy_info.get('status') != 'SERVICE_READY':
        stage_logger.info(tr("deploy.check_cluster_healthy.no_stage4_output_probe"))
        cloud_cfg = cfg_dict.get('cloudtower', {}) if isinstance(cfg_dict, dict) else {}
        cloudtower_ip = _resolve_cloudtower_ip(plan_model, parsed_plan, cloud_cfg, stage_logger)
        if not cloudtower_ip:
            raise RuntimeError("缺少 CloudTower IP，无法执行巡检。")

        stage_logger.info(
            tr("deploy.check_cluster_healthy.probe_port"),
            progress_extra={"ip": cloudtower_ip, "port": 443},
        )
        if not check_port(cloudtower_ip, 443, timeout=5.0):
            raise RuntimeError("CloudTower 443 端口不可达，无法执行巡检。")

        timeout = int(cfg_dict.get('api', {}).get('timeout', 10))
        client_probe = APIClient(
            base_url=f"https://{cloudtower_ip}",
            mock=False,
            timeout=timeout,
            verify=False,
        )
        token = _cloudtower_login(client=client_probe, ip=cloudtower_ip, stage_logger=stage_logger)
        client_probe.session.headers['Authorization'] = token

        deploy_info = {
            "status": "SERVICE_READY",
            "ip": cloudtower_ip,
            "cloudtower": {
                "session": {"token": token, "username": "root"},
            },
        }
        ctx.extra['deploy_cloudtower'] = deploy_info
        stage_logger.info(tr("deploy.check_cluster_healthy.probe_success_continue"), progress_extra={"ip": cloudtower_ip})

    cloudtower_ip = deploy_info.get('ip')
    if not cloudtower_ip:
        raise RuntimeError("缺少 CloudTower 访问 IP，请确认前序阶段输出。")

    timeout = int(cfg_dict.get('api', {}).get('timeout', 10))
    client = APIClient(
        base_url=f"https://{cloudtower_ip}",
        mock=False,
        timeout=timeout,
        verify=False,  # CloudTower 使用自签证书
    )

    session = (deploy_info.get('cloudtower') or {}).get('session') or {}
    token = session.get('token')
    if not token:
        stage_logger.warning(tr("deploy.check_cluster_healthy.missing_token_login"))
        token = _cloudtower_login(client=client, ip=cloudtower_ip, stage_logger=stage_logger)
    client.session.headers['Authorization'] = token
    headers = {"content-type": "application/json", "Authorization": token}

    attach_info = ctx.extra.get('attach_cluster') or {}
    cluster_id, cluster_uuid = _ensure_cluster_identity(
        attach_info=attach_info,
        client=client,
        headers=headers,
        stage_logger=stage_logger,
    )
    if not cluster_id or not cluster_uuid:
        raise RuntimeError("缺少 CloudTower 集群标识，无法提交巡检任务。")

    inspector_version = str(stage_cfg.get('version') or DEFAULT_INSPECTOR_VERSION)
    export_format = str(stage_cfg.get('export_format') or DEFAULT_EXPORT_FORMAT)
    graph_months = int(stage_cfg.get('graph_duration_months') or DEFAULT_GRAPH_DURATION_MONTHS)
    poll_interval = max(1, int(stage_cfg.get('poll_interval') or DEFAULT_POLL_INTERVAL))
    poll_timeout = max(poll_interval, int(stage_cfg.get('poll_timeout') or DEFAULT_POLL_TIMEOUT))

    items = _resolve_inspector_items(stage_cfg)
    stage_logger.info(
        tr("deploy.check_cluster_healthy.submit_job"),
        progress_extra={
            "cluster_uuid": cluster_uuid,
            "version": inspector_version,
            "item_count": len(items),
        },
    )

    job_payload = {
        "version": inspector_version,
        "cluster_uuids": [cluster_uuid],
        "user_defined_items_names": items,
    }
    job_response = client.post(INSPECTOR_JOB_ENDPOINT, payload=job_payload, headers=headers)
    job_id = _extract_str(job_response, 'id') or _extract_str(job_response.get('data') if isinstance(job_response, dict) else {}, 'id')
    if not job_id:
        raise RuntimeError("CloudTower 巡检任务请求未返回任务 ID。")

    stage_logger.info(
        tr("deploy.check_cluster_healthy.job_submitted_wait"),
        progress_extra={
            "job_id": job_id,
            "poll_interval": poll_interval,
            "poll_timeout": poll_timeout,
        },
    )
    _wait_for_job_completion(
        client=client,
        headers=headers,
        job_id=job_id,
        poll_interval=poll_interval,
        poll_timeout=poll_timeout,
        stage_logger=stage_logger,
    )

    export_payload = {
        "options": [
            {
                "cluster_uuid": cluster_uuid,
                "items_names": items,
                "graph_duration_months": graph_months,
            }
        ]
    }
    export_endpoint = INSPECTOR_EXPORT_ENDPOINT.format(job_id=job_id)
    export_response = client.post(export_endpoint, payload=export_payload, headers=headers, params={"format": export_format})
    filename = _extract_str(export_response, 'filename')
    if not filename:
        raise RuntimeError("巡检导出接口未返回报告文件名。")

    stage_logger.info(
        tr("deploy.check_cluster_healthy.export_submitted_wait"),
        progress_extra={
            "job_id": job_id,
            "filename": filename,
            "poll_interval": poll_interval,
            "poll_timeout": poll_timeout,
        },
    )
    _wait_for_export(
        client=client,
        headers=headers,
        filename=filename,
        poll_interval=poll_interval,
        poll_timeout=poll_timeout,
        stage_logger=stage_logger,
    )

    artifact_dir = _resolve_artifact_dir(ctx, stage_cfg)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    target_path = artifact_dir / filename

    download_url = client._full_url(INSPECTOR_DOWNLOAD_ENDPOINT)  # noqa: SLF001 - 复用内部工具拼接完整 URL
    response = client.session.get(
        download_url,
        params={"filename": filename},
        headers=headers,
        timeout=poll_interval,
    )
    response.raise_for_status()
    target_path.write_bytes(response.content)

    stage_logger.info(
        tr("deploy.check_cluster_healthy.download_done"),
        progress_extra={
            "job_id": job_id,
            "file": str(target_path),
        },
    )

    ctx.extra['check_cluster_healthy'] = {
        "status": "SUCCESS",
        "job_id": job_id,
        "filename": filename,
        "path": str(target_path),
        "cluster_uuid": cluster_uuid,
    }


def _resolve_inspector_items(stage_cfg: Dict[str, Any]) -> List[str]:
    """解析巡检项列表，若配置为空则回退到默认列表。"""

    raw = stage_cfg.get('user_defined_items')
    if raw is None:
        return DEFAULT_INSPECTOR_ITEMS
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        return [item.strip() for item in raw.replace('\n', ',').split(',') if item.strip()]
    return DEFAULT_INSPECTOR_ITEMS


def _wait_for_export(
    *,
    client: APIClient,
    headers: Dict[str, str],
    filename: str,
    poll_interval: int,
    poll_timeout: int,
    stage_logger: logging.LoggerAdapter,
) -> None:
    """轮询 CloudTower 导出进度，直到成功或超时。"""

    deadline = time.monotonic() + poll_timeout
    while time.monotonic() < deadline:
        status_response = client.get(
            INSPECTOR_EXPORT_STATUS_ENDPOINT,
            params={"filename": filename},
            headers=headers,
        )
        status = _extract_str(status_response, 'status')
        if status == 'EXPORT_SUCCEEDED':
            stage_logger.info(tr("deploy.check_cluster_healthy.export_success"))
            return
        if status == 'EXPORT_FAILED':
            raise RuntimeError("CloudTower 巡检报告导出失败")
        stage_logger.debug(
            tr("deploy.check_cluster_healthy.export_running"),
            progress_extra={"status": status or "UNKNOWN", "wait": poll_interval},
        )
        time.sleep(poll_interval)
    raise RuntimeError("等待 CloudTower 巡检报告导出超时，请人工确认。")


def _wait_for_job_completion(
    *,
    client: APIClient,
    headers: Dict[str, str],
    job_id: str,
    poll_interval: int,
    poll_timeout: int,
    stage_logger: logging.LoggerAdapter,
) -> None:
    """轮询巡检任务状态，确保任务完成后再导出报告。"""

    deadline = time.monotonic() + poll_timeout
    endpoint = INSPECTOR_JOB_STATUS_ENDPOINT.format(job_id=job_id)
    while time.monotonic() < deadline:
        status_response = client.get(endpoint, headers=headers)
        status = _extract_str(status_response, 'status')
        if status in {"SUCCEEDED", "FINISHED", "SUCCESS"}:
            stage_logger.info(tr("deploy.check_cluster_healthy.job_done"), progress_extra={"job_id": job_id, "status": status})
            return
        if status in {"FAILED", "ERROR"}:
            raise RuntimeError(f"CloudTower 巡检任务失败，status={status}")
        stage_logger.debug(
            tr("deploy.check_cluster_healthy.job_running"),
            progress_extra={"job_id": job_id, "status": status or "UNKNOWN", "wait": poll_interval},
        )
        time.sleep(poll_interval)
    raise RuntimeError("等待 CloudTower 巡检任务完成超时，请人工确认。")


def _resolve_artifact_dir(ctx: RunContext, stage_cfg: Dict[str, Any]) -> Path:
    """获取巡检报告的落盘目录。"""

    override = stage_cfg.get('download_dir')
    if isinstance(override, str) and override.strip():
        path = Path(override.strip())
        if not path.is_absolute():
            return (ctx.work_dir or Path.cwd()) / path
        return path
    # 默认写入项目根目录（工作目录），不再额外创建 artifacts 子目录
    return ctx.work_dir or Path.cwd()


def _is_enabled(stage_cfg: Dict[str, Any]) -> bool:
    value = stage_cfg.get('enabled', True)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "off", "no"}
    return bool(value)


def _extract_str(payload: Any, key: str) -> str:
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return ""


def _ensure_plan_for_inspector(ctx: RunContext, stage_logger: logging.LoggerAdapter):
    """独立运行时尝试自动加载规划表，以用于推算 CloudTower IP。"""

    plan_model = getattr(ctx, "plan", None)
    parsed_plan = ctx.extra.get('parsed_plan') if isinstance(ctx.extra, dict) else None
    if plan_model or parsed_plan:
        return plan_model, parsed_plan

    try:
        base_dir = ctx.work_dir if hasattr(ctx, "work_dir") and ctx.work_dir else Path.cwd()
        plan_path = find_plan_file(base_dir=base_dir)
        if plan_path:
            parsed_plan = parse_plan(plan_path)
            plan_model = to_model(parsed_plan)
            ctx.plan = plan_model
            if isinstance(ctx.extra, dict):
                ctx.extra['parsed_plan'] = parsed_plan
            stage_logger.info(tr("deploy.check_cluster_healthy.plan_loaded"), progress_extra={"plan_path": str(plan_path)})
        else:
            stage_logger.warning(
                tr("deploy.check_cluster_healthy.plan_not_found"),
                progress_extra={"base_dir": str(base_dir) if base_dir else ""},
            )
    except Exception as exc:  # noqa: BLE001
        stage_logger.warning(
            tr("deploy.check_cluster_healthy.plan_load_failed"),
            progress_extra={"error": str(exc)},
        )

    return plan_model, parsed_plan


def _ensure_cluster_identity(
    *,
    attach_info: Dict[str, Any],
    client: APIClient,
    headers: Dict[str, str],
    stage_logger: logging.LoggerAdapter,
) -> tuple[str, str]:
    """确保获得 cluster_id 与 cluster_uuid，若缓存缺失则实时查询。"""

    cluster = attach_info.get('cluster') if isinstance(attach_info, dict) else None
    if isinstance(cluster, dict):
        cluster_id = str(cluster.get('id') or cluster.get('cluster_id') or "").strip()
        cluster_uuid = str(
            cluster.get('local_id')
            or cluster.get('license_serial')
            or cluster.get('license_serial_number')
            or cluster_id
        ).strip()
        if cluster_id and cluster_uuid:
            return cluster_id, cluster_uuid

    stage_logger.info(tr("deploy.check_cluster_healthy.cluster_cache_miss"))
    response = client.post(CLOUDTOWER_GET_CLUSTERS_ENDPOINT, payload={}, headers=headers)
    clusters = _extract_cluster_list_for_inspector(response)
    if not clusters:
        raise RuntimeError("未能从 CloudTower 查询到任何集群信息。")

    chosen = clusters[0]
    cluster_id = str(chosen.get('id') or "").strip()
    cluster_uuid = str(
        chosen.get('local_id')
        or chosen.get('license_serial')
        or chosen.get('license_serial_number')
        or cluster_id
    ).strip()

    if not cluster_id or not cluster_uuid:
        raise RuntimeError("CloudTower 集群详情缺少标识信息。")

    stage_logger.info(
        tr("deploy.check_cluster_healthy.cluster_auto_selected"),
        progress_extra={"cluster_id": cluster_id, "cluster_uuid": cluster_uuid},
    )
    return cluster_id, cluster_uuid


def _extract_cluster_list_for_inspector(response: Any) -> List[Dict[str, Any]]:
    """解析 list 形态的 get-clusters 返回。"""

    if not isinstance(response, list):
        return []

    clusters: List[Dict[str, Any]] = []
    for item in response:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get('data'), dict) and isinstance(item['data'].get('clusters'), list):
            clusters.extend([cluster for cluster in item['data']['clusters'] if isinstance(cluster, dict)])
        else:
            clusters.append(item)
    return clusters
