# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage deploy_sks – 上传 SKS 包。"""
from __future__ import annotations

import re

from cxvoyager.workflow.stage_manager import Stage, stage_handler
from .app_upload import AppSpec, upload_app

APP_SPEC_SKS = AppSpec(
    abbr="SKS",
    label="SKS",
    package_pattern="SKS-X86_64-*.tar.gz",
    name_regex=re.compile(
        r"SKS-X86_64-v(?P<version>[\d\.]+)-release\.(?P<date>\d+)-(?P<build>\d+)\.tar\.gz",
        re.IGNORECASE,
    ),
    base_url_key="sks_base_url",
)


@stage_handler(Stage.deploy_sks)
def handle_deploy_sks(ctx_dict):
    """上传 SKS 应用包。"""

    upload_app(ctx_dict, APP_SPEC_SKS, Stage.deploy_sks)
