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

"""按阶段输出独立日志文件。"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict
from cxvoyager.library.common.system_constants import LOG_DIR

_LOG_CACHE: Dict[str, logging.Logger] = {}


def get_stage_logger(stage: str) -> logging.Logger:
    if stage in _LOG_CACHE:
        return _LOG_CACHE[stage]
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(f"stage.{stage}")
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        fh = logging.FileHandler(LOG_DIR / f"stage_{stage}.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)
    logger.setLevel(logging.INFO)
    _LOG_CACHE[stage] = logger
    return logger

