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

"""API 载荷模型定义（符合SmartX API规范）。

基于部署集群载荷示例.json的完整结构定义Pydantic模型，
确保生成的载荷与SmartX API期望的格式完全一致。
"""
from __future__ import annotations
from typing import List, Optional, Literal, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime


# ============= 主机相关模型 =============

class HostPassword(BaseModel):
    """主机密码配置"""
    user: str = Field(..., description="用户名，通常为root或smartx")
    password: str = Field(..., description="加密后的密码")


class HostInterface(BaseModel):
    """主机网络接口配置（用于载荷中的ifaces字段）"""
    ip: str = Field(..., description="IP地址")
    function: Literal["mgt", "storage"] = Field(..., description="接口用途：mgt=管理网络，storage=存储网络")


class HostDisk(BaseModel):
    """主机磁盘配置（载荷格式）"""
    drive: str = Field(..., description="磁盘设备名称，如nvme0n1、sdb等")
    function: Literal["cache", "data", "boot"] = Field(..., description="磁盘用途")
    model: str = Field(..., description="磁盘型号")
    serial: str = Field(..., description="磁盘序列号")
    size: int = Field(..., description="磁盘大小，单位字节")
    type: Literal["SSD", "HDD", "NVME"] = Field(..., description="磁盘类型")


class DeploymentHost(BaseModel):
    """部署载荷中的主机配置"""
    host_ip: str = Field(..., description="主机IPv6地址%网卡名或IPv4地址")
    host_uuid: str = Field(..., description="主机UUID")
    hostname: str = Field(..., description="主机名")
    disk_data_with_cache: bool = Field(False, description="磁盘数据缓存设置，通常为false")
    host_passwords: List[HostPassword] = Field(default_factory=list, description="主机密码配置")
    tags: List[str] = Field(default_factory=list, description="主机标签，通常为空")
    ifaces: List[HostInterface] = Field(default_factory=list, description="网络接口配置")
    disks: List[HostDisk] = Field(default_factory=list, description="磁盘配置")
    is_master: bool = Field(True, description="是否为主节点")
    with_faster_ssd_as_cache: bool = Field(True, description="是否启用SSD作为缓存")


# ============= 网络相关模型 =============

class VDSHostAssociation(BaseModel):
    """VDS与主机的关联配置"""
    host_uuid: str = Field(..., description="主机UUID")
    nics_associated: List[str] = Field(..., description="关联的物理网卡列表")


class VirtualDistributedSwitch(BaseModel):
    """虚拟分布式交换机(VDS)配置"""
    name: str = Field(..., description="VDS名称，如VDS-MGT、VDS-SDS")
    bond_mode: str = Field("active-backup", description="绑定模式")
    hosts_associated: List[VDSHostAssociation] = Field(default_factory=list, description="关联的主机配置")


class NetworkServiceConfig(BaseModel):
    """网络服务配置"""
    host_uuid: str = Field(..., description="主机UUID")
    service_interface_name: str = Field(..., description="服务接口名称，如port-mgt、port-storage")
    service_interface_ip: str = Field(..., description="服务接口IP地址")
    netmask: str = Field(..., description="子网掩码")


class NetworkRouteConfig(BaseModel):
    """网络路由配置"""
    gateway: str = Field(..., description="网关地址")


class NetworkModeConfig(BaseModel):
    """网络模式配置"""
    type: str = Field("vlan_access", description="网络模式类型")
    network_identities: List[int] = Field(default_factory=list, description="VLAN ID列表")


class NetworkConfig(BaseModel):
    """网络配置"""
    service: List[NetworkServiceConfig] = Field(default_factory=list, description="服务配置")
    route: Optional[List[NetworkRouteConfig]] = Field(None, description="路由配置，仅管理网络需要")


class VirtualNetwork(BaseModel):
    """虚拟网络配置"""
    name: str = Field(..., description="网络名称")
    attached_vds: str = Field(..., description="所属VDS名称")
    network_type: Literal["mgt", "storage"] = Field(..., description="网络类型")
    network_config: NetworkConfig = Field(..., description="网络配置")
    mode: NetworkModeConfig = Field(..., description="网络模式配置")


# ============= 时间和系统配置 =============

class NTPConfig(BaseModel):
    """NTP配置"""
    mode: str = Field("internal", description="NTP模式，internal或external")
    ntp_server: Optional[str] = Field(None, description="NTP服务器地址，internal模式下为null")
    current_time: str = Field(..., description="当前时间，ISO格式")


# ============= 完整部署载荷模型 =============

class ClusterDeploymentPayload(BaseModel):
    """集群部署载荷（完整版本）"""
    platform: str = Field("kvm", description="平台类型，固定为kvm")
    cluster_name: str = Field(..., description="集群名称")
    dns_server: List[str] = Field(default_factory=lambda: ["127.0.0.1"], description="DNS服务器列表")
    vdses: List[VirtualDistributedSwitch] = Field(default_factory=list, description="虚拟分布式交换机配置")
    networks: List[VirtualNetwork] = Field(default_factory=list, description="虚拟网络配置")
    hosts: List[DeploymentHost] = Field(default_factory=list, description="主机配置")
    ntp: NTPConfig = Field(..., description="NTP配置")
    vhost_enabled: bool = Field(True, description="vhost功能开关")
    rdma_enabled: bool = Field(False, description="RDMA功能开关")


# ============= 向后兼容的简化模型 =============

class HostIface(BaseModel):
    """主机网卡信息（扫描结果格式）"""
    name: str
    mac: Optional[str] = None
    speed: Optional[int] = None  # Mbps
    ipv4: List[str] = []
    ipv6: List[str] = []
    is_up: Optional[bool] = None


class HostDiskScan(BaseModel):
    """主机磁盘信息（扫描结果格式）"""
    name: str
    size_gb: Optional[float] = None
    model: Optional[str] = None
    type: Optional[str] = None  # ssd / hdd / nvme
    rpm: Optional[int] = None
    is_system: bool = False
    can_be_cache: bool = False
    can_be_data: bool = True


class HostDeployPayload(BaseModel):
    """主机部署载荷（简化版本，向后兼容）"""
    host_ip: str
    host_uuid: str
    hostname: str
    mgmt_ip: Optional[str] = None
    storage_ip: Optional[str] = None
    host_passwords: List[dict] = []
    ifaces: List[HostIface] = []
    disks: List[HostDiskScan] = []
    is_master: bool = True
    with_faster_ssd_as_cache: bool = False


class VDSBond(BaseModel):
    """VDS绑定配置（简化版本）"""
    mode: Literal["ACTIVE_BACKUP", "LACP", "SLB"] = Field(
        "ACTIVE_BACKUP", description="内部统一表示：active-backup->ACTIVE_BACKUP, balance-tcp->LACP, balance-slb->SLB"
    )
    nics: List[str] = []


class VDS(BaseModel):
    """虚拟分布式交换机（简化版本）"""
    name: str
    bond: Optional[VDSBond] = None
    mtu: int = 1500


class Network(BaseModel):
    """网络配置（简化版本）"""
    name: str
    vds: str
    vlan: Optional[int] = None
    subnetwork: Optional[str] = None  # CIDR
    gateway: Optional[str] = None
    usage: Optional[str] = None  # mgmt / storage / vm / etc.


class ClusterDeployPayload(BaseModel):
    """集群部署载荷（简化版本，向后兼容）"""
    platform: str = "kvm"
    cluster_name: str
    vip: Optional[str] = None
    hosts: List[HostDeployPayload]
    dns_server: List[str] = []
    vdses: List[VDS] = []
    networks: List[Network] = []


class CloudtowerConfigPayload(BaseModel):
    """Cloudtower配置载荷"""
    ip: str
    admin_password: str

