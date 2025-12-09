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

# Stage 2 init_cluster – 初始化集群
from __future__ import annotations
import logging
import json
import time
from pathlib import Path
from threading import Event
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from cxvoyager.core.deployment.stage_manager import Stage, stage_handler, raise_if_aborted
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.common.config import load_config
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE
from cxvoyager.integrations.excel.planning_sheet_parser import parse_plan
from cxvoyager.core.deployment.host_discovery_scanner import get_host_scan_defaults, scan_hosts
from cxvoyager.core.deployment.payload_builder import generate_deployment_payload
from cxvoyager.integrations.smartx.api_client import APIClient, APIError
from cxvoyager.common.mock_scan_host import mock_scan_host
from cxvoyager.core.deployment.progress import create_stage_progress_logger

logger = logging.getLogger(__name__)

DEPLOY_SUCCESS_MESSAGE = "SUCCEEDED: A new cluster deploying task is on its way now."
VERIFY_POLL_INTERVAL = 5
VERIFY_MAX_ATTEMPTS = 12
INITIAL_PROGRESS_DELAY = 10

@stage_handler(Stage.init_cluster)
def handle_init_cluster(ctx_dict):
    ctx: RunContext = ctx_dict['ctx']
    stage_logger = create_stage_progress_logger(ctx, Stage.init_cluster.value, logger=logger, prefix="[init_cluster]")
    abort_signal = ctx_dict.get('abort_signal') or ctx.extra.get('abort_signal')
    if not ctx.plan:
        raise RuntimeError("缺少规划数据，需先执行prepare阶段")
    cfg = ctx.config or load_config(DEFAULT_CONFIG_FILE)
    api_cfg = cfg.get('api', {}) if isinstance(cfg, dict) else {}
    raw_host_scan_cfg = cfg.get('host_scan', {}) if isinstance(cfg, dict) else {}
    host_scan_cfg = raw_host_scan_cfg if isinstance(raw_host_scan_cfg, dict) else {}
    host_scan_defaults = get_host_scan_defaults()

    def _int_or_default(value, fallback):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    token = api_cfg.get('x-smartx-token')
    base_url = api_cfg.get('base_url')
    timeout = api_cfg.get('timeout')
    if timeout is None:
        timeout = host_scan_cfg.get('timeout')
    timeout = _int_or_default(timeout, host_scan_defaults['timeout'])

    max_retries = _int_or_default(host_scan_cfg.get('max_retries'), host_scan_defaults['max_retries'])
    max_retries = max(1, max_retries)

    # 默认值集中配置：timeout 优先读取 api.timeout，其次 host_scan.timeout，最终回退到 default.yml 中的 host_scan 段；
    # 重试次数来自 host_scan.max_retries。两个模块均在 default.yml 内注明引用关系。
    use_mock = bool(api_cfg.get('mock', False))

    host_info: Dict[str, Dict[str, Any]]
    warnings: list[str] = []

    if use_mock:
        stage_logger.warning("API mock 模式启用，将使用示例主机数据。")
        host_info = {}
        for idx, host in enumerate(ctx.plan.hosts):
            mgmt_ip = str(host.管理地址) if host.管理地址 else None
            base_ip = mgmt_ip or f"192.168.0.{10 + idx}"
            payload = mock_scan_host(base_ip)
            ifaces = payload.setdefault("ifaces", [])
            if not ifaces:
                ifaces.append({"name": "eth0", "ipv4": [], "ipv6": []})
            if mgmt_ip:
                ifaces[0].setdefault("ipv4", [])
                ifaces[0]["ipv4"] = [mgmt_ip]
                payload["host_ip"] = mgmt_ip
            host_key = payload.get("host_ip", base_ip)
            host_info[host_key] = payload
        warnings.append("mock 模式使用内建示例数据，请勿用于生产部署。")
    else:
        host_info, warnings = scan_hosts(
            ctx.plan,
            token=token,
            timeout=timeout,
            max_retries=max_retries,
            base_url=base_url,
        )
        for msg in warnings:
            stage_logger.warning("主机扫描警告", progress_extra={"warning": msg})
        if not host_info:
            detail = "；".join(warnings) if warnings else "未获取到任何主机信息，请检查网络连接和配置后重试。"
            raise RuntimeError(f"主机扫描失败：{detail}")

    ctx.extra['host_scan'] = host_info
    if warnings:
        ctx.extra.setdefault('warnings', []).extend(warnings)
    stage_logger.info("主机扫描完成", progress_extra={"hosts": list(host_info.keys())})

    # 使用载荷生成器构建完整的部署载荷
    parsed_plan = None
    if hasattr(ctx.plan, 'source_file') and ctx.plan.source_file:
        try:
            parsed_plan = parse_plan(Path(ctx.plan.source_file))
            stage_logger.info(
                "重新解析规划表获取网络配置",
                progress_extra={"source": ctx.plan.source_file},
            )
            ctx.extra['parsed_plan'] = parsed_plan
        except Exception as exc:  # noqa: BLE001 - 仅记录告警
            stage_logger.warning("无法重新解析规划表", progress_extra={"error": str(exc)})

    try:
        deploy_payload_dict, artifact_path = generate_deployment_payload(
            plan=ctx.plan,
            host_scan_data=host_info,
            parsed_plan=parsed_plan,
        )
    except Exception as exc:  # noqa: BLE001
        stage_logger.exception("部署载荷生成失败")
        raise RuntimeError("生成部署载荷失败，请检查规划表和主机扫描数据。") from exc

    ctx.extra['deploy_payload'] = deploy_payload_dict
    ctx.extra.setdefault('artifacts', {})['deploy_payload'] = str(artifact_path)
    stage_logger.info(
        "部署载荷构建完成",
        progress_extra={
            "cluster": deploy_payload_dict.get('cluster_name'),
            "host_count": len(deploy_payload_dict.get('hosts', [])),
            "artifact": str(artifact_path),
        },
    )

    # 调用部署 API 触发集群初始化
    raise_if_aborted(ctx_dict, abort_signal=abort_signal, stage_logger=stage_logger, hint="准备调用部署接口")

    deploy_response = _trigger_cluster_deployment(
        payload=deploy_payload_dict,
        host_info=host_info,
        token=token,
        timeout=timeout,
        base_url_override=base_url,
        use_mock=use_mock,
        stage_logger=stage_logger,
    )

    ctx.extra['deploy_response'] = deploy_response
    stage_logger.info(
        "部署接口调用完成",
        progress_extra={"response_preview": json.dumps(deploy_response, ensure_ascii=False)[:400]},
    )

    deploy_cfg = cfg.get('deploy', {}) if isinstance(cfg, dict) else {}
    poll_interval_cfg = deploy_cfg.get('poll_interval')
    max_attempts_cfg = deploy_cfg.get('max_attempts')
    if poll_interval_cfg is None:
        poll_interval_cfg = deploy_cfg.get('verify_interval')
    if max_attempts_cfg is None:
        max_attempts_cfg = deploy_cfg.get('verify_max_attempts')

    poll_interval = int(poll_interval_cfg or 5)
    max_attempts = int(max_attempts_cfg or 60)

    raise_if_aborted(ctx_dict, abort_signal=abort_signal, stage_logger=stage_logger, hint="开始等待部署进度")

    verify_response = _wait_for_deployment_completion(
        host_info=host_info,
        token=token,
        timeout=timeout,
        base_url_override=base_url,
        use_mock=use_mock,
        poll_interval=max(1, poll_interval),
        max_attempts=max(1, max_attempts),
        stage_logger=stage_logger,
        ctx_dict=ctx_dict,
        abort_signal=abort_signal,
    )
    ctx.extra['deploy_verify'] = verify_response
    stage_logger.info(
        "部署状态校验完成",
        progress_extra={"is_deployed": verify_response.get("data", {}).get("is_deployed")},
    )


def _trigger_cluster_deployment(
    *,
    payload: Dict[str, Any],
    host_info: Dict[str, Dict[str, Any]],
    token: str | None,
    timeout: int,
    base_url_override: str | None,
    use_mock: bool,
    stage_logger: logging.LoggerAdapter,
) -> Dict[str, Any]:
    base_url, host_header = _resolve_deployment_base(base_url_override, host_info)
    client = APIClient(base_url=base_url, mock=use_mock, timeout=timeout)

    headers = {"content-type": "application/json"}
    if host_header:
        headers["host"] = host_header
    if token:
        headers["x-smartx-token"] = token

    stage_logger.info(
        "调用部署接口",
        progress_extra={"base_url": base_url.rstrip('/'), "path": "/api/v2/deployment/cluster"},
    )
    try:
        response = client.post("/api/v2/deployment/cluster", payload=payload, headers=headers)
    except APIError as exc:
        stage_logger.exception("部署接口返回错误", progress_extra={"error": str(exc)})
        raise RuntimeError(f"部署接口返回错误: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - 网络等异常
        stage_logger.exception("调用部署接口失败", progress_extra={"error": str(exc)})
        raise RuntimeError(f"调用部署接口失败: {exc}") from exc

    normalized = _normalize_deploy_response(response, use_mock)
    if _is_deploy_success(normalized):
        return normalized

    # 其它返回均视为失败，保留原始响应以便展示
    detail = json.dumps(response, ensure_ascii=False, indent=2) if isinstance(response, dict) else str(response)
    raise RuntimeError(f"部署接口返回错误: {detail}")


def _wait_for_deployment_completion(
    *,
    host_info: Dict[str, Dict[str, Any]],
    token: str | None,
    timeout: int,
    base_url_override: str | None,
    use_mock: bool,
    poll_interval: int,
    max_attempts: int,
    stage_logger: logging.LoggerAdapter,
    ctx_dict: Dict[str, Any] | None = None,
    abort_signal: Event | None = None,
) -> Dict[str, Any]:
    ctx_view = ctx_dict or {}

    raise_if_aborted(ctx_view, abort_signal=abort_signal, stage_logger=stage_logger, hint="准备轮询部署进展")

    if use_mock:
        stage_logger.info("mock 模式下跳过部署状态轮询，直接视为成功。")
        return {"data": {"is_deployed": True, "platform": "mock"}, "ec": "EOK", "error": {}}

    base_url, host_header = _resolve_deployment_base(base_url_override, host_info)
    client = APIClient(base_url=base_url, mock=use_mock, timeout=timeout)
    headers = {}
    if host_header:
        headers["host"] = host_header
    if token:
        headers["x-smartx-token"] = token

    host_ip_param = _resolve_host_ip_param(base_url, host_header, host_info)
    progress_completed = False
    last_progress: Dict[str, Any] | None = None

    if INITIAL_PROGRESS_DELAY > 0:
        raise_if_aborted(ctx_view, abort_signal=abort_signal, stage_logger=stage_logger, hint="等待首次进度轮询")
        message = f"部署任务已提交，等待 {INITIAL_PROGRESS_DELAY} 秒后开始查询主机进度"
        stage_logger.info(message)
        time.sleep(INITIAL_PROGRESS_DELAY)
        raise_if_aborted(ctx_view, abort_signal=abort_signal, stage_logger=stage_logger, hint="首次进度轮询前")

    for attempt in range(1, max_attempts + 1):
        raise_if_aborted(ctx_view, abort_signal=abort_signal, stage_logger=stage_logger, hint="部署进度轮询")
        should_wait = True
        try:
            response = client.get(
                "/api/v2/deployment/host/deploy_status",
                params={"host_ip": host_ip_param} if host_ip_param else None,
                headers=headers,
            )
        except APIError as exc:
            last_progress = {"error": str(exc)}
            if attempt < max_attempts:
                message = (
                    f"部署进度查询失败({attempt}/{max_attempts}): {exc}，将在 {poll_interval} 秒后重试"
                )
                stage_logger.warning(
                    "部署进度查询失败，稍后重试",
                    progress_extra={"attempt": attempt, "max_attempts": max_attempts, "error": str(exc)},
                )
            else:
                message = (
                    f"部署进度查询失败({attempt}/{max_attempts}): {exc}，已达到最大重试次数"
                )
                stage_logger.error(
                    "部署进度查询失败，已达到最大重试次数",
                    progress_extra={"attempt": attempt, "max_attempts": max_attempts, "error": str(exc)},
                )
                progress_completed = True
                should_wait = False
        except Exception as exc:  # noqa: BLE001
            last_progress = {"exception": str(exc)}
            if attempt < max_attempts:
                message = (
                    f"部署进度查询异常({attempt}/{max_attempts}): {exc}，将在 {poll_interval} 秒后重试"
                )
                stage_logger.warning(
                    "部署进度查询异常，稍后重试",
                    progress_extra={"attempt": attempt, "max_attempts": max_attempts, "error": str(exc)},
                )
            else:
                message = (
                    f"部署进度查询异常({attempt}/{max_attempts}): {exc}，已达到最大重试次数"
                )
                stage_logger.error(
                    "部署进度查询异常，已达到最大重试次数",
                    progress_extra={"attempt": attempt, "max_attempts": max_attempts, "error": str(exc)},
                )
                progress_completed = True
                should_wait = False
        else:
            progress = response if isinstance(response, dict) else {}
            last_progress = progress
            state = _extract_deploy_progress_state(progress)
            has_error = _progress_has_error(progress)
            stage_info = None
            data = progress.get("data") if isinstance(progress, dict) else None
            if isinstance(data, dict):
                stage_info = data.get("stage_info")

            if has_error:
                info_detail = json.dumps(progress.get("error"), ensure_ascii=False)[:400]
                message = (
                    f"初始化结束({attempt}/{max_attempts}): state={state}, response={info_detail}"
                )
                stage_logger.info(
                    "部署进度返回结束",
                    progress_extra={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "state": state,
                        "stage_info": stage_info,
                        "info_detail": info_detail,
                    },
                )
                progress_completed = True
                should_wait = False
            elif state is None:
                snapshot = json.dumps(progress, ensure_ascii=False)[:400]
                message = (
                    f"部署进度响应缺少 state 字段({attempt}/{max_attempts})，将继续等待: {snapshot}"
                )
                stage_logger.info(
                    "部署进度缺少 state 字段，继续等待",
                    progress_extra={"attempt": attempt, "max_attempts": max_attempts},
                )
            elif "running" in state:
                message = (
                    f"部署进度轮询({attempt}/{max_attempts}): state={state}, stage={stage_info}"
                )
                stage_logger.info(
                    "部署进度轮询",
                    progress_extra={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "state": state,
                        "stage_info": stage_info,
                    },
                )
            else:
                message = (
                    f"部署进度阶段已结束({attempt}/{max_attempts}): state={state}, stage={stage_info}"
                )
                stage_logger.info(
                    "部署进度阶段已结束",
                    progress_extra={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "state": state,
                        "stage_info": stage_info,
                    },
                )
                progress_completed = True
                should_wait = False

        if progress_completed:
            break

        if attempt < max_attempts and should_wait:
            raise_if_aborted(ctx_view, abort_signal=abort_signal, stage_logger=stage_logger, hint="等待下一次进度轮询")
            stage_logger.info(
                "部署进度仍在进行，将在稍后重试",
                progress_extra={"poll_interval": poll_interval, "attempt": attempt, "max_attempts": max_attempts},
            )
            time.sleep(poll_interval)
            raise_if_aborted(ctx_view, abort_signal=abort_signal, stage_logger=stage_logger, hint="进度轮询等待期间")

    if not progress_completed:
        detail = json.dumps(last_progress, ensure_ascii=False, indent=2) if last_progress else "无有效响应"
        raise RuntimeError(f"部署进度仍处于运行状态，超出最大轮询次数: {detail}")

    last_response: Dict[str, Any] | None = None
    for attempt in range(1, VERIFY_MAX_ATTEMPTS + 1):
        raise_if_aborted(ctx_view, abort_signal=abort_signal, stage_logger=stage_logger, hint="部署状态校验")
        try:
            response = client.get("/api/v2/deployment/deploy_verify", headers=headers)
        except APIError as exc:
            message = f"校验部署状态失败({attempt}/{VERIFY_MAX_ATTEMPTS}): {exc}"
            stage_logger.warning(
                "部署状态校验失败，稍后重试",
                progress_extra={"attempt": attempt, "max_attempts": VERIFY_MAX_ATTEMPTS, "error": str(exc)},
            )
            last_response = {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - 记录并继续轮询
            message = f"校验部署状态异常({attempt}/{VERIFY_MAX_ATTEMPTS}): {exc}"
            stage_logger.warning(
                "部署状态校验异常，稍后重试",
                progress_extra={"attempt": attempt, "max_attempts": VERIFY_MAX_ATTEMPTS, "error": str(exc)},
            )
            last_response = {"exception": str(exc)}
        else:
            normalized = _normalize_deploy_verify_response(response, use_mock)
            last_response = normalized
            status = _extract_is_deployed(normalized)
            message = f"部署状态轮询({attempt}/{VERIFY_MAX_ATTEMPTS}): is_deployed={status}"
            stage_logger.debug(
                "部署状态轮询",
                progress_extra={"attempt": attempt, "max_attempts": VERIFY_MAX_ATTEMPTS, "is_deployed": status},
            )
            if status is True:
                stage_logger.info("部署验证通过，集群已成功部署")
                return normalized
            if status is False and _response_has_error(normalized):
                detail = json.dumps(normalized, ensure_ascii=False, indent=2)
                stage_logger.error("部署验证失败", progress_extra={"detail": detail})
                raise RuntimeError(f"部署验证失败: {detail}")

        if attempt < VERIFY_MAX_ATTEMPTS:
            stage_logger.info(
                "部署验证未完成，将在稍后重试",
                progress_extra={"poll_interval": VERIFY_POLL_INTERVAL, "attempt": attempt},
            )
            time.sleep(VERIFY_POLL_INTERVAL)

    detail = json.dumps(last_response, ensure_ascii=False, indent=2) if last_response else "无有效响应"
    stage_logger.error("部署状态未在预期时间内成功", progress_extra={"detail": detail})
    raise RuntimeError(f"部署状态未在预期时间内成功: {detail}")


def _normalize_deploy_verify_response(response: Any, use_mock: bool) -> Dict[str, Any]:
    if use_mock and isinstance(response, dict) and response.get("ok"):
        return {"data": {"is_deployed": True, "platform": "mock"}, "ec": "EOK", "error": {}}
    return response if isinstance(response, dict) else {}


def _extract_is_deployed(response: Dict[str, Any]) -> Optional[bool]:
    if not isinstance(response, dict):
        return None
    if response.get("error") not in ({}, None):
        return False
    data = response.get("data")
    if isinstance(data, dict):
        value = data.get("is_deployed")
        if isinstance(value, bool):
            return value
    return None


def _response_has_error(response: Dict[str, Any]) -> bool:
    error = response.get("error") if isinstance(response, dict) else None
    if not error:
        return False
    if isinstance(error, dict):
        return bool(error)
    return True


def _resolve_host_ip_param(base_url: str, host_header: str | None, host_info: Dict[str, Dict[str, Any]]) -> Optional[str]:
    if host_header:
        return host_header
    parsed = urlparse(base_url)
    if parsed.hostname:
        return parsed.hostname
    if host_info:
        first = next(iter(host_info.keys()), None)
        if first:
            return str(first)
    return None


def _extract_deploy_progress_state(response: Dict[str, Any]) -> Optional[str]:
    if not isinstance(response, dict):
        return None
    data = response.get("data")
    if isinstance(data, dict):
        state = data.get("state")
        if isinstance(state, str):
            normalized = state.strip().lower()
            return normalized if normalized else None
    return None


def _progress_has_error(response: Dict[str, Any]) -> bool:
    if not isinstance(response, dict):
        return False
    error = response.get("error")
    if not error:
        return False
    if isinstance(error, dict):
        return any(_has_meaningful_value(value) for value in error.values())
    if isinstance(error, (list, tuple, set)):
        return any(_has_meaningful_value(value) for value in error)
    return bool(error)


def _has_meaningful_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return any(_has_meaningful_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_meaningful_value(item) for item in value.values())
    return bool(value)


def _resolve_deployment_base(base_url_override: str | None, host_info: Dict[str, Dict[str, Any]]) -> tuple[str, str | None]:
    if base_url_override:
        candidate = base_url_override.strip()
        parsed = urlparse(candidate)
        if not parsed.scheme:
            candidate = f"http://{candidate}"
            parsed = urlparse(candidate)
        host_header = parsed.hostname or None
        return candidate.rstrip('/'), host_header

    if host_info:
        mgmt_ip = next(iter(host_info.keys()))
        if mgmt_ip:
            return f"http://{mgmt_ip}", mgmt_ip

    raise RuntimeError("无法确定部署 API 基础地址，请在配置文件中提供 api.base_url 或检查主机扫描结果。")


def _normalize_deploy_response(response: Any, use_mock: bool) -> Dict[str, Any]:
    if not isinstance(response, dict):
        return {}
    if use_mock and response.get("ok") is True:
        return {"data": {"msg": DEPLOY_SUCCESS_MESSAGE}, "ec": "EOK", "error": {}}
    return response


def _is_deploy_success(response: Dict[str, Any]) -> bool:
    if not isinstance(response, dict):
        return False
    if response.get("error") not in ({}, None):
        return False
    data = response.get("data")
    if not isinstance(data, dict):
        return False
    return data.get("msg") == DEPLOY_SUCCESS_MESSAGE

