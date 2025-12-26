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

"""IP / CIDR / 网络相关辅助函数。

提供：
* is_ipv4 / is_ipv6
* parse_cidr -> (network_obj)
* cidr_overlap 判断两个CIDR是否重叠
* validate_cidrs 返回(有效列表, 错误信息列表, 重叠警告列表)
* pick_prefer_ipv6(interfaces) 根据接口字典结构选择首个包含IPv6地址的地址（无则回退IPv4）
"""
from __future__ import annotations
from ipaddress import ip_network, ip_address, IPv4Address, IPv6Address
from typing import Iterable, List, Tuple, Dict, Any


def is_ipv4(val: str) -> bool:
    try:
        return isinstance(ip_address(val), IPv4Address)
    except Exception:
        return False


def is_ipv6(val: str) -> bool:
    try:
        return isinstance(ip_address(val), IPv6Address)
    except Exception:
        return False


def parse_cidr(cidr: str):
    return ip_network(cidr, strict=False)


def cidr_overlap(a: str, b: str) -> bool:
    try:
        na = parse_cidr(a)
        nb = parse_cidr(b)
        return na.overlaps(nb)
    except Exception:
        return False


def validate_cidrs(cidrs: Iterable[str]) -> Tuple[List[str], List[str], List[str]]:
    ok: List[str] = []
    errors: List[str] = []
    overlaps: List[str] = []
    cidr_list = []
    for c in cidrs:
        if not c:
            continue
        try:
            net = parse_cidr(c)
            cidr_list.append((c, net))
            ok.append(c)
        except Exception:
            errors.append(f"非法CIDR: {c}")
    # 重叠检查 O(n^2) 规模小可接受
    for i in range(len(cidr_list)):
        for j in range(i + 1, len(cidr_list)):
            c1, n1 = cidr_list[i]
            c2, n2 = cidr_list[j]
            if n1.overlaps(n2):
                overlaps.append(f"CIDR重叠: {c1} <-> {c2}")
    return ok, errors, overlaps


def pick_prefer_ipv6(ifaces: List[Dict[str, Any]]) -> str | None:
    """从接口列表中优先选择含IPv6地址的任意一个地址；若无则选首个IPv4；再无返回None。

    接口结构期望：{"ipv6": [...], "ipv4": [...]}，允许字段缺失。
    """
    for it in ifaces:
        v6s = it.get("ipv6") or []
        for addr in v6s:
            if is_ipv6(addr.split('%')[0]):  # 去掉可能存在的作用域标记
                return addr
    for it in ifaces:
        v4s = it.get("ipv4") or []
        for addr in v4s:
            if is_ipv4(addr):
                return addr
    return None

