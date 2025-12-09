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

"""Mock 主机扫描结果生成器。

参考真实 API 返回结构，生成带有随机 IPv6、序列号等信息的示例数据。
"""
from __future__ import annotations

import ipaddress
import random
import uuid
from typing import Any, Dict, List

__all__ = ["mock_scan_host", "generate_mock_hostname"]


def _random_mac(rng: random.Random) -> str:
    """生成本地管理位设置为 1 的随机 MAC 地址。"""
    octets = [rng.randrange(0x00, 0xFF) for _ in range(6)]
    octets[0] |= 0x02  # 设置本地管理位
    octets[0] &= 0xFE  # 确保不是多播
    return ":".join(f"{octet:02x}" for octet in octets)


def _random_ipv6_link_local(rng: random.Random) -> str:
    hextets = [f"{rng.getrandbits(16):x}" for _ in range(4)]
    return "fe80::" + ":".join(hextets)


def _random_disk_set(rng: random.Random) -> List[Dict[str, Any]]:
    base_serial = uuid.uuid4().hex[:12].upper()
    disks: List[Dict[str, Any]] = []
    profiles = [
        ("nvme0n1", "cache", 1.5 * 1024**4, "SSD"),
        ("nvme0n2", "cache", 1.5 * 1024**4, "SSD"),
        ("sda", "boot", 480 * 1024**3, "SSD"),
        ("sdb", "data", 2 * 1024**4, "HDD"),
        ("sdc", "data", 2 * 1024**4, "HDD"),
    ]
    for idx, (name, function, size, media_type) in enumerate(profiles, start=1):
        disks.append(
            {
                "drive": name,
                "function": function,
                "model": "VMware Virtual Disk" if media_type == "HDD" else "VMware Virtual NVMe",
                "serial": f"{base_serial}{idx:02d}",
                "size": int(size),
                "type": media_type,
            }
        )
    # 额外追加两块容量盘，模拟更复杂环境
    extra_count = rng.randint(0, 2)
    for extra_idx in range(extra_count):
        disks.append(
            {
                "drive": f"sd{chr(100 + extra_idx)}",
                "function": "data",
                "model": "VMware Virtual Disk",
                "serial": f"{base_serial}{extra_idx + 10:02d}",
                "size": int(3 * 1024**4),
                "type": "HDD",
            }
        )
    return disks


def generate_mock_hostname(host_ip: str) -> str:
    """根据管理 IP 生成稳定可读的主机名。"""
    try:
        node = ipaddress.ip_address(host_ip)
    except ValueError:
        return f"node-{uuid.uuid4().hex[:6]}"
    if isinstance(node, ipaddress.IPv4Address):
        return f"node-{int(node) % 100:02d}"
    return f"node-{node.compressed.replace(':', '')[:6]}"


def mock_scan_host(host_ip: str, *, rack: str | None = None) -> Dict[str, Any]:
    """生成模拟的主机扫描数据。

    Args:
        host_ip: 管理网 IP。
        rack: 机架编号（可选），用于生成更真实的序列号。
    """
    rng = random.Random(host_ip)
    hostname = generate_mock_hostname(host_ip)
    host_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"smtx::{host_ip}"))
    serial_stub = uuid.uuid4().hex[:12].upper()
    rack_id = rack or f"R{rng.randint(1, 8):02d}"
    serial = f"VMware-{rack_id}-{serial_stub}"[:32]

    try:
        ip_obj = ipaddress.ip_address(host_ip)
        storage_ip = ip_obj + 256 if isinstance(ip_obj, ipaddress.IPv4Address) else ip_obj
        storage_ip_text = str(storage_ip)
    except ValueError:
        storage_ip_text = None

    mgmt_iface = {
        "name": "port-mgmt",
        "mac": _random_mac(rng),
        "ipv4": [host_ip],
        "ipv6": [_random_ipv6_link_local(rng)],
        "speed": 2500000000,
        "is_up": True,
    }
    storage_iface = {
        "name": "port-storage",
        "mac": _random_mac(rng),
        "ipv4": [storage_ip_text] if storage_ip_text else [],
        "ipv6": [_random_ipv6_link_local(rng)],
        "speed": 10000000000,
        "is_up": True,
    }
    backup_iface = {
        "name": "port-backup",
        "mac": _random_mac(rng),
        "ipv4": [],
        "ipv6": [_random_ipv6_link_local(rng)],
        "speed": 1000000000,
        "is_up": rng.choice([True, False]),
    }

    data = {
        "host_ip": host_ip,
        "host_uuid": host_uuid,
        "hostname": hostname,
        "sn": serial,
        "product": "SMTXOS",
        "version": f"6.2.{rng.randint(0, 9)}",
        "status": rng.choice(["ready", "disabled", "maintenance"]),
        "ifaces": [mgmt_iface, storage_iface, backup_iface],
        "disks": _random_disk_set(rng),
        "ipmi_ip": None,
        "is_all_flash": False,
        "is_os_in_single_disk": True,
    }
    return data

