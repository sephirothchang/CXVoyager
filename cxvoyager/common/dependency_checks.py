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

"""依赖检查工具。"""
from __future__ import annotations
import importlib
from typing import List, Dict

REQUIRED_PACKAGES = [
    "openpyxl",
    "requests",
    "pydantic",
]


def check_dependencies(optional: bool = False) -> Dict[str, bool]:
    status: Dict[str, bool] = {}
    pkgs = REQUIRED_PACKAGES.copy()
    if optional:
        pkgs += ["tenacity", "fastapi"]
    for pkg in pkgs:
        try:
            importlib.import_module(pkg)
            status[pkg] = True
        except Exception:
            status[pkg] = False
    return status

