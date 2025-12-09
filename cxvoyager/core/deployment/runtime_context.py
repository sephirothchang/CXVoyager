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

"""运行时上下文对象。"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
from pathlib import Path
from cxvoyager.models import PlanModel
from cxvoyager.common.config import Config

@dataclass
class RunContext:
    plan: PlanModel | None = None
    work_dir: Path = Path.cwd()
    extra: Dict[str, Any] = field(default_factory=dict)
    config: Config | None = None
    completed_stages: List[str] = field(default_factory=list)

