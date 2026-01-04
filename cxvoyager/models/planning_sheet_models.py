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

"""规划表相关数据模型。"""
from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, IPvAnyAddress, Field

class VirtualNetworkRow(BaseModel):
    集群名称: str = Field(..., description="集群名称")
    虚拟交换机: Optional[str] = None
    虚拟机网络: Optional[str] = None
    subnetwork: Optional[str] = Field(None, description="子网CIDR")
    主机端口: Optional[str] = None
    网口绑定模式: Optional[str] = Field(None, description="active-backup|balance-tcp|balance-slb")
    vlan_id: Optional[int | str] = None
    vlan_type: Optional[str] = None
    gateway: Optional[str] = None

class HostRow(BaseModel):
    集群名称: str
    集群VIP: Optional[str] = None
    SMTX主机名: Optional[str] = None
    管理地址: Optional[IPvAnyAddress] = None
    存储地址: Optional[IPvAnyAddress] = None
    带外地址: Optional[IPvAnyAddress] = None
    带外用户名: Optional[str] = None
    带外密码: Optional[str] = None

class MgmtInfo(BaseModel):
    Cloudtower_IP: Optional[IPvAnyAddress] = Field(None, alias="Cloudtower IP")
    root密码: Optional[str] = None
    其他组件IP: Optional[str] = None
    obs_ip: Optional[IPvAnyAddress] = Field(None, alias="OBS IP")
    backup_ip: Optional[IPvAnyAddress] = Field(None, alias="备份 IP")
    cloudtower_serial: Optional[str] = Field(None, alias="Cloudtower 序列号")
    obs_serial: Optional[str] = Field(None, alias="OBS 序列号")
    backup_serial: Optional[str] = Field(None, alias="备份 序列号")
    er_controller_cluster_vip: Optional[IPvAnyAddress] = Field(None, alias="ER 控制器集群VIP")
    er_controller_node_ips: List[IPvAnyAddress] = Field(default_factory=list, alias="ER 控制器节点IP列表")
    er_controller_serial: Optional[str] = Field(None, alias="ER 控制器序列号")
    ntp_servers: List[IPvAnyAddress | str] = Field(default_factory=list, alias="NTP 服务器")
    dns_servers: List[IPvAnyAddress | str] = Field(default_factory=list, alias="DNS 服务器")
    临时测试IP范围: Optional[Dict[str, IPvAnyAddress | str]] = Field(None, alias="临时测试IP范围")
    Cloudtower组织名称: Optional[str] = Field(None, alias="Cloudtower 组织名称")
    Cloudtower数据中心名称: Optional[str] = Field(None, alias="Cloudtower 数据中心名称")

class PlanModel(BaseModel):
    virtual_network: List[VirtualNetworkRow] = []
    hosts: List[HostRow] = []
    mgmt: Optional[MgmtInfo] = None
    source_file: Optional[str] = None
    storage_architecture: Optional[str] = None
    network_architecture: Optional[str] = None

