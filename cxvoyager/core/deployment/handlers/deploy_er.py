# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage deploy_er – 上传 ER 包。"""
from __future__ import annotations

import re

from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from .app_upload import AppSpec, upload_app

APP_SPEC_ER = AppSpec(
    abbr="ER",
    label="ER",
    package_pattern="ER-X86_64-*.tar.gz",
    name_regex=re.compile(
        r"ER-X86_64-v(?P<version>[\d\.]+)-release\.(?P<date>\d+)-(?P<build>\d+)\.tar\.gz",
        re.IGNORECASE,
    ),
    base_url_key="er_base_url",
)


@stage_handler(Stage.deploy_er)
def handle_deploy_er(ctx_dict):
    """上传 ER 应用包。"""

    try:
        upload_app(ctx_dict, APP_SPEC_ER, Stage.deploy_er)
    except Exception as exc:
        # 占位实现，记录错误但不中断
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"ER 部署失败（占位实现）: {exc}")
