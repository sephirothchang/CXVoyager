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

"""通用工具包。

该包聚合了并发、网络、Mock 数据等辅助工具，供项目其它模块统一引用。
"""
from .parallel_utils import parallel_map  # noqa: F401
from .mock_scan_host import mock_scan_host  # noqa: F401
from .ip_utils import validate_cidrs, pick_prefer_ipv6, is_ipv4, is_ipv6  # noqa: F401

