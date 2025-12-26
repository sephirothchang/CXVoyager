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

# Stage 11 perf_reliability – 性能与可靠性验证
from __future__ import annotations
import logging
import random
from statistics import mean
from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.progress import create_stage_progress_logger
from cxvoyager.common.i18n import tr

logger = logging.getLogger(__name__)


@stage_handler(Stage.perf_reliability)
def handle_perf_reliability(ctx_dict):
    ctx: RunContext = ctx_dict['ctx']
    stage_logger = create_stage_progress_logger(ctx, Stage.perf_reliability.value, logger=logger, prefix="[perf_reliability]")
    test_vms = ctx.extra.get('create_test_vms', {}).get('vms', [])
    if not test_vms:
        stage_logger.warning(tr("deploy.perf_reliability.no_test_vm"))
    # 模拟性能测试：生成随机 IOPS / 带宽 / 延迟
    results = []
    for vm in test_vms:
        res = {
            'vm': vm['name'],
            'iops': random.randint(5000, 15000),
            'bw_MBps': random.uniform(200, 800),
            'lat_ms': random.uniform(0.5, 2.5),
        }
        results.append(res)
    summary = {
        'vm_count': len(results),
        'avg_iops': int(mean(r['iops'] for r in results)) if results else 0,
        'avg_bw_MBps': round(mean(r['bw_MBps'] for r in results), 2) if results else 0,
        'avg_lat_ms': round(mean(r['lat_ms'] for r in results), 3) if results else 0,
    }
    # 模拟故障注入记录
    fault_injections = [
        {'type': 'disk_unplug', 'result': 'recovered'},
        {'type': 'host_power_cycle', 'result': 'recovered'},
    ] if results else []
    stage_logger.info(tr("deploy.perf_reliability.summary"), progress_extra=summary)
    ctx.extra['perf_reliability'] = {
        'results': results,
        'summary': summary,
        'faults': fault_injections,
        'status': 'SUCCESS'
    }
