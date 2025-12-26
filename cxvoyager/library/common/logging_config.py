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

"""日志初始化模块。"""
from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .system_constants import LOG_DIR

LOG_DIR.mkdir(exist_ok=True)

DEFAULT_LOG_FILE = LOG_DIR / "cxvoyager.log"


def setup_logging(level: str = "INFO") -> None:
    """初始化日志配置。

    Args:
        level: 日志级别字符串。
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # 使用 force 以覆盖之前的基础配置，确保日志级别能够被更新。
    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt, force=True)

    root = logging.getLogger()
    root.setLevel(log_level)

    # 轮转文件处理器
    file_handler = RotatingFileHandler(
        DEFAULT_LOG_FILE,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(fmt, datefmt))
    root.addHandler(file_handler)

    logging.getLogger(__name__).debug("日志系统初始化完成，文件: %s", DEFAULT_LOG_FILE)

