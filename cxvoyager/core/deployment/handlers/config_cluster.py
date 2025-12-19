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

# Stage 3 config_cluster – 集群配置
from __future__ import annotations
import hashlib
import importlib
import logging
import math
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import openpyxl

from cxvoyager.core.deployment.handlers.init_cluster import _resolve_deployment_base
from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.progress import create_stage_progress_logger
from cxvoyager.common.config import load_config
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE
from cxvoyager.common.parallel_utils import parallel_map
from cxvoyager.integrations.smartx.api_client import APIClient, APIError
from cxvoyager.integrations.excel import field_variables as plan_vars

logger = logging.getLogger(__name__)
DEFAULT_SVT_CHUNK_SIZE = 8 * 1024 * 1024


@stage_handler(Stage.config_cluster)
def run_config_cluster_stage(ctx_dict):
    ctx: RunContext = ctx_dict['ctx']
    stage_name = Stage.config_cluster.value
    stage_logger = create_stage_progress_logger(ctx, stage_name, logger=logger, prefix="[config_cluster]")

    # === 1. 阶段入口与前置校验 ===
    stage_logger.info("开始执行集群配置阶段")

    verify_result = ctx.extra.get('deploy_verify')
    if not _is_deployment_successful(verify_result):
        stage_logger.error("部署校验尚未通过，无法执行集群配置")
        raise RuntimeError("集群尚未部署成功，无法开始配置阶段")

    cfg = ctx.config or load_config(DEFAULT_CONFIG_FILE)
    ctx.config = cfg
    api_cfg = cfg.get('api', {}) if isinstance(cfg, dict) else {}
    token = api_cfg.get('x-smartx-token')
    base_url_override = api_cfg.get('base_url')
    timeout = int(api_cfg.get('timeout', 10))
    use_mock = bool(api_cfg.get('mock', False))
    stage_logger.debug(
        "API 认证配置已加载",
        progress_extra={"base_url_override": base_url_override, "timeout": timeout, "use_mock": use_mock},
    )

    host_info = ctx.extra.get('host_scan')
    if not isinstance(host_info, dict) or not host_info:
        stage_logger.error("缺少主机扫描数据，无法确定集群 API 地址")
        raise RuntimeError("缺少主机扫描数据，无法确定集群 API 地址")
    stage_logger.debug("主机扫描结果已准备就绪", progress_extra={"hosts": list(host_info.keys())})

    base_url, host_header = _resolve_deployment_base(base_url_override, host_info)
    client = APIClient(base_url=base_url, mock=use_mock, timeout=timeout)
    stage_logger.debug(
        "SmartX API 客户端初始化完成",
        progress_extra={"base_url": base_url, "timeout": timeout, "mock": use_mock},
    )

    base_headers = {"content-type": "application/json"}
    if host_header:
        base_headers["host"] = host_header
    if token:
        base_headers["x-smartx-token"] = token
    # 仅保留必要字段记录日志，避免泄露 token 明文
    sanitized_headers = {
        key: ("***" if "token" in key.lower() else value) for key, value in base_headers.items()
    }
    stage_logger.debug("HTTP 请求基础头部已设置", progress_extra=sanitized_headers)

    # === 2. 解析规划表，提取部署参数 ===
    parsed_plan = ctx.extra.get('parsed_plan')
    plan_source = getattr(ctx.plan, 'source_file', None)
    if parsed_plan is None and plan_source:
        try:
            from cxvoyager.integrations.excel.planning_sheet_parser import parse_plan

            parsed_plan = parse_plan(Path(plan_source))
            ctx.extra['parsed_plan'] = parsed_plan
            stage_logger.info("已重新解析规划表，准备集群配置", progress_extra={"source": plan_source})
        except Exception as exc:  # noqa: BLE001 - 记录但不阻断
            logger.debug("规划表解析异常详情", exc_info=exc)
            stage_logger.warning(f"重新解析规划表失败: {exc}")
            parsed_plan = None

    fisheye_user, fisheye_password = _load_fisheye_credentials(parsed_plan)
    cluster_vip = _resolve_cluster_vip(ctx.plan, parsed_plan)
    dns_servers = _parse_management_service_list(parsed_plan, "DNS 服务器")
    ntp_servers = _parse_management_service_list(parsed_plan, "NTP 服务器")
    stage_logger.debug(
        "规划表提取关键参数",
        progress_extra={
            "fisheye_user": fisheye_user,
            "cluster_vip": cluster_vip,
            "dns_servers": dns_servers,
            "ntp_servers": ntp_servers,
        },
    )

    host_entries = _collect_host_config_entries(ctx.plan, parsed_plan)

    results: List[Dict[str, Any]] = []

    # === 3. 初始化 Fisheye 管理员账号 ===
    # 避免在日志中输出真实密码，仅作为请求载荷使用
    password_payload = {
        "password": fisheye_password,
        "repeat": fisheye_password,
        "encrypted": False,
    }
    if fisheye_user:
        password_payload["username"] = fisheye_user
    stage_logger.info("正在初始化 Fisheye 管理员密码")
    stage_logger.debug(
        "Fisheye 初始化请求载荷",
        progress_extra={"username": password_payload.get("username"), "password_length": len(fisheye_password or "")},
    )
    _send_post_request(client, "/api/v3/users:setupRoot", password_payload, base_headers, "初始化 Fisheye 管理员密码", results)
    password_entry = results[-1]
    if password_entry.get("status") == "ok":
        stage_logger.info("Fisheye 管理员密码初始化完成")
    else:
        stage_logger.warning("Fisheye 管理员密码初始化失败，请人工处理")

    login_payload = {
        "username": fisheye_user or "root",
        "password": fisheye_password,
        "encrypted": False,
    }
    stage_logger.info("正在登录 Fisheye 获取 token")
    stage_logger.debug("Fisheye 登录载荷", progress_extra={"username": login_payload["username"]})
    session_resp = _send_post_request(client, "/api/v3/sessions", login_payload, base_headers, "登录 Fisheye 获取凭证", results)
    session_entry = results[-1]
    session_token = _extract_api_token(session_resp)
    if session_entry.get("status") == "ok" and session_token:
        stage_logger.info("成功获取 Fisheye 会话 token")
    else:
        warning_msg = "Fisheye 登录未返回有效 token，请人工处理并重新执行"
        stage_logger.warning(warning_msg)
        results.append({"action": "获取 Fisheye 会话 token", "status": "warning", "error": warning_msg})
        session_token = None

    auth_headers = dict(base_headers)
    if session_token:
        auth_headers["x-smartx-token"] = session_token
    stage_logger.debug(
        "鉴权头部已更新为会话 token",
        progress_extra={key: ("***" if "token" in key.lower() else value) for key, value in auth_headers.items()},
    )

    # === 4. 配置集群网络与基础服务 ===
    if cluster_vip:
        vip_payload = {"iscsi_vip": None, "management_vip": cluster_vip}
        stage_logger.info(f"正在配置管理 VIP: {cluster_vip}")
        stage_logger.debug("VIP 配置载荷", progress_extra=vip_payload)
        _send_put_request(client, "/api/v2/settings/vip", vip_payload, auth_headers, "配置管理 VIP", results)
        vip_entry = results[-1]
        if vip_entry.get("status") == "ok":
            stage_logger.info("管理 VIP 配置完成")
        else:
            stage_logger.warning("管理 VIP 配置失败，请人工确认")
    else:
        stage_logger.warning("规划表未提供管理 VIP，跳过配置")

    if dns_servers:
        dns_payload = {"dns_servers": dns_servers}
        stage_logger.info(f"正在配置 DNS 服务器，共 {len(dns_servers)} 个")
        stage_logger.debug("DNS 配置载荷", progress_extra=dns_payload)
        _send_put_request(client, "/api/v2/settings/dns", dns_payload, auth_headers, "配置 DNS 服务器", results)
        dns_entry = results[-1]
        if dns_entry.get("status") == "ok":
            stage_logger.info("DNS 服务器配置完成")
        else:
            stage_logger.warning("DNS 服务器配置失败，请人工确认")
    else:
        stage_logger.warning("规划表未提供 DNS 服务器，跳过配置")

    if ntp_servers:
        ntp_payload = {"ntp_mode": "external", "ntp_servers": ntp_servers}
        stage_logger.info(f"正在配置 NTP 服务器，共 {len(ntp_servers)} 个")
        stage_logger.debug("NTP 配置载荷", progress_extra=ntp_payload)
        _send_put_request(client, "/api/v2/settings/ntp", ntp_payload, auth_headers, "配置 NTP 服务器", results)
        ntp_entry = results[-1]
        if ntp_entry.get("status") == "ok":
            stage_logger.info("NTP 服务器配置完成")
        else:
            stage_logger.warning("NTP 服务器配置失败，请人工确认")
    else:
        stage_logger.warning("规划表未提供 NTP 服务器，跳过配置")

    # === 5. 配置 IPMI 帐号 ===
    ipmi_payload = _build_ipmi_accounts_payload(host_entries, host_info)
    if ipmi_payload:
        payload = cast(Dict[str, Any], ipmi_payload)
        stage_logger.info(f"正在批量配置 IPMI 帐号，共 {len(payload['accounts'])} 台主机")
        stage_logger.debug(
            "IPMI 配置载荷摘要",
            progress_extra={
                "accounts": [
                    {
                        "node_uuid": item.get("node_uuid"),
                        "node_name": item.get("node_name"),
                        "host": item.get("host"),
                        "user": item.get("user"),
                    }
                    for item in payload["accounts"]
                ]
            },
        )
        before_len = len(results)
        _send_post_request(
            client,
            "/api/v2/ipmi/upsert_accounts",
            payload,
            auth_headers,
            "批量配置 IPMI 帐号",
            results,
        )
        after_entry = results[-1] if len(results) > before_len else {"status": "ok"}
        if after_entry.get("status") == "warning":
            stage_logger.warning(
                "IPMI 帐号配置未完全成功，已记录告警但继续执行",
                progress_extra={"error": after_entry.get("error")},
            )
        else:
            stage_logger.info("IPMI 帐号配置完成")
    else:
        stage_logger.warning("未找到有效的 IPMI 配置数据，跳过此步骤")

    # === 6. 配置业务虚拟交换机 ===
    business_vds_uuid: Optional[str] = None
    business_vds_payload = _build_business_vds_request_payload(parsed_plan, host_entries, host_info)
    if business_vds_payload:
        stage_logger.info(
            "正在配置业务虚拟交换机",
            progress_extra={
                "name": business_vds_payload.get("name"),
                "host_count": len(business_vds_payload.get("hosts_associated", [])),
                "bond_mode": business_vds_payload.get("bond_mode"),
            },
        )
        vds_response = _send_post_request(
            client,
            "/api/v2/network/vds",
            business_vds_payload,
            auth_headers,
            "配置业务虚拟交换机",
            results,
        )
        vds_entry = results[-1]
        if vds_entry.get("status") == "ok":
            business_vds_uuid = _extract_resource_uuid(vds_response)
            if not business_vds_uuid:
                job_id = _extract_job_id(vds_response)
                if job_id:
                    stage_logger.info(
                        "业务虚拟交换机创建返回任务，正在查询 UUID",
                        progress_extra={"job_id": job_id},
                    )
                    job_response = _fetch_json_response(
                        client,
                        f"/api/v2/jobs/{job_id}",
                        auth_headers,
                        "查询业务虚拟交换机创建任务",
                        results,
                    )
                    job_entry = results[-1]
                    if job_entry.get("status") == "ok":
                        business_vds_uuid = _extract_vds_uuid_from_job(job_response)
                        if business_vds_uuid:
                            stage_logger.debug(
                                "已从任务详情解析到业务虚拟交换机 UUID",
                                progress_extra={"job_id": job_id, "vds_uuid": business_vds_uuid},
                            )
                        else:
                            stage_logger.warning(
                                "任务详情未包含业务虚拟交换机 UUID",
                                progress_extra={"job_id": job_id},
                            )
                    else:
                        stage_logger.warning(
                            "查询业务虚拟交换机创建任务失败，跳过业务虚拟网络创建",
                            progress_extra={"job_id": job_id, "error": job_entry.get("error")},
                        )
            if not business_vds_uuid and use_mock:
                fallback_name = str(business_vds_payload.get("name") or "mock-vds")
                business_vds_uuid = f"mock-{fallback_name}"
                stage_logger.debug(
                    "使用模拟 uuid 创建业务虚拟网络",
                    progress_extra={"vds_uuid": business_vds_uuid},
                )
            if business_vds_uuid:
                stage_logger.info(
                    "业务虚拟交换机配置完成",
                    progress_extra={"vds_uuid": business_vds_uuid},
                )
            else:
                stage_logger.warning("业务虚拟交换机创建响应缺少 uuid，跳过业务虚拟网络创建")
        else:
            stage_logger.warning("业务虚拟交换机配置失败，请人工确认")
    else:
        stage_logger.warning("未准备好业务虚拟交换机配置，跳过此步骤")

    if business_vds_uuid:
        business_network_payloads = _build_business_network_payloads(parsed_plan, business_vds_uuid)
        if business_network_payloads:
            stage_logger.info(
                "正在创建业务虚拟网络",
                progress_extra={"count": len(business_network_payloads)},
            )
            success = 0
            for payload in business_network_payloads:
                name = payload.get("name") or "(未命名)"
                action_desc = f"创建业务虚拟网络[{name}]"
                _send_post_request(
                    client,
                    f"/api/v2/network/vds/{business_vds_uuid}/vlans",
                    payload,
                    auth_headers,
                    action_desc,
                    results,
                )
                network_entry = results[-1]
                if network_entry.get("status") == "ok":
                    success += 1
                    stage_logger.info(
                        "业务虚拟网络创建成功",
                        progress_extra={"name": name, "vlan_id": payload.get("vlan_id")},
                    )
                else:
                    stage_logger.warning(
                        "业务虚拟网络创建失败",
                        progress_extra={
                            "name": name,
                            "vlan_id": payload.get("vlan_id"),
                            "error": network_entry.get("error"),
                        },
                    )
            stage_logger.info(
                "业务虚拟网络创建完成",
                progress_extra={"success": success, "total": len(business_network_payloads)},
            )
            detail_response = _fetch_json_response(
                client,
                f"/api/v2/network/vds/{business_vds_uuid}",
                auth_headers,
                "查询业务虚拟交换机详情",
                results,
            )
            detail_entry = results[-1]
            if detail_entry.get("status") == "ok":
                actual_vlans_count = _extract_vlans_count(detail_response)
                expected_count = len(business_network_payloads)
                if actual_vlans_count is None:
                    stage_logger.warning(
                        "业务虚拟交换机详情未返回vlans_count字段，请人工确认业务网络是否创建成功",
                        progress_extra={"expected": expected_count},
                    )
                elif actual_vlans_count != expected_count:
                    stage_logger.warning(
                        "业务虚拟网络数量与规划表不一致，请人工确认",
                        progress_extra={
                            "expected": expected_count,
                            "actual": actual_vlans_count,
                            "vds_uuid": business_vds_uuid,
                        },
                    )
                else:
                    stage_logger.info(
                        "业务虚拟网络数量校验通过",
                        progress_extra={
                            "expected": expected_count,
                            "actual": actual_vlans_count,
                            "vds_uuid": business_vds_uuid,
                        },
                    )
        else:
            stage_logger.info("规划表未提供业务虚拟网络配置，跳过创建业务虚拟网络")

    # === 7. 批量更新主机账号密码 ===
    password_summary = _update_host_login_passwords(stage_logger, host_entries, cfg)
    if password_summary is not None:
        results.append(password_summary)

    # === 8. 上传虚拟机工具（SVT） ===
    svt_entry = _upload_svt_image(
        ctx=ctx,
        client=client,
        auth_headers=auth_headers,
        cluster_vip=cluster_vip,
        stage_logger=stage_logger,
    )
    if svt_entry:
        results.append(svt_entry)

    # === 9. 配置 CPU 兼容性 ===
    _configure_cpu_compatibility(
        client=client,
        headers=auth_headers,
        stage_logger=stage_logger,
        results=results,
    )

    # === 10. 获取并回填集群序列号 ===
    stage_logger.info("正在获取集群序列号")
    license_resp = _fetch_json_response(client, "/api/v2/tools/license", auth_headers, "获取集群序列号", results)
    license_entry = results[-1]
    serial = _extract_cluster_serial(license_resp)
    if license_entry.get("status") == "ok" and serial:
        ctx.extra.setdefault('cluster', {})['serial'] = serial
        stage_logger.info(f"已获取集群序列号: {serial}")
        stage_logger.debug(
            "序列号响应体摘要",
            progress_extra={
                "ec": license_resp.get("ec"),
                "has_error": bool(license_resp.get("error")),
                "data_keys": sorted(list(license_resp.get("data", {}).keys())) if isinstance(license_resp.get("data"), dict) else [],
            },
        )
        plan_path = _resolve_plan_workbook_path(ctx)
        if plan_path:
            try:
                _write_cluster_serial_to_plan(plan_path, serial)
                results.append({"action": "write_plan_serial", "status": "ok", "path": str(plan_path)})
                stage_logger.info(f"已在规划表写入集群序列号[{plan_path.name}]")
            except Exception as exc:  # noqa: BLE001 - 记录失败
                logger.debug("写入集群序列号到规划表失败详情", exc_info=exc)
                results.append({"action": "write_plan_serial", "status": "failed", "error": str(exc)})
                stage_logger.warning(f"写入集群序列号到规划表失败: {exc}")
        else:
            stage_logger.warning("未找到规划表路径，序列号仅保存于运行上下文")
    elif license_entry.get("status") == "ok":
        warning_msg = "未能解析到集群序列号，请人工确认"
        stage_logger.warning(warning_msg)
        results.append({"action": "解析集群序列号", "status": "warning", "error": warning_msg})
    else:
        stage_logger.warning("未能获取集群序列号")

    # === 11. 持久化阶段执行明细到运行上下文 ===
    ctx.extra.setdefault('config_cluster', {})['results'] = results
    stage_logger.info("集群配置阶段完成")


def _is_deployment_successful(verify_result: Any) -> bool:
    if not isinstance(verify_result, dict):
        return False
    data = verify_result.get('data')
    if not isinstance(data, dict):
        return False
    return data.get('is_deployed') is True


def _send_post_request(
    client: APIClient,
    path: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    description: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    try:
        response = client.post(path, payload, headers=headers)
        results.append({"action": description, "status": "ok"})
        return response
    except APIError as exc:
        logger.warning("%s失败: %s", description, exc)
        results.append(
            {
                "action": description,
                "status": "warning",
                "error": str(exc),
            }
        )
        return {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s异常: %s", description, exc)
        results.append(
            {
                "action": description,
                "status": "warning",
                "error": str(exc),
            }
        )
        return {}


def _send_put_request(
    client: APIClient,
    path: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    description: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    try:
        response = client.put(path, payload, headers=headers)
        results.append({"action": description, "status": "ok"})
        return response
    except APIError as exc:
        logger.warning("%s失败: %s", description, exc)
        results.append({"action": description, "status": "warning", "error": str(exc)})
        return {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s异常: %s", description, exc)
        results.append({"action": description, "status": "warning", "error": str(exc)})
        return {}


def _fetch_json_response(
    client: APIClient,
    path: str,
    headers: Dict[str, str],
    description: str,
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    try:
        response = client.get(path, headers=headers)
        results.append({"action": description, "status": "ok"})
        return response
    except APIError as exc:
        logger.warning("%s失败: %s", description, exc)
        results.append({"action": description, "status": "warning", "error": str(exc)})
        return {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s异常: %s", description, exc)
        results.append({"action": description, "status": "warning", "error": str(exc)})
        return {}


def _extract_api_token(response: Dict[str, Any]) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    token = response.get("token")
    if token:
        return str(token)
    data = response.get("data")
    if isinstance(data, dict):
        token = data.get("token")
        if token:
            return str(token)
    return None


def _extract_cluster_serial(response: Dict[str, Any]) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, dict):
        serial = data.get("serial")
        if serial:
            return str(serial)
    return None


def _load_fisheye_credentials(parsed_plan: Any) -> tuple[str, str]:
    default_user = plan_vars.FISHEYE_ADMIN_USER.default or "root"
    default_password = plan_vars.FISHEYE_ADMIN_PASSWORD.default or "HC!r0cks"
    if isinstance(parsed_plan, dict):
        hosts_section = parsed_plan.get('hosts', {})
        extra = hosts_section.get('extra', {}) if isinstance(hosts_section, dict) else {}
        user = extra.get('fisheye_admin_user') or default_user
        password = extra.get('fisheye_admin_password') or default_password
        return str(user), str(password)
    return default_user, default_password


def _resolve_cluster_vip(plan: Any, parsed_plan: Any) -> Optional[str]:
    if getattr(plan, 'hosts', None):
        for host in plan.hosts:
            vip = getattr(host, '集群VIP', None)
            if vip:
                return str(vip)
    if isinstance(parsed_plan, dict):
        host_records = parsed_plan.get('hosts', {}).get('records', [])
        for record in host_records:
            vip = record.get('集群VIP')
            if vip:
                return str(vip)
    return None


def _parse_management_service_list(parsed_plan: Any, key: str) -> List[str]:
    if not isinstance(parsed_plan, dict):
        return []
    mgmt = parsed_plan.get('mgmt', {})
    records = mgmt.get('records', []) if isinstance(mgmt, dict) else []
    if not records:
        return []
    first = records[0]
    if not isinstance(first, dict):
        return []
    values = first.get(key) or []
    return [str(item) for item in values if item]


def _collect_host_config_entries(plan: Any, parsed_plan: Any) -> List[Dict[str, Any]]:
    entries: Dict[str, Dict[str, Any]] = {}

    plan_hosts = getattr(plan, 'hosts', None)
    if plan_hosts:
        for host in plan_hosts:
            mgmt_ip = getattr(host, '管理地址', None)
            if mgmt_ip is None:
                continue
            key = str(mgmt_ip)
            entry = entries.setdefault(key, {"mgmt_ip": key})
            entry.setdefault("hostname", getattr(host, 'SMTX主机名', None))
            storage_ip = getattr(host, '存储地址', None)
            if storage_ip is not None:
                entry["storage_ip"] = str(storage_ip)
            bmc_ip = getattr(host, '带外地址', None)
            if bmc_ip is not None:
                entry["bmc_ip"] = str(bmc_ip)
            bmc_user = getattr(host, '带外用户名', None)
            if bmc_user:
                entry["bmc_user"] = str(bmc_user)
            bmc_password = getattr(host, '带外密码', None)
            if bmc_password:
                entry["bmc_password"] = str(bmc_password)

    if isinstance(parsed_plan, dict):
        host_section = parsed_plan.get('hosts', {})
        records = host_section.get('records', []) if isinstance(host_section, dict) else []
        for record in records:
            if not isinstance(record, dict):
                continue
            mgmt_ip = record.get('管理地址')
            if not mgmt_ip:
                continue
            key = str(mgmt_ip)
            entry = entries.setdefault(key, {"mgmt_ip": key})
            for field in [
                ('hostname', 'SMTX主机名'),
                ('storage_ip', '存储地址'),
                ('bmc_ip', '带外地址'),
                ('bmc_user', '带外用户名'),
                ('bmc_password', '带外密码'),
                ('ssh_user', '主机SSH用户名'),
                ('ssh_password', '主机SSH密码'),
            ]:
                value = record.get(field[1])
                if value:
                    entry[field[0]] = str(value)

    return list(entries.values())


def _build_ipmi_accounts_payload(host_entries: List[Dict[str, Any]], host_scan_data: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(host_scan_data, dict):
        return None
    accounts: List[Dict[str, Any]] = []
    for entry in host_entries:
        mgmt_ip = entry.get('mgmt_ip')
        if not mgmt_ip:
            continue
        scan_data = host_scan_data.get(mgmt_ip)
        if not isinstance(scan_data, dict):
            continue
        node_uuid = scan_data.get('host_uuid')
        if not node_uuid:
            continue
        bmc_ip = entry.get('bmc_ip')
        bmc_user = entry.get('bmc_user')
        bmc_password = entry.get('bmc_password')
        if not (bmc_ip and bmc_user and bmc_password):
            continue
        accounts.append(
            {
                "node_uuid": node_uuid,
                "node_name": scan_data.get('hostname') or entry.get('hostname'),
                "host": bmc_ip,
                "user": bmc_user,
                "password": bmc_password,
            }
        )
    if not accounts:
        return None
    return {"accounts": accounts}


def _parse_nic_name_list(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        tokens = re.split(r"[\s,;/\\，、]+", raw)
    elif isinstance(raw, (list, tuple, set)):
        tokens = []
        for item in raw:
            tokens.extend(_parse_nic_name_list(item))
    else:
        tokens = [str(raw)]
    return [token.strip() for token in tokens if token and token.strip()]


def _map_bond_mode_to_backend(raw: Any) -> str:
    if not raw:
        return "active-backup"
    text = str(raw).strip().lower()
    mapping = {
        "active-backup": "active-backup",
        "active_backup": "active-backup",
        "balance-tcp": "lacp",
        "balance_tcp": "lacp",
        "lacp": "lacp",
        "balance-slb": "balance-slb",
        "balance_slb": "balance-slb",
        "slb": "balance-slb",
    }
    return mapping.get(text, "active-backup")


def _lookup_storage_ip_from_scan(scan_data: Dict[str, Any]) -> Optional[str]:
    if not isinstance(scan_data, dict):
        return None
    ifaces = scan_data.get('ifaces')
    if isinstance(ifaces, list):
        for iface in ifaces:
            if not isinstance(iface, dict):
                continue
            role = str(iface.get('function') or '').lower()
            if role and role not in {"storage", "data"}:
                continue
            ipv4_list = iface.get('ipv4') or iface.get('ip')
            if isinstance(ipv4_list, list) and ipv4_list:
                return str(ipv4_list[0])
    return None


def _build_business_vds_request_payload(
    parsed_plan: Any,
    host_entries: List[Dict[str, Any]],
    host_scan_data: Any,
) -> Optional[Dict[str, Any]]:
    if not isinstance(parsed_plan, dict):
        return None
    variables = parsed_plan.get('variables')
    if not isinstance(variables, dict):
        return None

    vds_name = variables.get(plan_vars.BUSINESS_VDS_NAME.key)
    if not vds_name:
        return None

    bond_mode = _map_bond_mode_to_backend(variables.get(plan_vars.BUSINESS_BOND_MODE.key))
    nics_raw = variables.get(plan_vars.BUSINESS_SWITCH_PORTS.key)
    nic_names = _parse_nic_name_list(nics_raw)
    if not nic_names:
        return None

    if not isinstance(host_scan_data, dict):
        return None

    hosts_associated: List[Dict[str, Any]] = []
    for entry in host_entries:
        mgmt_ip = entry.get('mgmt_ip')
        if not mgmt_ip:
            continue
        scan_data = host_scan_data.get(mgmt_ip)
        if not isinstance(scan_data, dict):
            continue
        node_uuid = scan_data.get('host_uuid')
        if not node_uuid:
            continue
        storage_ip = entry.get('storage_ip') or _lookup_storage_ip_from_scan(scan_data)
        if not storage_ip:
            continue
        hosts_associated.append(
            {
                "host_uuid": node_uuid,
                "nics_associated": nic_names,
                "data_ip": str(storage_ip),
            }
        )

    if not hosts_associated:
        return None

    payload: Dict[str, Any] = {
        "name": vds_name,
        "bond_mode": bond_mode,
        "hosts_associated": hosts_associated,
    }
    return payload


def _extract_resource_uuid(response: Dict[str, Any]) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    for candidate in ("uuid", "id"):
        value = response.get(candidate)
        if value:
            return str(value)
    data = response.get("data")
    if isinstance(data, dict):
        for candidate in ("uuid", "id"):
            value = data.get(candidate)
            if value:
                return str(value)
    return None


def _normalize_vlan_id(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    if isinstance(raw, bool):  # bool 是 int 子类，需要单独排除
        return None
    if isinstance(raw, int):
        return raw if raw >= 0 else None
    if isinstance(raw, float):
        return int(raw) if raw >= 0 else None
    text = str(raw).strip()
    if not text:
        return None
    match = re.search(r"(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _build_business_network_payloads(parsed_plan: Any, vds_uuid: str) -> List[Dict[str, Any]]:
    if not isinstance(parsed_plan, dict) or not vds_uuid:
        return []
    section = parsed_plan.get('virtual_network', {})
    records = section.get('records', []) if isinstance(section, dict) else []
    payloads: List[Dict[str, Any]] = []

    for record in records:
        if not isinstance(record, dict):
            continue
        marker = str(record.get("网络标识") or "")
        if not marker.startswith("business"):
            continue
        vlan_id = _normalize_vlan_id(record.get("vlan_id"))
        if vlan_id is None:
            logger.debug("跳过业务虚拟网络配置：缺少有效的 VLAN ID，记录=%s", record)
            continue
        raw_name = record.get("虚拟机网络") or record.get("name")
        name = str(raw_name).strip() if isinstance(raw_name, str) else None
        if not name:
            name = f"business-{len(payloads) + 1:02d}"
        payloads.append({
            "name": name,
            "vlan_id": vlan_id,
            "vds_uuid": vds_uuid,
        })

    return payloads


def _extract_job_id(response: Dict[str, Any]) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, dict):
        job_id = data.get("job_id") or data.get("jobId")
        if job_id:
            return str(job_id)
    return None


def _extract_vds_uuid_from_job(response: Dict[str, Any]) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if not isinstance(data, dict):
        return None
    # 1) data.job.resources -> {uuid: {...}}
    job = data.get("job")
    if isinstance(job, dict):
        resources = job.get("resources")
        if isinstance(resources, dict):
            for payload in resources.values():
                if isinstance(payload, dict):
                    candidate = payload.get("uuid") or payload.get("id")
                    if candidate:
                        return str(candidate)
        event = job.get("event")
        if isinstance(event, dict):
            event_data = event.get("data")
            if isinstance(event_data, dict):
                candidate = event_data.get("uuid") or event_data.get("id")
                if candidate:
                    return str(candidate)
    # 2) data.resources (其他结构兼容)
    resources = data.get("resources")
    if isinstance(resources, dict):
        for payload in resources.values():
            if isinstance(payload, dict):
                candidate = payload.get("uuid") or payload.get("id")
                if candidate:
                    return str(candidate)
    return None


def _extract_vlans_count(response: Dict[str, Any]) -> Optional[int]:
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, dict):
        value = data.get("vlans_count")
    else:
        value = response.get("vlans_count")
    if value is None:
        return None
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count >= 0 else None


def _update_host_login_passwords(stage_logger, host_entries: List[Dict[str, Any]], cfg: Any) -> Optional[Dict[str, Any]]:
    host_cfg = {}
    if isinstance(cfg, dict):
        host_cfg = cfg.get('host_password_update', {}) or {}

    if isinstance(host_cfg, dict) and host_cfg.get('enabled') is False:
        stage_logger.info("配置已禁用主机密码修改，跳过执行")
        return {"action": "批量更新主机密码", "status": "skipped", "reason": "disabled"}

    DEFAULT_PASSWORD = "HC!r0cks"
    jobs_map: Dict[str, Dict[str, Any]] = {}
    for entry in host_entries:
        mgmt_ip = entry.get('mgmt_ip')
        if not mgmt_ip:
            continue
        target_password = entry.get('ssh_password') or host_cfg.get('target_password') or DEFAULT_PASSWORD
        if not target_password:
            continue
        login_user = host_cfg.get('login_user') or 'smartx'
        if str(login_user).lower() != 'smartx':
            stage_logger.warning(
                "密码更新登录账号固定使用 smartx，已忽略自定义",
                progress_extra={"host": mgmt_ip, "login_user": login_user},
            )
            login_user = 'smartx'
        login_password = host_cfg.get('login_password') or entry.get('ssh_password') or DEFAULT_PASSWORD
        root_password = host_cfg.get('root_password') or target_password
        jobs_map[mgmt_ip] = {
            "host": mgmt_ip,
            "hostname": entry.get('hostname'),
            "login_user": login_user,
            "login_password": login_password,
            "target_password": target_password,
            "root_password": root_password,
            "update_root": host_cfg.get('update_root', True),
        }

    jobs = list(jobs_map.values())
    if not jobs:
        stage_logger.warning("没有可用于更新密码的主机记录，跳过")
        return {"action": "批量更新主机密码", "status": "skipped", "reason": "no_hosts"}

    try:
        paramiko_module = importlib.import_module('paramiko')
    except ImportError as exc:  # pragma: no cover - runtime environment issue
        stage_logger.warning("未安装 paramiko，无法执行主机密码更新: %s", exc)
        return {
            "action": "批量更新主机密码",
            "status": "failed",
            "error": "missing paramiko",
        }

    max_workers = int(host_cfg.get('max_workers', min(4, len(jobs)))) or 1
    ssh_timeout = int(host_cfg.get('ssh_timeout', 30))

    stage_logger.info("正在批量更新主机账号密码", progress_extra={"host_count": len(jobs), "max_workers": max_workers})
    stage_logger.debug(
        "主机密码更新任务摘要",
        progress_extra={
            "jobs": [
                {
                    "host": job["host"],
                    "login_user": job["login_user"],
                    "update_root": job["update_root"],
                }
                for job in jobs
            ]
        },
    )

    def _runner(job: Dict[str, Any]) -> Dict[str, Any]:
        return _change_password_via_ssh(job, ssh_timeout, paramiko_module)

    task_results = parallel_map(_runner, jobs, max_workers=max_workers)

    success_hosts: List[str] = []
    errors: List[str] = []
    for result in task_results:
        if isinstance(result, Exception):
            errors.append(str(result))
            continue
        if result.get('status') == 'ok':
            success_hosts.append(result.get('host', '?'))
        else:
            errors.append(str(result))

    if errors and success_hosts:
        stage_logger.warning("部分主机密码更新失败", progress_extra={"failed": errors, "succeeded": success_hosts})
        status = "partial"
    elif errors:
        for err in errors:
            stage_logger.error("主机密码更新失败: %s", err)
        status = "failed"
    else:
        stage_logger.info("全部主机密码更新成功", progress_extra={"hosts": success_hosts})
        status = "ok"

    summary: Dict[str, Any] = {
        "action": "批量更新主机密码",
        "status": status,
        "success": success_hosts,
    }
    if errors:
        summary['errors'] = errors
    return summary


def _change_password_via_ssh(job: Dict[str, Any], timeout: int, paramiko_module) -> Dict[str, Any]:
    host = job['host']
    username = job['login_user']
    login_password = job['login_password']
    target_password = job['target_password']
    root_password = job['root_password']
    update_root = bool(job.get('update_root', True))

    client = paramiko_module.SSHClient()
    client.set_missing_host_key_policy(paramiko_module.AutoAddPolicy())

    try:
        client.connect(host, username=username, password=login_password, timeout=timeout)

        lines = [f"{username}:{target_password}"]
        if update_root and username != 'root':
            lines.append(f"root:{root_password}")
        elif update_root and username == 'root':
            root_password = target_password
        payload = "\n".join(lines)

        if username == 'root':
            command = "/usr/sbin/chpasswd"
            stdin_prefix = ""
        else:
            command = "sudo -S /usr/sbin/chpasswd"
            stdin_prefix = f"{login_password}\n"

        stdin, stdout, stderr = client.exec_command(command, get_pty=True)
        stdin.write(f"{stdin_prefix}{payload}\n")
        stdin.flush()
        if not stdin.channel.closed:
            stdin.channel.shutdown_write()

        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            err_text = stderr.read().decode('utf-8', 'ignore').strip()
            raise RuntimeError(f"{host}: chpasswd exited with {exit_status} ({err_text or 'no stderr'})")

        return {"host": host, "status": "ok"}
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass


def _resolve_plan_workbook_path(ctx: RunContext) -> Optional[Path]:
    source = getattr(ctx.plan, 'source_file', None)
    if source:
        path = Path(source)
        if path.exists():
            return path
    return None


def _write_cluster_serial_to_plan(plan_path: Path, serial: str) -> None:
    workbook = openpyxl.load_workbook(plan_path)
    sheet = workbook[plan_vars.CLUSTER_SERIAL.sheet]
    sheet[plan_vars.CLUSTER_SERIAL.cell] = serial
    workbook.save(plan_path)


def _upload_svt_image(
    *,
    ctx: RunContext,
    client: APIClient,
    auth_headers: Dict[str, str],
    cluster_vip: Optional[str],
    stage_logger,
) -> Optional[Dict[str, Any]]:
    cfg_dict: Dict[str, Any] = ctx.config or {}
    svt_cfg = cfg_dict.get('svt', {}) if isinstance(cfg_dict, dict) else {}

    if isinstance(svt_cfg, dict) and svt_cfg.get('enabled') is False:
        stage_logger.info("配置已禁用 SVT 上传，跳过")
        return {"action": "上传SVT镜像", "status": "skipped", "reason": "disabled"}

    iso_path = _resolve_svt_iso_path(ctx, svt_cfg)
    if iso_path is None:
        stage_logger.warning(
            "未找到 SVT 镜像文件，跳过上传",
            progress_extra={"glob": (svt_cfg.get('iso_glob') if isinstance(svt_cfg, dict) else None)},
        )
        return {"action": "上传SVT镜像", "status": "skipped", "reason": "not_found"}

    iso_size = iso_path.stat().st_size
    if iso_size <= 0:
        stage_logger.warning(
            "SVT 镜像为空，跳过上传",
            progress_extra={"path": str(iso_path)},
        )
        return {"action": "上传SVT镜像", "status": "skipped", "reason": "empty_file"}

    upload_client = client
    if cluster_vip and getattr(client, "mock", False) is False:
        try:
            upload_client = APIClient(
                base_url=f"http://{cluster_vip}",
                mock=client.mock,
                timeout=client.timeout,
                verify=getattr(client, "verify", True),
            )
            stage_logger.debug(
                "SVT 上传优先使用集群 VIP",
                progress_extra={"base_url": upload_client.base_url},
            )
        except Exception as exc:  # noqa: BLE001 - 回退到现有客户端
            stage_logger.warning(
                "基于集群 VIP 的上传客户端创建失败，回退到默认 API 客户端",
                progress_extra={"error": str(exc)},
            )

    upload_headers = dict(auth_headers)
    upload_headers.pop("content-type", None)

    chunk_size_fallback = int(svt_cfg.get('chunk_size_fallback') or DEFAULT_SVT_CHUNK_SIZE)
    max_attempts = 2
    last_error: Optional[Exception] = None

    stage_logger.info(
        "准备上传 SVT 镜像",
        progress_extra={"path": str(iso_path), "size": iso_size, "cluster_vip": cluster_vip},
    )

    for attempt in range(1, max_attempts + 1):
        volume_info: Optional[Dict[str, Any]] = None
        try:
            volume_info = _create_svt_upload_volume(
                client=upload_client,
                headers=upload_headers,
                iso_path=iso_path,
                iso_size=iso_size,
                chunk_size_fallback=chunk_size_fallback,
                stage_logger=stage_logger,
            )
            summary = _upload_svt_chunks(
                client=upload_client,
                headers=upload_headers,
                iso_path=iso_path,
                iso_size=iso_size,
                volume_info=volume_info,
                stage_logger=stage_logger,
            )
            summary["file_name"] = iso_path.name
            summary["file_size"] = iso_size
            ctx.extra.setdefault('config_cluster', {})['svt_image'] = summary
            ctx.extra.setdefault('deploy_cloudtower', {}).setdefault('vmtools', summary)
            stage_logger.info(
                "SVT 镜像上传完成",
                progress_extra={"image_uuid": summary.get("image_uuid"), "zbs_volume_id": summary.get("zbs_volume_id")},
            )
            return {
                "action": "上传SVT镜像",
                "status": "ok",
                "image_uuid": summary.get("image_uuid"),
                "zbs_volume_id": summary.get("zbs_volume_id"),
            }
        except Exception as exc:  # noqa: BLE001 - 记录失败并重试
            last_error = exc
            stage_logger.warning(
                "SVT 上传尝试失败，准备回滚后重试",
                progress_extra={"attempt": attempt, "error": str(exc)},
            )
            if volume_info and volume_info.get("image_uuid"):
                _cleanup_svt_image(upload_client, upload_headers, str(volume_info.get("image_uuid")), stage_logger)

    if last_error is None:
        last_error = RuntimeError("SVT 上传失败，未捕获具体原因")
    stage_logger.error(
        "SVT 镜像上传失败，将跳过并记录以便后续人工处理",
        progress_extra={"error": str(last_error)},
    )
    return {
        "action": "上传SVT镜像",
        "status": "warning",
        "error": str(last_error),
    }


def _configure_cpu_compatibility(
    *,
    client: APIClient,
    headers: Dict[str, str],
    stage_logger,
    results: List[Dict[str, Any]],
) -> None:
    try:
        stage_logger.info("正在查询推荐 CPU 兼容性")
        recommend_resp = _fetch_json_response(
            client,
            "/api/v2/elf/cluster_recommended_cpu_models",
            headers,
            "查询推荐CPU兼容性",
            results,
        )
        model = _extract_recommended_cpu_model(recommend_resp)
        if not model:
            warning_msg = "未获取到推荐 CPU 兼容性，跳过配置"
            stage_logger.warning(warning_msg)
            results.append({"action": "配置CPU兼容性", "status": "skipped", "reason": "no_recommendation"})
            return

        payload = {"cpu_model": model}
        stage_logger.info("正在配置 CPU 兼容性", progress_extra={"cpu_model": model})
        _send_put_request(
            client,
            "/api/v2/elf/cluster_cpu_compatibility",
            payload,
            headers,
            "配置CPU兼容性",
            results,
        )
    except Exception as exc:  # noqa: BLE001 - 不阻断流程
        stage_logger.warning(
            "CPU 兼容性配置失败，已跳过，请后续人工确认",
            progress_extra={"error": str(exc)},
        )
        results.append({"action": "配置CPU兼容性", "status": "warning", "error": str(exc)})


def _extract_recommended_cpu_model(response: Dict[str, Any]) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, dict):
        models = data.get("cpu_models")
        if isinstance(models, list) and models:
            first = models[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
    models = response.get("cpu_models")
    if isinstance(models, list) and models:
        first = models[0]
        if isinstance(first, str) and first.strip():
            return first.strip()
    return None


def _resolve_svt_iso_path(ctx: RunContext, svt_cfg: Dict[str, Any]) -> Optional[Path]:
    work_dir = ctx.work_dir if isinstance(ctx.work_dir, Path) else Path.cwd()
    iso_path_cfg = svt_cfg.get('iso_path') if isinstance(svt_cfg, dict) else None
    glob_pattern = svt_cfg.get('iso_glob', 'SMTX_VMTOOLS-*.iso') if isinstance(svt_cfg, dict) else 'SMTX_VMTOOLS-*.iso'

    candidates: List[Path] = []
    if iso_path_cfg:
        path = Path(iso_path_cfg)
        if not path.is_absolute():
            path = work_dir / path
        candidates.append(path)

    if not candidates:
        versioned: List[tuple[tuple[int, ...], Path]] = []
        unversioned: List[Path] = []

        for path in work_dir.glob(glob_pattern):
            if not path.exists() or not path.is_file():
                continue
            version = _extract_vmtools_version(path.name)
            if version:
                versioned.append((version, path))
            else:
                unversioned.append(path)

        if versioned:
            # 优先选择版本号最高的文件，版本相同时按修改时间最新。
            versioned.sort(key=lambda item: (item[0], item[1].stat().st_mtime), reverse=True)
            candidates.append(versioned[0][1])
        elif unversioned:
            unversioned.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            candidates.append(unversioned[0])

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _extract_vmtools_version(name: str) -> Optional[tuple[int, ...]]:
    match = re.search(r"SMTX_VMTOOLS-([0-9]+(?:\.[0-9]+){0,2})", name)
    if not match:
        return None
    parts = match.group(1).split('.')
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    while len(numbers) < 3:
        numbers.append(0)
    return tuple(numbers)


def _create_svt_upload_volume(
    *,
    client: APIClient,
    headers: Dict[str, str],
    iso_path: Path,
    iso_size: int,
    chunk_size_fallback: int,
    stage_logger,
) -> Dict[str, Any]:
    params = {"name": iso_path.name, "size": iso_size}
    stage_logger.info(
        "创建 SVT 上传卷",
        progress_extra={"file_name": iso_path.name, "size": iso_size},
    )
    response = client.post("/api/v2/svt_image/create_volume", None, headers=headers, params=params, data={})
    data = _extract_data_dict(response)

    image_uuid = data.get("image_uuid") or data.get("uuid") or data.get("id")
    zbs_volume_id = data.get("zbs_volume_id") or data.get("volume_id")
    chunk_size = int(data.get("chunk_size") or chunk_size_fallback or DEFAULT_SVT_CHUNK_SIZE)
    if chunk_size <= 0:
        chunk_size = DEFAULT_SVT_CHUNK_SIZE
    to_upload = data.get("to_upload") if isinstance(data.get("to_upload"), list) else None

    if not image_uuid or not zbs_volume_id:
        raise RuntimeError("创建 SVT 上传卷响应缺少 image_uuid 或 zbs_volume_id")

    stage_logger.info(
        "SVT 上传卷创建成功",
        progress_extra={
            "image_uuid": image_uuid,
            "zbs_volume_id": zbs_volume_id,
            "chunk_size": chunk_size,
            "total_chunks": len(to_upload) if to_upload is not None else None,
        },
    )

    return {
        "image_uuid": image_uuid,
        "zbs_volume_id": zbs_volume_id,
        "chunk_size": chunk_size,
        "to_upload": to_upload or [],
        "image_path": data.get("image_path"),
    }


def _upload_svt_chunks(
    *,
    client: APIClient,
    headers: Dict[str, str],
    iso_path: Path,
    iso_size: int,
    volume_info: Dict[str, Any],
    stage_logger,
    chunk_retry: int = 2,
) -> Dict[str, Any]:
    image_uuid = volume_info["image_uuid"]
    zbs_volume_id = volume_info["zbs_volume_id"]
    chunk_size = int(volume_info.get("chunk_size") or DEFAULT_SVT_CHUNK_SIZE)
    if chunk_size <= 0:
        chunk_size = DEFAULT_SVT_CHUNK_SIZE

    sha256 = hashlib.sha256()
    uploaded_chunks = 0
    chunk_numbers: List[int] = []
    uploaded_bytes = 0
    total_chunks = len(volume_info.get("to_upload", [])) if isinstance(volume_info.get("to_upload"), list) else 0
    if chunk_size > 0:
        estimated_total = math.ceil(iso_size / chunk_size)
        if estimated_total:
            total_chunks = max(total_chunks, estimated_total)

    start_time = time.monotonic()
    last_log_time = start_time

    def _log_progress(current_chunk_index: int, remaining_chunks: Optional[int], *, force: bool = False) -> None:
        nonlocal last_log_time
        now = time.monotonic()
        if not force and (now - last_log_time) < 2:
            return
        elapsed = max(now - start_time, 1e-6)
        speed_bps = uploaded_bytes / elapsed if uploaded_bytes else 0.0
        progress_percent = (uploaded_bytes / iso_size * 100) if iso_size else None
        percentage: Optional[float] = None
        if total_chunks:
            percentage = (max(current_chunk_index, 0) / total_chunks) * 100
        elif progress_percent is not None:
            percentage = progress_percent
        if percentage is not None:
            percentage = max(0.0, min(percentage, 100.0))
        stage_logger.info(
            "SVT 上传进度",
            progress_extra={
                "chunk": max(current_chunk_index, 0),
                "total_chunks": total_chunks or None,
                "remaining_chunks": remaining_chunks,
                "uploaded_bytes": uploaded_bytes,
                "total_bytes": iso_size,
                "progress_percent": round(progress_percent, 2) if progress_percent is not None else None,
                "percentage": round(percentage, 2) if percentage is not None else None,
                "speed_bps": speed_bps,
            },
        )
        last_log_time = now

    with iso_path.open('rb') as iso_file:
        chunk_num = 0
        while True:
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

            attempt_error: Optional[Exception] = None
            for attempt in range(1, chunk_retry + 2):
                try:
                    response = client.post(
                        "/api/v2/svt_image/upload_template",
                        None,
                        headers=headers,
                        params=params,
                        files={"file": (iso_path.name, chunk, "application/octet-stream")},
                    )
                    attempt_error = None
                    break
                except Exception as exc:  # noqa: BLE001
                    attempt_error = exc
                    if attempt > chunk_retry:
                        break
                    stage_logger.warning(
                        "SVT 分片上传失败，重试中",
                        progress_extra={"chunk_num": chunk_num, "attempt": attempt, "error": str(exc)},
                    )
                    time.sleep(1)

            if attempt_error is not None:
                raise RuntimeError(f"上传 SVT 分片 {chunk_num} 失败: {attempt_error}") from attempt_error

            data = _extract_data_dict(response)
            to_upload = data.get("to_upload") if isinstance(data.get("to_upload"), list) else None
            remaining_chunks = len(to_upload) if to_upload is not None else None
            if remaining_chunks is not None and total_chunks:
                total_chunks = max(total_chunks, uploaded_chunks + remaining_chunks + 1)

            uploaded_chunks += 1
            chunk_numbers.append(chunk_num)
            _log_progress(uploaded_chunks, remaining_chunks, force=False)
            stage_logger.debug(
                "SVT 分片上传成功",
                progress_extra={"chunk_num": chunk_num, "remaining": remaining_chunks},
            )
            chunk_num += 1

    _log_progress(uploaded_chunks, 0, force=True)

    return {
        "image_uuid": image_uuid,
        "zbs_volume_id": zbs_volume_id,
        "chunk_size": chunk_size,
        "uploaded_chunks": uploaded_chunks,
        "sha256": sha256.hexdigest(),
        "chunk_numbers": chunk_numbers,
        "image_path": volume_info.get("image_path"),
    }


def _cleanup_svt_image(client: APIClient, headers: Dict[str, str], image_uuid: str, stage_logger) -> None:
    if not image_uuid:
        return
    try:
        client.delete(f"/api/v2/images/{image_uuid}", headers=headers)
        stage_logger.warning("已回滚 SVT 上传卷", progress_extra={"image_uuid": image_uuid})
    except Exception as exc:  # noqa: BLE001
        stage_logger.warning(
            "清理 SVT 上传卷失败",
            progress_extra={"image_uuid": image_uuid, "error": str(exc)},
        )


def _extract_data_dict(response: Any) -> Dict[str, Any]:
    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, dict):
            return data
        return response
    return {}
