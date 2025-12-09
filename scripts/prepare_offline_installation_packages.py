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

"""在联网环境中准备离线依赖包。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
OFFLINE_DIR = ROOT / "cxvoyager" / "common" / "resources" / "offline_packages"


def ensure_offline_dir() -> None:
    OFFLINE_DIR.mkdir(parents=True, exist_ok=True)


def download() -> None:
    if not REQUIREMENTS.exists():
        raise SystemExit(f"未找到 {REQUIREMENTS}，无法下载依赖。")

    ensure_offline_dir()

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "download",
        "-r",
        str(REQUIREMENTS),
        "-d",
        str(OFFLINE_DIR),
    ]
    print("运行命令:", " ".join(str(part) for part in cmd))
    subprocess.check_call(cmd)
    print(f"离线依赖已下载至 {OFFLINE_DIR}")


if __name__ == "__main__":  # pragma: no cover
    download()

