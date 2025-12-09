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
from ipaddress import IPv4Address
from pathlib import Path
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.handlers.prepare import handle_prepare
from cxvoyager.core.deployment.prechecks.types import PrecheckReport
from cxvoyager.common.config import Config
from cxvoyager.models.planning_sheet_models import PlanModel, HostRow


def test_prepare_strict_blocks_warnings(monkeypatch):
    ctx = RunContext(config=Config({"precheck": {"ports": []}}))
    ctx.extra["cli_options"] = {"strict_validation": True}

    sample_plan = PlanModel(
        hosts=[HostRow(集群名称="c1", 集群VIP="10.0.0.10", 管理地址=IPv4Address("10.0.0.11"))],
        virtual_network=[],
        mgmt=None,
    )

    monkeypatch.setattr(
        "cxvoyager.core.deployment.handlers.prepare.find_plan_file", lambda work_dir: Path("dummy.xlsx")
    )
    monkeypatch.setattr(
        "cxvoyager.core.deployment.handlers.prepare.parse_plan", lambda path: {"raw": True}
    )
    monkeypatch.setattr(
        "cxvoyager.core.deployment.handlers.prepare.to_model", lambda parsed: sample_plan
    )
    monkeypatch.setattr(
        "cxvoyager.core.deployment.handlers.prepare.validate",
        lambda parsed: {"ok": True, "errors": [], "warnings": ["warn"]},
    )
    monkeypatch.setattr(
        "cxvoyager.core.deployment.handlers.prepare.check_dependencies", lambda optional=True: {}
    )
    monkeypatch.setattr(
        "cxvoyager.core.deployment.handlers.prepare.run_ip_prechecks", lambda *args, **kwargs: PrecheckReport()
    )

    with pytest.raises(RuntimeError):
        handle_prepare({"ctx": ctx})

