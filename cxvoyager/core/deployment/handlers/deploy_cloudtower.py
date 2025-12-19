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

# Stage 4 deploy_cloudtower – 部署 CloudTower
from __future__ import annotations
import hashlib
import importlib
import ipaddress
import logging
import math
import shlex
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from logging import LoggerAdapter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import openpyxl

from cxvoyager.common.config import load_config
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE
from cxvoyager.common.network_utils import check_port
from cxvoyager.core.deployment.progress import create_stage_progress_logger
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.stage_manager import AbortRequestedError, Stage, stage_handler, raise_if_aborted
from cxvoyager.integrations.smartx.api_client import APIClient, APIError
from cxvoyager.integrations.excel import field_variables as plan_vars
from cxvoyager.integrations.excel.planning_sheet_parser import find_plan_file, parse_plan, to_model
from cxvoyager.models.planning_sheet_models import PlanModel


logger = logging.getLogger(__name__)


DEFAULT_CHUNK_SIZE = 128 * 1024 * 1024  # 每个 ISO 分片默认大小，单位字节（128 MiB）。
CLOUDTOWER_DEFAULT_VM_DESCRIPTION = "CloudTower VM auto created by CXVoyager"  # 虚拟机描述的默认值，指明来源。
CLOUDTOWER_DEFAULT_VM_NAME = "cloudtower"  # 默认的 CloudTower 虚拟机名称。
CLOUDTOWER_DEFAULT_STORAGE_POLICY = "default"  # 默认使用的存储策略名称。
CLOUDTOWER_DEFAULT_OVS_HINTS = ("ovsbr", "VDS-MGT")  # 推断管理网络时常见的 OVS 命名前缀，用于日志提示。
DEFAULT_CLOUDTOWER_SSH_USER = "cloudtower"  # CloudTower 虚拟机默认 SSH 用户名。
DEFAULT_CLOUDTOWER_SSH_PASSWORD = "HC!r0cks"  # CloudTower 用户默认密码。
DEFAULT_CLOUDTOWER_SSH_PORT = 22  # SSH 默认端口。
DEFAULT_SSH_TIMEOUT = 30  # SSH 连接默认超时时间（秒）。
CLOUDTOWER_SSH_KEEPALIVE_INTERVAL = 30  # SSH keepalive 间隔，避免长时间执行时连接被断开。
CLOUDTOWER_INSTALL_SUCCESS_TOKEN = "Install Operation Center Successfully"  # 表示安装成功的日志关键字。
CLOUDTOWER_INSTALL_TIMEOUT = 40 * 60  # CloudTower 服务安装最长等待时间 40 分钟（单位秒）。
CLOUDTOWER_LOG_CHECK_INTERVAL = 30  # 轮询 installer.out 日志间隔 30 秒。
CLOUDTOWER_LOG_GRACE_PERIOD = 180  # 前 3 分钟允许 installer.out 不存在。
CLOUDTOWER_HTTPS_PORT = 443  # CloudTower 管理界面使用的 HTTPS 端口。
CLOUDTOWER_PORT_RETRY = 3  # 端口检查最大重试次数。
CLOUDTOWER_PORT_RETRY_INTERVAL = 10  # 端口检查重试间隔（秒）。
CLOUDTOWER_ROOT_PASSWORD_ENCODED = "NzllNTE3NTgxYWY5NDY3ODM4ZTczMTg1MDc4YmM3YzQ6eVpSSTlodUNxNDBNL3J4ZTViZ1dqZz09"  # CloudTower 管理员 root 密码（Base64 编码）。
CLOUDTOWER_GRAPHQL_ENDPOINT = "/api"  # CloudTower GraphQL 入口。
CLOUDTOWER_LOGIN_ENDPOINT = "/v2/api/login"  # CloudTower 登录接口入口。
CLOUDTOWER_CREATE_DATACENTER_ENDPOINT = "/v2/api/create-datacenter"  # 创建数据中心接口入口。
CLOUDTOWER_CONNECT_CLUSTER_ENDPOINT = "/v2/api/connect-cluster"  # 关联集群接口入口。
CLOUDTOWER_GET_CLUSTERS_ENDPOINT = "/v2/api/get-clusters"  # 查询集群信息接口入口。
CLOUDTOWER_STORAGE_POLICIES_ENDPOINT = "/api/v2/storage_policies"  # 查询存储策略列表。
CLOUDTOWER_VDS_ENDPOINT = "/api/v2/network/vds"  # 查询 VDS 列表。
CLOUDTOWER_VDS_VLANS_ENDPOINT = "/api/v2/network/vds/{vds_uuid}/vlans"  # 查询指定 VDS 下的 VLAN 列表。
CLOUDTOWER_VM_ENDPOINT = "/api/v2/vms"  # 创建 CloudTower 虚拟机。
CLOUDTOWER_JOB_ENDPOINT = "/api/v2/jobs/{job_id}"  # 查询异步任务状态。
CLOUDTOWER_VM_DETAIL_ENDPOINT = "/api/v2/vms/{vm_uuid}"  # 查询或更新虚拟机详情。
CLOUDTOWER_IMAGES_ENDPOINT = "/api/v2/images"  # 查询 CloudTower ISO 列表。
CLOUDTOWER_VOLUME_ENDPOINT = "/api/v2/images/upload/volume"  # 创建 CloudTower ISO 上传卷。
CLOUDTOWER_UPLOAD_ENDPOINT = "/api/v2/images/upload"  # 上传 CloudTower ISO 分片。
CLOUDTOWER_DELETE_ENDPOINT = "/api/v2/images/{image_uuid}"  # 删除 CloudTower ISO 上传卷。
CLOUDTOWER_CLUSTER_POLL_INTERVAL = 10  # 轮询集群关联状态的默认间隔。
CLOUDTOWER_CLUSTER_POLL_TIMEOUT = 15 * 60  # 集群关联状态轮询总超时，默认 15 分钟。
CLOUDTOWER_DEFAULT_DATACENTER_NAME = "SMTX-HCI-DC"  # 数据中心默认名称。
CLOUDTOWER_DEFAULT_ORGANIZATION_NAME = "SMTX-HCI"  # 组织默认名称。
CLOUDTOWER_VM_READY_INTERVAL = 10  # 虚拟机 Guest OS 轮询间隔（秒）。
CLOUDTOWER_VM_READY_TIMEOUT = 30 * 60  # 等待虚拟机操作系统就绪的超时时间（秒）。

CLOUDTOWER_GQL_CREATE_ROOT = """
mutation createRootUser($root_password: String!, $now: DateTime!) {
    createUser(
        data: {
            name: "root"
            source: LOCAL
            role: ROOT
            username: "root"
            display_username: "root"
            password: $root_password
            password_recover_qa: { enabled: false, items: [] }
            password_updated_at: $now
        }
        effect: { encoded: true }
    ) {
        id
        __typename
    }
}
""".strip()

CLOUDTOWER_GQL_CREATE_ORGANIZATION = """
mutation createOrganization($data: OrganizationCreateInput!) {
    createOrganization(data: $data) {
        id
        __typename
    }
}
""".strip()

CLOUDTOWER_GQL_CHECK_SETUP = """
query checkTowerIsSetup {
    organizations(first: 10) {
        id
        name
        __typename
    }
    userCreated {
        created
        __typename
    }
}
""".strip()

CLOUDTOWER_GQL_UPDATE_NTP = """
mutation updateCloudTowerNtpUrl($data: NtpCommonUpdateInput!) {
    updateCloudTowerNtpUrl(data: $data) {
        ntp_service_url
        __typename
    }
}
""".strip()

CLOUDTOWER_GQL_DEPLOYED_LICENSE = """
query deployedLicense {
    deploys(first: 1) {
        id
        license {
            id
            license_serial
            maintenance_end_date
            maintenance_start_date
            max_chunk_num
            max_cluster_num
            max_vm_num
            used_vm_num
            sign_date
            expire_date
            software_edition
            type
            vendor
            __typename
        }
        __typename
    }
}
""".strip()


@dataclass
class CloudTowerNetworkPlan:
    """CloudTower 虚拟机的网络规划信息，来源于规划表或用户配置。"""

    vds_name: str = ""  # VDS 名称，用于在 API 中检索对应的虚拟交换机。
    vlan_name: Optional[str] = None  # VLAN 名称，辅助在接口返回值中定位目标网络。
    vlan_id: Optional[int] = None  # VLAN ID，若无法从名称匹配则使用数值匹配。
    gateway: Optional[str] = None  # 管理网络网关地址。
    subnet_cidr: Optional[str] = None  # 管理网络的 CIDR 表达式，用于推导子网掩码。
    subnet_mask: Optional[str] = None  # 子网掩码，若未显式提供则由 subnet_cidr 推导。
    ip_address: Optional[str] = None  # CloudTower 虚拟机在管理网络中的静态 IP。
    ovs_name: Optional[str] = None  # 查询 VDS 后得到的 OVS 名称，提交网络配置时需要。
    vds_uuid: Optional[str] = None  # VDS 在 API 中的唯一标识符。
    vlan_uuid: Optional[str] = None  # VLAN 在 API 中的唯一标识符。


@dataclass
class CloudTowerVMConfig:
    """CloudTower 虚拟机硬件配置参数。"""

    vm_name: str = CLOUDTOWER_DEFAULT_VM_NAME  # 虚拟机名称。
    description: str = CLOUDTOWER_DEFAULT_VM_DESCRIPTION  # 虚拟机描述信息。
    vcpu: int = 8  # vCPU 数量，根据官方推荐固定为 8。
    cpu_sockets: int = 8  # CPU 插槽数量，与拓扑要求保持一致。
    cpu_cores: int = 1  # 每个插槽的核心数，固定为 1。
    memory_bytes: int = 20_401_094_656  # 内存大小（字节），约 19 GiB，符合文档要求。
    os_disk_size_bytes: int = 429_496_729_600  # 系统盘大小（字节），400 GiB。
    cdrom_path: Optional[str] = None  # ISO 挂载路径，由上传卷返回的 image_path 提供。
    storage_policy_name: str = CLOUDTOWER_DEFAULT_STORAGE_POLICY  # 优先选取的存储策略名称。
    storage_policy_uuid: Optional[str] = None  # 查询 API 后得到的存储策略 UUID。
    vm_uuid: Optional[str] = None  # 虚拟机创建成功后返回的 UUID。
    os_version: Optional[str] = None  # CloudTower 虚拟机检测到的操作系统版本信息。
    guest_agent_state: Optional[str] = None  # VMTools/Guest Agent 的运行状态。


@dataclass
class CloudTowerSSHConfig:
    """CloudTower 虚拟机 SSH 访问参数。"""

    username: str = DEFAULT_CLOUDTOWER_SSH_USER  # SSH 用户名。
    password: str = DEFAULT_CLOUDTOWER_SSH_PASSWORD  # SSH 密码。
    port: int = DEFAULT_CLOUDTOWER_SSH_PORT  # SSH 端口号。
    timeout: int = DEFAULT_SSH_TIMEOUT  # SSH 连接超时时间。


@dataclass
class CloudTowerDeploymentPlan:
    """汇总 CloudTower 部署所需的全部上下文信息。"""

    network: CloudTowerNetworkPlan = field(default_factory=CloudTowerNetworkPlan)
    vm: CloudTowerVMConfig = field(default_factory=CloudTowerVMConfig)
    ssh: CloudTowerSSHConfig = field(default_factory=CloudTowerSSHConfig)
    cloudtower_ip: Optional[str] = None  # CloudTower 服务最终访问 IP。
    iso_summary: Dict[str, Any] = field(default_factory=dict)  # ISO 上传摘要信息。
    additional_headers: Dict[str, str] = field(default_factory=dict)  # 补充的请求头，例如重写 token。


@dataclass
class CloudTowerSetupInputs:
    """CloudTower 后续配置所需的输入参数集合。"""

    organization_name: str = CLOUDTOWER_DEFAULT_ORGANIZATION_NAME
    datacenter_name: str = CLOUDTOWER_DEFAULT_DATACENTER_NAME
    ntp_servers: List[str] = field(default_factory=list)
    dns_servers: List[str] = field(default_factory=list)
    cluster_vip: Optional[str] = None
    cluster_username: str = "root"
    cluster_password: str = "HC!r0cks"


@stage_handler(Stage.deploy_cloudtower)
def handle_deploy_cloudtower(ctx_dict):
    """执行 CloudTower 部署阶段：上传 ISO、创建虚拟机、配置网络并安装服务。"""

    ctx: RunContext = ctx_dict['ctx']
    stage_logger = create_stage_progress_logger(
        ctx, Stage.deploy_cloudtower.value, logger=logger, prefix="[deploy_cloudtower]"
    )

    abort_signal = ctx_dict.get('abort_signal')
    if abort_signal is None and isinstance(ctx.extra, dict):
        abort_signal = ctx.extra.get('abort_signal')
    if abort_signal is not None and isinstance(ctx.extra, dict):
        ctx.extra.setdefault('abort_signal', abort_signal)

    raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="准备 CloudTower 部署")

    plan, parsed_plan_data = _ensure_plan_context(ctx, stage_logger)

    cfg = ctx.config or load_config(DEFAULT_CONFIG_FILE)
    cfg_dict = cfg if isinstance(cfg, dict) else {}
    api_cfg = cfg_dict.get('api', {}) if isinstance(cfg_dict, dict) else {}
    token = api_cfg.get('x-smartx-token')
    timeout = int(api_cfg.get('timeout', 10))
    use_mock = bool(api_cfg.get('mock', False))

    stage_logger.info(
        "开始执行 CloudTower 部署阶段",
        progress_extra={"timeout": timeout, "mock_mode": use_mock},
    )

    parsed_plan = parsed_plan_data or (ctx.extra.get('parsed_plan') if isinstance(ctx.extra, dict) else None)
    host_info = _ensure_host_scan_context(
        ctx,
        plan=plan,
        parsed_plan=parsed_plan,
        cfg=cfg_dict,
        stage_logger=stage_logger,
    )
    base_url, host_header = _resolve_fisheye_api_endpoint(
        host_info=host_info,
        plan=plan,
        parsed_plan=parsed_plan,
        stage_logger=stage_logger,
    )
    client = APIClient(base_url=base_url, mock=use_mock, timeout=timeout)
    headers = _build_base_headers(token, host_header)

    if not use_mock:
        stage_logger.info(
            "使用 Fisheye 凭证获取会话 token",
            progress_extra={"base_url": base_url.rstrip('/')},
        )
        if not _refresh_fisheye_token(
            ctx=ctx,
            client=client,
            headers=headers,
            stage_logger=stage_logger,
        ):
            raise RuntimeError("Fisheye 会话认证失败，无法继续 CloudTower 部署")
    else:
        stage_logger.debug("Mock 模式跳过 Fisheye 登录步骤")

    json_headers = dict(headers)
    json_headers["content-type"] = "application/json"
    stage_logger.debug(
        "API 客户端初始化完成",
        progress_extra={
            "base_url": base_url.rstrip('/'),
            "timeout": timeout,
            "mock": use_mock,
            "has_token": bool(token),
        },
    )

    raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="Fisheye 连接初始化")

    if _should_verify_existing_cluster(ctx):
        _verify_existing_cluster_services(ctx, client, json_headers, stage_logger)

    raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="准备定位 CloudTower ISO")

    iso_path, iso_cfg = _resolve_iso_path(ctx, cfg_dict)
    iso_size = iso_path.stat().st_size
    if iso_size <= 0:
        raise RuntimeError(f"CloudTower ISO 文件为空: {iso_path}")

    stage_logger.info(
        "准备上传 CloudTower ISO",
        progress_extra={"path": str(iso_path), "size": iso_size},
    )

    upload_summary: Optional[Dict[str, Any]] = None
    deployment_plan: Optional[CloudTowerDeploymentPlan] = None
    post_setup: Optional[Dict[str, Any]] = None
    volume_info: Optional[Dict[str, Any]] = None
    try:
        raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="查询 CloudTower ISO 列表")

        existing_iso = _find_existing_cloudtower_iso(
            ctx=ctx,
            client=client,
            headers=headers,
            iso_path=iso_path,
            iso_size=iso_size,
            iso_cfg=iso_cfg,
            stage_logger=stage_logger,
        )

        if existing_iso:
            upload_summary = existing_iso
        else:
            raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="创建 CloudTower 上传卷")
            volume_info = _create_cloudtower_upload_volume(
                client=client,
                headers=headers,
                iso_path=iso_path,
                iso_size=iso_size,
                iso_cfg=iso_cfg,
                stage_logger=stage_logger,
            )
            raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="CloudTower ISO 上传")
            upload_summary = _upload_cloudtower_iso_chunks(
                client=client,
                headers=headers,
                iso_path=iso_path,
                iso_size=iso_size,
                volume_info=volume_info,
                iso_cfg=iso_cfg,
                stage_logger=stage_logger,
                ctx_dict=ctx_dict,
            )

        if not isinstance(upload_summary, dict):
            raise RuntimeError("未获取到 CloudTower ISO 上传摘要信息")

        raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="组装 CloudTower 部署计划")
        deployment_plan = _assemble_cloudtower_deployment_plan(
            ctx=ctx,
            iso_cfg=iso_cfg,
            upload_summary=upload_summary,
            parsed_plan=parsed_plan,
            stage_logger=stage_logger,
        )

        raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="创建 CloudTower 虚拟机")
        _deploy_cloudtower_virtual_machine(
            ctx=ctx,
            client=client,
            headers=json_headers,
            base_headers=headers,
            deployment_plan=deployment_plan,
            stage_logger=stage_logger,
        )

        raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="部署 CloudTower 服务")
        _install_and_verify_cloudtower_services(
            deployment_plan=deployment_plan,
            stage_logger=stage_logger,
        )

        raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="执行 CloudTower 后置配置")
        post_setup = _configure_cloudtower_post_install(
            ctx=ctx,
            deployment_plan=deployment_plan,
            config_data=cfg_dict,
            parsed_plan=parsed_plan,
            timeout=timeout,
            use_mock=use_mock,
            stage_logger=stage_logger,
        )
    except AbortRequestedError as exc:
        if upload_summary is None and volume_info is not None:
            _cleanup_upload_volume(client, headers, volume_info, stage_logger)
        stage_logger.warning(
            "CloudTower 部署阶段收到终止信号，正在停止",
            progress_extra={"stage": Stage.deploy_cloudtower.value},
        )
        raise exc
    except Exception as exc:  # noqa: BLE001 - 统一处理异常
        if upload_summary is None and volume_info is not None:
            _cleanup_upload_volume(client, headers, volume_info, stage_logger)
        stage_logger.error(
            "CloudTower 部署阶段失败",
            progress_extra={"error": str(exc)},
        )
        raise RuntimeError(f"CloudTower 部署失败: {exc}") from exc

    result = ctx.extra.setdefault('deploy_cloudtower', {})
    cloudtower_ip = deployment_plan.cloudtower_ip if deployment_plan else str(getattr(mgmt, "Cloudtower_IP", ""))
    result.update({
        "status": "SERVICE_READY",
        "ip": cloudtower_ip,
        "base_url": base_url.rstrip('/') if isinstance(base_url, str) else None,
        "iso": upload_summary,
        "vm": {
            "name": deployment_plan.vm.vm_name if deployment_plan else CLOUDTOWER_DEFAULT_VM_NAME,
            "uuid": deployment_plan.vm.vm_uuid if deployment_plan else None,
            "storage_policy_uuid": deployment_plan.vm.storage_policy_uuid if deployment_plan else None,
            "os_version": deployment_plan.vm.os_version if deployment_plan else None,
            "guest_agent_state": deployment_plan.vm.guest_agent_state if deployment_plan else None,
        },
        "network": {
            "ip": deployment_plan.network.ip_address if deployment_plan else cloudtower_ip,
            "gateway": deployment_plan.network.gateway if deployment_plan else None,
            "subnet_mask": deployment_plan.network.subnet_mask if deployment_plan else None,
            "vds_uuid": deployment_plan.network.vds_uuid if deployment_plan else None,
            "vlan_uuid": deployment_plan.network.vlan_uuid if deployment_plan else None,
        } if deployment_plan else {},
        "cloudtower": post_setup or {},
    })

    stage_logger.info(
        "CloudTower 服务部署完成",
        progress_extra={
            "cloudtower_ip": cloudtower_ip,
            "vm_uuid": deployment_plan.vm.vm_uuid if deployment_plan else None,
            "storage_policy": deployment_plan.vm.storage_policy_name if deployment_plan else None,
            "image_uuid": upload_summary.get("image_uuid") if upload_summary else None,
            "os_version": deployment_plan.vm.os_version if deployment_plan else None,
            "guest_agent_state": deployment_plan.vm.guest_agent_state if deployment_plan else None,
        },
    )


def _ensure_plan_context(ctx: RunContext, stage_logger: LoggerAdapter) -> tuple[PlanModel, Optional[Dict[str, Any]]]:
    """确保 ctx 中存在 PlanModel；如缺失则自动加载规划表。"""

    plan = getattr(ctx, "plan", None)
    parsed_plan: Optional[Dict[str, Any]] = None
    if isinstance(ctx.extra, dict):
        candidate = ctx.extra.get('parsed_plan')
        if isinstance(candidate, dict):
            parsed_plan = candidate

    def _locate_plan_path() -> Optional[Path]:
        path_candidate: Optional[Path] = None
        if plan is not None:
            source = getattr(plan, "source_file", None)
            if source:
                candidate_path = Path(str(source))
                if not candidate_path.is_absolute():
                    base_dir = ctx.work_dir if isinstance(ctx.work_dir, Path) else Path.cwd()
                    candidate_path = (base_dir / candidate_path).resolve()
                if candidate_path.exists():
                    path_candidate = candidate_path
        if path_candidate is None and isinstance(ctx.extra, dict):
            extra_source = ctx.extra.get('plan_source')
            if extra_source:
                candidate_path = Path(str(extra_source)).resolve()
                if candidate_path.exists():
                    path_candidate = candidate_path
        if path_candidate is None:
            work_dir = ctx.work_dir if isinstance(ctx.work_dir, Path) else Path.cwd()
            located = find_plan_file(work_dir)
            if located and located.exists():
                path_candidate = located
        return path_candidate

    mgmt_present = getattr(plan, "mgmt", None) is not None if plan is not None else False
    if plan is not None and mgmt_present:
        # 如果缺少 parsed_plan，则尝试在不影响现有上下文的情况下补充。
        if parsed_plan is None:
            plan_path = _locate_plan_path()
            if plan_path is not None:
                try:
                    parsed_plan = parse_plan(plan_path)
                except Exception as exc:  # noqa: BLE001
                    stage_logger.debug(
                        "无法自动解析规划表，继续使用已提供的 PlanModel。",
                        progress_extra={"plan_path": str(plan_path), "error": str(exc)},
                    )
                else:
                    if isinstance(ctx.extra, dict):
                        ctx.extra['parsed_plan'] = parsed_plan
                        ctx.extra.setdefault('plan_source', str(plan_path))
        return plan, parsed_plan

    plan_path = _locate_plan_path()
    work_dir = ctx.work_dir if isinstance(ctx.work_dir, Path) else Path.cwd()

    if plan_path is None:
        stage_logger.error(
            "未能自动定位规划表，请确认当前工作目录包含有效规划表。",
            progress_extra={"work_dir": str(work_dir)},
        )
        raise RuntimeError("缺少规划表 PlanModel 实例 (ctx.plan)，无法部署 CloudTower。")

    try:
        parsed_plan = parse_plan(plan_path)
    except Exception as exc:  # noqa: BLE001
        stage_logger.error(
            "解析规划表失败",
            progress_extra={"plan_path": str(plan_path), "error": str(exc)},
        )
        raise RuntimeError(f"解析规划表失败: {exc}") from exc

    try:
        plan_model = to_model(parsed_plan)
    except Exception as exc:  # noqa: BLE001
        stage_logger.error(
            "规划表转换 PlanModel 失败",
            progress_extra={"plan_path": str(plan_path), "error": str(exc)},
        )
        raise RuntimeError(f"规划表转换失败: {exc}") from exc

    if not getattr(plan_model, "source_file", None):
        try:
            setattr(plan_model, "source_file", str(plan_path))
        except Exception:  # noqa: BLE001
            pass

    ctx.plan = plan_model
    if isinstance(ctx.extra, dict):
        ctx.extra['parsed_plan'] = parsed_plan
        ctx.extra.setdefault('plan_source', str(plan_path))

    stage_logger.info(
        "已自动补充 CloudTower 部署所需的规划表上下文",
        progress_extra={"plan_path": str(plan_path)},
    )

    if getattr(plan_model, "mgmt", None) is None:
        stage_logger.error(
            "规划表解析后仍缺少 mgmt 管理信息，请检查规划表内容或填写是否完整。",
            progress_extra={"plan_path": str(plan_path)},
        )
        raise RuntimeError("规划表缺少 mgmt 管理信息，请检查规划表或解析结果。")

    return plan_model, parsed_plan


def _resolve_plan_path_for_write(ctx: RunContext) -> Optional[Path]:
    """解析规划表路径，供写回序列号使用。"""

    candidates: List[str] = []
    plan_obj = getattr(ctx, "plan", None)
    if plan_obj is not None:
        source = getattr(plan_obj, "source_file", None)
        if source:
            candidates.append(str(source))
    if isinstance(ctx.extra, dict):
        extra_source = ctx.extra.get("plan_source")
        if extra_source:
            candidates.append(str(extra_source))

    work_dir = ctx.work_dir if isinstance(ctx.work_dir, Path) else Path.cwd()
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_absolute():
            path = (work_dir / path).resolve()
        if path.exists():
            return path
    return None


def _write_cloudtower_serial_to_plan(plan_path: Path, serial: str) -> None:
    workbook = openpyxl.load_workbook(plan_path)
    sheet = workbook[plan_vars.CLOUDTOWER_SERIAL.sheet]
    sheet[plan_vars.CLOUDTOWER_SERIAL.cell] = serial
    workbook.save(plan_path)


def _configure_rack_topology_placeholder(*, ctx: RunContext, stage_logger: LoggerAdapter) -> None:
    """TODO: 读取机架拓扑表并调用 CloudTower 接口配置机架拓扑。"""

    stage_logger.info(
        "机架拓扑自动化尚未实装，当前为占位实现",
        progress_extra={"plan_source": ctx.extra.get('plan_source') if isinstance(ctx.extra, dict) else None},
    )


def _ensure_host_scan_context(
    ctx: RunContext,
    *,
    plan: PlanModel,
    parsed_plan: Optional[Dict[str, Any]],
    cfg: Dict[str, Any],
    stage_logger: LoggerAdapter,
) -> Dict[str, Any]:
    """确保 ctx.extra['host_scan'] 至少包含一条主机记录。"""

    host_scan = ctx.extra.get('host_scan') if isinstance(ctx.extra, dict) else None
    if isinstance(host_scan, dict) and host_scan:
        return host_scan

    candidates: List[str] = []

    api_cfg = cfg.get('api', {}) if isinstance(cfg, dict) else {}
    base_url = api_cfg.get('base_url') if isinstance(api_cfg, dict) else None
    if base_url:
        try:
            parsed = urlparse(str(base_url))
            if parsed.hostname:
                candidates.append(parsed.hostname)
        except Exception:  # noqa: BLE001
            stage_logger.debug("解析 base_url 失败，忽略", progress_extra={"base_url": base_url})

    if parsed_plan is None:
        parsed_plan = ctx.extra.get('parsed_plan') if isinstance(ctx.extra, dict) else None

    plan_ips = _collect_plan_host_management_ips(plan, parsed_plan)
    for ip in plan_ips:
        if ip not in candidates:
            candidates.append(ip)

    vip = _extract_cluster_management_vip(plan, parsed_plan)
    if vip and vip not in candidates:
        candidates.append(vip)

    if not candidates:
        stage_logger.warning(
            "未检测到主机扫描结果，且无法从规划表推导主机 IP，后续将尝试仅依赖规划表数据继续部署。",
        )
        return {}

    primary_ip = candidates[0]
    stub = {primary_ip: {"host_ip": primary_ip}}
    if isinstance(ctx.extra, dict):
        ctx.extra['host_scan'] = stub

    stage_logger.info(
        "未检测到主机扫描结果，已根据规划表补充最小 host_scan 数据。",
        progress_extra={"host_ip": primary_ip},
    )
    return stub


def _resolve_fisheye_api_endpoint(
    *,
    host_info: Any,
    plan: Any,
    parsed_plan: Any,
    stage_logger: LoggerAdapter,
) -> tuple[str, Optional[str]]:
    candidates: List[tuple[str, str]] = []
    errors: List[Dict[str, str]] = []
    seen: set[str] = set()

    def _push(source: str, value: Any) -> None:
        if value is None:
            return
        value_str = str(value).strip()
        if not value_str or value_str in seen:
            return
        seen.add(value_str)
        candidates.append((source, value_str))

    cluster_vip = _extract_cluster_management_vip(plan, parsed_plan)
    if cluster_vip:
        _push("cluster_vip", cluster_vip)

    host_ips = _collect_host_management_ips(plan, parsed_plan, host_info)
    if host_ips:
        primary_ip, *rest = host_ips
        _push("primary_host_mgmt_ip", primary_ip)
        for ip in rest:
            _push("host_mgmt_ip", ip)

    if not candidates:
        if stage_logger:
            stage_logger.error(
                "无法解析任何 Fisheye API 候选地址",
                progress_extra={"plan_present": plan is not None, "host_scan_present": bool(host_info)},
            )
        raise RuntimeError("无法确定 Fisheye API 访问地址，请检查规划表与主机扫描数据是否完整。")

    for source, address in candidates:
        try:
            base_url, host_header = _format_endpoint_candidate(address)
        except ValueError as exc:
            errors.append({"source": source, "address": address, "error": str(exc)})
            continue

        if stage_logger:
            stage_logger.info(
                "选定 Fisheye API 端点",
                progress_extra={
                    "source": source,
                    "address": address,
                    "base_url": base_url.rstrip('/'),
                },
            )
        return base_url, host_header

    if stage_logger:
        stage_logger.error(
            "所有 Fisheye API 候选地址均无效",
            progress_extra={"attempts": candidates, "errors": errors},
        )
    raise RuntimeError("无法确定 Fisheye API 访问地址，请检查集群管理 VIP 及主机管理地址的填写。")


def _extract_cluster_management_vip(plan: Any, parsed_plan: Any) -> Optional[str]:
    def _normalize(value: Any) -> Optional[str]:
        if value is None:
            return None
        value_str = str(value).strip()
        return value_str or None

    if plan is not None:
        hosts = getattr(plan, "hosts", None)
        if hosts:
            for host in hosts:
                vip = _normalize(getattr(host, "集群VIP", None))
                if vip:
                    return vip
        mgmt = getattr(plan, "mgmt", None)
        if mgmt is not None:
            vip = _normalize(getattr(mgmt, "Cloudtower_IP", None))
            if vip:
                return vip

    if isinstance(parsed_plan, dict):
        hosts_section = parsed_plan.get("hosts")
        if isinstance(hosts_section, dict):
            records = hosts_section.get("records")
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict):
                        vip = _normalize(record.get("集群VIP") or record.get("cluster_vip"))
                        if vip:
                            return vip
        mgmt_section = parsed_plan.get("mgmt")
        if isinstance(mgmt_section, dict):
            records = mgmt_section.get("records")
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict):
                        vip = _normalize(record.get("Cloudtower IP") or record.get("cloudtower_ip"))
                        if vip:
                            return vip

    return None


def _collect_host_management_ips(plan: Any, parsed_plan: Any, host_info: Any) -> List[str]:
    ips: List[str] = []
    seen: set[str] = set()

    def _add(value: Any) -> None:
        if value is None:
            return
        value_str = str(value).strip()
        if not value_str or value_str in seen:
            return
        seen.add(value_str)
        ips.append(value_str)

    if isinstance(host_info, dict):
        for key in host_info.keys():
            _add(key)

    plan_ips = _collect_plan_host_management_ips(plan, parsed_plan)
    for ip in plan_ips:
        _add(ip)

    return ips


def _collect_plan_host_management_ips(plan: Any, parsed_plan: Any) -> List[str]:
    ips: List[str] = []

    def _add(value: Any) -> None:
        if value is None:
            return
        value_str = str(value).strip()
        if not value_str or value_str in ips:
            return
        ips.append(value_str)

    if plan is not None:
        hosts = getattr(plan, "hosts", None)
        if hosts:
            for host in hosts:
                _add(getattr(host, "管理地址", None))
                _add(getattr(host, "Host_IP", None))

    if isinstance(parsed_plan, dict):
        hosts_section = parsed_plan.get("hosts")
        if isinstance(hosts_section, dict):
            records = hosts_section.get("records")
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict):
                        _add(record.get("管理地址"))
                        _add(record.get("host_ip"))
                        _add(record.get("管理地址IP"))

    return ips


def _format_endpoint_candidate(address: str) -> tuple[str, str]:
    candidate = address.strip()
    if not candidate:
        raise ValueError("地址为空")
    if "://" not in candidate:
        candidate = f"http://{candidate}"

    parsed = urlparse(candidate)
    if not parsed.scheme or not parsed.netloc or not parsed.hostname:
        raise ValueError(f"地址格式不合法: {address}")

    base_url = f"{parsed.scheme}://{parsed.netloc}"
    return base_url, parsed.hostname


def _build_base_headers(token: Optional[str], host_header: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if host_header:
        headers["host"] = host_header
    if token:
        headers["x-smartx-token"] = token
    return headers


def _should_verify_existing_cluster(ctx: RunContext) -> bool:
    mode = ctx.extra.get('run_mode')
    if isinstance(mode, str) and mode == 'cloudtower-only':
        return True
    stages = ctx.extra.get('selected_stages') or []
    normalized: set[str] = set()
    for item in stages:
        if isinstance(item, Stage):
            normalized.add(item.value)
        elif isinstance(item, str):
            normalized.add(item)
    return normalized == {Stage.prepare.value, Stage.deploy_cloudtower.value}


def _verify_existing_cluster_services(
    ctx: RunContext,
    client: APIClient,
    headers: Dict[str, str],
    stage_logger: LoggerAdapter,
) -> None:
    """在复用旧集群模式下，验证 Fisheye API 会话是否可用。"""

    parsed_plan = ctx.extra.get('parsed_plan')
    user, password = _load_fisheye_credentials(ctx.plan, parsed_plan)
    payload = {
        "username": user or "root",
        "password": password or "HC!r0cks",
        "encrypted": False,
    }

    stage_logger.info(
        "复用已部署集群，正在验证 Fisheye API 会话",
        progress_extra={"username": payload.get("username")},
    )
    try:
        response = client.post("/api/v3/sessions", payload, headers=headers)
    except Exception as exc:  # noqa: BLE001
        stage_logger.error(
            "Fisheye 登录验证失败",
            progress_extra={"error": str(exc)},
        )
        raise RuntimeError("无法通过 Fisheye 登录验证现有集群，请确认集群服务状态。") from exc

    token = _extract_api_token(response)
    if not token:
        stage_logger.error(
            "Fisheye 登录未返回 token",
            progress_extra={"response_type": type(response).__name__},
        )
        raise RuntimeError("Fisheye 登录未返回有效 token，请确认集群服务正常后重试。")

    stage_logger.info(
        "Fisheye 会话验证通过",
        progress_extra={"has_token": bool(token)},
    )
    ctx.extra.setdefault('probes', {})['fisheye_login'] = {"status": "ok"}



def _assemble_cloudtower_deployment_plan(
    *,
    ctx: RunContext,
    iso_cfg: Dict[str, Any],
    upload_summary: Dict[str, Any],
    parsed_plan: Optional[Dict[str, Any]],
    stage_logger: LoggerAdapter,
) -> CloudTowerDeploymentPlan:
    """根据规划表与用户配置生成 CloudTower 部署计划。"""

    deployment_plan = CloudTowerDeploymentPlan()
    deployment_plan.iso_summary = dict(upload_summary or {})

    deployment_plan.cloudtower_ip = _resolve_cloudtower_ip(ctx.plan, parsed_plan, iso_cfg, stage_logger)
    deployment_plan.network = _resolve_network_plan(
        plan=ctx.plan,
        parsed_plan=parsed_plan,
        iso_cfg=iso_cfg,
        cloudtower_ip=deployment_plan.cloudtower_ip,
        stage_logger=stage_logger,
    )
    deployment_plan.vm = _build_vm_config(iso_cfg, upload_summary, stage_logger)
    deployment_plan.ssh = _build_ssh_config(ctx.plan, iso_cfg, stage_logger)

    stage_logger.debug(
        "组装 CloudTower 部署计划",
        progress_extra={
            "cloudtower_ip": deployment_plan.cloudtower_ip,
            "vm_name": deployment_plan.vm.vm_name,
            "vds_name": deployment_plan.network.vds_name,
            "vlan_id": deployment_plan.network.vlan_id,
        },
    )

    return deployment_plan


def _resolve_cloudtower_ip(
    plan: Optional[PlanModel],
    parsed_plan: Optional[Dict[str, Any]],
    iso_cfg: Dict[str, Any],
    stage_logger: LoggerAdapter,
) -> Optional[str]:
    """优先从规划表解析 CloudTower IP，若缺失则尝试读取配置覆盖。"""

    mgmt_info = getattr(plan, "mgmt", None) if plan else None
    if mgmt_info and getattr(mgmt_info, "Cloudtower_IP", None):
        ip_value = str(getattr(mgmt_info, "Cloudtower_IP"))
        stage_logger.debug("从规划表 mgmt 区域读取 CloudTower IP", progress_extra={"ip": ip_value})
        return ip_value

    if isinstance(parsed_plan, dict):
        mgmt_section = parsed_plan.get("mgmt", {})
        records = mgmt_section.get("records") if isinstance(mgmt_section, dict) else None
        if isinstance(records, list) and records:
            record = records[0]
            ip_value = record.get("Cloudtower IP") or record.get("cloudtower_ip")
            if ip_value:
                ip_str = str(ip_value)
                stage_logger.debug("从解析后的规划表字典读取 CloudTower IP", progress_extra={"ip": ip_str})
                return ip_str

    if isinstance(iso_cfg, dict):
        network_cfg = iso_cfg.get("network")
        if isinstance(network_cfg, dict):
            ip_override = network_cfg.get("ip") or network_cfg.get("ip_address")
            if ip_override:
                ip_str = str(ip_override)
                stage_logger.info(
                    "使用配置文件中的 CloudTower IP 覆盖",
                    progress_extra={"ip": ip_str},
                )
                return ip_str

    stage_logger.warning("未在规划表或配置中找到 CloudTower IP，将继续尝试后续步骤")
    return None


def _resolve_network_plan(
    *,
    plan: Optional[PlanModel],
    parsed_plan: Optional[Dict[str, Any]],
    iso_cfg: Dict[str, Any],
    cloudtower_ip: Optional[str],
    stage_logger: LoggerAdapter,
) -> CloudTowerNetworkPlan:
    """根据规划表与配置确定 CloudTower 管理网络的关键信息。"""

    network_plan = CloudTowerNetworkPlan()

    network_cfg = iso_cfg.get("network") if isinstance(iso_cfg, dict) else None
    if isinstance(network_cfg, dict):
        network_plan.vds_name = str(network_cfg.get("vds_name") or network_cfg.get("vds") or network_plan.vds_name)
        network_plan.vlan_name = network_cfg.get("vlan_name")
        network_plan.vlan_id = _safe_int(network_cfg.get("vlan_id"))
        network_plan.gateway = _safe_str(network_cfg.get("gateway"))
        network_plan.subnet_cidr = _safe_str(network_cfg.get("subnet") or network_cfg.get("subnet_cidr"))
        network_plan.subnet_mask = _safe_str(network_cfg.get("subnet_mask"))
        network_plan.ip_address = _safe_str(network_cfg.get("ip") or network_cfg.get("ip_address") or cloudtower_ip)

    if not network_plan.vds_name:
        derived = parsed_plan.get("_derived_network") if isinstance(parsed_plan, dict) else None
        records = derived.get("networks") if isinstance(derived, dict) else None
        selected = _pick_management_network(records, stage_logger)
        if selected:
            network_plan.vds_name = str(selected.get("vds") or network_plan.vds_name or "")
            network_plan.vlan_name = selected.get("name") or network_plan.vlan_name
            meta_raw = selected.get("metadata") if isinstance(selected, dict) else {}
            meta: Dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
            network_plan.vlan_id = network_plan.vlan_id or _safe_int(meta.get("vlan_id"))
            network_plan.gateway = network_plan.gateway or _safe_str(meta.get("gateway"))
            network_plan.subnet_cidr = network_plan.subnet_cidr or _safe_str(selected.get("subnetwork"))
            network_plan.ip_address = network_plan.ip_address or cloudtower_ip

    if network_plan.subnet_cidr and not network_plan.subnet_mask:
        try:
            subnet = ipaddress.ip_network(network_plan.subnet_cidr, strict=False)
            network_plan.subnet_mask = str(subnet.netmask)
        except ValueError as exc:  # noqa: BLE001
            stage_logger.warning(
                "无法从 CIDR 推导子网掩码，将继续使用默认值",
                progress_extra={"cidr": network_plan.subnet_cidr, "error": str(exc)},
            )

    stage_logger.debug(
        "解析得到的管理网络参数",
        progress_extra={
            "vds": network_plan.vds_name,
            "vlan_id": network_plan.vlan_id,
            "gateway": network_plan.gateway,
            "subnet": network_plan.subnet_cidr,
            "mask": network_plan.subnet_mask,
            "ip": network_plan.ip_address,
        },
    )

    return network_plan


def _build_vm_config(iso_cfg: Dict[str, Any], upload_summary: Dict[str, Any], stage_logger: LoggerAdapter) -> CloudTowerVMConfig:
    """生成 CloudTower 虚拟机硬件配置。"""

    vm_cfg = CloudTowerVMConfig()
    if isinstance(iso_cfg, dict):
        vm_cfg.vm_name = str(iso_cfg.get("vm_name") or vm_cfg.vm_name)
        vm_cfg.description = str(iso_cfg.get("vm_description") or vm_cfg.description)
        vm_cfg.storage_policy_name = str(
            iso_cfg.get("storage_policy") or iso_cfg.get("storage_policy_name") or vm_cfg.storage_policy_name
        )
    vm_cfg.cdrom_path = upload_summary.get("image_path") or vm_cfg.cdrom_path

    stage_logger.debug(
        "虚拟机配置",
        progress_extra={
            "vm_name": vm_cfg.vm_name,
            "description": vm_cfg.description,
            "storage_policy": vm_cfg.storage_policy_name,
        },
    )

    return vm_cfg


def _build_ssh_config(plan: Optional[PlanModel], iso_cfg: Dict[str, Any], stage_logger: LoggerAdapter) -> CloudTowerSSHConfig:
    """构建用于安装 CloudTower 服务的 SSH 登录配置。"""

    ssh_cfg = CloudTowerSSHConfig()
    if isinstance(iso_cfg, dict) and isinstance(iso_cfg.get("ssh"), dict):
        ssh_section = iso_cfg["ssh"]
        ssh_cfg.username = str(ssh_section.get("username") or ssh_cfg.username)
        ssh_cfg.password = str(ssh_section.get("password") or ssh_cfg.password)
        ssh_cfg.port = int(ssh_section.get("port") or ssh_cfg.port)
        ssh_cfg.timeout = int(ssh_section.get("timeout") or ssh_cfg.timeout)

    if plan and getattr(plan, "mgmt", None) and getattr(plan.mgmt, "root密码", None):
        # 若规划表提供 CloudTower root 密码，提示用户检查是否与 SSH 密码保持一致。
        stage_logger.debug(
            "规划表提供了 CloudTower root 密码",
            progress_extra={"root_password_length": len(str(getattr(plan.mgmt, "root密码")))},
        )

    stage_logger.debug(
        "SSH 配置",
        progress_extra={"username": ssh_cfg.username, "port": ssh_cfg.port, "timeout": ssh_cfg.timeout},
    )
    return ssh_cfg


def _safe_int(value: Any) -> Optional[int]:
    """尝试将值转换为整数，失败时返回 None。"""

    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> Optional[str]:
    """将值转换为字符串，若为空串则返回 None。"""

    if value is None:
        return None
    value_str = str(value).strip()
    return value_str or None


def _pick_management_network(
    records: Optional[Iterable[Dict[str, Any]]],
    stage_logger: LoggerAdapter,
) -> Optional[Dict[str, Any]]:
    """从派生网络列表中选择最符合管理网络特征的一项。"""

    if not records:
        return None

    candidates = list(records)
    for record in candidates:
        meta_raw = record.get("metadata") if isinstance(record, dict) else None
        meta: Dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
        name = str(record.get("name") or "").lower()
        net_type = str(meta.get("type") or "").lower()
        if any(key in name for key in ("mgmt", "cloudtower", "management")) or any(
            key in net_type for key in ("管理", "mgmt", "cloudtower")
        ):
            stage_logger.debug(
                "优先匹配到可能的管理网络",
                progress_extra={"network_name": record.get("name"), "metadata": meta},
            )
            return record

    stage_logger.debug("未找到显式管理网络，回退使用第一条网络记录")
    return candidates[0] if candidates else None


def _deploy_cloudtower_virtual_machine(
    *,
    ctx: RunContext,
    client: APIClient,
    headers: Dict[str, str],
    base_headers: Dict[str, str],
    deployment_plan: CloudTowerDeploymentPlan,
    stage_logger: LoggerAdapter,
) -> None:
    """通过 Fisheye API 创建 CloudTower 虚拟机并完成初始网络配置。"""

    stage_logger.info("开始创建 CloudTower 虚拟机", progress_extra={"vm_name": deployment_plan.vm.vm_name})

    storage_uuid = _query_storage_policy_uuid(
        ctx=ctx,
        client=client,
        headers=base_headers,
        policy_name=deployment_plan.vm.storage_policy_name,
        stage_logger=stage_logger,
    )
    deployment_plan.vm.storage_policy_uuid = storage_uuid

    vds_uuid, ovs_name = _resolve_vds_details(
        client=client,
        headers=base_headers,
        vds_name=deployment_plan.network.vds_name,
        stage_logger=stage_logger,
    )
    deployment_plan.network.vds_uuid = vds_uuid
    deployment_plan.network.ovs_name = ovs_name

    vlan_uuid = _resolve_vlan_uuid(
        client=client,
        headers=base_headers,
        network_plan=deployment_plan.network,
        stage_logger=stage_logger,
    )
    deployment_plan.network.vlan_uuid = vlan_uuid

    vm_uuid, job_id = _create_cloudtower_vm(
        client=client,
        headers=headers,
        deployment_plan=deployment_plan,
        stage_logger=stage_logger,
    )

    job_detail = _poll_cloudtower_job(
        client=client,
        headers=base_headers,
        job_id=job_id,
        description="创建 CloudTower 虚拟机",
        stage_logger=stage_logger,
    )
    deployment_plan.vm.vm_uuid = vm_uuid or _extract_vm_uuid_from_job(job_detail)

    vm_details = _wait_for_vm_guest_agent_ready(
        client=client,
        headers=base_headers,
        vm_uuid=deployment_plan.vm.vm_uuid,
        stage_logger=stage_logger,
    )
    if isinstance(vm_details, dict):
        guest_info = vm_details.get("guest_info") if isinstance(vm_details.get("guest_info"), dict) else {}
        os_version_raw = guest_info.get("os_version") if isinstance(guest_info, dict) else None
        if os_version_raw is None:
            os_version_raw = vm_details.get("os_version")
        if os_version_raw is None:
            os_version_raw = vm_details.get("guest_os_type") or vm_details.get("guest_os")
        os_version = str(os_version_raw).strip() if os_version_raw is not None else ""
        deployment_plan.vm.os_version = os_version or None
        ga_state_value = guest_info.get("ga_state") if isinstance(guest_info, dict) else None
        if ga_state_value is None:
            ga_state_value = vm_details.get("ga_state")
        deployment_plan.vm.guest_agent_state = str(ga_state_value or "") or None

    primary_mac = _fetch_vm_primary_mac(
        client=client,
        headers=base_headers,
        vm_uuid=deployment_plan.vm.vm_uuid,
        stage_logger=stage_logger,
        vm_info=vm_details,
    )

    network_job_id = _configure_vm_network_configuration(
        client=client,
        headers=headers,
        deployment_plan=deployment_plan,
        mac_address=primary_mac,
        stage_logger=stage_logger,
    )

    _poll_cloudtower_job(
        client=client,
        headers=base_headers,
        job_id=network_job_id,
        description="配置 CloudTower 网络",
        stage_logger=stage_logger,
    )

    stage_logger.info(
        "CloudTower 虚拟机创建与网络配置完成",
        progress_extra={"vm_uuid": deployment_plan.vm.vm_uuid, "mac": primary_mac},
    )


def _query_storage_policy_uuid(
    *,
    ctx: RunContext,
    client: APIClient,
    headers: Dict[str, str],
    policy_name: str,
    stage_logger: LoggerAdapter,
) -> str:
    """查询存储策略列表并返回指定名称的 UUID。

    若 Fisheye API 返回 401，将尝试使用规划表中的管理员账号刷新 token 后重试一次。
    """

    stage_logger.info("查询存储策略", progress_extra={"policy_name": policy_name})

    try:
        response = client.get(CLOUDTOWER_STORAGE_POLICIES_ENDPOINT, headers=headers)
    except APIError as exc:
        if "status=401" not in str(exc):
            raise

        stage_logger.warning(
            "Fisheye API 返回 401，尝试使用规划表凭证重新登录",
            progress_extra={"policy_name": policy_name},
        )
        if not _refresh_fisheye_token(
            ctx=ctx,
            client=client,
            headers=headers,
            stage_logger=stage_logger,
        ):
            raise
        response = client.get(CLOUDTOWER_STORAGE_POLICIES_ENDPOINT, headers=headers)

    policies = _extract_data_list(response)
    for policy in policies:
        name = str(policy.get("name") or "").strip()
        if name.lower() == policy_name.lower():
            uuid = policy.get("uuid") or policy.get("id")
            if not uuid:
                break
            stage_logger.debug(
                "匹配到存储策略",
                progress_extra={"policy_name": name, "uuid": uuid},
            )
            return str(uuid)

    if not policies:
        raise RuntimeError("存储策略列表为空，无法创建 CloudTower 虚拟机")

    fallback = policies[0]
    uuid = fallback.get("uuid") or fallback.get("id")
    if not uuid:
        raise RuntimeError("未能获取存储策略 UUID，请检查 Fisheye API 返回值")

    stage_logger.warning(
        "未找到指定名称的存储策略，回退使用第一条记录",
        progress_extra={"fallback_name": fallback.get("name"), "uuid": uuid},
    )
    return str(uuid)


def _refresh_fisheye_token(
    *,
    ctx: RunContext,
    client: APIClient,
    headers: Dict[str, str],
    stage_logger: LoggerAdapter,
) -> bool:
    """尝试使用规划表提供的 Fisheye 凭证刷新 token。

    返回 True 表示刷新成功并已更新 headers；False 表示刷新失败。
    """

    parsed_plan = ctx.extra.get('parsed_plan') if isinstance(ctx.extra, dict) else None
    username, password = _load_fisheye_credentials(ctx.plan, parsed_plan)
    payload = {
        "username": username or "root",
        "password": password or "HC!r0cks",
        "encrypted": False,
    }

    login_headers = dict(headers)
    login_headers.pop("x-smartx-token", None)
    login_headers["content-type"] = "application/json"

    try:
        response = client.post("/api/v3/sessions", payload, headers=login_headers)
    except Exception as exc:  # noqa: BLE001 - 记录并返回失败
        stage_logger.error(
            "刷新 Fisheye token 失败",
            progress_extra={"error": str(exc), "username": payload.get("username")},
        )
        return False

    token = _extract_api_token(response)
    if not token:
        stage_logger.error(
            "Fisheye 登录未返回有效 token",
            progress_extra={"username": payload.get("username")},
        )
        return False

    headers["x-smartx-token"] = token
    client.session.headers["x-smartx-token"] = token
    stage_logger.info(
        "已刷新 Fisheye token",
        progress_extra={"username": payload.get("username")},
    )
    return True


def _resolve_vds_details(
    *,
    client: APIClient,
    headers: Dict[str, str],
    vds_name: str,
    stage_logger: LoggerAdapter,
) -> Tuple[str, str]:
    """根据 VDS 名称获取其 UUID 与 OVS 名称。"""

    if not vds_name:
        raise RuntimeError("未提供 VDS 名称，无法定位管理网络")

    stage_logger.info("匹配管理网络 VDS", progress_extra={"vds_name": vds_name})
    response = client.get(CLOUDTOWER_VDS_ENDPOINT, headers=headers)
    vds_list = _extract_data_list(response)
    for vds in vds_list:
        name = str(vds.get("name") or "").strip()
        if name.lower() == vds_name.lower():
            uuid = vds.get("uuid") or vds.get("id")
            ovs_name = vds.get("ovsbr_name") or vds.get("ovs_name")
            if not uuid or not ovs_name:
                break
            stage_logger.debug(
                "找到目标 VDS",
                progress_extra={"uuid": uuid, "ovs_name": ovs_name},
            )
            return str(uuid), str(ovs_name)

    raise RuntimeError(f"未在 VDS 列表中找到名称为 {vds_name} 的记录，请确认规划表填写无误")


def _resolve_vlan_uuid(
    *,
    client: APIClient,
    headers: Dict[str, str],
    network_plan: CloudTowerNetworkPlan,
    stage_logger: LoggerAdapter,
) -> str:
    """查询指定 VDS 下的 VLAN 列表并返回目标 VLAN 的 UUID。"""

    if not network_plan.vds_uuid:
        raise RuntimeError("缺少 VDS UUID，无法查询 VLAN")

    stage_logger.info(
        "查询 VDS 对应的 VLAN",
        progress_extra={"vds_uuid": network_plan.vds_uuid, "vlan_id": network_plan.vlan_id, "vlan_name": network_plan.vlan_name},
    )
    path = CLOUDTOWER_VDS_VLANS_ENDPOINT.format(vds_uuid=network_plan.vds_uuid)
    response = client.get(path, headers=headers)
    vlan_list = _extract_data_list(response)
    for vlan in vlan_list:
        name = str(vlan.get("name") or "").strip()
        vlan_id = _safe_int(vlan.get("vlan_id"))
        if network_plan.vlan_uuid and str(vlan.get("uuid")) == network_plan.vlan_uuid:
            return str(vlan.get("uuid"))
        if network_plan.vlan_name and name.lower() == str(network_plan.vlan_name).lower():
            uuid = vlan.get("uuid") or vlan.get("id")
            if uuid:
                return str(uuid)
        if network_plan.vlan_id is not None and vlan_id == network_plan.vlan_id:
            uuid = vlan.get("uuid") or vlan.get("id")
            if uuid:
                return str(uuid)

    raise RuntimeError(
        "未在目标 VDS 下找到匹配的 VLAN，请检查规划表中的网络名称或 VLAN ID",
    )


def _create_cloudtower_vm(
    *,
    client: APIClient,
    headers: Dict[str, str],
    deployment_plan: CloudTowerDeploymentPlan,
    stage_logger: LoggerAdapter,
) -> Tuple[Optional[str], str]:
    """提交创建 CloudTower 虚拟机的请求，返回（vm_uuid, job_id）。"""

    if not deployment_plan.network.ovs_name or not deployment_plan.network.vlan_uuid:
        raise RuntimeError("缺少 OVS 或 VLAN UUID，无法创建 CloudTower 虚拟机")
    if not deployment_plan.vm.storage_policy_uuid:
        raise RuntimeError("缺少存储策略 UUID，无法创建 CloudTower 虚拟机")

    payload = {
        "vm_name": deployment_plan.vm.vm_name,
        "description": deployment_plan.vm.description,
        "vcpu": deployment_plan.vm.vcpu,
        "memory": deployment_plan.vm.memory_bytes,
        "cpu": {
            "topology": {
                "sockets": deployment_plan.vm.cpu_sockets,
                "cores": deployment_plan.vm.cpu_cores,
            }
        },
        "nics": [
            {
                "ovs": deployment_plan.network.ovs_name,
                "model": "virtio",
                "mirror": False,
                "vlan_uuid": deployment_plan.network.vlan_uuid,
                "link": "up",
            }
        ],
        "disks": [
            {
                "type": "disk",
                "bus": "virtio",
                "storage_policy_uuid": deployment_plan.vm.storage_policy_uuid,
                "name": "cloudtower-os",
                "quota_policy": None,
                "size_in_byte": deployment_plan.vm.os_disk_size_bytes,
            }
        ],
        "ha": True,
        "nested_virtualization": False,
        "hasNormalVol": False,
        "hasSharedVol": False,
        "hasVolume": False,
        "cpu_model": "cluster_default",
        "firmware": "BIOS",
        "diskNamePrefix": "cloudtower",
        "folder_uuid": None,
        "node_ip": None,
        "auto_schedule": True,
        "quota_policy": None,
        "status": "running",
    }

    if deployment_plan.vm.cdrom_path:
        payload.setdefault("disks", []).append(
            {
                "type": "cdrom",
                "bus": "ide",
                "path": deployment_plan.vm.cdrom_path,
                "disabled": False,
            }
        )

    stage_logger.info("提交 CloudTower 虚拟机创建请求", progress_extra={"payload_keys": sorted(payload.keys())})
    response = client.post(CLOUDTOWER_VM_ENDPOINT, payload, headers=headers)
    job_id = _extract_job_id(response)
    vm_uuid = _extract_vm_uuid_from_response(response)
    if not job_id:
        raise RuntimeError("创建 CloudTower 虚拟机接口未返回 job_id")
    stage_logger.debug("创建虚拟机返回信息", progress_extra={"job_id": job_id, "vm_uuid": vm_uuid})
    return vm_uuid, job_id


def _extract_vm_uuid_from_response(response: Dict[str, Any]) -> Optional[str]:
    """尝试从创建虚拟机的响应中提取 vm_uuid。"""

    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, dict):
        vm = data.get("vm")
        if isinstance(vm, dict) and vm.get("uuid"):
            return str(vm.get("uuid"))
    return None


def _extract_job_id(response: Dict[str, Any]) -> Optional[str]:
    """从 API 响应中提取 job_id。"""

    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, dict) and data.get("job_id"):
        return str(data.get("job_id"))
    if response.get("job_id"):
        return str(response.get("job_id"))
    return None


def _poll_cloudtower_job(
    *,
    client: APIClient,
    headers: Dict[str, str],
    job_id: str,
    description: str,
    stage_logger: LoggerAdapter,
    interval: int = 5,
    timeout: int = 20 * 60,
) -> Dict[str, Any]:
    """轮询 CloudTower 后端任务直至成功或超时。"""

    stage_logger.info("开始轮询任务状态", progress_extra={"job_id": job_id, "description": description})
    deadline = time.monotonic() + timeout
    last_state: Optional[str] = None

    while time.monotonic() < deadline:
        response = client.get(CLOUDTOWER_JOB_ENDPOINT.format(job_id=job_id), headers=headers)
        job = _extract_job_object(response)
        state = str(job.get("state") or "").lower()
        if state != last_state:
            stage_logger.debug(
                "任务状态更新",
                progress_extra={"job_id": job_id, "state": state, "description": description},
            )
            last_state = state
        if state in {"done", "success", "succeed", "finished"}:
            stage_logger.info("任务已完成", progress_extra={"job_id": job_id, "description": description})
            return job
        if state in {"failed", "error", "aborted"}:
            detail = job.get("error") or job.get("message") or job
            raise RuntimeError(f"{description}失败: {detail}")
        time.sleep(interval)

    raise RuntimeError(f"{description}超时，超时时长 {timeout} 秒")


def _extract_job_object(response: Dict[str, Any]) -> Dict[str, Any]:
    """从任务查询响应中抽取 job 字段。"""

    if not isinstance(response, dict):
        return {}
    data = response.get("data")
    if isinstance(data, dict) and isinstance(data.get("job"), dict):
        return data["job"]
    if isinstance(response.get("job"), dict):
        return response["job"]
    return {}


def _extract_vm_uuid_from_job(job_detail: Dict[str, Any]) -> Optional[str]:
    """从任务详情中解析出新建虚拟机的 UUID。"""

    if not isinstance(job_detail, dict):
        return None
    resources = job_detail.get("resources")
    if isinstance(resources, dict):
        for value in resources.values():
            if isinstance(value, dict) and value.get("uuid"):
                return str(value.get("uuid"))
    return None


def _extract_vm_info(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从虚拟机详情响应中提取 vm 对象。"""

    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, dict):
        vm_info = data.get("vm")
        if isinstance(vm_info, dict):
            return vm_info
        return data if isinstance(data, dict) else None
    return None


def _wait_for_vm_guest_agent_ready(
    *,
    client: APIClient,
    headers: Dict[str, str],
    vm_uuid: Optional[str],
    stage_logger: LoggerAdapter,
    interval: int = CLOUDTOWER_VM_READY_INTERVAL,
    timeout: int = CLOUDTOWER_VM_READY_TIMEOUT,
) -> Dict[str, Any]:
    """轮询虚拟机详情直至 os_version 判定完成且 VMTools 运行。"""

    if not vm_uuid:
        raise RuntimeError("缺少 CloudTower 虚拟机 UUID，无法等待操作系统就绪")

    stage_logger.info(
        "等待 CloudTower 虚拟机操作系统就绪",
        progress_extra={"vm_uuid": vm_uuid, "timeout": timeout},
    )

    deadline = time.monotonic() + timeout
    last_status: tuple[Optional[str], Optional[str]] = (None, None)

    while time.monotonic() < deadline:
        response = client.get(CLOUDTOWER_VM_DETAIL_ENDPOINT.format(vm_uuid=vm_uuid), headers=headers)
        vm_info = _extract_vm_info(response)
        if not isinstance(vm_info, dict):
            stage_logger.debug(
                "虚拟机详情返回格式异常，继续等待",
                progress_extra={"vm_uuid": vm_uuid},
            )
            time.sleep(interval)
            continue

        guest_info = vm_info.get("guest_info") if isinstance(vm_info.get("guest_info"), dict) else {}
        os_version_raw = guest_info.get("os_version") if isinstance(guest_info, dict) else None
        if os_version_raw is None:
            os_version_raw = vm_info.get("os_version")
        if os_version_raw is None:
            os_version_raw = vm_info.get("guest_os_type") or vm_info.get("guest_os")
        os_version = str(os_version_raw).strip() if os_version_raw is not None else ""

        ga_state_raw = guest_info.get("ga_state") if isinstance(guest_info, dict) else None
        if ga_state_raw is None:
            ga_state_raw = vm_info.get("ga_state")
        ga_version_raw = guest_info.get("ga_version") if isinstance(guest_info, dict) else None
        if ga_version_raw is None:
            ga_version_raw = vm_info.get("ga_version")

        ga_state = str(ga_state_raw).strip() if ga_state_raw is not None else ""
        ga_version = str(ga_version_raw).strip() if ga_version_raw is not None else ""

        normalized_ga = ga_state.lower()

        if normalized_ga == "running":
            stage_logger.info(
                "虚拟机操作系统已就绪",
                progress_extra={
                    "vm_uuid": vm_uuid,
                    "os_version": os_version,
                    "ga_state": ga_state,
                    "ga_version": ga_version or None,
                },
            )
            return vm_info

        status_key = (os_version or None, normalized_ga or None)
        if status_key != last_status:
            stage_logger.debug(
                "等待虚拟机操作系统就绪",
                progress_extra={
                    "vm_uuid": vm_uuid,
                    "os_version": os_version or None,
                    "ga_state": ga_state or None,
                    "ga_version": ga_version or None,
                },
            )
            last_status = status_key

        time.sleep(interval)

    raise RuntimeError("等待 CloudTower 虚拟机操作系统就绪超时")


def _fetch_vm_primary_mac(
    *,
    client: APIClient,
    headers: Dict[str, str],
    vm_uuid: Optional[str],
    stage_logger: LoggerAdapter,
    vm_info: Optional[Dict[str, Any]] = None,
) -> str:
    """查询虚拟机详情并返回首个网卡的 MAC 地址。"""

    if not vm_uuid:
        raise RuntimeError("缺少 CloudTower 虚拟机 UUID，无法配置网络")

    if vm_info is None:
        response = client.get(CLOUDTOWER_VM_DETAIL_ENDPOINT.format(vm_uuid=vm_uuid), headers=headers)
        vm_info = _extract_vm_info(response)
    if not isinstance(vm_info, dict):
        raise RuntimeError("查询虚拟机详情失败，返回数据格式不正确")

    nics = vm_info.get("nics") if isinstance(vm_info.get("nics"), list) else vm_info.get("interfaces")
    if not isinstance(nics, list) or not nics:
        raise RuntimeError("虚拟机详情未包含网卡信息")

    nic = nics[0]
    mac = nic.get("mac_address") or nic.get("mac")
    if not mac:
        raise RuntimeError("未能找到虚拟机网卡的 MAC 地址")

    stage_logger.debug("获取到虚拟机 MAC", progress_extra={"vm_uuid": vm_uuid, "mac": mac})
    return str(mac)


def _configure_vm_network_configuration(
    *,
    client: APIClient,
    headers: Dict[str, str],
    deployment_plan: CloudTowerDeploymentPlan,
    mac_address: str,
    stage_logger: LoggerAdapter,
) -> str:
    """通过虚拟机更新接口下发 CloudTower 管理网配置。"""

    network = deployment_plan.network
    if not network.vlan_uuid or not network.ovs_name:
        raise RuntimeError("缺少 VLAN/OVS 信息，无法执行网络配置")
    if not network.ip_address or not network.gateway or not network.subnet_mask:
        raise RuntimeError("管理网络的 IP、网关或子网掩码缺失，请检查规划表")

    payload = {
        "nics": [
            {
                "vlan_uuid": network.vlan_uuid,
                "ovs": network.ovs_name,
                "model": "virtio",
                "mac_address": mac_address,
                "mirror": False,
                "gateway": network.gateway,
                "subnet_mask": network.subnet_mask,
                "ip_address": network.ip_address,
                "link": "up",
            }
        ]
    }

    stage_logger.info(
        "通过虚拟机更新接口配置 CloudTower 网络",
        progress_extra={"vm_uuid": deployment_plan.vm.vm_uuid, "payload": payload["nics"][0]},
    )
    path = CLOUDTOWER_VM_DETAIL_ENDPOINT.format(vm_uuid=deployment_plan.vm.vm_uuid)
    response = client.put(path, payload, headers=headers)
    job_id = _extract_job_id(response)
    if not job_id:
        raise RuntimeError("配置 CloudTower 网络未返回 job_id")
    return job_id


def _extract_data_list(response: Any) -> List[Dict[str, Any]]:
    """将 API 响应归一化为字典列表。"""

    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            preferred_keys = ("items", "list", "records", "results", "images")
            for key in preferred_keys:
                candidate = data.get(key)
                if isinstance(candidate, list):
                    return [item for item in candidate if isinstance(item, dict)]
            for value in data.values():
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
    return []


def _install_and_verify_cloudtower_services(
    *,
    deployment_plan: CloudTowerDeploymentPlan,
    stage_logger: LoggerAdapter,
) -> None:
    """通过 SSH 执行 CloudTower 安装脚本并验证服务可用性。"""

    target_ip = deployment_plan.cloudtower_ip or deployment_plan.network.ip_address
    if not target_ip:
        stage_logger.warning("缺少 CloudTower IP，跳过服务部署阶段")
        return

    stage_logger.info(
        "准备通过 SSH 部署 CloudTower 服务",
        progress_extra={"ip": target_ip, "ssh_user": deployment_plan.ssh.username, "ssh_port": deployment_plan.ssh.port},
    )

    ssh_client = None
    log_ssh_client = None
    monitor_executor: Optional[ThreadPoolExecutor] = None
    monitor_future = None
    monitor_completed = False
    install_exception: Optional[BaseException] = None
    try:
        ssh_client = _create_ssh_client_and_connect(
            target_ip,
            port=deployment_plan.ssh.port,
            username=deployment_plan.ssh.username,
            password=deployment_plan.ssh.password,
            timeout=deployment_plan.ssh.timeout,
        )
        stage_logger.debug("SSH 连接成功", progress_extra={"ip": target_ip})

        log_ssh_client = _create_ssh_client_and_connect(
            target_ip,
            port=deployment_plan.ssh.port,
            username=deployment_plan.ssh.username,
            password=deployment_plan.ssh.password,
            timeout=deployment_plan.ssh.timeout,
        )
        stage_logger.debug("日志监控 SSH 连接就绪", progress_extra={"ip": target_ip})

        monitor_executor = ThreadPoolExecutor(max_workers=1)
        monitor_future = monitor_executor.submit(
            _wait_for_installation_success,
            ssh_client=log_ssh_client,
            ssh_config=deployment_plan.ssh,
            stage_logger=stage_logger,
        )

        _run_sudo_command(
            ssh_client=ssh_client,
            ssh_config=deployment_plan.ssh,
            command="touch /etc/resolv.conf",
            description="创建 DNS 解析文件",
            stage_logger=stage_logger,
        )

        _run_sudo_command(
            ssh_client=ssh_client,
            ssh_config=deployment_plan.ssh,
            command="sh /usr/share/smartx/tower/preinstall.sh",
            description="执行 CloudTower 预安装脚本",
            stage_logger=stage_logger,
        )

        _run_sudo_command(
            ssh_client=ssh_client,
            ssh_config=deployment_plan.ssh,
            command="/usr/share/smartx/tower/installer/binary/installer deploy >> /home/cloudtower/installer.out",
            description="启动 CloudTower 安装程序，请等待完成",
            stage_logger=stage_logger,
            background=True,
        )

        if monitor_future is not None:
            monitor_future.result()
            monitor_completed = True
    except Exception as exc:
        install_exception = exc
        raise
    finally:
        if monitor_future is not None and not monitor_completed:
            if log_ssh_client is not None:
                try:
                    log_ssh_client.close()
                except Exception:  # noqa: BLE001
                    pass
                log_ssh_client = None
            try:
                monitor_future.result()
            except Exception as monitor_exc:
                if install_exception is None:
                    raise monitor_exc
        if monitor_executor is not None:
            monitor_executor.shutdown(wait=False)
        if log_ssh_client is not None:
            try:
                log_ssh_client.close()
            except Exception:  # noqa: BLE001
                pass
        if ssh_client is not None:
            try:
                ssh_client.close()
            except Exception:  # noqa: BLE001 - 关闭连接失败无需中断流程
                pass

    _verify_cloudtower_https_port(
        ip=target_ip,
        stage_logger=stage_logger,
    )


def _create_ssh_client_and_connect(
    host: str,
    *,
    port: int,
    username: str,
    password: str,
    timeout: int,
) -> Any:
    try:
        paramiko = importlib.import_module("paramiko")
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("缺少 paramiko 依赖，请先安装后重试：pip install paramiko") from exc

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(host, port=port, username=username, password=password, timeout=timeout)
    transport = ssh_client.get_transport()
    if transport is not None:
        transport.set_keepalive(CLOUDTOWER_SSH_KEEPALIVE_INTERVAL)
    return ssh_client


def _wrap_with_bash(command: str) -> str:
    """使用 bash -lc 包装命令，确保远程执行在 bash 解释器中进行。"""

    return f"bash -lc {shlex.quote(command)}"


def _clean_stderr_noise(stderr_data: str) -> str:
    """过滤已知的噪声输出，例如 system-info.sh 缺少 bc 的提示。"""

    if not stderr_data:
        return stderr_data
    noisy_prefixes = (
        "/etc/profile.d/system-info.sh:",
    )
    cleaned_lines = []
    for line in stderr_data.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(prefix) and "bc: command not found" in stripped for prefix in noisy_prefixes):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _run_sudo_command(
    *,
    ssh_client,
    ssh_config: CloudTowerSSHConfig,
    command: str,
    description: str,
    stage_logger: LoggerAdapter,
    background: bool = False,
) -> None:
    """在远程主机上执行带 sudo 的命令，可用于后台任务。"""

    full_command = f"sudo -S {command}"
    stage_logger.info(description, progress_extra={"command": command})
    stdin, stdout, stderr = ssh_client.exec_command(_wrap_with_bash(full_command), get_pty=True)
    if ssh_config.password:
        stdin.write(f"{ssh_config.password}\n")
        stdin.flush()
    if not stdin.channel.closed:
        stdin.channel.shutdown_write()

    stdout_data = stdout.read().decode('utf-8', 'ignore').strip()
    stderr_data = stderr.read().decode('utf-8', 'ignore').strip()
    stderr_data = _clean_stderr_noise(stderr_data)
    exit_status = stdout.channel.recv_exit_status()

    if exit_status != 0:
        raise RuntimeError(f"{description}失败: {stderr_data or stdout_data or exit_status}")

    if stdout_data:
        stage_logger.debug(
            f"{description}输出",
            progress_extra={"stdout": stdout_data.splitlines()[-5:]},
        )
    if stderr_data:
        stage_logger.warning(
            f"{description}产生警告",
            progress_extra={"stderr": stderr_data.splitlines()[-5:]},
        )

    if background:
        stage_logger.debug("后台命令已提交", progress_extra={"command": command})


def _wait_for_installation_success(
    *,
    ssh_client,
    ssh_config: CloudTowerSSHConfig,
    stage_logger: LoggerAdapter,
) -> None:
    """轮询远程 installer.out 日志，等待安装成功提示。"""

    start_time = time.monotonic()
    deadline = start_time + CLOUDTOWER_INSTALL_TIMEOUT
    grace_period = CLOUDTOWER_LOG_GRACE_PERIOD
    success_token = CLOUDTOWER_INSTALL_SUCCESS_TOKEN
    last_excerpt: Optional[List[str]] = None

    stage_logger.info(
        "开始监控 CloudTower 安装日志",
        progress_extra={"timeout": CLOUDTOWER_INSTALL_TIMEOUT, "interval": CLOUDTOWER_LOG_CHECK_INTERVAL},
    )

    while time.monotonic() < deadline:
        exists, success, excerpt = _fetch_installer_status(
            ssh_client=ssh_client,
            ssh_config=ssh_config,
            stage_logger=stage_logger,
            success_token=success_token,
        )
        elapsed = int(time.monotonic() - start_time)
        if exists and excerpt:
            if last_excerpt != excerpt:
                stage_logger.debug(
                    "最新 installer.out 片段",
                    progress_extra={"elapsed": elapsed, "lines": excerpt[-5:]},
                )
                last_excerpt = excerpt
        elif not exists and elapsed < grace_period:
            stage_logger.debug(
                "日志文件尚未生成，属于预期",
                progress_extra={"elapsed": elapsed, "grace_period": grace_period},
            )
        elif not exists:
            stage_logger.warning(
                "仍未检测到 installer.out，继续等待",
                progress_extra={"elapsed": elapsed},
            )

        if success:
            stage_logger.info(
                "检测到 CloudTower 安装成功标识",
                progress_extra={"elapsed": elapsed, "token": success_token},
            )
            return

        time.sleep(CLOUDTOWER_LOG_CHECK_INTERVAL)

    raise RuntimeError("CloudTower 部署超时：在预设时间内未检测到成功标识")


def _fetch_installer_status(
    *,
    ssh_client,
    ssh_config: CloudTowerSSHConfig,
    stage_logger: LoggerAdapter,
    success_token: str,
) -> Tuple[bool, bool, List[str]]:
    """获取 installer.out 状态：是否存在、是否包含成功关键字以及最近日志。"""

    log_path = f"/home/cloudtower/installer.out"
    command = f"if [ -f {log_path} ]; then tail -n 50 {log_path}; else echo __CXV_NO_FILE__ ; fi"
    stdin, stdout, stderr = ssh_client.exec_command(_wrap_with_bash(command))
    stdout_data = stdout.read().decode('utf-8', 'ignore')
    stderr_data = stderr.read().decode('utf-8', 'ignore')
    if stderr_data:
        stage_logger.debug("读取 installer.out 警告", progress_extra={"stderr": stderr_data.splitlines()[-5:]})

    if "__CXV_NO_FILE__" in stdout_data:
        return False, False, []

    lines = [line for line in stdout_data.splitlines() if line.strip()]
    success = any(success_token in line for line in lines)
    return True, success, lines


def _verify_cloudtower_https_port(*, ip: str, stage_logger: LoggerAdapter) -> None:
    """检测 CloudTower 443 端口是否可访问，支持重试。"""

    stage_logger.info(
        "验证 CloudTower HTTPS 端口连通性",
        progress_extra={"ip": ip, "port": CLOUDTOWER_HTTPS_PORT, "retries": CLOUDTOWER_PORT_RETRY},
    )

    for attempt in range(1, CLOUDTOWER_PORT_RETRY + 1):
        reachable = check_port(ip, CLOUDTOWER_HTTPS_PORT, timeout=5.0)
        if reachable:
            stage_logger.info("443 端口可达，CloudTower 服务已就绪", progress_extra={"attempt": attempt})
            return
        stage_logger.warning(
            "443 端口暂不可达，稍后重试",
            progress_extra={"attempt": attempt, "wait": CLOUDTOWER_PORT_RETRY_INTERVAL},
        )
        time.sleep(CLOUDTOWER_PORT_RETRY_INTERVAL)

    raise RuntimeError("多次检测 CloudTower 443 端口失败，请人工检查服务状态")


def _configure_cloudtower_post_install(
    *,
    ctx: RunContext,
    deployment_plan: CloudTowerDeploymentPlan,
    config_data: Dict[str, Any],
    parsed_plan: Any,
    timeout: int,
    use_mock: bool,
    stage_logger: LoggerAdapter,
) -> Dict[str, Any]:
    """在 CloudTower 服务部署完成后执行初始配置，包括创建 root 用户、组织与基础参数设置。"""

    cloudtower_ip = deployment_plan.cloudtower_ip or deployment_plan.network.ip_address
    if not cloudtower_ip:
        stage_logger.warning("缺少 CloudTower IP，无法执行后续初始化配置")
        return {}

    inputs = _resolve_cloudtower_setup_inputs(
        plan=ctx.plan,
        parsed_plan=parsed_plan,
        config_data=config_data,
        stage_logger=stage_logger,
    )
    masked_inputs = asdict(inputs)
    if masked_inputs.get("cluster_password"):
        masked_inputs["cluster_password"] = "***"
    stage_logger.debug(
        "CloudTower 初始化参数",
        progress_extra={"cloudtower_ip": cloudtower_ip, "inputs": masked_inputs},
    )

    if use_mock:
        stage_logger.info("Mock 模式跳过 CloudTower 后续配置", progress_extra={"cloudtower_ip": cloudtower_ip})
        result = asdict(inputs)
        return {
            "mode": "mock",
            "inputs": result,
            "session": {"token": "mock-token", "username": "root"},
        }

    stage_logger.info(
        "开始执行 CloudTower 初始化配置",
        progress_extra={"cloudtower_ip": cloudtower_ip, "organization": inputs.organization_name},
    )
    client = APIClient(
        base_url=f"https://{cloudtower_ip}",
        mock=False,
        timeout=timeout,
        verify=False,  # CloudTower 默认使用自签名证书
    )

    _cloudtower_create_root_user(client=client, stage_logger=stage_logger)
    organization_info = _cloudtower_create_organization(
        client=client,
        stage_logger=stage_logger,
        organization_name=inputs.organization_name,
    )
    setup_status = _cloudtower_check_setup(client=client, stage_logger=stage_logger)

    login_token = _cloudtower_login(
        client=client,
        ip=cloudtower_ip,
        stage_logger=stage_logger,
    )
    client.session.headers["Authorization"] = login_token

    if inputs.ntp_servers:
        _cloudtower_update_ntp(
            client=client,
            stage_logger=stage_logger,
            servers=inputs.ntp_servers,
        )
    if inputs.dns_servers:
        _update_cloudtower_dns_via_ssh(
            deployment_plan=deployment_plan,
            dns_servers=inputs.dns_servers,
            stage_logger=stage_logger,
        )

    license_info = _cloudtower_query_license(client=client, stage_logger=stage_logger)

    serial = license_info.get("license_serial") if isinstance(license_info, dict) else None
    plan_updates: Dict[str, Any] = {}
    if serial:
        plan_path = _resolve_plan_path_for_write(ctx)
        if plan_path:
            try:
                _write_cloudtower_serial_to_plan(plan_path, serial)
            except Exception as exc:  # noqa: BLE001
                stage_logger.warning(
                    "写入 CloudTower 序列号到规划表失败",
                    progress_extra={"path": str(plan_path), "error": str(exc)},
                )
                plan_updates["cloudtower_serial"] = {"status": "failed", "error": str(exc)}
            else:
                stage_logger.info(
                    "已在规划表写入 CloudTower 序列号",
                    progress_extra={
                        "path": plan_path.name,
                        "cell": plan_vars.CLOUDTOWER_SERIAL.cell,
                        "serial": serial,
                    },
                )
                plan_updates["cloudtower_serial"] = {"status": "ok", "path": str(plan_path)}
        else:
            stage_logger.warning("未找到规划表路径，CloudTower 序列号未写入规划表")

    result = {
        "organization": {
            "id": organization_info.get("id") if isinstance(organization_info, dict) else None,
            "name": inputs.organization_name,
        },
        "session": {"token": login_token, "username": "root"},
        "inputs": asdict(inputs),
        "ntp": {"servers": inputs.ntp_servers},
        "dns": {"servers": inputs.dns_servers},
        "license": license_info,
    }
    if plan_updates:
        result["plan_updates"] = plan_updates
    if setup_status:
        result["setup_status"] = setup_status

    stage_logger.info(
        "CloudTower 初始化配置完成",
        progress_extra={
            "organization_id": result["organization"]["id"],
            "datacenter_name": inputs.datacenter_name,
            "ntp_servers": inputs.ntp_servers,
            "dns_servers": inputs.dns_servers,
        },
    )

    return result


def _resolve_cloudtower_setup_inputs(
    *,
    plan: Optional[PlanModel],
    parsed_plan: Any,
    config_data: Dict[str, Any],
    stage_logger: LoggerAdapter,
) -> CloudTowerSetupInputs:
    """综合规划表与配置项，推导 CloudTower 初始化所需参数。"""

    cloud_cfg = dict(config_data.get("cloudtower", {}) or {})

    mgmt_model = getattr(plan, "mgmt", None)
    organization_name = (
        getattr(mgmt_model, "Cloudtower组织名称", None)
        or _extract_mgmt_value(parsed_plan, "Cloudtower 组织名称")
        or cloud_cfg.get("organization_name")
        or CLOUDTOWER_DEFAULT_ORGANIZATION_NAME
    )

    datacenter_name = (
        getattr(mgmt_model, "Cloudtower数据中心名称", None)
        or _extract_mgmt_value(parsed_plan, "Cloudtower 数据中心名称")
        or cloud_cfg.get("datacenter_name")
        or f"{organization_name}-DC"
    )

    ntp_servers = _normalize_server_list(
        _extract_mgmt_value(parsed_plan, "NTP 服务器")
        or cloud_cfg.get("ntp_servers")
    )
    dns_servers = _normalize_server_list(
        _extract_mgmt_value(parsed_plan, "DNS 服务器")
        or cloud_cfg.get("dns_servers")
    )

    cluster_vip = cloud_cfg.get("cluster_vip") or _extract_cluster_management_vip(plan, parsed_plan)
    cluster_creds = _extract_cluster_credentials(parsed_plan, cloud_cfg)

    if not cluster_vip:
        stage_logger.warning("未能从规划表解析集群 VIP，将在后续步骤中提示用户补充")

    return CloudTowerSetupInputs(
        organization_name=str(organization_name).strip() if organization_name else CLOUDTOWER_DEFAULT_ORGANIZATION_NAME,
        datacenter_name=str(datacenter_name).strip() if datacenter_name else CLOUDTOWER_DEFAULT_DATACENTER_NAME,
        ntp_servers=ntp_servers,
        dns_servers=dns_servers,
        cluster_vip=cluster_vip,
        cluster_username=cluster_creds["username"],
        cluster_password=cluster_creds["password"],
    )


def _extract_mgmt_value(parsed_plan: Any, key: str) -> Any:
    if not isinstance(parsed_plan, dict):
        return None
    mgmt = parsed_plan.get("mgmt")
    if not isinstance(mgmt, dict):
        return None
    records = mgmt.get("records")
    if not isinstance(records, list) or not records:
        return None
    first = records[0]
    if isinstance(first, dict):
        return first.get(key)
    return None


def _extract_cluster_credentials(parsed_plan: Any, cloud_cfg: Dict[str, Any]) -> Dict[str, str]:
    default_user = cloud_cfg.get("cluster_username") or "root"
    default_password = cloud_cfg.get("cluster_password") or "HC!r0cks"

    if isinstance(parsed_plan, dict):
        hosts = parsed_plan.get("hosts")
        if isinstance(hosts, dict):
            extra = hosts.get("extra")
            if isinstance(extra, dict):
                user = extra.get("fisheye_admin_user") or default_user
                password = extra.get("fisheye_admin_password") or default_password
                return {"username": str(user).strip(), "password": str(password).strip()}

    return {"username": str(default_user).strip(), "password": str(default_password).strip()}


def _normalize_server_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        values = list(raw)
    elif isinstance(raw, str):
        values = [item.strip() for item in raw.replace(";", ",").split(",")]
    else:
        values = [str(raw).strip()]
    return [item for item in values if item]


def _cloudtower_create_root_user(*, client: APIClient, stage_logger: LoggerAdapter) -> None:
    now_iso = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(timespec="milliseconds")
    payload = {
        "operationName": "createRootUser",
        "variables": {
            "root_password": CLOUDTOWER_ROOT_PASSWORD_ENCODED,
            "now": now_iso,
        },
        "query": CLOUDTOWER_GQL_CREATE_ROOT,
    }
    data = _post_cloudtower_graphql(
        client=client,
        payload=payload,
        stage_logger=stage_logger,
        description="创建 CloudTower 管理员 root 用户",
        ignore_messages=("already exists", "UserAlreadyExists"),
    )
    if data:
        stage_logger.debug("CloudTower root 用户创建返回", progress_extra={"keys": list(data.keys())})


def _cloudtower_create_organization(
    *,
    client: APIClient,
    stage_logger: LoggerAdapter,
    organization_name: str,
) -> Dict[str, Any]:
    payload = {
        "operationName": "createOrganization",
        "variables": {"data": {"name": organization_name}},
        "query": CLOUDTOWER_GQL_CREATE_ORGANIZATION,
    }
    data = _post_cloudtower_graphql(
        client=client,
        payload=payload,
        stage_logger=stage_logger,
        description="创建 CloudTower 组织",
        ignore_messages=("already exists", "Duplicate"),
    )
    org = (data or {}).get("createOrganization") if isinstance(data, dict) else None
    stage_logger.info(
        "CloudTower 组织已就绪",
        progress_extra={"organization_name": organization_name, "organization_id": org.get("id") if isinstance(org, dict) else None},
    )
    return org or {}


def _cloudtower_check_setup(*, client: APIClient, stage_logger: LoggerAdapter) -> Dict[str, Any]:
    payload = {"operationName": "checkTowerIsSetup", "variables": {}, "query": CLOUDTOWER_GQL_CHECK_SETUP}
    data = _post_cloudtower_graphql(
        client=client,
        payload=payload,
        stage_logger=stage_logger,
        description="验证 CloudTower 初始化状态",
        ignore_messages=(),
    )
    if data:
        stage_logger.debug("CloudTower 初始化状态", progress_extra={"keys": list(data.keys())})
    return data or {}


def _cloudtower_login(
    *,
    client: APIClient,
    ip: str,
    stage_logger: LoggerAdapter,
    username: str = "root",
    password: str = "HC!r0cks",
) -> str:
    payload = {
        "username": username,
        "source": "LOCAL",
        "password": password,
    }
    response = client.post(
        f"http://{ip}{CLOUDTOWER_LOGIN_ENDPOINT}",
        payload=payload,
        headers={"content-type": "application/json"},
    )
    token: Optional[str] = None
    if isinstance(response, dict):
        data = response.get("data") if isinstance(response.get("data"), dict) else None
        if isinstance(data, dict) and data.get("token"):
            token = str(data.get("token"))
        elif response.get("token"):
            token = str(response.get("token"))
    if not token:
        raise RuntimeError("CloudTower 登录未返回 token")
    stage_logger.info("已获取 CloudTower 会话 token")
    return token


def _cloudtower_update_ntp(*, client: APIClient, stage_logger: LoggerAdapter, servers: List[str]) -> None:
    joined = ",".join(servers)
    payload = {
        "operationName": "updateCloudTowerNtpUrl",
        "variables": {"data": {"ntp_service_url": joined}},
        "query": CLOUDTOWER_GQL_UPDATE_NTP,
    }
    data = _post_cloudtower_graphql(
        client=client,
        payload=payload,
        stage_logger=stage_logger,
        description="配置 CloudTower NTP",
        ignore_messages=(),
    )
    stage_logger.info("已更新 CloudTower NTP 配置", progress_extra={"servers": servers, "response": data})


def _cloudtower_query_license(*, client: APIClient, stage_logger: LoggerAdapter) -> Dict[str, Any]:
    payload = {"operationName": "deployedLicense", "variables": {}, "query": CLOUDTOWER_GQL_DEPLOYED_LICENSE}
    data = _post_cloudtower_graphql(
        client=client,
        payload=payload,
        stage_logger=stage_logger,
        description="查询 CloudTower 许可证",
        ignore_messages=(),
    )
    deploys = (data or {}).get("deploys") if isinstance(data, dict) else None
    if isinstance(deploys, list) and deploys:
        license_info = deploys[0].get("license") if isinstance(deploys[0], dict) else None
        if isinstance(license_info, dict):
            stage_logger.info(
                "已获取 CloudTower 许可证信息",
                progress_extra={"license_serial": license_info.get("license_serial")},
            )
            return license_info
    stage_logger.warning("未获取到 CloudTower 许可证信息")
    return {}


def _post_cloudtower_graphql(
    *,
    client: APIClient,
    payload: Dict[str, Any],
    stage_logger: LoggerAdapter,
    description: str,
    ignore_messages: Tuple[str, ...],
) -> Dict[str, Any]:
    response = client.post(
        CLOUDTOWER_GRAPHQL_ENDPOINT,
        payload=payload,
        headers={"content-type": "application/json"},
    )
    errors = []
    if isinstance(response, dict):
        errors = response.get("errors") or []
    if errors:
        messages = " | ".join(str(err.get("message", err)) for err in errors if isinstance(err, dict))
        lowered = messages.lower()
        if any(keyword.lower() in lowered for keyword in ignore_messages):
            stage_logger.warning("%s出现可忽略的提示: %s", description, messages)
        else:
            raise RuntimeError(f"{description}失败: {messages}")
    return response.get("data", {}) if isinstance(response, dict) else {}


def _update_cloudtower_dns_via_ssh(
    *,
    deployment_plan: CloudTowerDeploymentPlan,
    dns_servers: List[str],
    stage_logger: LoggerAdapter,
) -> None:
    target_ip = deployment_plan.cloudtower_ip or deployment_plan.network.ip_address
    if not target_ip:
        stage_logger.warning("缺少 CloudTower IP，跳过 DNS 配置")
        return
    if not dns_servers:
        return

    stage_logger.info(
        "通过 SSH 更新 CloudTower DNS 配置",
        progress_extra={"ip": target_ip, "servers": dns_servers},
    )

    try:
        paramiko = importlib.import_module("paramiko")
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("缺少 paramiko 依赖，请先安装后重试：pip install paramiko") from exc

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        try:
            ssh_client.connect(
                target_ip,
                port=deployment_plan.ssh.port,
                username=deployment_plan.ssh.username,
                password=deployment_plan.ssh.password,
                timeout=deployment_plan.ssh.timeout,
            )
            content = "\n".join(f"nameserver {server}" for server in dns_servers)
            command = (
                "sudo cat <<'EOF' | sudo tee /etc/resolv.conf >/dev/null\n"
                + content.replace("'", "'\\''")
                + "\nEOF"
            )
            _run_sudo_command(
                ssh_client=ssh_client,
                ssh_config=deployment_plan.ssh,
                command=command,
                description="写入 /etc/resolv.conf",
                stage_logger=stage_logger,
            )
        except Exception as exc:  # noqa: BLE001 - DNS 写入失败不应阻断流程
            stage_logger.warning(
                "DNS 配置尝试失败，将跳过且继续部署",
                progress_extra={"ip": target_ip, "servers": dns_servers, "error": str(exc)},
            )
    finally:
        try:
            ssh_client.close()
        except Exception:  # noqa: BLE001
            pass

def _resolve_iso_path(ctx: RunContext, cfg: Dict[str, Any]) -> tuple[Path, Dict[str, Any]]:
    iso_cfg = cfg.get('cloudtower', {}) if isinstance(cfg, dict) else {}
    iso_path_cfg = iso_cfg.get('iso_path') if isinstance(iso_cfg, dict) else None
    glob_pattern = iso_cfg.get('iso_glob', 'cloudtower*.iso') if isinstance(iso_cfg, dict) else 'cloudtower*.iso'

    candidates: list[Path] = []
    work_dir = ctx.work_dir if isinstance(ctx.work_dir, Path) else Path.cwd()

    if iso_path_cfg:
        iso_path = Path(iso_path_cfg)
        if not iso_path.is_absolute():
            iso_path = work_dir / iso_path
        candidates.append(iso_path)

    if not candidates:
        candidates = sorted(work_dir.glob(glob_pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

    for path in candidates:
        if path.exists() and path.is_file():
            return path, iso_cfg if isinstance(iso_cfg, dict) else {}

    raise FileNotFoundError(
        f"未找到 CloudTower ISO 文件，请在 cloudtower.iso_path 配置中指定，或确保 {glob_pattern} 匹配的文件存在。"
    )


def _find_existing_cloudtower_iso(
    *,
    ctx: RunContext,
    client: APIClient,
    headers: Dict[str, str],
    iso_path: Path,
    iso_size: int,
    iso_cfg: Dict[str, Any],
    stage_logger: LoggerAdapter,
) -> Optional[Dict[str, Any]]:
    """查询 CloudTower 上是否已存在同名同大小的 ISO。"""

    iso_name = str(iso_cfg.get('name') or iso_path.name)

    stage_logger.info(
        "查询 CloudTower 上已存在的 ISO",
        progress_extra={"file_name": iso_name, "file_size": iso_size},
    )

    extra_query = iso_cfg.get('extra_image_query_params') if isinstance(iso_cfg, dict) else None
    query_params: Dict[str, Any] = {}
    if isinstance(extra_query, dict):
        for key, value in extra_query.items():
            if value is not None:
                query_params[str(key)] = value

    params = query_params or None

    try:
        response = client.get(CLOUDTOWER_IMAGES_ENDPOINT, params=params, headers=headers)
    except APIError as exc:
        if "status=401" not in str(exc):
            stage_logger.warning(
                "查询 CloudTower ISO 列表失败，将继续上传",
                progress_extra={"error": str(exc), "file_name": iso_name},
            )
            stage_logger.debug("查询 CloudTower ISO 列表异常详情", exc_info=exc)
            return None

        stage_logger.warning(
            "查询 CloudTower ISO 列表返回 401，尝试刷新 token",
            progress_extra={"file_name": iso_name},
        )
        stage_logger.debug("查询 CloudTower ISO 列表 401 异常详情", exc_info=exc)
        if not _refresh_fisheye_token(
            ctx=ctx,
            client=client,
            headers=headers,
            stage_logger=stage_logger,
        ):
            stage_logger.error(
                "刷新 token 失败，无法复用已存在的 ISO",
                progress_extra={"file_name": iso_name},
            )
            return None
        try:
            response = client.get(CLOUDTOWER_IMAGES_ENDPOINT, params=params, headers=headers)
        except Exception as retry_exc:  # noqa: BLE001
            stage_logger.warning(
                "刷新 token 后查询 CloudTower ISO 仍失败，将继续上传",
                progress_extra={"error": str(retry_exc), "file_name": iso_name},
            )
            stage_logger.debug("刷新 token 后查询 CloudTower ISO 异常详情", exc_info=retry_exc)
            return None
    except Exception as exc:  # noqa: BLE001 - 捕获网络异常
        stage_logger.warning(
            "查询 CloudTower ISO 列表出现异常，将继续上传",
            progress_extra={"error": str(exc), "file_name": iso_name},
        )
        stage_logger.debug("查询 CloudTower ISO 列表异常详情", exc_info=exc)
        return None

    images = _extract_data_list(response)
    if not images:
        stage_logger.debug(
            "CloudTower 上未找到已上传的 ISO",
            progress_extra={"file_name": iso_name},
        )
        return None

    normalized_name = iso_name.lower()

    for image in images:
        candidate_name = str(image.get("name") or image.get("file_name") or "").strip()
        if candidate_name and candidate_name.lower() != normalized_name:
            continue

        raw_size = image.get("file_size") or image.get("size") or image.get("total_size")
        candidate_size = _safe_int(raw_size)
        if candidate_size is not None and candidate_size != iso_size:
            stage_logger.debug(
                "发现名称匹配但大小不一致的 ISO，忽略",
                progress_extra={
                    "file_name": candidate_name or iso_name,
                    "expected_size": iso_size,
                    "actual_size": candidate_size,
                },
            )
            continue

        image_uuid = image.get("uuid") or image.get("image_uuid") or image.get("id")
        image_path = image.get("path") or image.get("image_path") or image.get("iso_path")
        if not image_uuid or not image_path:
            stage_logger.debug(
                "匹配到的 ISO 缺少必要字段，忽略",
                progress_extra={"file_name": candidate_name or iso_name, "uuid": image_uuid, "path": image_path},
            )
            continue

        summary: Dict[str, Any] = {
            "image_uuid": str(image_uuid),
            "zbs_volume_id": image.get("zbs_volume_id") or image.get("volume_uuid"),
            "file_name": candidate_name or iso_path.name,
            "file_size": candidate_size or iso_size,
            "chunk_size": image.get("chunk_size"),
            "uploaded_chunks": image.get("uploaded_chunks"),
            "sha256": image.get("sha256") or image.get("checksum"),
            "chunk_numbers": [],
            "image_path": image_path,
            "status": image.get("status"),
            "skipped": True,
            "raw": image,
        }

        stage_logger.info(
            "检测到已存在的 CloudTower ISO，跳过上传",
            progress_extra={
                "image_uuid": summary["image_uuid"],
                "file_name": summary["file_name"],
                "file_size": summary["file_size"],
            },
        )
        return summary

    stage_logger.debug(
        "未找到名称和大小匹配的 ISO，继续上传",
        progress_extra={"file_name": iso_name},
    )
    return None


def _create_cloudtower_upload_volume(
    *,
    client: APIClient,
    headers: Dict[str, str],
    iso_path: Path,
    iso_size: int,
    iso_cfg: Dict[str, Any],
    stage_logger: LoggerAdapter,
) -> Dict[str, Any]:
    """调用 API 创建 CloudTower ISO 上传卷。"""

    query_params: Dict[str, Any] = {
        "size": iso_size,
        "device": iso_cfg.get('upload_device', 'iscsi'),
        "name": iso_cfg.get('name') or iso_path.name,
        "description": iso_cfg.get('description', ""),
        "task_id": iso_cfg.get('task_id', 2),
    }
    # 允许通过配置传入额外的查询参数，例如 cloudtower.extra_volume_params
    extra_params = iso_cfg.get('extra_volume_params') if isinstance(iso_cfg, dict) else None
    if isinstance(extra_params, dict):
        for key, value in extra_params.items():
            if value is not None:
                query_params[str(key)] = value

    query_params = {str(k): v for k, v in query_params.items() if v is not None}

    stage_logger.info(
        "创建 CloudTower ISO 上传卷",
        progress_extra={
            "device": query_params.get("device"),
            "size": iso_size,
            "params": {k: query_params[k] for k in sorted(query_params)},
        },
    )
    response = client.post(
        CLOUDTOWER_VOLUME_ENDPOINT,
        None,
        headers=headers,
        params=query_params,
        data={},
    )
    data, source = _normalize_upload_volume_response(response)

    if stage_logger:
        stage_logger.debug(
            "解析上传卷响应",
            progress_extra={
                "data_source": source,
                "available_keys": sorted(str(key) for key in data.keys()),
            },
        )

    image_uuid = data.get("image_uuid")
    zbs_volume_id = data.get("zbs_volume_id")
    chunk_size = int(data.get("chunk_size") or iso_cfg.get('chunk_size_fallback') or DEFAULT_CHUNK_SIZE)
    image_path = data.get("image_path")
    if not image_uuid or not zbs_volume_id:
        raise RuntimeError("创建上传卷响应缺少 image_uuid 或 zbs_volume_id。")
    if chunk_size <= 0:
        chunk_size = DEFAULT_CHUNK_SIZE

    total_chunks = len(data.get("to_upload", [])) if isinstance(data.get("to_upload"), list) else None

    stage_logger.info(
        "CloudTower 上传卷创建成功",
        progress_extra={
            "image_uuid": image_uuid,
            "zbs_volume_id": zbs_volume_id,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks,
        },
    )

    return {
        "image_uuid": image_uuid,
        "zbs_volume_id": zbs_volume_id,
        "chunk_size": chunk_size,
        "to_upload": data.get("to_upload", []),
        "image_path": image_path,
    }


def _normalize_upload_volume_response(response: Any) -> tuple[Dict[str, Any], str]:
    def _from_mapping(mapping: Dict[str, Any], *, label: str) -> Optional[tuple[Dict[str, Any], str]]:
        direct_keys = {"image_uuid", "zbs_volume_id"}
        if direct_keys.issubset(mapping.keys()):
            return mapping, label
        for key in ("data", "result", "payload", "response"):
            candidate = mapping.get(key)
            if isinstance(candidate, dict):
                return candidate, f"{label}.{key}" if label else key
            if isinstance(candidate, list) and candidate:
                first = candidate[0]
                if isinstance(first, dict):
                    return first, f"{label}.{key}[0]" if label else f"{key}[0]"
        return None

    if isinstance(response, dict):
        normalized = _from_mapping(response, label="")
        if normalized:
            return normalized
    if isinstance(response, list) and response:
        first = response[0]
        if isinstance(first, dict):
            normalized = _from_mapping(first, label="[0]")
            if normalized:
                return normalized
            return first, "[0]"

    raise RuntimeError("创建上传卷响应格式不正确，未找到有效的卷信息字段。")


def _upload_cloudtower_iso_chunks(
    *,
    client: APIClient,
    headers: Dict[str, str],
    iso_path: Path,
    iso_size: int,
    volume_info: Dict[str, Any],
    iso_cfg: Dict[str, Any],
    stage_logger: LoggerAdapter,
    ctx_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """按照分片方式上传 CloudTower ISO，并汇总上传结果。"""

    raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="CloudTower ISO 上传")

    image_uuid = volume_info["image_uuid"]
    zbs_volume_id = volume_info["zbs_volume_id"]
    chunk_size = int(volume_info["chunk_size"])

    sha256 = hashlib.sha256()
    uploaded_chunks = 0
    chunk_nums = []
    uploaded_bytes = 0

    initial_to_upload = volume_info.get("to_upload") if isinstance(volume_info, dict) else None
    total_chunks = len(initial_to_upload) if isinstance(initial_to_upload, list) else 0
    if total_chunks <= 0 and chunk_size > 0:
        total_chunks = math.ceil(iso_size / chunk_size)

    start_time = time.monotonic()
    last_log_time = start_time

    def _log_progress(current_chunk_index: int, remaining_chunks: Optional[int], *, force: bool = False) -> None:
        nonlocal last_log_time
        now = time.monotonic()
        if not force and (now - last_log_time) < 3:
            return
        elapsed = max(now - start_time, 1e-6)
        speed_bps = uploaded_bytes / elapsed if uploaded_bytes else 0.0
        remaining_bytes = max(iso_size - uploaded_bytes, 0)
        eta_seconds = (remaining_bytes / speed_bps) if speed_bps > 0 else None
        progress_percent = (uploaded_bytes / iso_size * 100) if iso_size else None
        percentage: Optional[float] = None
        if total_chunks:
            percentage = (max(current_chunk_index, 0) / total_chunks) * 100
        elif progress_percent is not None:
            percentage = progress_percent
        if percentage is not None:
            percentage = max(0.0, min(percentage, 100.0))
        stage_logger.info(
            "CloudTower ISO 上传进度",
            progress_extra={
                "chunk": max(current_chunk_index, 0),
                "total_chunks": total_chunks or None,
                "remaining_chunks": remaining_chunks,
                "uploaded_bytes": uploaded_bytes,
                "total_bytes": iso_size,
                "uploaded_human": _format_bytes(uploaded_bytes),
                "total_human": _format_bytes(iso_size),
                "progress_percent": round(progress_percent, 2) if progress_percent is not None else None,
                "percentage": round(percentage, 2) if percentage is not None else None,
                "speed_bps": speed_bps,
                "speed_human": f"{_format_bytes(speed_bps)}/s" if speed_bps > 0 else "0 B/s",
                "eta_seconds": eta_seconds,
                "eta": _format_duration(eta_seconds),
            },
        )
        last_log_time = now

    with iso_path.open('rb') as iso_file:
        chunk_num = 0
        while True:
            raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="CloudTower ISO 上传")
            chunk = iso_file.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
            uploaded_bytes += len(chunk)
            params = {
                "zbs_volume_id": zbs_volume_id,
                "chunk_num": chunk_num,
                "image_uuid": image_uuid,
            }
            files = {
                "file": (iso_path.name, chunk, "application/octet-stream"),
            }
            try:
                response = client.post(
                    CLOUDTOWER_UPLOAD_ENDPOINT,
                    None,
                    headers=headers,
                    params=params,
                    files=files,
                )
            except APIError as exc:
                raise RuntimeError(f"上传分片 {chunk_num} 失败: {exc}") from exc

            raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="CloudTower ISO 上传")

            data = response.get("data") if isinstance(response, dict) else {}
            chunk_nums.append(chunk_num)
            uploaded_chunks += 1
            to_upload = data.get("to_upload") if isinstance(data, dict) else None
            remaining_chunks = len(to_upload) if isinstance(to_upload, list) else None
            if remaining_chunks is not None:
                estimated_total = uploaded_chunks + remaining_chunks
                if estimated_total > total_chunks:
                    total_chunks = estimated_total
            current_chunk_index = uploaded_chunks
            if total_chunks and remaining_chunks is not None:
                current_chunk_index = max(total_chunks - remaining_chunks, uploaded_chunks)
            _log_progress(current_chunk_index, remaining_chunks, force=False)
            stage_logger.debug(
                "分片上传成功",
                progress_extra={"chunk_num": chunk_num, "remaining": len(to_upload or [])},
            )
            chunk_num += 1

    raise_if_aborted(ctx_dict, stage_logger=stage_logger, hint="CloudTower ISO 上传")

    _log_progress(uploaded_chunks, 0, force=True)

    stage_logger.info(
        "CloudTower ISO 分片上传完成",
        progress_extra={"chunks": uploaded_chunks, "chunk_size": chunk_size},
    )

    return {
        "image_uuid": image_uuid,
        "zbs_volume_id": zbs_volume_id,
        "file_name": iso_path.name,
        "file_size": iso_size,
        "chunk_size": chunk_size,
        "uploaded_chunks": uploaded_chunks,
        "sha256": sha256.hexdigest(),
        "chunk_numbers": chunk_nums,
        "image_path": volume_info.get("image_path"),
    }


def _cleanup_upload_volume(
    client: APIClient,
    headers: Dict[str, str],
    volume_info: Dict[str, Any],
    stage_logger: LoggerAdapter,
) -> None:
    image_uuid = volume_info.get("image_uuid")
    if not image_uuid:
        return
    path = CLOUDTOWER_DELETE_ENDPOINT.format(image_uuid=image_uuid)
    try:
        client.delete(path, headers=headers)
        stage_logger.warning(
            "已回滚 CloudTower 上传卷",
            progress_extra={"image_uuid": image_uuid},
        )
    except Exception as exc:  # noqa: BLE001 - 记录清理失败
        stage_logger.error(
            "清理 CloudTower 上传卷失败",
            progress_extra={"image_uuid": image_uuid, "error": str(exc)},
        )


def _format_bytes(value: float) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "0 B"
    if value < 0:
        value = 0.0
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    if idx == 0:
        return f"{int(value)} {units[idx]}"
    return f"{value:.2f} {units[idx]}"


def _format_duration(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0 or math.isinf(seconds) or math.isnan(seconds):
        return "N/A"
    total_seconds = int(seconds)
    if total_seconds <= 0:
        return "0s"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: List[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def _load_fisheye_credentials(plan: Optional[PlanModel], parsed_plan: Any) -> tuple[Optional[str], Optional[str]]:
    default_user = "root"
    default_password = "HC!r0cks"

    if plan is not None and getattr(plan, "mgmt", None) is not None:
        mgmt = plan.mgmt
        plan_password = getattr(mgmt, "root密码", None)
        if plan_password:
            return default_user, str(plan_password)

    if isinstance(parsed_plan, dict):
        hosts_section = parsed_plan.get('hosts') or {}
        extra = hosts_section.get('extra') if isinstance(hosts_section, dict) else {}
        if isinstance(extra, dict):
            user = extra.get('fisheye_admin_user') or default_user
            password = extra.get('fisheye_admin_password') or default_password
            return str(user), str(password)

        mgmt_section = parsed_plan.get('mgmt') if isinstance(parsed_plan, dict) else None
        records = mgmt_section.get('records') if isinstance(mgmt_section, dict) else None
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict):
                    password = record.get('root密码') or record.get('fisheye_admin_password')
                    username = record.get('fisheye_admin_user') or default_user
                    if password:
                        return str(username or default_user), str(password)

    return default_user, default_password


def _extract_api_token(response: Dict[str, Any]) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    token = response.get("token")
    if token:
        return str(token)
    data = response.get("data")
    if isinstance(data, dict) and data.get("token"):
        return str(data["token"])
    return None
