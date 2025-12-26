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

# Stage 12 cleanup – 收尾清理
from __future__ import annotations
import logging
import json
import tarfile
from datetime import datetime
from pathlib import Path
from cxvoyager.workflow.stage_manager import Stage, stage_handler
from cxvoyager.workflow.runtime_context import RunContext
from cxvoyager.workflow.progress import create_stage_progress_logger
from cxvoyager.common.i18n import tr

logger = logging.getLogger(__name__)


@stage_handler(Stage.cleanup)
def handle_cleanup(ctx_dict):
    ctx: RunContext = ctx_dict['ctx']
    stage_logger = create_stage_progress_logger(ctx, Stage.cleanup.value, logger=logger, prefix="[cleanup]")
    artifacts_dir = Path('artifacts')
    artifacts_dir.mkdir(exist_ok=True)
    # 汇总 context 关键信息写入 summary.json
    summary_path = artifacts_dir / 'run-summary.json'
    summary_content = {
        'stages': list(ctx.completed_stages),
        'extra_keys': list(ctx.extra.keys()),
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    summary_path.write_text(json.dumps(summary_content, ensure_ascii=False, indent=2), encoding='utf-8')
    # 打包日志与 artifacts
    bundle_name = f"bundle-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.tar.gz"
    bundle_path = artifacts_dir / bundle_name
    with tarfile.open(bundle_path, 'w:gz') as tf:
        # 添加 artifacts 目录下的所有文件
        for p in artifacts_dir.glob('*'):
            if p.name == bundle_name:
                continue
            tf.add(p, arcname=p.name)
        # 添加 logs 目录（如果存在）
        log_dir = Path('logs')
        if log_dir.exists():
            for lp in log_dir.rglob('*'):
                if lp.is_file():
                    tf.add(lp, arcname=f'logs/{lp.relative_to(log_dir)}')
    ctx.extra['cleanup'] = {
        'bundle': str(bundle_path),
        'summary': str(summary_path),
        'status': 'SUCCESS'
    }
    stage_logger.info(tr("deploy.cleanup.done"), progress_extra={"bundle": str(bundle_path)})
