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

import pytest
from cxvoyager.core.validation.rules import validate_plan_model
from cxvoyager.models.planning_sheet_models import PlanModel, HostRow, VirtualNetworkRow, MgmtInfo


def make_plan(**kw):
    return PlanModel(**kw)


def test_cidr_overlap_and_invalid():
    plan = make_plan(
        hosts=[HostRow(集群名称="c1", 集群VIP="10.0.0.10", 管理地址="10.0.0.11")],
        virtual_network=[
            VirtualNetworkRow(集群名称="c1", 虚拟交换机="v1", subnetwork="10.0.0.0/24"),
            VirtualNetworkRow(集群名称="c1", 虚拟交换机="v2", subnetwork="10.0.0.0/25"),  # overlap
            VirtualNetworkRow(集群名称="c1", 虚拟交换机="v3", subnetwork="invalid-cidr"),
        ],
        mgmt=MgmtInfo(root密码="pwd"),
    )
    report = validate_plan_model(plan)
    assert not report["ok"], "应因非法CIDR失败"
    assert any("非法CIDR" in e for e in report["errors"])  # invalid
    assert any("CIDR重叠" in w for w in report["warnings"])  # overlap warning


def test_vip_conflict():
    plan = make_plan(
        hosts=[
            HostRow(集群名称="c1", 集群VIP="10.1.1.5", 管理地址="10.1.1.5"),
        ],
        virtual_network=[],
        mgmt=MgmtInfo(root密码="pwd"),
    )
    rep = validate_plan_model(plan)
    assert not rep["ok"]
    assert any("VIP" in e for e in rep["errors"])  # conflict


def test_ipv6_vip_warn():
    plan = make_plan(
        hosts=[HostRow(集群名称="c1", 集群VIP="fd00::10", 管理地址="10.2.2.2")],
        virtual_network=[],
        mgmt=MgmtInfo(root密码="pwd"),
    )
    rep = validate_plan_model(plan)
    assert rep["ok"], rep
    assert any("IPv6 VIP" in w for w in rep["warnings"])  # only warning

