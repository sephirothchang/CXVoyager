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

"""规划表固定坐标变量表。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class PlanVariable:
    """单个规划表字段的坐标定义。"""

    key: str
    sheet: str
    cell: str
    description: str = ""
    default: Any = None


PLAN_VARIABLES: Dict[str, PlanVariable] = {}


def register_variable(key: str, sheet: str, cell: str, description: str = "", default: Any = None) -> PlanVariable:
    if key in PLAN_VARIABLES:
        raise ValueError(f"重复的变量声明: {key}")
    var = PlanVariable(key=key, sheet=sheet, cell=cell, description=description, default=default)
    PLAN_VARIABLES[key] = var
    return var


# --- 虚拟网络 sheet 固定字段 ---
CLUSTER_NAME = register_variable("CLUSTER_NAME", "虚拟网络", "B3", "集群名称")
MGMT_VDS_NAME = register_variable("MGMT_VDS_NAME", "虚拟网络", "C4", "管理虚拟交换机名称")
STORAGE_VDS_NAME = register_variable("STORAGE_VDS_NAME", "虚拟网络", "C6", "存储虚拟交换机名称")
BACKUP_VDS_NAME = register_variable("BACKUP_VDS_NAME", "虚拟网络", "C7", "备份虚拟交换机名称")
BUSINESS_VDS_NAME = register_variable("BUSINESS_VDS_NAME", "虚拟网络", "C8", "业务虚拟交换机名称")

DEFAULT_MGMT_NETWORK_NAME = register_variable("DEFAULT_MGMT_NETWORK_NAME", "虚拟网络", "D4", "默认管理虚拟网络名称")
EXTRA_NETWORK_NAME = register_variable("EXTRA_NETWORK_NAME", "虚拟网络", "D5", "额外管理组件虚拟网络名称")
STORAGE_NETWORK_NAME = register_variable("STORAGE_NETWORK_NAME", "虚拟网络", "D6", "存储虚拟网络名称")
BACKUP_NETWORK_NAME = register_variable("BACKUP_NETWORK_NAME", "虚拟网络", "D7", "备份虚拟网络名称")

DEFAULT_MGMT_VLAN_ID = register_variable("DEFAULT_MGMT_VLAN_ID", "虚拟网络", "F4", "默认管理 VLAN ID",default="0")
EXTRA_VLAN_ID = register_variable("EXTRA_VLAN_ID", "虚拟网络", "F5", "额外管理组件 VLAN ID")
STORAGE_VLAN_ID = register_variable("STORAGE_VLAN_ID", "虚拟网络", "F6", "存储 VLAN ID",default="0")
BACKUP_VLAN_ID = register_variable("BACKUP_VLAN_ID", "虚拟网络", "F7", "备份 VLAN ID")

DEFAULT_MGMT_VLAN_TYPE = register_variable("DEFAULT_MGMT_VLAN_TYPE", "虚拟网络", "G4", "默认管理 VLAN 类型")
EXTRA_VLAN_TYPE = register_variable("EXTRA_VLAN_TYPE", "虚拟网络", "G5", "额外管理组件 VLAN 类型")
STORAGE_VLAN_TYPE = register_variable("STORAGE_VLAN_TYPE", "虚拟网络", "G6", "存储 VLAN 类型")
BACKUP_VLAN_TYPE = register_variable("BACKUP_VLAN_TYPE", "虚拟网络", "G7", "备份 VLAN 类型")

DEFAULT_MGMT_SUBNET = register_variable("DEFAULT_MGMT_SUBNET", "虚拟网络", "H4", "默认管理子网")
EXTRA_SUBNET = register_variable("EXTRA_SUBNET", "虚拟网络", "H5", "额外管理组件子网")
STORAGE_SUBNET = register_variable("STORAGE_SUBNET", "虚拟网络", "H6", "存储子网")
BACKUP_SUBNET = register_variable("BACKUP_SUBNET", "虚拟网络", "H7", "备份子网")

DEFAULT_MGMT_GATEWAY = register_variable("DEFAULT_MGMT_GATEWAY", "虚拟网络", "I4", "默认管理网关")
EXTRA_GATEWAY = register_variable("EXTRA_GATEWAY", "虚拟网络", "I5", "额外管理组件网关")
STORAGE_GATEWAY = register_variable("STORAGE_GATEWAY", "虚拟网络", "I6", "存储网关")
BACKUP_GATEWAY = register_variable("BACKUP_GATEWAY", "虚拟网络", "I7", "备份网关")

MGMT_SWITCH_PORTS = register_variable("MGMT_SWITCH_PORTS", "虚拟网络", "J4", "管理交换机主机端口")
STORAGE_SWITCH_PORTS = register_variable("STORAGE_SWITCH_PORTS", "虚拟网络", "J6", "存储交换机主机端口")
BACKUP_SWITCH_PORTS = register_variable("BACKUP_SWITCH_PORTS", "虚拟网络", "J7", "备份交换机主机端口")
BUSINESS_SWITCH_PORTS = register_variable("BUSINESS_SWITCH_PORTS", "虚拟网络", "J8", "业务交换机主机端口")

MGMT_BOND_MODE = register_variable("MGMT_BOND_MODE", "虚拟网络", "K4", "管理交换机网口绑定模式")
STORAGE_BOND_MODE = register_variable("STORAGE_BOND_MODE", "虚拟网络", "K6", "存储交换机网口绑定模式")
BACKUP_BOND_MODE = register_variable("BACKUP_BOND_MODE", "虚拟网络", "K7", "备份交换机网口绑定模式")
BUSINESS_BOND_MODE = register_variable("BUSINESS_BOND_MODE", "虚拟网络", "K8", "业务交换机网口绑定模式")


BUSINESS_NETWORK_MAX = 11
BUSINESS_NETWORK_NAME_KEYS: List[str] = []
BUSINESS_NETWORK_VLAN_ID_KEYS: List[str] = []
BUSINESS_NETWORK_VLAN_TYPE_KEYS: List[str] = []
BUSINESS_NETWORK_SUBNET_KEYS: List[str] = []
BUSINESS_NETWORK_GATEWAY_KEYS: List[str] = []

for idx, row in enumerate(range(8, 19), start=1):
    suffix = f"{idx:02d}"
    BUSINESS_NETWORK_NAME_KEYS.append(
        register_variable(f"BUSINESS_NETWORK_{suffix}_NAME", "虚拟网络", f"D{row}", "业务虚拟网络名称").key
    )
    BUSINESS_NETWORK_VLAN_ID_KEYS.append(
        register_variable(f"BUSINESS_NETWORK_{suffix}_VLAN_ID", "虚拟网络", f"F{row}", "业务 VLAN ID").key
    )
    BUSINESS_NETWORK_VLAN_TYPE_KEYS.append(
        register_variable(f"BUSINESS_NETWORK_{suffix}_VLAN_TYPE", "虚拟网络", f"G{row}", "业务 VLAN 类型").key
    )
    BUSINESS_NETWORK_SUBNET_KEYS.append(
        register_variable(f"BUSINESS_NETWORK_{suffix}_SUBNET", "虚拟网络", f"H{row}", "业务子网").key
    )
    BUSINESS_NETWORK_GATEWAY_KEYS.append(
        register_variable(f"BUSINESS_NETWORK_{suffix}_GATEWAY", "虚拟网络", f"I{row}", "业务网关").key
    )


# --- 主机规划 sheet 固定字段 ---
HOST_CLUSTER_NAME = register_variable("HOST_CLUSTER_NAME", "主机规划", "C3", "主机规划表中的集群名称")
CLUSTER_VIP = register_variable("CLUSTER_VIP", "主机规划", "I19", "集群 VIP")
CLUSTER_FUNCTION = register_variable("CLUSTER_FUNCTION", "主机规划", "O19", "集群功能")
FISHEYE_ADMIN_USER = register_variable("FISHEYE_ADMIN_USER", "主机规划", "L19", "Fisheye 集群管理员用户名", default="root")
FISHEYE_ADMIN_PASSWORD = register_variable("FISHEYE_ADMIN_PASSWORD", "主机规划", "M19", "Fisheye 集群管理员密码", default="HC!r0cks")
CLUSTER_SERIAL = register_variable("CLUSTER_SERIAL", "主机规划", "E19", "集群序列号")
STORAGE_ARCHITECTURE = register_variable("STORAGE_ARCHITECTURE","主机规划","Q19","存储架构（混闪-分层 / 全闪-不分层）",default="混闪-分层")
NETWORK_ARCHITECTURE = register_variable("NETWORK_ARCHITECTURE","主机规划","Q20","网络架构（三网融合 / 存储独立 / 三网独立）",default="三网独立")

HOST_MAX = 16
HOST_ROW_RANGE = range(3, 3 + HOST_MAX)

HOST_BMC_IP_KEYS: List[str] = []
HOST_BMC_USER_KEYS: List[str] = []
HOST_BMC_PASSWORD_KEYS: List[str] = []
HOST_HOSTNAME_KEYS: List[str] = []
HOST_MGMT_IP_KEYS: List[str] = []
HOST_STORAGE_IP_KEYS: List[str] = []
HOST_SSH_USER_KEYS: List[str] = []
HOST_SSH_PASSWORD_KEYS: List[str] = []

for idx, row in enumerate(HOST_ROW_RANGE, start=1):
    suffix = f"{idx:02d}"
    HOST_BMC_IP_KEYS.append(
        register_variable(f"HOST_{suffix}_BMC_IP", "主机规划", f"E{row}", "主机带外管理 IP").key
    )
    HOST_BMC_USER_KEYS.append(
        register_variable(
            f"HOST_{suffix}_BMC_USER", "主机规划", f"F{row}", "主机带外用户名", default="ADMIN"
        ).key
    )
    HOST_BMC_PASSWORD_KEYS.append(
        register_variable(
            f"HOST_{suffix}_BMC_PASSWORD", "主机规划", f"G{row}", "主机带外密码", default="ADMIN"
        ).key
    )
    HOST_HOSTNAME_KEYS.append(
        register_variable(f"HOST_{suffix}_HOSTNAME", "主机规划", f"H{row}", "SMTX OS 主机名").key
    )
    HOST_MGMT_IP_KEYS.append(
        register_variable(f"HOST_{suffix}_MGMT_IP", "主机规划", f"I{row}", "管理地址").key
    )
    HOST_SSH_USER_KEYS.append(
        register_variable(
            f"HOST_{suffix}_SSH_USER", "主机规划", f"J{row}", "主机 SSH 用户名", default="smartx"
        ).key
    )
    HOST_SSH_PASSWORD_KEYS.append(
        register_variable(
            f"HOST_{suffix}_SSH_PASSWORD", "主机规划", f"K{row}", "主机 SSH 密码", default="HC!r0cks"
        ).key
    )
    HOST_STORAGE_IP_KEYS.append(
        register_variable(f"HOST_{suffix}_STORAGE_IP", "主机规划", f"N{row}", "存储地址").key
    )


# --- 集群管理信息 sheet 固定字段 ---
CLOUDTOWER_IP = register_variable("CLOUDTOWER_IP", "集群管理信息", "E3", "CloudTower IP")
CLOUDTOWER_ROOT_PASSWORD = register_variable(
    "CLOUDTOWER_ROOT_PASSWORD", "集群管理信息", "G3", "CloudTower web 管理员 root 密码", default="HC!r0cks"
)
CLOUDTOWER_SERIAL = register_variable("CLOUDTOWER_SERIAL", "集群管理信息", "M3", "CloudTower 序列号")
OBS_IP = register_variable("OBS_IP", "集群管理信息", "E4", "OBS IP")
OBS_SERIAL = register_variable("OBS_SERIAL", "集群管理信息", "M4", "OBS 序列号")
BACKUP_IP = register_variable("BACKUP_IP", "集群管理信息", "E5", "备份 IP")
BACKUP_SERIAL = register_variable("BACKUP_SERIAL", "集群管理信息", "M5", "备份序列号")
ER_CONTROLLER_CLUSTER_VIP = register_variable(
    "ER_CONTROLLER_CLUSTER_VIP", "集群管理信息", "E6", "ER 控制器集群 VIP"
)
ER_CONTROLLER_SERIAL = register_variable(
    "ER_CONTROLLER_SERIAL", "集群管理信息", "M6", "ER 控制器节点序列号"
)

ER_CONTROLLER_NODE_MAX = 5
ER_CONTROLLER_NODE_IP_KEYS: List[str] = []
for idx, row in enumerate(range(7, 7 + ER_CONTROLLER_NODE_MAX), start=1):
    suffix = f"{idx:02d}"
    ER_CONTROLLER_NODE_IP_KEYS.append(
        register_variable(
            f"ER_CONTROLLER_NODE_{suffix}_IP", "集群管理信息", f"E{row}", "ER 控制器节点 IP"
        ).key
    )

NTP_SERVER_MAX = 3
NTP_SERVER_KEYS: List[str] = []
for idx, row in enumerate(range(22, 22 + NTP_SERVER_MAX), start=1):
    suffix = f"{idx:02d}"
    NTP_SERVER_KEYS.append(
        register_variable(f"NTP_SERVER_{suffix}", "集群管理信息", f"E{row}", "NTP 服务器").key
    )

DNS_SERVER_MAX = 2
DNS_SERVER_KEYS: List[str] = []
for idx, row in enumerate(range(25, 25 + DNS_SERVER_MAX), start=1):
    suffix = f"{idx:02d}"
    DNS_SERVER_KEYS.append(
        register_variable(f"DNS_SERVER_{suffix}", "集群管理信息", f"E{row}", "DNS 服务器").key
    )

TEST_IP_RANGE_START = register_variable("TEST_IP_RANGE_START", "集群管理信息", "E18", "临时测试 IP 起始")
TEST_IP_RANGE_END = register_variable("TEST_IP_RANGE_END", "集群管理信息", "E19", "临时测试 IP 结束")


# --- 文档描述 sheet 固定字段 ---
CLOUDTOWER_ORGANIZATION_NAME = register_variable(
    "CLOUDTOWER_ORGANIZATION_NAME", "文档描述", "C15", "CloudTower 组织名称", default="SMTX-HCI"
)
CLOUDTOWER_DATACENTER_NAME = register_variable(
    "CLOUDTOWER_DATACENTER_NAME", "文档描述", "C17", "CloudTower 数据中心名称", default="SMTX-HCI-DC"
)


__all__ = [
    "PlanVariable",
    "PLAN_VARIABLES",
    "register_variable",
    "CLUSTER_NAME",
    "MGMT_VDS_NAME",
    "STORAGE_VDS_NAME",
    "BACKUP_VDS_NAME",
    "BUSINESS_VDS_NAME",
    "DEFAULT_MGMT_NETWORK_NAME",
    "EXTRA_NETWORK_NAME",
    "STORAGE_NETWORK_NAME",
    "BACKUP_NETWORK_NAME",
    "DEFAULT_MGMT_VLAN_ID",
    "EXTRA_VLAN_ID",
    "STORAGE_VLAN_ID",
    "BACKUP_VLAN_ID",
    "DEFAULT_MGMT_VLAN_TYPE",
    "EXTRA_VLAN_TYPE",
    "STORAGE_VLAN_TYPE",
    "BACKUP_VLAN_TYPE",
    "DEFAULT_MGMT_SUBNET",
    "EXTRA_SUBNET",
    "STORAGE_SUBNET",
    "BACKUP_SUBNET",
    "DEFAULT_MGMT_GATEWAY",
    "EXTRA_GATEWAY",
    "STORAGE_GATEWAY",
    "BACKUP_GATEWAY",
    "MGMT_SWITCH_PORTS",
    "STORAGE_SWITCH_PORTS",
    "BACKUP_SWITCH_PORTS",
    "BUSINESS_SWITCH_PORTS",
    "MGMT_BOND_MODE",
    "STORAGE_BOND_MODE",
    "BACKUP_BOND_MODE",
    "BUSINESS_BOND_MODE",
    "BUSINESS_NETWORK_MAX",
    "BUSINESS_NETWORK_NAME_KEYS",
    "BUSINESS_NETWORK_VLAN_ID_KEYS",
    "BUSINESS_NETWORK_VLAN_TYPE_KEYS",
    "BUSINESS_NETWORK_SUBNET_KEYS",
    "BUSINESS_NETWORK_GATEWAY_KEYS",
    "HOST_CLUSTER_NAME",
    "CLUSTER_VIP",
    "CLUSTER_FUNCTION",
    "FISHEYE_ADMIN_USER",
    "FISHEYE_ADMIN_PASSWORD",
    "CLUSTER_SERIAL",
    "HOST_MAX",
    "HOST_ROW_RANGE",
    "HOST_BMC_IP_KEYS",
    "HOST_BMC_USER_KEYS",
    "HOST_BMC_PASSWORD_KEYS",
    "HOST_HOSTNAME_KEYS",
    "HOST_MGMT_IP_KEYS",
    "HOST_STORAGE_IP_KEYS",
    "HOST_SSH_USER_KEYS",
    "HOST_SSH_PASSWORD_KEYS",
    "CLOUDTOWER_IP",
    "CLOUDTOWER_ROOT_PASSWORD",
    "CLOUDTOWER_SERIAL",
    "OBS_IP",
    "OBS_SERIAL",
    "BACKUP_IP",
    "BACKUP_SERIAL",
    "ER_CONTROLLER_CLUSTER_VIP",
    "ER_CONTROLLER_SERIAL",
    "ER_CONTROLLER_NODE_MAX",
    "ER_CONTROLLER_NODE_IP_KEYS",
    "NTP_SERVER_MAX",
    "NTP_SERVER_KEYS",
    "DNS_SERVER_MAX",
    "DNS_SERVER_KEYS",
    "TEST_IP_RANGE_START",
    "TEST_IP_RANGE_END",
    "CLOUDTOWER_ORGANIZATION_NAME",
    "CLOUDTOWER_DATACENTER_NAME",
    "STORAGE_ARCHITECTURE",
]

