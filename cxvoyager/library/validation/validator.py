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

"""数据验证模块。"""
from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import Any, Dict, Iterable, List, Tuple

from .rules import validate_plan_model
from cxvoyager.library.integrations.excel.planning_sheet_parser import to_model


def _collect_component_ips(mgmt_record: Dict[str, Any]) -> List[str]:
    candidates: List[str] = []
    for key in ("Cloudtower IP", "OBS IP", "备份 IP", "ER 控制器集群VIP"):
        value = mgmt_record.get(key)
        if value:
            candidates.append(str(value).strip())

    node_ips = mgmt_record.get("ER 控制器节点IP列表")
    if isinstance(node_ips, str):
        node_iter = [part.strip() for part in node_ips.split(",") if part.strip()]
    elif isinstance(node_ips, Iterable):
        node_iter = [str(part).strip() for part in node_ips if str(part).strip()]
    else:
        node_iter = []
    candidates.extend(node_iter)

    # 去重同时保持原有顺序
    seen = set()
    deduped: List[str] = []
    for ip in candidates:
        if ip and ip not in seen:
            deduped.append(ip)
            seen.add(ip)
    return deduped


def _check_ips_within_network(ips: Iterable[str], cidr: str, label: str) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    try:
        network = ip_network(cidr, strict=False)
    except ValueError:
        errors.append(f"{label} 子网 {cidr} 非法，无法校验管理组件 IP")
        return errors, warnings

    for ip_str in ips:
        try:
            addr = ip_address(ip_str)
        except ValueError:
            errors.append(f"管理组件 IP {ip_str} 非法，无法校验所属网络")
            continue
        if addr not in network:
            errors.append(f"管理组件 IP {ip_str} 不在 {label} {cidr} 范围内")
    return errors, warnings


def _check_ips_in_any_network(ips: Iterable[str], cidrs: List[str]) -> List[str]:
    """验证 IP 是否至少落在任一声明的子网中。"""

    if not cidrs:
        return []

    networks = []
    for cidr in cidrs:
        try:
            networks.append(ip_network(cidr, strict=False))
        except ValueError:
            # 非法子网会在前置校验中报错，这里忽略以避免重复。
            continue

    errors: List[str] = []
    for ip_str in ips:
        try:
            addr = ip_address(ip_str)
        except ValueError:
            errors.append(f"管理组件 IP {ip_str} 非法，无法校验所属网络")
            continue
        if not any(addr in net for net in networks):
            errors.append(
                f"管理组件 IP {ip_str} 未落在任何声明的子网 {', '.join(sorted({n.with_prefixlen for n in networks}))} 内"
            )
    return errors


def _validate_management_components(parsed: Dict[str, Any]) -> Tuple[List[str], List[str], Dict[str, Any] | None]:
    vn_section = parsed.get("virtual_network", {})
    vn_records = vn_section.get("records", []) if isinstance(vn_section, dict) else []

    mgmt_section = parsed.get("mgmt", {})
    mgmt_records = mgmt_section.get("records", []) if isinstance(mgmt_section, dict) else []
    if not mgmt_records:
        return [], [], None

    mgmt_record = mgmt_records[0]
    component_ips = _collect_component_ips(mgmt_record)
    if not component_ips:
        return [], [], {"component_ips": []}

    default_record = next((r for r in vn_records if r.get("网络标识") == "default"), None)
    extra_record = next((r for r in vn_records if r.get("网络标识") == "extra_mgmt"), None)

    errors: List[str] = []
    warnings: List[str] = []
    details: Dict[str, Any] = {
        "component_ips": component_ips,
    }

    cidr_pool = [r.get("subnetwork") for r in vn_records if r.get("subnetwork")]

    if extra_record:
        extra_cidr = extra_record.get("subnetwork")
        details["expected_network"] = {"type": "extra_mgmt", "cidr": extra_cidr}
        if not extra_cidr:
            errors.append("额外管理网络已配置但缺少子网，无法校验管理组件 IP")
        else:
            net_errors, net_warnings = _check_ips_within_network(component_ips, extra_cidr, "额外管理网络")
            errors.extend(net_errors)
            warnings.extend(net_warnings)
    else:
        default_cidr = default_record.get("subnetwork") if default_record else None
        details["expected_network"] = {"type": "default", "cidr": default_cidr}
        if not default_cidr:
            warnings.append("默认管理网络缺少子网，无法校验管理组件 IP")
        else:
            net_errors, net_warnings = _check_ips_within_network(component_ips, default_cidr, "默认管理网络")
            errors.extend(net_errors)
            warnings.extend(net_warnings)

    # 补充校验：至少落在任一声明的子网内，防止标识错误导致漏检。
    errors.extend(_check_ips_in_any_network(component_ips, cidr_pool))

    return errors, warnings, details


def validate(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """综合验证：基础结构 + 模型规则。"""
    # 基础结构统计
    summary = {}
    for section in ("virtual_network", "hosts", "mgmt"):
        sec = parsed.get(section, {})
        if isinstance(sec, dict) and "records" in sec:
            summary[section] = len(sec.get("records", []))

    model = to_model(parsed)
    rule_report = validate_plan_model(model)
    errors = rule_report.setdefault("errors", [])
    warnings = rule_report.setdefault("warnings", [])

    net_errors, net_warnings, net_details = _validate_management_components(parsed)
    errors.extend(net_errors)
    warnings.extend(net_warnings)
    if net_details is not None:
        rule_report["management_network"] = net_details

    rule_report["ok"] = not errors
    rule_report["summary"] = summary
    return rule_report

