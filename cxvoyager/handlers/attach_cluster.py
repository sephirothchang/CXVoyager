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

# Stage 5 attach_cluster – 接入 CloudTower 集群
from __future__ import annotations

import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    CLOUDTOWER_CLUSTER_POLL_INTERVAL,
    CLOUDTOWER_CLUSTER_POLL_TIMEOUT,
    CLOUDTOWER_CREATE_DATACENTER_ENDPOINT,
    CLOUDTOWER_CONNECT_CLUSTER_ENDPOINT,
    CLOUDTOWER_DEFAULT_DATACENTER_NAME,
    CLOUDTOWER_GET_CLUSTERS_ENDPOINT,
    _cloudtower_login,
    _extract_cluster_management_vip,
    _resolve_cloudtower_ip,
    _resolve_cloudtower_setup_inputs,
)

logger = logging.getLogger(__name__)


def _ensure_plan_for_attach(ctx: RunContext, stage_logger: logging.LoggerAdapter):
    """确保在独立运行时也能获得规划表模型与解析结果。"""

    plan_model = getattr(ctx, "plan", None)
    parsed_plan = ctx.extra.get('parsed_plan') if isinstance(ctx.extra, dict) else None
    if plan_model or parsed_plan:
        return plan_model, parsed_plan

    try:
        base_dir = ctx.work_dir if hasattr(ctx, "work_dir") and isinstance(ctx.work_dir, Path) else Path.cwd()
        plan_path = find_plan_file(base_dir=base_dir)
        if plan_path:
            parsed_plan = parse_plan(plan_path)
            plan_model = to_model(parsed_plan)
            ctx.plan = plan_model
            if isinstance(ctx.extra, dict):
                ctx.extra['parsed_plan'] = parsed_plan
            stage_logger.info(tr("deploy.attach_cluster.plan_loaded"), progress_extra={"plan_path": str(plan_path)})
        else:
            stage_logger.warning(
                tr("deploy.attach_cluster.plan_not_found"),
                progress_extra={"base_dir": str(base_dir)},
            )
    except Exception as exc:  # noqa: BLE001
        stage_logger.warning(
            tr("deploy.attach_cluster.plan_load_failed"),
            progress_extra={"error": str(exc)},
        )

    return plan_model, parsed_plan


def _fetch_existing_organization(client: APIClient, stage_logger: logging.LoggerAdapter) -> Dict[str, Any]:
    headers = {"content-type": "application/json"}
    # 如果 session 已有 Authorization，则沿用；否则调用前需确保登录已设置。
    auth_token = client.session.headers.get("Authorization") if hasattr(client, "session") else None
    if auth_token:
        headers["Authorization"] = str(auth_token)

    try:
        response = client.post("/v2/api/get-organizations", payload={}, headers=headers)
    except Exception as exc:  # noqa: BLE001
        stage_logger.warning(tr("deploy.attach_cluster.org_query_fail_retry"), progress_extra={"error": str(exc)})
        return {}

    # 返回固定为列表形态：[{"datacenters": [...], "id": "string", "name": "string"}]
    orgs: List[Dict[str, Any]] = []
    if isinstance(response, list):
        orgs = [item for item in response if isinstance(item, dict)]
    else:
        stage_logger.warning(
            tr("deploy.attach_cluster.org_response_not_list"),
            progress_extra={"type": type(response).__name__},
        )

    if orgs:
        first = orgs[0]
        stage_logger.info(
            "复用已有 CloudTower 组织",
            progress_extra={"organization_id": first.get("id"), "organization_name": first.get("name")},
        )
        return first

    stage_logger.warning(tr("deploy.attach_cluster.org_list_empty"))
    return {}


@stage_handler(Stage.attach_cluster)
def handle_attach_cluster(ctx_dict: Dict[str, Any]) -> None:
    ctx: RunContext = ctx_dict['ctx']
    stage_logger = create_stage_progress_logger(ctx, Stage.attach_cluster.value, logger=logger, prefix="[attach_cluster]")

    cfg = ctx.config or load_config(DEFAULT_CONFIG_FILE)
    cfg_dict = dict(cfg) if isinstance(cfg, dict) else {}
    api_cfg = dict(cfg_dict.get('api', {}) or {})
    timeout = int(api_cfg.get('timeout', 10))

    plan_model, parsed_plan = _ensure_plan_for_attach(ctx, stage_logger)

    deploy_info = ctx.extra.get('deploy_cloudtower') or {}
    if not deploy_info or deploy_info.get('status') != 'SERVICE_READY':
        stage_logger.info(tr("deploy.attach_cluster.no_stage4_output_probe"))
        cloud_cfg = cfg_dict.get('cloudtower', {}) if isinstance(cfg_dict, dict) else {}
        cloudtower_ip = _resolve_cloudtower_ip(plan_model, parsed_plan, cloud_cfg, stage_logger)
        if not cloudtower_ip:
            raise RuntimeError("缺少 CloudTower IP，无法执行探测与关联。")

        stage_logger.info(tr("deploy.attach_cluster.probe_port"), progress_extra={"ip": cloudtower_ip, "port": 443})
        if not check_port(cloudtower_ip, 443, timeout=5.0):
            raise RuntimeError("CloudTower 443 端口不可达，无法执行关联。")

        client_probe = APIClient(
            base_url=f"https://{cloudtower_ip}",
            mock=False,
            timeout=timeout,
            verify=False,
        )
        token = _cloudtower_login(client=client_probe, ip=cloudtower_ip, stage_logger=stage_logger)
        client_probe.session.headers['Authorization'] = token

        inputs = _resolve_cloudtower_setup_inputs(
            plan=ctx.plan,
            parsed_plan=parsed_plan,
            config_data=cfg_dict,
            stage_logger=stage_logger,
        )
        org_info = _fetch_existing_organization(client_probe, stage_logger)
        org_id = org_info.get('id') if isinstance(org_info, dict) else None
        if not org_id:
            raise RuntimeError("CloudTower 已就绪但未能获取组织 ID，无法继续关联。")

        deploy_info = {
            "status": "SERVICE_READY",
            "ip": cloudtower_ip,
            "cloudtower": {
                "organization": {"id": org_id, "name": inputs.organization_name},
                "inputs": asdict(inputs),
                "session": {"token": token, "username": "root"},
            },
        }
        ctx.extra['deploy_cloudtower'] = deploy_info
        stage_logger.info(tr("deploy.attach_cluster.probe_success_continue"), progress_extra={"ip": cloudtower_ip})

    cloudtower_ip = deploy_info.get('ip')
    if not cloudtower_ip:
        raise RuntimeError("缺少 CloudTower 访问 IP，请先完成阶段 04 或确保规划表填写。")

    setup_info = deploy_info.get('cloudtower') or {}
    inputs = setup_info.get('inputs') or {}
    organization = setup_info.get('organization') or {}
    session = setup_info.get('session') or {}

    organization_id = organization.get('id')
    if not organization_id:
        raise RuntimeError("缺少 CloudTower 组织 ID，请先执行部署阶段初始化配置。")

    datacenter_name = (inputs.get('datacenter_name') or CLOUDTOWER_DEFAULT_DATACENTER_NAME).strip()
    cluster_vip = inputs.get('cluster_vip')
    if not cluster_vip:
        cluster_vip = _extract_cluster_management_vip(ctx.plan, ctx.extra.get('parsed_plan'))
    if not cluster_vip:
        raise RuntimeError("无法确定集群 VIP，请在规划表中补充后重试。")

    cluster_username = (inputs.get('cluster_username') or 'root').strip()
    cluster_password = (inputs.get('cluster_password') or 'HC!r0cks').strip()

    stage_logger.info(
        tr("deploy.attach_cluster.start"),
        progress_extra={
            "cloudtower_ip": cloudtower_ip,
            "datacenter_name": datacenter_name,
            "cluster_vip": cluster_vip,
        },
    )

    client = APIClient(
        base_url=f"https://{cloudtower_ip}",
        mock=False,
        timeout=timeout,
        verify=False,  # CloudTower 使用自签证书
    )
    token = session.get('token')
    if not token:
        stage_logger.warning(tr("deploy.attach_cluster.missing_token_login"))
        token = _cloudtower_login(client=client, ip=cloudtower_ip, stage_logger=stage_logger)

    headers = {
        "Authorization": token,
        "content-type": "application/json",
    }

    datacenter_id = _create_cloudtower_datacenter(
        client=client,
        headers=headers,
        organization_id=organization_id,
        datacenter_name=datacenter_name,
        stage_logger=stage_logger,
    )
    cluster_info = _connect_cloudtower_cluster(
        client=client,
        headers=headers,
        datacenter_id=datacenter_id,
        cluster_vip=cluster_vip,
        username=cluster_username,
        password=cluster_password,
        stage_logger=stage_logger,
    )

    ctx.extra['attach_cluster'] = {
        "status": "SUCCESS",
        "cloudtower_ip": cloudtower_ip,
        "datacenter": {"id": datacenter_id, "name": datacenter_name},
        "cluster": cluster_info,
    }

    stage_logger.info(
        tr("deploy.attach_cluster.success"),
        progress_extra={
            "datacenter_id": datacenter_id,
            "cluster_id": cluster_info.get('id'),
            "connect_state": cluster_info.get('connect_state'),
        },
    )


def _create_cloudtower_datacenter(
    *,
    client: APIClient,
    headers: Dict[str, str],
    organization_id: str,
    datacenter_name: str,
    stage_logger: logging.LoggerAdapter,
) -> str:
    stage_logger.info(
        tr("deploy.attach_cluster.create_datacenter"),
        progress_extra={"organization_id": organization_id, "datacenter_name": datacenter_name},
    )

    payload = {"organization_id": organization_id, "name": datacenter_name}
    response = client.post(CLOUDTOWER_CREATE_DATACENTER_ENDPOINT, payload=payload, headers=headers)
    data = _extract_response_dict(response)
    datacenter = data.get('data') if isinstance(data.get('data'), dict) else data
    datacenter_id = datacenter.get('id') if isinstance(datacenter, dict) else None
    if not datacenter_id:
        raise RuntimeError("创建数据中心失败：未返回 ID")
    stage_logger.debug(tr("deploy.attach_cluster.datacenter_created_debug"), progress_extra={"datacenter_id": datacenter_id})
    return str(datacenter_id)


def _connect_cloudtower_cluster(
    *,
    client: APIClient,
    headers: Dict[str, str],
    datacenter_id: str,
    cluster_vip: str,
    username: str,
    password: str,
    stage_logger: logging.LoggerAdapter,
) -> Dict[str, Any]:
    stage_logger.info(
        tr("deploy.attach_cluster.connect_cluster"),
        progress_extra={"datacenter_id": datacenter_id, "cluster_vip": cluster_vip, "username": username},
    )

    payload = {
        "datacenter_id": datacenter_id,
        "ip": cluster_vip,
        "username": username,
        "password": password,
    }
    response = client.post(CLOUDTOWER_CONNECT_CLUSTER_ENDPOINT, payload=payload, headers=headers)
    data = _extract_response_dict(response)
    cluster_stub = data.get('data') if isinstance(data.get('data'), dict) else data
    cluster_id = cluster_stub.get('id') if isinstance(cluster_stub, dict) else None
    task_id = data.get('task_id')
    if cluster_id:
        stage_logger.debug(
            tr("deploy.attach_cluster.cluster_id_debug"),
            progress_extra={"cluster_id": cluster_id, "task_id": task_id},
        )

    cluster = _poll_cloudtower_cluster_status(
        client=client,
        headers=headers,
        expected_cluster_id=cluster_id,
        expected_cluster_ip=cluster_vip,
        stage_logger=stage_logger,
    )
    if cluster_id and not cluster.get('id'):
        cluster['id'] = cluster_id
    return cluster


def _poll_cloudtower_cluster_status(
    *,
    client: APIClient,
    headers: Dict[str, str],
    expected_cluster_id: Optional[str],
    expected_cluster_ip: Optional[str],
    stage_logger: logging.LoggerAdapter,
) -> Dict[str, Any]:
    deadline = time.monotonic() + CLOUDTOWER_CLUSTER_POLL_TIMEOUT
    while time.monotonic() < deadline:
        response = client.post(CLOUDTOWER_GET_CLUSTERS_ENDPOINT, payload={}, headers=headers)
        clusters = _extract_clusters(response)
        for cluster in clusters:
            cid = str(cluster.get('id')) if cluster.get('id') else None
            cip = str(cluster.get('ip')) if cluster.get('ip') else None
            if expected_cluster_id and cid == expected_cluster_id or expected_cluster_ip and cip == expected_cluster_ip:
                state = str(cluster.get('connect_state') or '').upper()
                stage_logger.debug(
                    tr("deploy.attach_cluster.cluster_status_update"),
                    progress_extra={"cluster_id": cid or cip, "connect_state": state},
                )
                if state == 'CONNECTED':
                    return cluster
                if state in {"FAILED", "ERROR"}:
                    raise RuntimeError(f"CloudTower 集群关联失败，状态：{state}")
        stage_logger.info(
            tr("deploy.attach_cluster.wait_cluster_attach"),
            progress_extra={"interval": CLOUDTOWER_CLUSTER_POLL_INTERVAL},
        )
        time.sleep(CLOUDTOWER_CLUSTER_POLL_INTERVAL)

    raise RuntimeError("CloudTower 集群关联超时，请人工确认集群状态。")


def _extract_response_dict(response: Any) -> Dict[str, Any]:
    if isinstance(response, list):
        for item in response:
            if isinstance(item, dict):
                return item
    if isinstance(response, dict):
        return response
    return {}


def _extract_clusters(response: Any) -> List[Dict[str, Any]]:
    if isinstance(response, list):
        clusters: List[Dict[str, Any]] = []
        for item in response:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get('data'), dict) and isinstance(item['data'].get('clusters'), list):
                clusters.extend([cluster for cluster in item['data']['clusters'] if isinstance(cluster, dict)])
            elif item:
                clusters.append(item)
        return clusters

    data = _extract_response_dict(response)
    if isinstance(data.get('data'), dict) and isinstance(data['data'].get('clusters'), list):
        return [cluster for cluster in data['data']['clusters'] if isinstance(cluster, dict)]
    if isinstance(data.get('clusters'), list):
        return [cluster for cluster in data['clusters'] if isinstance(cluster, dict)]
    return []
