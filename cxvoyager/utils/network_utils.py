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

"""网络连通性与端口检测工具。"""
from __future__ import annotations

import platform
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Literal, Optional


@dataclass
class ProbeTask:
    """探测任务定义，用于描述一次 ICMP 或 TCP 检查。"""

    target: str
    kind: Literal["icmp", "tcp"]
    port: Optional[int] = None
    timeout: float = 1.0
    retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeResult:
    """探测结果，记录成功与否及补充信息。"""

    task: ProbeTask
    success: bool
    detail: str = ""
    elapsed: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.task.target,
            "kind": self.task.kind,
            "port": self.task.port,
            "timeout": self.task.timeout,
            "retries": self.task.retries,
            "metadata": self.task.metadata,
            "success": self.success,
            "detail": self.detail,
            "elapsed": self.elapsed,
        }


def _build_ping_command(host: str, count: int, timeout: int) -> List[str]:
    system = platform.system().lower()
    if system == "windows":
        return ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
    return ["ping", "-c", str(count), "-W", str(timeout), host]


def ping(host: str, count: int = 1, timeout: int = 1) -> bool:
    """执行 ICMP 探测，返回是否连通。"""

    try:
        command = _build_ping_command(host, count, timeout)
        result = subprocess.run(command, capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def check_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """执行 TCP 端口握手检查。"""

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_icmp(host: str, timeout: float = 1.0, *, retries: int = 0) -> ProbeResult:
    """ICMP 探测封装，带重试与耗时统计。"""

    task = ProbeTask(target=host, kind="icmp", timeout=timeout, retries=retries)
    start = time.perf_counter()
    for attempt in range(retries + 1):
        if ping(host, timeout=int(timeout)):
            elapsed = time.perf_counter() - start
            return ProbeResult(task=task, success=True, elapsed=elapsed)
        time.sleep(0.05)
    elapsed = time.perf_counter() - start
    return ProbeResult(task=task, success=False, elapsed=elapsed, detail="icmp unreachable")


def probe_tcp(host: str, port: int, timeout: float = 1.0, *, retries: int = 0) -> ProbeResult:
    """TCP 探测封装，带重试与耗时统计。"""

    task = ProbeTask(target=host, kind="tcp", port=port, timeout=timeout, retries=retries)
    start = time.perf_counter()
    for attempt in range(retries + 1):
        if check_port(host, port, timeout=timeout):
            elapsed = time.perf_counter() - start
            return ProbeResult(task=task, success=True, elapsed=elapsed)
        time.sleep(0.05)
    elapsed = time.perf_counter() - start
    return ProbeResult(task=task, success=False, elapsed=elapsed, detail=f"tcp {port} unreachable")


def run_probe_tasks(
    tasks: Iterable[ProbeTask],
    *,
    max_workers: int = 8,
    logger=None,
) -> List[ProbeResult]:
    """并发执行探测任务，返回所有结果。

    :param tasks: 待执行的探测任务集合。
    :param max_workers: 线程池并发度，默认 8。
    :param logger: 可选日志记录器，若提供且为 DEBUG 级别，将输出探测详情。
    """

    task_list = list(tasks)
    if not task_list:
        return []

    results: List[ProbeResult] = []

    def _execute(task: ProbeTask) -> ProbeResult:
        if task.kind == "icmp":
            return probe_icmp(task.target, timeout=task.timeout, retries=task.retries)
        if task.kind == "tcp":
            if task.port is None:
                raise ValueError("TCP 探测需要指定端口")
            return probe_tcp(task.target, task.port, timeout=task.timeout, retries=task.retries)
        raise ValueError(f"未知探测类型: {task.kind}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_execute, task): task for task in task_list}
        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - 捕获执行异常
                detail = str(exc) or "probe failed"
                result = ProbeResult(task=task, success=False, detail=detail)
            results.append(result)
            if logger and hasattr(logger, "debug"):
                logger.debug("探测结果", extra={"probe": result.to_dict()})
    return results


def batch_connectivity(hosts: List[str], ports: List[int]) -> Dict[str, Dict[int, bool]]:
    """兼容旧接口的批量连通性检测。"""

    report: Dict[str, Dict[int, bool]] = {}
    for h in hosts:
        report[h] = {}
        alive = ping(h)
        if not alive:
            report[h][-1] = False  # -1 代表ICMP失败
            continue
        for p in ports:
            report[h][p] = check_port(h, p)
    return report

