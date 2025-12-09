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

"""全局常量与魔法字符串集中管理。"""
from pathlib import Path

# 规划表定位关键词
PLAN_KEYWORDS = ["SmartX超融合", "规划设计表", "ELF环境"]
PLAN_SHEETS = {
    "virtual_network": "虚拟网络",
    "hosts": "主机规划",
    "mgmt": "集群管理信息",
}

# 日志与配置目录
PACKAGE_DIR = Path(__file__).resolve().parent
BASE_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = BASE_DIR.parent
CONFIG_DIR = PACKAGE_DIR / "config"
LOG_DIR = PROJECT_ROOT / "logs"
RESOURCES_DIR = PACKAGE_DIR / "resources"
EXAMPLES_DIR = PROJECT_ROOT / "示例文件"

DEFAULT_CONFIG_FILE = CONFIG_DIR / "default.yml"

# 阶段枚举（初版，不含全部细节）
STAGES = [
    "prepare",
    "init_cluster",
    "config_cluster",
    "deploy_cloudtower",
    "attach_cluster",
    "cloudtower_config",
    "check_cluster_healthy",
    "deploy_obs",
    "deploy_bak",
    "deploy_er",
    "deploy_sfs",
    "deploy_sks",
    "create_test_vms",
    "perf_reliability",
    "cleanup",
]

