# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage deploy_bak – 上传 Backup 包。"""
from __future__ import annotations

import re

from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from .app_upload import AppSpec, upload_app

APP_SPEC_BAK = AppSpec(
    abbr="BAK",
    label="Backup",
    package_pattern="Backup-X86_64-*.tar.gz",
    name_regex=re.compile(
        r"Backup-X86_64-v(?P<version>[\d\.]+)-release\.(?P<date>\d+)-(?P<build>\d+)\.tar\.gz",
        re.IGNORECASE,
    ),
    base_url_key="bak_base_url",
)


@stage_handler(Stage.deploy_bak)
def handle_deploy_bak(ctx_dict):
    """上传 BAK 应用包。"""

    upload_app(ctx_dict, APP_SPEC_BAK, Stage.deploy_bak)
