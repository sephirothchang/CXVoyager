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

"""SMTX 自动化部署工具包。

提供：
- Excel 规划表解析
- 数据验证
- 分阶段工作流调度
- API 客户端（真实/模拟）
- CLI & Web 接口

# CLI 入口（保持向后兼容）
from .resources.interfaces.cli import app as cli_app  # noqa: E402,F401
"""
from .application_version import __version__  # noqa: F401
