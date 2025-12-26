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

"""Helpers for scanning host inventory via platform APIs."""
from __future__ import annotations

import json
import logging
import re
import time
from functools import lru_cache
from typing import Dict, List, Tuple, Set

from tenacity import RetryError

from cxvoyager.common.config import load_config
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE
from cxvoyager.integrations.smartx.api_client import APIClient, APIError
from cxvoyager.models.planning_sheet_models import PlanModel
from cxvoyager.common.parallel_utils import parallel_map
from cxvoyager.common.i18n import tr

logger = logging.getLogger(__name__)


@lru_cache()
def _load_host_scan_defaults() -> Dict[str, int]:
    """读取主机扫描的默认配置。

    默认值集中维护在 ``common/config/default.yml`` 的 ``host_scan`` 段落中，
    便于跨模块统一管理。函数使用 LRU 缓存避免重复解析配置文件。
    """

    cfg = load_config(DEFAULT_CONFIG_FILE)
    cfg_dict = cfg if isinstance(cfg, dict) else {}
    host_cfg = cfg_dict.get("host_scan", {}) if isinstance(cfg_dict, dict) else {}

    def _parse_int(value, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    timeout = _parse_int(host_cfg.get("timeout"), 10)
    retries = max(1, _parse_int(host_cfg.get("max_retries"), 3))
    return {"timeout": timeout, "max_retries": retries}


def get_host_scan_defaults() -> Dict[str, int]:
    """返回主机扫描默认配置的副本，供其它模块复用。"""

    return dict(_load_host_scan_defaults())

ROLE_LABELS: Dict[str, str] = {
    "mgmt": "管理网卡",
    "storage": "存储网卡",
    "backup": "备份网卡",
    "business": "业务网卡",
}


def _normalize_iface_name(name: str | None) -> str:
    return str(name or "").strip().lower()


def _split_nic_names(value) -> Set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        tokens = re.split(r"[\s,;/\\，、]+", value)
    else:
        tokens = []
        for item in value:
            if item is None:
                continue
            if isinstance(item, str):
                tokens.extend(re.split(r"[\s,;/\\，、]+", item))
            else:
                tokens.append(str(item))
    return {token.strip() for token in tokens if token and token.strip()}


def _infer_network_role(row) -> str:
    hints = [getattr(row, "虚拟交换机", None), getattr(row, "虚拟机网络", None)]
    for hint in hints:
        if not hint:
            continue
        hint_lower = str(hint).lower()
        if any(key in hint_lower for key in ("guanli", "mgt", "mgmt", "management", "管理")):
            return "mgmt"
        if any(key in hint_lower for key in ("sds", "stor", "storage", "存储", "data")):
            return "storage"
        if any(key in hint_lower for key in ("back-up", "bakup", "bak", "backup", "备份")):
            return "backup"
        if any(key in hint_lower for key in ("busines", "production", "product", "vmnetwork", "yewu", "shengchan", "prd", "prod", "bizs", "business", "业务")):
            return "business"
    return "unknown"


def _collect_required_nics(model: PlanModel) -> Dict[str, Set[str]]:
    required: Dict[str, Set[str]] = {role: set() for role in ROLE_LABELS}
    for row in getattr(model, "virtual_network", []) or []:
        nic_names = _split_nic_names(getattr(row, "主机端口", None))
        if not nic_names:
            continue
        role = _infer_network_role(row)
        if role in required:
            required[role].update(nic_names)
    return required


def _validate_host_data(data: dict, required_ifaces: Dict[str, Set[str]] | None = None) -> Tuple[bool, List[str]]:
    """验证主机数据是否完整。"""

    required_ifaces = required_ifaces or {}
    errors: List[str] = []

    if "data" in data and isinstance(data["data"], dict):
        host_data = data["data"]
    else:
        host_data = data

    if not isinstance(host_data, dict):
        msg = tr("deploy.host_scan.invalid_response_format")
        logger.warning(msg)
        return False, [msg]

    required_fields = ["host_ip", "host_uuid", "hostname", "ifaces", "disks"]
    for field in required_fields:
        if field not in host_data or host_data[field] is None:
            msg = tr("deploy.host_scan.missing_field", field=field)
            logger.warning(msg)
            errors.append(msg)

    host_uuid = host_data.get("host_uuid", "")
    if not isinstance(host_uuid, str) or len(host_uuid) < 32:
        msg = tr("deploy.host_scan.invalid_host_uuid", host_uuid=host_uuid)
        logger.warning(msg)
        errors.append(msg)

    ifaces = host_data.get("ifaces", [])
    available_nics: Set[str] = set()
    if not isinstance(ifaces, list) or len(ifaces) == 0:
        msg = tr("deploy.host_scan.iface_data_invalid")
        logger.warning(msg)
        errors.append(msg)
        ifaces = []

    for iface in ifaces:
        if not isinstance(iface, dict):
            continue
        required_iface_fields = ["name", "hwaddr"]
        missing_fields = [f for f in required_iface_fields if not iface.get(f)]
        if missing_fields:
            msg = tr("deploy.host_scan.iface_missing_fields", missing=", ".join(missing_fields), iface=iface)
            logger.warning(msg)
            errors.append(msg)
        iface_name = iface.get("name")
        if iface_name:
            available_nics.add(_normalize_iface_name(iface_name))

    for role, expected in required_ifaces.items():
        if not expected:
            continue
        missing = [name for name in expected if _normalize_iface_name(name) not in available_nics]
        if missing:
            label = ROLE_LABELS.get(role, f"{role} 网卡")
            msg = tr("deploy.host_scan.required_ifaces_missing", label=label, missing=", ".join(sorted(missing)))
            logger.warning(msg)
            errors.append(msg)

    disks_raw = host_data.get("disks", [])
    if not isinstance(disks_raw, list) or len(disks_raw) == 0:
        msg = tr("deploy.host_scan.disk_data_invalid")
        logger.warning(msg)
        errors.append(msg)
        disks = disks_raw if isinstance(disks_raw, list) else []
    else:
        disks = disks_raw

    has_boot_disk = False
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        required_disk_fields = ["drive", "function", "model", "serial", "size", "type"]
        for field in required_disk_fields:
            if field not in disk or disk[field] is None:
                msg = tr("deploy.host_scan.disk_missing_field", field=field, disk=disk)
                logger.warning(msg)
                errors.append(msg)
        size = disk.get("size")
        if not isinstance(size, (int, float)) or size <= 0:
            msg = tr("deploy.host_scan.disk_invalid_size", disk=disk)
            logger.warning(msg)
            errors.append(msg)
        disk_type = disk.get("type")
        if disk_type not in ["SSD", "HDD"]:
            msg = tr("deploy.host_scan.disk_invalid_type", disk_type=disk_type)
            logger.warning(msg)
            errors.append(msg)
        if disk.get("function") in ["boot", "system"]:
            has_boot_disk = True

    if disks and not has_boot_disk:
        msg = tr("deploy.host_scan.missing_boot_disk")
        logger.warning(msg)
        errors.append(msg)

    optional_fields = ["sn", "product", "version", "status"]
    for field in optional_fields:
        if field in host_data and not isinstance(host_data[field], str):
            logger.warning(tr("deploy.host_scan.field_should_be_str", field=field, type=type(host_data[field])))

    if errors:
        return False, errors

    return True, []


def _scan_single_host(
    host,
    *,
    token: str | None,
    timeout: int,
    max_retries: int,
    base_override: str | None,
    required_ifaces: Dict[str, Set[str]] | None = None,
) -> Tuple[str, Dict]:
    mgmt_ip = str(host.管理地址) if host.管理地址 else None
    if not mgmt_ip:
        raise ValueError(f"主机 {host.SMTX主机名 or '?'} 缺少管理地址，无法扫描")

    base_url = base_override or f"http://{mgmt_ip}"
    client = APIClient(base_url=base_url, mock=False, timeout=timeout)

    headers = {"content-type": "application/json", "host": mgmt_ip}
    if token:
        headers["x-smartx-token"] = token

    logger.debug(tr("deploy.host_scan.start_scan", ip=mgmt_ip, base_url=base_url))
    
    # 重试逻辑
    last_exception: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(tr("deploy.host_scan.retry_scan", ip=mgmt_ip, attempt=attempt))
            data = client.get("/api/v2/deployment/host", headers=headers)
            
            if not isinstance(data, dict):
                raise RuntimeError(f"扫描 {mgmt_ip} 返回的不是 JSON 对象")
            
            # debug级别记录完整的JSON响应
            logger.debug(tr("deploy.host_scan.response_debug", ip=mgmt_ip, payload=json.dumps(data, ensure_ascii=False, indent=2)))
            
            # 验证数据完整性
            valid, validation_errors = _validate_host_data(data, required_ifaces=required_ifaces)
            if valid:
                logger.info(tr("deploy.host_scan.scan_success", ip=mgmt_ip))
                # 如果数据结构有data字段，需要提取出来
                if "data" in data and isinstance(data["data"], dict):
                    return mgmt_ip, data["data"]
                else:
                    return mgmt_ip, data
            else:
                detail = "；".join(validation_errors) if validation_errors else "数据验证失败"
                logger.warning(tr("deploy.host_scan.validation_failed_attempt", ip=mgmt_ip, attempt=attempt, detail=detail))
                if attempt < max_retries:
                    time.sleep(1)  # 等待1秒后重试
                    continue
                else:
                    raise RuntimeError(f"数据校验失败: {detail}")
                    
        except Exception as exc:
            root_exc = _unwrap_retry_error(exc)
            last_exception = root_exc

            message = str(root_exc)
            if isinstance(root_exc, APIError):
                logger.warning(tr("deploy.host_scan.api_retry_fail", ip=mgmt_ip, attempt=attempt, error=message))
            else:
                logger.warning(tr("deploy.host_scan.retry_fail", ip=mgmt_ip, attempt=attempt, error=message))
            if attempt < max_retries:
                time.sleep(1)  # 等待1秒后重试
                continue
            else:
                break
    
    # 所有重试都失败了
    error_msg = tr("deploy.host_scan.final_error", ip=mgmt_ip, retries=max_retries)
    if last_exception:
        error_detail = str(last_exception)
        if error_detail:
            error_msg += f": {error_detail}"

        if _is_auth_failure(last_exception):
            error_msg += " " + tr("deploy.host_scan.auth_hint")
    raise RuntimeError(error_msg)


def _unwrap_retry_error(exc: Exception) -> Exception:
    if isinstance(exc, RetryError):
        last_attempt = getattr(exc, "last_attempt", None)
        if last_attempt and last_attempt.exception():
            return last_attempt.exception()
        return exc
    return exc


def _is_auth_failure(exc: Exception) -> bool:
    if isinstance(exc, APIError):
        message = str(exc)
    else:
        message = str(exc)

    lowered = message.lower()
    return "status=401" in lowered or "status=403" in lowered


def scan_hosts(
    model: PlanModel,
    *,
    token: str | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
    base_url: str | None = None,
    max_workers: int | None = None,
) -> Tuple[Dict[str, dict], List[str]]:
    """Scan all hosts defined in *model* and return inventory payloads.

    Parameters
    ----------
    model:
        Parsed planning model providing host metadata.
    token:
        Optional authentication token for SmartX APIs.
    timeout:
        HTTP timeout per request in seconds. 默认为配置项 ``host_scan.timeout``。
    max_retries:
        最大重试次数。默认为配置项 ``host_scan.max_retries``。
    base_url:
        Optional override base URL. When omitted each host is accessed via ``http://<mgmt_ip>``.
    max_workers:
        Optional worker pool size for parallel scans. Defaults to ``min(8, host_count)``.

    Returns
    -------
    tuple(dict, list[str])
        The host inventory keyed by management IP and a list of warning messages.
    """

    if not model.hosts:
        return {}, []

    defaults = _load_host_scan_defaults()
    effective_timeout = defaults["timeout"] if timeout is None else int(timeout)
    effective_retries = defaults["max_retries"] if max_retries is None else max(1, int(max_retries))

    warnings: List[str] = []
    results: Dict[str, dict] = {}
    required_ifaces = _collect_required_nics(model)

    worker_count = max_workers or min(8, max(len(model.hosts), 1))

    def _worker(host):
        try:
            return _scan_single_host(
                host,
                token=token,
                timeout=effective_timeout,
                max_retries=effective_retries,
                base_override=base_url,
                required_ifaces=required_ifaces,
            )
        except Exception as exc:  # noqa: BLE001 - surface to aggregator
            message = tr(
                "deploy.host_scan.worker_failure",
                host=host.SMTX主机名 or host.管理地址 or "?",
                error=exc,
            )
            logger.warning(message)
            return RuntimeError(message)

    for outcome in parallel_map(_worker, model.hosts, max_workers=worker_count):
        if isinstance(outcome, Exception):
            logger.warning(tr("deploy.host_scan.aggregate_failure", error=outcome))
            warnings.append(str(outcome))
            continue
        host_ip, payload = outcome
        results[host_ip] = payload

    return results, warnings