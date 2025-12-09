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

"""命令行接口。"""
from __future__ import annotations
from pathlib import Path
import typer
from rich.console import Console
from .common.logging_config import setup_logging
from .integrations.excel.planning_sheet_parser import find_plan_file, parse_plan, to_model
from .core.validation.validator import validate
from .integrations.smartx.api_client import APIClient
from .core.deployment.host_discovery_scanner import scan_hosts
from .core.deployment.deployment_executor import (
    RunOptions,
    execute_run,
    list_stage_infos,
    resolve_stages,
)

app = typer.Typer(help="CXVoyager 自动化部署 CLI")
console = Console()


def _build_check_summary(model, parsed):
    cluster_names = sorted({h.集群名称 for h in model.hosts if h.集群名称})
    cluster_vips = sorted({str(h.集群VIP) for h in model.hosts if h.集群VIP})
    host_details = [
        {
            "index": idx + 1,
            "hostname": host.SMTX主机名,
            "mgmt_ip": str(host.管理地址) if host.管理地址 else None,
            "storage_ip": str(host.存储地址) if host.存储地址 else None,
            "bmc_ip": str(host.带外地址) if host.带外地址 else None,
        }
        for idx, host in enumerate(model.hosts)
    ]

    mgmt_record = None
    mgmt_section = parsed.get("mgmt", {})
    if isinstance(mgmt_section, dict):
        records = mgmt_section.get("records", [])
        if records:
            mgmt_record = records[0]

    components = []
    services = {}
    if mgmt_record:
        mapping = [
            ("CloudTower", "Cloudtower IP", "Cloudtower 序列号"),
            ("OBS", "OBS IP", "OBS 序列号"),
            ("备份", "备份 IP", "备份 序列号"),
        ]
        for name, ip_key, serial_key in mapping:
            ip_value = mgmt_record.get(ip_key)
            if ip_value:
                component = {"name": name, "ip": str(ip_value)}
                serial_value = mgmt_record.get(serial_key)
                if serial_value:
                    component["serial"] = serial_value
                components.append(component)

        controller_vip = mgmt_record.get("ER 控制器集群VIP")
        controller_nodes = mgmt_record.get("ER 控制器节点IP列表") or []
        if controller_vip or controller_nodes:
            controller_component = {
                "name": "ER 控制器",
                "cluster_vip": str(controller_vip) if controller_vip else None,
                "node_ips": [str(ip) for ip in controller_nodes],
            }
            controller_serial = mgmt_record.get("ER 控制器序列号")
            if controller_serial:
                controller_component["serial"] = controller_serial
            components.append(controller_component)

        services = {
            "ntp_servers": [str(ip) for ip in mgmt_record.get("NTP 服务器") or []],
            "dns_servers": [str(ip) for ip in mgmt_record.get("DNS 服务器") or []],
            "temp_test_ip_range": mgmt_record.get("临时测试IP范围"),
        }

    cluster_info = {
        "names": cluster_names,
        "vips": cluster_vips,
        "host_count": len(host_details),
    }

    host_extra = parsed.get("hosts", {}).get("extra", {}) if isinstance(parsed.get("hosts"), dict) else {}
    if isinstance(host_extra, dict):
        extra_filtered = {k: v for k, v in host_extra.items() if v}
        if extra_filtered:
            cluster_info["extra"] = extra_filtered

    return {
        "cluster": cluster_info,
        "hosts": host_details,
        "management_components": components,
        "services": services,
        "plan_file": parsed.get("_meta", {}).get("source_file"),
    }


@app.command()
def parse(plan: Path | None = typer.Option(None, help="规划表路径, 缺省自动查找")):
    """解析规划表并输出结构摘要。"""
    setup_logging()
    base = Path.cwd()
    f = plan or find_plan_file(base)
    if not f:
        console.print("[red]未找到匹配的规划表文件[/red]")
        raise typer.Exit(code=1)
    data = parse_plan(f)
    summary = {}
    sections = {}
    for key, section in data.items():
        if isinstance(section, dict) and "records" in section:
            records = section.get("records", [])
            summary[key] = len(records)
            payload = {
                "records": records,
            }
            for extra_key in ("header", "extra"):
                if extra_key in section:
                    payload[extra_key] = section[extra_key]
            sections[key] = payload
        else:
            sections[key] = section

    console.print(f"[green]解析文件:[/] {f}")
    console.print_json(data={
        "summary": summary,
        "sections": sections,
    })


@app.command()
def check(plan: Path | None = typer.Option(None, help="规划表路径")):
    """解析并验证规划表。"""
    setup_logging()
    base = Path.cwd()
    f = plan or find_plan_file(base)
    if not f:
        console.print("[red]未找到匹配的规划表文件[/red]")
        raise typer.Exit(code=1)
    data = parse_plan(f)
    model = to_model(data)
    report = validate(data)
    report["plan_summary"] = _build_check_summary(model, data)
    console.print_json(data=report)
    if not report.get("ok"):
        raise typer.Exit(code=2)


@app.command()
def run(
    stages: str = typer.Option("prepare,init_cluster,deploy_obs", help="逗号分隔阶段列表"),
    dry_run: bool | None = typer.Option(None, "--dry-run/--no-dry-run", help="部署提交阶段是否仅dry-run预览载荷"),
    strict_validation: bool | None = typer.Option(None, "--strict-validation/--no-strict-validation", help="严格验证：警告视为错误"),
    debug: bool | None = typer.Option(None, "--debug/--no-debug", help="调试模式：启用额外调试日志"),
):
    """执行指定阶段（新增 dry-run 与严格验证开关）。"""
    tokens = [part.strip() for part in stages.split(",") if part.strip()]
    if not tokens:
        console.print("[red]请至少指定一个阶段[/red]")
        raise typer.Exit(code=1)

    try:
        selected = resolve_stages(tokens)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    opts = RunOptions(dry_run=dry_run, strict_validation=strict_validation, debug=debug)
    try:
        result = execute_run(selected, opts)
    except Exception as exc:  # pragma: no cover - surfaced to user as error message
        console.print(f"[red]执行失败: {exc}[/red]")
        raise typer.Exit(code=2) from exc

    console.print_json(data={"status": "ok", **result.to_dict()})


@app.command()
def scan(
    plan: Path | None = typer.Option(None, help="规划表路径"),
    token: str | None = typer.Option(None, help="访问 SmartX API 所需的令牌"),
    timeout: int = typer.Option(10, help="单个主机扫描超时时间（秒）"),
    base_url: str | None = typer.Option(None, help="可选的统一 API Base URL，缺省使用每个主机管理地址"),
):
    """扫描规划表内的所有主机并输出硬件信息。"""
    setup_logging()
    f = plan or find_plan_file(Path.cwd())
    if not f:
        console.print("[red]未找到规划表文件[/red]")
        raise typer.Exit(1)
    parsed = parse_plan(f)
    model = to_model(parsed)

    console.print("[cyan]开始主机扫描，共 {0} 台[/cyan]".format(len(model.hosts)))
    inventory, warnings = scan_hosts(model, token=token, timeout=timeout, base_url=base_url)

    payload = {
        "count": len(inventory),
        "hosts": inventory,
    }
    if warnings:
        payload["warnings"] = warnings

    console.print_json(data=payload)


@app.command()
def deploy(plan: Path | None = typer.Option(None, help="规划表路径"), mock: bool = True):
    """示例部署：仅构建载荷并调用mock API。"""
    setup_logging()
    f = plan or find_plan_file(Path.cwd())
    if not f:
        console.print("[red]未找到规划表文件[/red]")
        raise typer.Exit(1)
    parsed = parse_plan(f)
    model = to_model(parsed)
    client = APIClient(base_url="http://localhost:9000", mock=mock)
    payload = {
        "cluster": {
            "name": model.hosts[0].集群名称 if model.hosts else "unknown",
            "hosts": [
                {
                    "hostname": h.SMTX主机名,
                    "mgmt_ip": str(h.管理地址),
                    "bmc": str(h.带外地址) if h.带外地址 else None,
                }
                for h in model.hosts
            ],
        }
    }
    resp = client.post("/deploy/cluster", payload)
    console.print_json(data=resp)


@app.command()
def stages_list():
    """列出所有可用阶段及说明。"""
    info = [
        {
            "name": meta.name,
            "label": meta.label,
            "description": meta.description,
            "group": meta.group,
        }
        for meta in list_stage_infos()
    ]
    console.print_json(data=info)


if __name__ == "__main__":  # pragma: no cover
    app()

