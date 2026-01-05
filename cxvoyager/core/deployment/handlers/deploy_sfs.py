# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage deploy_sfs – 上传 SFS 包。"""
from __future__ import annotations

import re

from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from .app_upload import AppSpec, upload_app

APP_SPEC_SFS = AppSpec(
    abbr="SFS",
    label="SFS",
    package_pattern="SFS-X86_64-*.tar.gz",
    name_regex=re.compile(
        r"SFS-X86_64-v(?P<version>[\d\.]+)-release\.(?P<date>\d+)-(?P<build>\d+)\.tar\.gz",
        re.IGNORECASE,
    ),
    base_url_key="sfs_base_url",
)


@stage_handler(Stage.deploy_sfs)
def handle_deploy_sfs(ctx_dict):
    """上传 SFS 应用包。"""

    try:
        upload_app(ctx_dict, APP_SPEC_SFS, Stage.deploy_sfs)
    except Exception as exc:
        # 占位实现，记录错误但不中断
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"SFS 部署失败（占位实现）: {exc}")
