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

"""快速构建部署载荷并支持交互式选择主机扫描数据来源。

脚本读取规划表后可以：

* 使用内建 mock 数据生成示例部署载荷（默认）。
* 调用真实 API 扫描主机，利用返回的网卡 / 磁盘信息构建载荷。

适合在本地查看 `ClusterDeployPayload` 结构或导出 JSON 供后续流程调试。
"""
# python scripts/test_build_payload.py --plan "05.【模板】SmartX超融合核心平台规划设计表-ELF环境-v20250820.xlsx" --mode real --output .\release\sample_deploy_payload.json


from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cxvoyager.common.config import load_config
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE
from cxvoyager.integrations.excel.planning_sheet_parser import find_plan_file, parse_plan, to_model
from cxvoyager.core.deployment.host_discovery_scanner import scan_hosts
from cxvoyager.models import (
    ClusterDeployPayload,
    HostDeployPayload,
    HostDiskScan,
    HostIface,
    Network,
    VDS,
    VDSBond,
)
from cxvoyager.common.ip_utils import pick_prefer_ipv6
from cxvoyager.common.mock_scan_host import mock_scan_host


def _resolve_plan(path: str | None) -> Path:
    if path:
        candidate = Path(path).expanduser().resolve()
        if candidate.is_file():
            return candidate
        raise SystemExit(f"指定的规划表不存在: {path}")

    auto = find_plan_file(Path.cwd())
    if not auto:
        raise SystemExit("未在当前目录找到符合命名约定的规划表，请使用 --plan 指定。")
    return auto


def _prompt_mode(enable_prompt: bool) -> str:
    if not enable_prompt:
        return "mock"

    choices = {
        "1": "mock",
        "m": "mock",
        "mock": "mock",
        "2": "real",
        "r": "real",
        "real": "real",
    }
    print("\n请选择主机数据来源：")
    print("  [1] 使用内建示例 (Mock 数据，默认)")
    print("  [2] 扫描真实主机 (调用 API)")
    while True:
        answer = input("请输入选项 (1/2)：").strip().lower()
        if not answer:
            return "mock"
        if answer in choices:
            return choices[answer]
        print("无效的输入，请重新选择 1 或 2。")


def _prompt_real_scan_config(enable_prompt: bool) -> Tuple[str | None, str | None, int]:
    cfg = load_config(DEFAULT_CONFIG_FILE)
    api_cfg = cfg.get("api", {}) if isinstance(cfg, dict) else {}
    base_url = api_cfg.get("base_url")
    token = api_cfg.get("token")
    timeout = api_cfg.get("timeout", 10)

    if not enable_prompt:
        return base_url, token, timeout

    print("\n将使用真实 API 进行主机扫描，可根据需要覆盖配置文件参数。直接回车表示沿用默认值。")
    if base_url:
        print(f"当前 base_url: {base_url}")
    else:
        print("当前 base_url: 未配置，将使用各主机管理 IP 作为请求地址。")
    custom_base = input("自定义 base_url (可选)：").strip()
    if custom_base:
        base_url = custom_base.rstrip("/")

    if token:
        masked = token[:4] + "..." if len(token) > 8 else "*" * len(token)
        print(f"当前 token: {masked} (来自 cxvoyager/common/config/default.yml)")
    custom_token = getpass.getpass("自定义 token (可选)：")
    if custom_token:
        token = custom_token.strip() or None

    custom_timeout = input(f"请求超时 (秒, 默认 {timeout})：").strip()
    if custom_timeout:
        try:
            timeout = max(1, int(custom_timeout))
        except ValueError:
            print("超时必须为正整数，已沿用默认值。")
    return base_url, token, timeout


def _scan_hosts_mock(model) -> Dict[str, dict]:
    results: Dict[str, dict] = {}
    for idx, host in enumerate(model.hosts):
        mgmt_ip = str(host.管理地址) if host.管理地址 else None
        base_ip = mgmt_ip or f"192.168.0.{10 + idx}"
        payload = mock_scan_host(base_ip)
        ifaces = payload.setdefault("ifaces", [])
        if not ifaces:
            ifaces.append({"name": "port-mgmt", "ipv4": [], "ipv6": []})
        if mgmt_ip:
            ifaces[0].setdefault("ipv4", [])
            ifaces[0]["ipv4"] = [mgmt_ip]
            payload["host_ip"] = mgmt_ip
        results[payload.get("host_ip", base_ip)] = payload
    return results


def _build_ifaces(items: list[dict] | None) -> List[HostIface]:
    ifaces: List[HostIface] = []
    if not items:
        return ifaces
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("iface") or item.get("device")
        if not name:
            continue
        ipv4 = [str(ip) for ip in item.get("ipv4", []) if ip]
        ipv6 = [str(ip) for ip in item.get("ipv6", []) if ip]
        iface = HostIface(
            name=name,
            mac=item.get("mac"),
            speed=item.get("speed"),
            ipv4=ipv4,
            ipv6=ipv6,
            is_up=item.get("is_up"),
        )
        ifaces.append(iface)
    return ifaces


def _build_disks(items: list[dict] | None) -> Tuple[List[HostDiskScan], bool]:
    disks: List[HostDiskScan] = []
    has_cache_candidate = False
    if not items:
        return disks, has_cache_candidate

    for item in items:
        if not isinstance(item, dict):
            continue
        disk_type_raw = item.get("type") or item.get("media_type")
        disk_type = disk_type_raw.lower() if isinstance(disk_type_raw, str) else disk_type_raw
        is_system = bool(item.get("is_system", False) or item.get("function") == "boot")
        can_be_cache = item.get("can_be_cache")
        if can_be_cache is None:
            can_be_cache = disk_type in {"ssd", "nvme"} and not is_system
        can_be_data = item.get("can_be_data")
        if can_be_data is None:
            can_be_data = not is_system

        disk = HostDiskScan(
            name=item.get("name") or item.get("device") or item.get("drive") or f"disk{len(disks) + 1}",
            size_gb=item.get("size_gb") or item.get("size"),
            model=item.get("model"),
            type=disk_type,
            rpm=item.get("rpm"),
            is_system=is_system,
            can_be_cache=can_be_cache,
            can_be_data=can_be_data,
        )
        if disk.can_be_cache and (disk.size_gb or 0) >= 400:
            has_cache_candidate = True
        disks.append(disk)
    return disks, has_cache_candidate


def _build_host_payloads(model, scan_data: Dict[str, dict]) -> List[HostDeployPayload]:
    hosts: List[HostDeployPayload] = []

    for idx, host in enumerate(model.hosts):
        mgmt_ip = str(host.管理地址) if host.管理地址 else None
        storage_ip = str(host.存储地址) if host.存储地址 else None
        base_ip = mgmt_ip or f"192.168.0.{10 + idx}"

        raw = {}
        if mgmt_ip and mgmt_ip in scan_data:
            raw = scan_data[mgmt_ip] or {}
        elif base_ip in scan_data:
            raw = scan_data[base_ip] or {}

        ifaces = _build_ifaces(raw.get("ifaces"))
        disks, has_cache = _build_disks(raw.get("disks"))

        if not ifaces:
            ifaces = [
                HostIface(name="eth0", ipv4=[mgmt_ip] if mgmt_ip else [], ipv6=[]),
                HostIface(name="eth1", ipv4=[], ipv6=[]),
            ]
        if not disks:
            disks = [
                HostDiskScan(name="sda", size_gb=480, type="ssd", is_system=True, can_be_cache=False, can_be_data=False),
                HostDiskScan(name="sdb", size_gb=960, type="ssd", can_be_cache=True, can_be_data=True),
                HostDiskScan(name="sdc", size_gb=2048, type="hdd", can_be_cache=False, can_be_data=True),
            ]
            has_cache = True

        host_uuid = (
            raw.get("host_uuid")
            or raw.get("uuid")
            or raw.get("echo", {}).get("host_uuid")
            or f"mock-host-{idx + 1:02d}"
        )

        preferred_ip = pick_prefer_ipv6(raw.get("ifaces", [])) or raw.get("host_ip") or base_ip

        hosts.append(
            HostDeployPayload(
                host_ip=preferred_ip,
                host_uuid=host_uuid,
                hostname=host.SMTX主机名 or f"node-{idx + 1:02d}",
                mgmt_ip=mgmt_ip,
                storage_ip=storage_ip,
                host_passwords=[
                    {"user": "root", "password": "changeme"},
                    {"user": "smartx", "password": "HC!r0cks"},
                ],
                ifaces=ifaces,
                disks=disks,
                is_master=(idx == 0),
                with_faster_ssd_as_cache=has_cache,
            )
        )
    return hosts


def _build_vdses(parsed) -> List[VDS]:
    derived = parsed.get("_derived_network", {}) if isinstance(parsed, dict) else {}
    vdses: List[VDS] = []
    for item in derived.get("vdses", []):
        bond_raw = item.get("bond") or {}
        vdses.append(
            VDS(
                name=item.get("name", "vds0"),
                bond=VDSBond(
                    mode=bond_raw.get("mode", "ACTIVE_BACKUP"),
                    nics=bond_raw.get("nics", []),
                ),
                mtu=item.get("mtu", 1500),
            )
        )
    if not vdses:
        vdses.append(VDS(name="vds0", bond=VDSBond(mode="ACTIVE_BACKUP", nics=["eth0", "eth1"])))
    return vdses


def _build_networks(parsed) -> List[Network]:
    derived = parsed.get("_derived_network", {}) if isinstance(parsed, dict) else {}
    networks: List[Network] = []
    for item in derived.get("networks", []):
        metadata = item.get("metadata") or {}
        networks.append(
            Network(
                name=item.get("name", "network"),
                vds=item.get("vds", "vds0"),
                vlan=metadata.get("vlan_id"),
                subnetwork=item.get("subnetwork"),
                gateway=metadata.get("gateway"),
                usage=metadata.get("type"),
            )
        )
    if not networks:
        networks.append(
            Network(name="mgmt-net", vds="vds0", subnetwork="192.168.0.0/24", usage="mgmt")
        )
    return networks


def build_payload(parsed: dict, model, scan_data: Dict[str, dict]) -> ClusterDeployPayload:
    if not model.hosts:
        raise SystemExit("规划表中未解析到主机信息，无法构建部署载荷。")

    host_payloads = _build_host_payloads(model, scan_data)
    vdses = _build_vdses(parsed)
    networks = _build_networks(parsed)

    cluster_name = model.hosts[0].集群名称 if model.hosts else "UNKNOWN"
    vip = str(model.hosts[0].集群VIP) if model.hosts and model.hosts[0].集群VIP else None

    payload = ClusterDeployPayload(
        cluster_name=cluster_name,
        vip=vip,
        hosts=host_payloads,
        dns_server=["127.0.0.1"],
        vdses=vdses,
        networks=networks,
    )
    return payload


def _print_summary(mode: str, payload: ClusterDeployPayload, warnings: List[str]) -> None:
    print("", file=sys.stderr)
    print(f"数据来源：{'真实扫描' if mode == 'real' else 'Mock 示例'}", file=sys.stderr)
    print(f"集群名称：{payload.cluster_name}", file=sys.stderr)
    print("主机载荷概览：", file=sys.stderr)
    for host in payload.hosts:
        iface_desc = ", ".join(iface.name for iface in host.ifaces)
        print(
            f"  - {host.hostname} ({host.mgmt_ip or host.host_ip}) | 网卡: {len(host.ifaces)} [{iface_desc}] | 磁盘: {len(host.disks)}",
            file=sys.stderr,
        )
    if warnings:
        print("警告：", file=sys.stderr)
        for msg in warnings:
            print(f"  * {msg}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="测试构建部署载荷并以 JSON 形式输出。")
    parser.add_argument("--plan", help="规划表路径，不提供则自动匹配")
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径；若不指定则打印到标准输出",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON 缩进空格数，默认为 2",
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "real"],
        help="主机数据来源：mock 使用示例数据，real 调用真实 API 扫描 (覆盖交互选择)",
    )
    parser.add_argument(
        "--no-input",
        action="store_true",
        help="以非交互方式运行（无法读取用户输入时自动启用）",
    )

    args = parser.parse_args(argv)

    plan_path = _resolve_plan(args.plan)
    parsed = parse_plan(plan_path)
    model = to_model(parsed)

    if not model.hosts:
        raise SystemExit("规划表中未解析到主机信息，无法构建部署载荷。")

    enable_prompt = sys.stdin.isatty() and not args.no_input
    mode = args.mode or _prompt_mode(enable_prompt)

    if mode == "real":
        base_url, token, timeout = _prompt_real_scan_config(enable_prompt)
        try:
            scan_data, warnings = scan_hosts(model, base_url=base_url, token=token, timeout=timeout)
            if not scan_data:
                raise RuntimeError("未获取到任何主机扫描结果")
        except Exception as exc:
            print(f"错误: 主机扫描失败 - {exc}")
            print("提示: 请检查网络连接、API配置或使用 --mode mock 进行测试")
            return 1
    else:
        scan_data = _scan_hosts_mock(model)
        warnings = []

    payload = build_payload(parsed, model, scan_data)
    _print_summary(mode, payload, warnings)
    payload_dict = payload.model_dump()

    json_text = json.dumps(payload_dict, ensure_ascii=False, indent=args.indent)

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_text + "\n", encoding="utf-8")
        print(f"部署载荷已写入 {output_path}")
    else:
        print(json_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())

