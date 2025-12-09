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

"""集群部署载荷生成器

基于规划表和主机扫描结果，生成符合SmartX API规范的完整部署载荷。
载荷结构严格遵循 部署集群载荷示例.json 的格式和要求。
"""

from __future__ import annotations
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from cxvoyager.models.planning_sheet_models import PlanModel
from cxvoyager.models.deployment_payload_models import (
    ClusterDeploymentPayload, DeploymentHost, HostPassword, HostInterface, HostDisk,
    VirtualDistributedSwitch, VDSHostAssociation, VirtualNetwork, NetworkConfig,
    NetworkServiceConfig, NetworkRouteConfig, NetworkModeConfig, NTPConfig
)
from cxvoyager.common.ip_utils import pick_prefer_ipv6

logger = logging.getLogger(__name__)


class DeploymentPayloadGenerator:
    """集群部署载荷生成器"""
    
    def __init__(
        self,
        plan: PlanModel,
        host_scan_data: Dict[str, Dict[str, Any]],
        parsed_plan: Optional[Dict] = None,
        artifact_dir: Union[Path, str, None] = None,
    ):
        """
        初始化载荷生成器
        
        Args:
            plan: 解析后的规划表模型
            host_scan_data: 主机扫描结果数据，key为管理IP，value为主机扫描数据
            parsed_plan: 原始解析的规划表数据（包含_derived_network等）
        """
        self.plan = plan
        self.host_scan_data = host_scan_data
        self.parsed_plan = parsed_plan or {}
        self.artifact_dir = self._resolve_artifact_dir(artifact_dir)
        self.saved_artifact_path: Path | None = None
        self._vds_role_to_name: Dict[str, str] = {}
        
    def generate(self) -> Dict[str, Any]:
        """生成完整的部署载荷"""
        if not self.plan.hosts:
            raise ValueError("规划表中没有主机信息")
            
        # 获取集群基本信息
        cluster_name = self.plan.hosts[0].集群名称 if self.plan.hosts else "HCI-01"
        
        # 构建载荷各部分
        payload = {
            "platform": "kvm",  # 固定为kvm
            "cluster_name": cluster_name,
            "dns_server": self._build_dns_servers(),
            "vdses": self._build_vdses(),
            "networks": self._build_networks(),
            "hosts": self._build_hosts(),
            "ntp": self._build_ntp_config(),
            "vhost_enabled": self._get_vhost_enabled(),
            "rdma_enabled": self._get_rdma_enabled()
        }
        
        self.saved_artifact_path = self._persist_payload(payload, cluster_name)
        logger.info("集群部署载荷生成完成: %s，已保存到 %s", cluster_name, self.saved_artifact_path)
        return payload

    def _resolve_artifact_dir(self, override: Union[Path, str, None]) -> Path:
        if override:
            return Path(override).expanduser().resolve()
        # 默认使用项目根目录下的 artifacts
        project_root = Path(__file__).resolve().parents[3]
        return project_root / "artifacts"

    def _persist_payload(self, payload: Dict[str, Any], cluster_name: str) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        safe_cluster = re.sub(r"[^\w.-]+", "_", cluster_name or "cluster")
        filename = f"deploy_{timestamp}_{safe_cluster}.json"
        target_dir = self.artifact_dir
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / filename
            with target_path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
        except Exception as exc:  # noqa: BLE001 - ensure持久化失败不会悄然吞掉
            logger.exception("保存部署载荷到 %s 失败", target_dir)
            raise RuntimeError("保存部署载荷失败") from exc
        return target_path
    
    def _build_dns_servers(self) -> List[str]:
        """构建DNS服务器配置"""
        # TODO: 从规划表中读取DNS配置，目前使用默认值
        return ["127.0.0.1"]

    def _collect_host_uuid_info(self) -> Tuple[List[str], Dict[str, Dict[str, List[str]]]]:
        host_uuids: List[str] = []
        fallback: Dict[str, Dict[str, List[str]]] = {}

        for host in self.plan.hosts:
            mgmt_ip = str(host.管理地址) if host.管理地址 else None
            if not mgmt_ip:
                continue
            scan_data = self.host_scan_data.get(mgmt_ip)
            if not isinstance(scan_data, dict):
                continue
            host_uuid = scan_data.get("host_uuid")
            if not host_uuid:
                continue
            if host_uuid not in host_uuids:
                host_uuids.append(host_uuid)
            fallback[host_uuid] = self._group_host_nics(scan_data)

        return host_uuids, fallback

    def _group_host_nics(self, scan_data: Dict[str, Any]) -> Dict[str, List[str]]:
        ifaces = scan_data.get("ifaces", [])
        nic_names: List[str] = []
        if isinstance(ifaces, list):
            for iface in ifaces:
                if not isinstance(iface, dict):
                    continue
                name = iface.get("name")
                if name:
                    nic_names.append(str(name).strip())

        nic_names = self._dedupe_preserve(nic_names)
        mgmt_slice = self._dedupe_preserve(nic_names[:2])
        storage_slice = self._dedupe_preserve(nic_names[2:4]) or mgmt_slice

        return {
            "mgmt": mgmt_slice,
            "storage": storage_slice,
            "all": nic_names,
        }

    def _extract_plan_vds_info(self, vdses_config: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        info: Dict[str, Dict[str, Any]] = {}
        derived = self.parsed_plan.get("_derived_network", {}) if isinstance(self.parsed_plan, dict) else {}
        source = derived.get("vdses", []) if isinstance(derived, dict) else []
        if not source:
            source = vdses_config

        for entry in source:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("vds")
            if not name:
                continue

            bond_value = entry.get("bond")
            bond = bond_value if isinstance(bond_value, dict) else {}
            nics_value = bond.get("nics")
            if isinstance(nics_value, (list, tuple)):
                nics = self._dedupe_preserve([str(n).strip() for n in nics_value if n])
            else:
                nics = []
            bond_mode_candidate = entry.get("bond_mode") or bond.get("mode")

            info[name] = {
                "bond_mode": self._normalize_bond_mode(bond_mode_candidate),
                "nics": nics,
            }

        return info

    def _extract_vds_roles(self) -> Dict[str, str]:
        records_section = self.parsed_plan.get("virtual_network", {}) if isinstance(self.parsed_plan, dict) else {}
        records = records_section.get("records", []) if isinstance(records_section, dict) else []
        roles: Dict[str, str] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            vds_name = record.get("虚拟交换机")
            label = record.get("网络标识")
            role = self._infer_vds_role(label)
            if vds_name and role and vds_name not in roles:
                roles[vds_name] = role
        return roles

    def _infer_vds_role(self, label: Any) -> Optional[str]:
        if not label:
            return None
        text = str(label).strip().lower()
        if not text:
            return None
        if any(key in text for key in ("mgmt", "management", "default")):
            return "mgmt"
        if "storage" in text:
            return "storage"
        if "backup" in text:
            return "backup"
        if "business" in text:
            return "business"
        return None

    def _normalize_bond_mode(self, mode: Any) -> str:
        if not mode:
            return "active-backup"

        text = str(mode).strip()
        lower = text.lower().replace("_", "-")
        mapping_lower = {
            "active-backup": "active-backup",
            "active backup": "active-backup",
            "balance-tcp": "balance-tcp",
            "balance tcp": "balance-tcp",
            "balance-slb": "balance-slb",
            "balance slb": "balance-slb",
            "lacp": "balance-tcp",
            "slb": "balance-slb",
        }
        if lower in mapping_lower:
            return mapping_lower[lower]

        mapping_upper = {
            "ACTIVE_BACKUP": "active-backup",
            "LACP": "balance-tcp",
            "SLB": "balance-slb",
        }
        return mapping_upper.get(text.upper(), "active-backup")

    def _dedupe_preserve(self, items: List[str]) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for item in items:
            if not item:
                continue
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    def _resolve_vds_name_for_role(self, role: str, default: str) -> str:
        return self._vds_role_to_name.get(role) or default
    
    def _build_vdses(self) -> List[Dict[str, Any]]:
        """构建虚拟分布式交换机(VDS)配置"""

        derived_network = self.parsed_plan.get("_derived_network", {}) if isinstance(self.parsed_plan, dict) else {}
        raw_vdses_config = derived_network.get("vdses", []) if isinstance(derived_network, dict) else []
        if not isinstance(raw_vdses_config, list):
            raw_vdses_config = []

        plan_vds_info = self._extract_plan_vds_info(raw_vdses_config)
        vds_roles = self._extract_vds_roles()
        host_uuids, host_fallback_nics = self._collect_host_uuid_info()

        role_order = {"mgmt": 0, "storage": 1}
        allowed_roles = set(role_order)
        selected_entries: List[Tuple[str, Dict[str, Any]]] = []
        self._vds_role_to_name = {}

        for vds_config in raw_vdses_config:
            if not isinstance(vds_config, dict):
                continue
            vds_name = vds_config.get("name") or vds_config.get("vds")
            if not vds_name:
                continue
            role = vds_roles.get(vds_name) or self._infer_vds_role(vds_name)
            if role not in allowed_roles:
                continue
            if role in self._vds_role_to_name:
                continue
            selected_entries.append((role, vds_config))
            self._vds_role_to_name[role] = vds_name

        if not selected_entries:
            logger.warning("未找到VDS配置，使用默认配置")

        defaults = {
            "mgmt": {"name": "VDS-MGT", "bond_mode": "active-backup"},
            "storage": {"name": "VDS-SDS", "bond_mode": "active-backup"},
        }
        for role, default_cfg in defaults.items():
            if role not in self._vds_role_to_name:
                selected_entries.append((role, default_cfg))
                self._vds_role_to_name[role] = default_cfg["name"]

        selected_entries.sort(key=lambda item: role_order.get(item[0], 99))

        vdses: List[Dict[str, Any]] = []
        for role, vds_config in selected_entries:
            vds_name = vds_config.get("name") or vds_config.get("vds") or "VDS"
            plan_info = plan_vds_info.get(vds_name, {})
            bond_value = vds_config.get("bond")
            bond_dict = bond_value if isinstance(bond_value, dict) else {}
            bond_mode = plan_info.get("bond_mode") or self._normalize_bond_mode(
                vds_config.get("bond_mode") or bond_dict.get("mode")
            )
            plan_nics = [nic for nic in plan_info.get("nics", []) if nic]

            hosts_associated: List[Dict[str, Any]] = []
            for host_uuid in host_uuids:
                fallback = host_fallback_nics.get(host_uuid, {})
                associated_nics: List[str] = []
                if plan_nics:
                    associated_nics = list(plan_nics)
                else:
                    if role and fallback.get(role):
                        associated_nics = list(fallback[role])
                    elif fallback.get("all"):
                        associated_nics = list(fallback["all"])

                if associated_nics:
                    hosts_associated.append({
                        "host_uuid": host_uuid,
                        "nics_associated": associated_nics,
                    })

            vdses.append({
                "name": vds_name,
                "bond_mode": bond_mode or "active-backup",
                "hosts_associated": hosts_associated,
            })

        return vdses
    
    def _build_networks(self) -> List[Dict[str, Any]]:
        """构建虚拟网络配置"""
        networks = []
        
        # 构建管理网络
        mgmt_network = self._build_management_network()
        if mgmt_network:
            networks.append(mgmt_network)
        
        # 构建存储网络
        storage_network = self._build_storage_network()
        if storage_network:
            networks.append(storage_network)
        
        return networks
    
    def _build_management_network(self) -> Optional[Dict[str, Any]]:
        """构建管理网络配置"""
        # 收集所有主机的管理网络配置
        service_configs = []
        gateway = None
        netmask = None
        vlan_id = 0
        
        for host in self.plan.hosts:
            mgmt_ip = str(host.管理地址) if host.管理地址 else None
            if mgmt_ip and mgmt_ip in self.host_scan_data:
                scan_data = self.host_scan_data[mgmt_ip]
                host_uuid = scan_data.get("host_uuid")
                
                if host_uuid:
                    service_configs.append({
                        "host_uuid": host_uuid,
                        "service_interface_name": "port-mgt",  # 固定值
                        "service_interface_ip": mgmt_ip,
                        "netmask": getattr(host, "管理网络子网掩码", "255.255.255.0")
                    })
                    
                    # 获取网关和VLAN信息（从第一个主机）
                    if gateway is None:
                        gateway = getattr(host, "管理网络网关", None)
                        if gateway:
                            gateway = str(gateway)
                    
                    if netmask is None:
                        netmask = getattr(host, "管理网络子网掩码", "255.255.255.0")
                    
                    # TODO: 从规划表获取VLAN ID
                    vlan_id = getattr(host, "管理网络VLAN", 0) or 0
        
        if not service_configs:
            return None
        
        network = {
            "name": "mgt-network",
            "attached_vds": self._resolve_vds_name_for_role("mgmt", "VDS-MGT"),
            "network_type": "mgt",
            "network_config": {
                "service": service_configs
            },
            "mode": {
                "type": "vlan_access",
                "network_identities": [vlan_id]
            }
        }
        
        # 添加路由配置（管理网络必须有路由配置）
        if gateway:
            network["network_config"]["route"] = [{"gateway": gateway}]
        else:
            # 如果没有指定网关，使用默认网关（从管理IP推断）
            if service_configs:
                first_mgmt_ip = service_configs[0]["service_interface_ip"]
                # 假设网关是网段的第一个IP
                import ipaddress
                try:
                    ip_obj = ipaddress.IPv4Address(first_mgmt_ip)
                    # 假设是/24网络，网关是.1
                    network_parts = str(ip_obj).split('.')
                    network_parts[-1] = '1'
                    default_gateway = '.'.join(network_parts)
                    network["network_config"]["route"] = [{"gateway": default_gateway}]
                except:
                    # 如果IP解析失败，使用固定默认网关
                    network["network_config"]["route"] = [{"gateway": "10.0.20.1"}]
        
        return network
    
    def _build_storage_network(self) -> Optional[Dict[str, Any]]:
        """构建存储网络配置"""
        service_configs = []
        vlan_id = 0
        
        for host in self.plan.hosts:
            mgmt_ip = str(host.管理地址) if host.管理地址 else None
            storage_ip = str(host.存储地址) if host.存储地址 else None
            
            if mgmt_ip and mgmt_ip in self.host_scan_data and storage_ip:
                scan_data = self.host_scan_data[mgmt_ip]
                host_uuid = scan_data.get("host_uuid")
                
                if host_uuid:
                    service_configs.append({
                        "host_uuid": host_uuid,
                        "service_interface_name": "port-storage",  # 固定值
                        "service_interface_ip": storage_ip,
                        "netmask": getattr(host, "存储网络子网掩码", "255.255.255.0")
                    })
                    
                    # TODO: 从规划表获取存储网络VLAN ID
                    vlan_id = getattr(host, "存储网络VLAN", 0) or 0
        
        if not service_configs:
            return None
        
        return {
            "name": "storage-network",
            "attached_vds": self._resolve_vds_name_for_role("storage", "VDS-SDS"),
            "network_type": "storage",
            "network_config": {
                "service": service_configs
            },
            "mode": {
                "type": "vlan_access",
                "network_identities": [vlan_id]
            }
        }
    
    def _build_hosts(self) -> List[Dict[str, Any]]:
        """构建主机配置"""
        hosts = []
        
        for idx, host in enumerate(self.plan.hosts):
            mgmt_ip = str(host.管理地址) if host.管理地址 else None
            if mgmt_ip and mgmt_ip in self.host_scan_data:
                scan_data = self.host_scan_data[mgmt_ip]
                host_config = self._build_single_host(host, scan_data, idx)
                if host_config:
                    hosts.append(host_config)
        
        return hosts
    
    def _build_single_host(self, host, scan_data: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
        """构建单个主机配置"""
        host_uuid = scan_data.get("host_uuid")
        if not host_uuid:
            logger.warning("主机 %s 缺少UUID，跳过", host.管理地址)
            return None
        
        # 获取IPv6地址（优先选择）
        ifaces = scan_data.get("ifaces", [])
        host_ip = pick_prefer_ipv6(ifaces) or str(host.管理地址)
        
        # 构建主机密码配置
        host_passwords = [
            {"user": "root", "password": "c+G6KvJYsKyQyY4U"},  # 固定加密密码
            {"user": "smartx", "password": "c+G6KvJYsKyQyY4U"}
        ]
        
        # 构建网络接口配置
        host_ifaces = []
        mgmt_ip = str(host.管理地址) if host.管理地址 else None
        storage_ip = str(host.存储地址) if host.存储地址 else None
        
        if mgmt_ip:
            host_ifaces.append({
                "ip": mgmt_ip,
                "function": "mgt"
            })
        
        if storage_ip:
            host_ifaces.append({
                "ip": storage_ip,
                "function": "storage"
            })
        
        # 构建磁盘配置
        disks = self._build_host_disks(scan_data.get("disks", []))
        
        # 判断是否为主节点
        total_hosts = len(self.plan.hosts)
        is_master = index < 3 if total_hosts < 5 else index < 5
        
        # 检查是否启用分层存储
        with_faster_ssd_as_cache = self._check_tiered_storage_enabled() and self._has_cache_disks(disks)
        
        return {
            "host_ip": host_ip,
            "host_uuid": host_uuid,
            "hostname": host.SMTX主机名 or f"node-{index + 1:02d}",
            "disk_data_with_cache": False,  # 固定为false
            "host_passwords": host_passwords,
            "tags": [],
            "ifaces": host_ifaces,
            "disks": disks,
            "is_master": is_master,
            "with_faster_ssd_as_cache": with_faster_ssd_as_cache
        }
    
    def _build_host_disks(self, disks_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """构建主机磁盘配置"""
        disks = []
        allowed_functions = {"smtx_system", "data", "cache"}
        
        for disk_data in disks_data:
            function_raw = str(disk_data.get("function", "data") or "data").lower()
            if function_raw not in allowed_functions:
                logger.debug("忽略不支持的磁盘功能 %s: %s", function_raw, disk_data)
                continue

            disk = {
                "drive": disk_data.get("drive") or disk_data.get("name", "unknown"),
                "function": function_raw,
                "model": disk_data.get("model", "Unknown Model"),
                "serial": disk_data.get("serial", "Unknown Serial"),
                "size": disk_data.get("size") or (disk_data.get("size_gb", 0) * 1024 * 1024 * 1024),
                "type": disk_data.get("type", "HDD").upper()
            }
            disks.append(disk)
        
        return disks
    
    def _build_ntp_config(self) -> Dict[str, Any]:
        """构建NTP配置"""
        return {
            "mode": "internal",  # 固定为internal避免部署失败
            "ntp_server": None,
            "current_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
    
    def _get_vhost_enabled(self) -> bool:
        """获取vhost功能开关状态"""
        # TODO: 从规划表读取集群功能选项
        # 目前返回默认值true
        return True
    
    def _get_rdma_enabled(self) -> bool:
        """获取RDMA功能开关状态"""
        # TODO: 从规划表读取集群功能选项
        # 目前返回默认值false
        return False
    
    def _check_tiered_storage_enabled(self) -> bool:
        """检查是否启用分层存储"""
        # TODO: 从规划表读取分层存储配置
        return True
    
    def _has_cache_disks(self, disks: List[Dict[str, Any]]) -> bool:
        """检查是否有缓存盘"""
        return any(disk.get("function") == "cache" for disk in disks)
    
def generate_deployment_payload(
    plan: PlanModel,
    host_scan_data: Dict[str, Dict[str, Any]],
    parsed_plan: Optional[Dict] = None,
    *,
    artifact_dir: Union[Path, str, None] = None,
) -> Tuple[Dict[str, Any], Path]:
    """
    生成集群部署载荷的便捷函数
    
    Args:
        plan: 解析后的规划表模型
        host_scan_data: 主机扫描结果数据
        parsed_plan: 原始解析的规划表数据
        
    Returns:
        完整的部署载荷字典
    """
    generator = DeploymentPayloadGenerator(plan, host_scan_data, parsed_plan, artifact_dir=artifact_dir)
    payload = generator.generate()
    artifact_path = generator.saved_artifact_path
    if artifact_path is None:
        raise RuntimeError("载荷生成后未找到保存路径")
    return payload, artifact_path