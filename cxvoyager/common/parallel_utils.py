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

"""并发执行相关辅助函数。"""
from __future__ import annotations

import concurrent.futures as cf
from typing import Any, Callable, Iterable, List


def parallel_map(func: Callable[[Any], Any], items: Iterable[Any], max_workers: int = 8) -> List[Any]:
    """并发执行 *func*，保持简单的顺序结果集合。

    捕获异常并按调用顺序追加到结果列表，便于上层判断。
    """
    results: List[Any] = []
    with cf.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(func, item): item for item in items}
        for future in cf.as_completed(future_map):
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001 - 直接返回异常供调用方处理
                results.append(exc)
    return results

