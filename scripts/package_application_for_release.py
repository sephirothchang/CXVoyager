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

"""打包脚本：生成 release/cxvoyager_bundle.zip"""
from __future__ import annotations
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "release" / "cxvoyager_bundle.zip"
EXCLUDE_DIRS = {"logs", "__pycache__", "开发辅助工具-忽略且无需处理"}


def should_include(p: Path) -> bool:
    parts = set(p.parts)
    return not parts & EXCLUDE_DIRS


def build():
    if OUTPUT.exists():
        OUTPUT.unlink()
    OUTPUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob('*'):
            if path.is_dir():
                continue
            rel = path.relative_to(ROOT)
            if not should_include(rel):
                continue
            if rel.suffix in {'.pyc', '.log'}:
                continue
            zf.write(path, arcname=str(rel))
    print(f"打包完成: {OUTPUT}")

if __name__ == '__main__':
    build()

