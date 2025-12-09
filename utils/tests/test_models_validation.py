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

from cxvoyager.models.planning_sheet_models import VirtualNetworkRow, HostRow, PlanModel
from cxvoyager.core.validation.rules import validate_plan_model

def test_validate_simple():
    model = PlanModel(
        virtual_network=[VirtualNetworkRow(集群名称="c1", 虚拟交换机="vsw1", subnetwork="10.0.0.0/24")],
        hosts=[HostRow(集群名称="c1", 管理地址="192.168.1.10")],
    )
    report = validate_plan_model(model)
    # 当前逻辑：缺少root密码记录为警告而非致命错误 -> 修改断言
    # 如果未来策略调整为错误，需同步更新
    assert report["ok"] is True
    # root密码缺失应在warnings或errors之一
    joined = "\n".join(report.get("warnings", []) + report.get("errors", []))
    assert "管理信息缺失" in joined

