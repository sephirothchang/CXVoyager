# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage deploy_obs – 上传 Observability 包。"""
from __future__ import annotations

import re

from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from .app_upload import AppSpec, upload_app

APP_SPEC_OBS = AppSpec(
    abbr="OBS",
    label="Observability",
    package_pattern="Observability-X86_64-*.tar.gz",
    name_regex=re.compile(
        r"Observability-X86_64-v(?P<version>[\d\.]+)-release\.(?P<date>\d+)-(?P<build>\d+)\.tar\.gz",
        re.IGNORECASE,
    ),
)


@stage_handler(Stage.deploy_obs)
def handle_deploy_obs(ctx_dict):
    """上传 OBS 应用包。"""

    upload_app(ctx_dict, APP_SPEC_OBS, Stage.deploy_obs)
