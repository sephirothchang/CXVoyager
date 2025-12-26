#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# This file is part of CXVoyager.

"""测试新的载荷生成器功能

验证生成的载荷与部署集群载荷示例.json的结构一致性。
"""

from __future__ import annotations
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cxvoyager.library.integrations.excel.planning_sheet_parser import parse_plan, to_model
from cxvoyager.process.workflow.payload_builder import generate_deployment_payload
from cxvoyager.process.workflow.host_discovery_scanner import scan_hosts
from cxvoyager.utils.mock_scan_host import mock_scan_host


def load_example_payload() -> dict:
    """加载示例载荷文件"""
    example_file = PROJECT_ROOT / "开发辅助工具-忽略且无需处理" / "示例文件" / "部署集群载荷示例.json"
    with open(example_file, 'r', encoding='utf-8') as f:
        content = f.read()
        # 移除注释
        lines = []
        for line in content.split('\n'):
            # 简单的注释移除，不处理字符串内的//
            if '//' in line:
                line = line[:line.find('//')]
            lines.append(line)
        clean_content = '\n'.join(lines)
        return json.loads(clean_content)


def create_mock_host_data(plan_model) -> dict:
    """创建模拟主机扫描数据"""
    host_data = {}
    
    for idx, host in enumerate(plan_model.hosts):
        mgmt_ip = str(host.管理地址) if host.管理地址 else f"192.168.1.{10+idx}"
        
        # 生成模拟数据
        mock_data = mock_scan_host(mgmt_ip)
        
        # 添加一些更真实的字段
        mock_data.update({
            "host_uuid": f"1f967a52-9ac8-11f0-9b61-05cf1b7143e{idx:01d}",
            "host_ip": f"fe80::250:56ff:feb5:944{idx}%ens192",
            "ifaces": [
                {
                    "name": "ens192",
                    "mac": f"00:50:56:b5:94:4{idx}",
                    "ipv4": [mgmt_ip],
                    "ipv6": [f"fe80::250:56ff:feb5:944{idx}"],
                    "speed": 1000,
                    "is_up": True
                },
                {
                    "name": "ens224", 
                    "mac": f"00:50:56:b5:94:5{idx}",
                    "ipv4": [],
                    "ipv6": [],
                    "speed": 1000,
                    "is_up": True
                },
                {
                    "name": "ens256",
                    "mac": f"00:50:56:b5:94:6{idx}",
                    "ipv4": [str(host.存储地址)] if host.存储地址 else [f"10.0.21.{204+idx}"],
                    "ipv6": [],
                    "speed": 1000,
                    "is_up": True
                },
                {
                    "name": "ens161",
                    "mac": f"00:50:56:b5:94:7{idx}",
                    "ipv4": [],
                    "ipv6": [],
                    "speed": 1000,
                    "is_up": True
                }
            ],
            "disks": [
                {
                    "drive": "nvme0n1",
                    "function": "cache",
                    "model": "VMware Virtual NVMe Disk",
                    "serial": "VMware NVME_0000",
                    "size": 1759218604032,
                    "type": "SSD"
                },
                {
                    "drive": "nvme0n2", 
                    "function": "cache",
                    "model": "VMware Virtual NVMe Disk",
                    "serial": "VMware NVME_0000",
                    "size": 1759218604032,
                    "type": "SSD"
                },
                {
                    "drive": "sdb",
                    "function": "data", 
                    "model": "VMware_Virtual_SATA_Hard_Drive",
                    "serial": f"0{idx+1}000000000000000001",
                    "size": 2199023255552,
                    "type": "HDD"
                },
                {
                    "drive": "sdc",
                    "function": "data",
                    "model": "VMware_Virtual_SATA_Hard_Drive", 
                    "serial": f"0{idx+2}000000000000000001",
                    "size": 2199023255552,
                    "type": "HDD"
                }
            ]
        })
        
        host_data[mgmt_ip] = mock_data
    
    return host_data


def compare_structures(generated: dict, example: dict, path: str = "") -> list[str]:
    """比较两个载荷结构的差异"""
    differences = []
    
    # 比较顶层字段
    gen_keys = set(generated.keys())
    exp_keys = set(example.keys())
    
    missing_keys = exp_keys - gen_keys
    extra_keys = gen_keys - exp_keys
    
    if missing_keys:
        differences.append(f"{path}: 缺少字段 {missing_keys}")
    if extra_keys:
        differences.append(f"{path}: 多余字段 {extra_keys}")
    
    # 比较共同字段的类型
    for key in gen_keys & exp_keys:
        gen_val = generated[key]
        exp_val = example[key]
        current_path = f"{path}.{key}" if path else key
        
        if type(gen_val) != type(exp_val):
            differences.append(f"{current_path}: 类型不匹配 {type(gen_val)} vs {type(exp_val)}")
        elif isinstance(gen_val, dict):
            differences.extend(compare_structures(gen_val, exp_val, current_path))
        elif isinstance(gen_val, list) and gen_val and exp_val:
            # 比较列表第一个元素的结构
            if isinstance(gen_val[0], dict) and isinstance(exp_val[0], dict):
                differences.extend(compare_structures(gen_val[0], exp_val[0], f"{current_path}[0]"))
    
    return differences


def test_payload_generation():
    """测试载荷生成功能"""
    print("=== 测试载荷生成器 ===")
    
    # 1. 加载规划表
    plan_file = PROJECT_ROOT / "05.【模板】SmartX超融合核心平台规划设计表-ELF环境-v20250820.xlsx"
    if not plan_file.exists():
        print(f"错误: 规划表文件不存在 {plan_file}")
    assert plan_file.exists(), f"规划表文件不存在 {plan_file}"
    
    print(f"加载规划表: {plan_file}")
    parsed_plan = parse_plan(plan_file)
    plan_model = to_model(parsed_plan)
    
    if not plan_model.hosts:
        print("错误: 规划表中没有主机信息")
    assert plan_model.hosts, "规划表中没有主机信息"
    
    print(f"解析到 {len(plan_model.hosts)} 台主机")
    
    # 2. 创建模拟主机扫描数据
    print("创建模拟主机扫描数据...")
    host_scan_data = create_mock_host_data(plan_model)
    
    # 3. 生成载荷
    print("生成部署载荷...")
    try:
        generated_payload, artifact_path = generate_deployment_payload(
            plan=plan_model,
            host_scan_data=host_scan_data,
            parsed_plan=parsed_plan
        )
        print("✓ 载荷生成成功")
        print(f"载荷已保存到: {artifact_path}")
    except Exception as e:
        print(f"✗ 载荷生成失败: {e}")
        import traceback
        traceback.print_exc()
        raise AssertionError("生成部署载荷失败") from e
    
    # 4. 加载示例载荷进行比较
    print("加载示例载荷进行结构比较...")
    try:
        example_payload = load_example_payload()
        print("✓ 示例载荷加载成功")
    except Exception as e:
        print(f"✗ 示例载荷加载失败: {e}")
        raise AssertionError("示例载荷加载失败") from e
    
    # 5. 比较结构
    print("比较载荷结构...")
    differences = compare_structures(generated_payload, example_payload)
    
    if differences:
        print("发现结构差异:")
        for diff in differences[:10]:  # 只显示前10个差异
            print(f"  - {diff}")
        if len(differences) > 10:
            print(f"  ... 还有 {len(differences) - 10} 个差异")
        raise AssertionError(f"生成的载荷结构与示例不一致，首个差异: {differences[0]}")
    else:
        print("✓ 载荷结构完全匹配示例!")
    
    # 6. 输出生成的载荷信息
    print("\n=== 生成的载荷概要 ===")
    print(f"集群名称: {generated_payload.get('cluster_name')}")
    print(f"平台类型: {generated_payload.get('platform')}")
    print(f"主机数量: {len(generated_payload.get('hosts', []))}")
    print(f"VDS数量: {len(generated_payload.get('vdses', []))}")
    print(f"网络数量: {len(generated_payload.get('networks', []))}")
    print(f"vhost启用: {generated_payload.get('vhost_enabled')}")
    print(f"RDMA启用: {generated_payload.get('rdma_enabled')}")
    
    # 7. 保存生成的载荷供检查
    output_file = PROJECT_ROOT / "release" / "generated_payload.json" 
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(generated_payload, f, indent=2, ensure_ascii=False)
    print(f"\n生成的载荷已保存到: {output_file}")
    
    assert not differences, "生成的载荷结构与示例不一致"


if __name__ == "__main__":
    try:
        test_payload_generation()
    except Exception:
        sys.exit(1)
    sys.exit(0)