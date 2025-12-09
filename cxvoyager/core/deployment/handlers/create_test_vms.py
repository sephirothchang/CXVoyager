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

# Stage 10 create_test_vms – 创建测试虚机
from __future__ import annotations
import logging
from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.progress import create_stage_progress_logger

logger = logging.getLogger(__name__)


@stage_handler(Stage.create_test_vms)
def handle_create_test_vms(ctx_dict):
    ctx: RunContext = ctx_dict['ctx']
    stage_logger = create_stage_progress_logger(ctx, Stage.create_test_vms.value, logger=logger, prefix="[create_test_vms]")
    deploy_payload = ctx.extra.get('deploy_payload', {})
    hosts = deploy_payload.get('hosts', []) if isinstance(deploy_payload, dict) else []
    # 简单策略：全闪/有cache的主机2个fio vm，否则1个
    vm_plan = []
    for h in hosts:
        count = 2 if h.get('with_faster_ssd_as_cache') else 1
        for i in range(count):
            vm_plan.append({
                'host': h.get('hostname'),
                'name': f"fio-{h.get('hostname')}-{i}",
                'net': 'mgmt-net',
                'size_gb': 20,
            })
    stage_logger.info("规划测试 VM", progress_extra={"vm_count": len(vm_plan)})
    ctx.extra['create_test_vms'] = {'vms': vm_plan, 'status': 'SUCCESS'}
