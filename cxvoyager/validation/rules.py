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

"""详细验证规则：在基础模型校验后进行语义与冲突检查。"""
from __future__ import annotations
from typing import List, Set
from cxvoyager.models import PlanModel
from cxvoyager.utils.ip_utils import validate_cidrs, is_ipv6

ALLOWED_BOND = {"active-backup", "balance-tcp", "balance-slb"}


def validate_plan_model(model: PlanModel) -> dict:
    errors: List[str] = []
    warnings: List[str] = []

    if not model.hosts:
        errors.append("主机规划为空，无法继续部署")

    # 集群名称一致性
    cluster_names = {h.集群名称 for h in model.hosts if h.集群名称}
    if len(cluster_names) > 1:
        errors.append(f"主机规划中存在多个集群名称: {cluster_names}")

    # 绑定模式与子网
    cidrs: List[str] = []
    for row in model.virtual_network:
        if row.网口绑定模式 and row.网口绑定模式 not in ALLOWED_BOND:
            errors.append(f"无效绑定模式: {row.网口绑定模式}")
        if not row.subnetwork:
            warnings.append(f"虚拟交换机/网络 {row.虚拟交换机 or row.虚拟机网络} 未提供subnetwork")
        else:
            cidrs.append(row.subnetwork)

    # CIDR 校验 & 重叠检查
    _, cidr_errors, cidr_overlaps = validate_cidrs(cidrs)
    errors.extend(cidr_errors)
    warnings.extend(cidr_overlaps)

    # 管理信息
    if not model.mgmt:
        warnings.append("管理信息缺失（可能后续阶段受限）")
    else:
        if not model.mgmt.root密码:
            errors.append("缺少Cloudtower root密码")

    # 管理地址重复
    mgmt_ips = [str(h.管理地址) for h in model.hosts if h.管理地址]
    dup = {ip for ip in mgmt_ips if mgmt_ips.count(ip) > 1}
    if dup:
        errors.append(f"重复管理地址: {dup}")

    # VIP 与主机地址冲突
    vips: Set[str] = {str(h.集群VIP) for h in model.hosts if h.集群VIP}
    conflict = vips.intersection(mgmt_ips)
    if conflict:
        errors.append(f"VIP 与 管理地址冲突: {conflict}")

    # 额外：若有IPv6格式的VIP，但所有主机均无IPv6管理地址，提示警告
    if any(is_ipv6(v) for v in vips) and not any(':' in ip for ip in mgmt_ips):
        warnings.append("存在IPv6 VIP 但主机管理地址均非IPv6")

    return {"errors": errors, "warnings": warnings, "ok": not errors}

