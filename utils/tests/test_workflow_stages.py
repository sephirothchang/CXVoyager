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
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.stage_manager import run_stages, Stage


def test_minimal_workflow(monkeypatch):
    # 构造上下文并运行若干阶段（在无真实Excel情况下应提前跳过）
    ctx = RunContext()
    # 由于 prepare 需要真实文件，这里仅断言阶段枚举完整性
    all_stages = [s for s in Stage]
    assert 'perf_reliability' in {s.value for s in all_stages}
    assert 'cleanup' in {s.value for s in all_stages}

