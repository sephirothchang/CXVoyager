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

import os
from pathlib import Path
import typer
from rich.console import Console
from cxvoyager.library.common.logging_config import setup_logging
from cxvoyager.library.integrations.excel.planning_sheet_parser import find_plan_file, parse_plan, to_model
from cxvoyager.library.validation.validator import validate
from cxvoyager.process.workflow.host_discovery_scanner import scan_hosts, get_host_scan_defaults
from cxvoyager.process.workflow.payload_builder import generate_deployment_payload
from cxvoyager.process.workflow.deployment_executor import (
    RunOptions,
    execute_run,
    list_stage_infos,
    resolve_stages,
)

def _is_en() -> bool:
    lang = os.environ.get("CXVOYAGER_LANG", "").lower()
    return lang.startswith("en")


def _t(cn: str, en: str) -> str:
    return en if _is_en() else cn


app = typer.Typer(help=_t("CXVoyager 自动化部署 CLI", "CXVoyager Automation CLI"))
console = Console()


def _detect_project_root() -> Path:
    here = Path(__file__).resolve()
    candidates = list(here.parents)
    markers = [".git", "requirements.txt", "pyproject.toml", "main.py"]
    for parent in candidates:
        if not parent.is_dir():
            continue
        # 优先识别包含 git 或依赖清单的目录
        if (parent / ".git").exists():
            return parent
        if (parent / "requirements.txt").exists() and (parent / "cxvoyager").is_dir():
            return parent
        if (parent / "pyproject.toml").exists() and (parent / "cxvoyager").is_dir():
            return parent
        if (parent / "main.py").exists() and (parent / "cxvoyager").is_dir():
            return parent

    fallback = here.parents[3] if len(here.parents) >= 4 else here.parent
    return fallback


PROJECT_ROOT = _detect_project_root()


def _ensure_cwd_repo_root() -> None:
    if Path.cwd() != PROJECT_ROOT:
        os.chdir(PROJECT_ROOT)


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


def _payload_readiness(model, parsed, *, token, base_url, timeout, max_retries, artifact_dir, skip_scan):
    report = {
        "ok": True,
        "skipped": bool(skip_scan),
        "errors": [],
        "warnings": [],
    }

    if skip_scan:
        return report

    try:
        scan_kwargs = {}
        if timeout is not None:
            scan_kwargs["timeout"] = timeout
        if max_retries is not None:
            scan_kwargs["max_retries"] = max_retries
        host_data, scan_warnings = scan_hosts(
            model,
            token=token,
            base_url=base_url,
            **scan_kwargs,
        )
        report["warnings"].extend(scan_warnings)

        if not host_data:
            report["errors"].append("主机扫描结果为空，无法构建部署载荷")
            report["ok"] = False
            return report

        payload, artifact_path = generate_deployment_payload(
            plan=model,
            host_scan_data=host_data,
            parsed_plan=parsed,
            artifact_dir=artifact_dir,
        )

        expected_hosts = len(model.hosts)
        payload_hosts = len(payload.get("hosts", []))
        report.update(
            {
                "hosts_expected": expected_hosts,
                "hosts_in_payload": payload_hosts,
                "vds_count": len(payload.get("vdses", [])),
                "network_count": len(payload.get("networks", [])),
                "artifact": str(artifact_path),
            }
        )

        if payload_hosts != expected_hosts:
            report["errors"].append(
                f"载荷中的主机数量({payload_hosts})与规划表({expected_hosts})不一致"
            )

    except Exception as exc:  # noqa: BLE001 - surfaced给用户
        report["errors"].append(f"构建部署载荷失败: {exc}")

    report["ok"] = report["ok"] and not report["errors"]
    return report


def _print_stage_menu(stage_infos):
    console.print(_t("[cyan]\n可选阶段列表（输入序号选择，支持逗号与范围）[/cyan]",
                     "[cyan]\nStage list (enter numbers, support comma and ranges)[/cyan]"))
    for idx, info in enumerate(stage_infos, start=1):
        label = info.label
        desc = info.description
        # StageInfo 元数据目前固定中文，若处于英文模式则仅显示英文占位或名称
        if _is_en():
            # 如果 label/desc 是中文则退化显示 name
            label = info.name if label else info.name
            desc = info.name if desc else info.name
        console.print(f"  {idx:02d}. {label} ({info.name}) - {desc}")


def _parse_stage_selection(text: str, stage_infos):
    tokens = [token.strip() for token in text.split(',') if token.strip()]
    selected: set[int] = set()

    for token in tokens:
        if '-' in token:
            parts = [p.strip() for p in token.split('-') if p.strip()]
            if len(parts) != 2:
                raise ValueError(_t(f"范围格式无效: {token}", f"Invalid range: {token}"))
            start, end = parts
            if not start.isdigit() or not end.isdigit():
                raise ValueError(_t(f"范围必须是数字: {token}", f"Range must be numeric: {token}"))
            a, b = int(start), int(end)
            if a < 1 or b < 1 or a > len(stage_infos) or b > len(stage_infos):
                raise ValueError(_t(f"范围超出可选序号: {token}", f"Range out of bounds: {token}"))
            if a > b:
                a, b = b, a
            selected.update(range(a, b + 1))
        else:
            if not token.isdigit():
                raise ValueError(_t(f"序号必须是数字: {token}", f"Index must be numeric: {token}"))
            value = int(token)
            if value < 1 or value > len(stage_infos):
                raise ValueError(_t(f"序号超出范围: {token}", f"Index out of range: {token}"))
            selected.add(value)

    if not selected:
        raise ValueError(_t("未选择任何阶段", "No stage selected"))

    ordered = []
    for idx, info in enumerate(stage_infos, start=1):
        if idx in selected:
            ordered.append(info)
    return ordered


@app.command(help=_t("解析规划表并输出结构摘要。", "Parse plan file and show summary."))
def parse(plan: Path | None = typer.Option(None, help=_t("规划表路径, 缺省自动查找", "Plan file path; auto-detect by default"))):
    _ensure_cwd_repo_root()
    setup_logging()
    base = Path.cwd()
    f = plan or find_plan_file(base)
    if not f:
        console.print(_t("[red]未找到匹配的规划表文件[/red]", "[red]No matching plan file found[/red]"))
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

    console.print(_t(f"[green]解析文件:[/] {f}", f"[green]Parsed file:[/] {f}"))
    console.print_json(data={
        "summary": summary,
        "sections": sections,
    })


@app.command(help=_t("解析规划表并执行完整校验（含部署载荷可用性检查）。", "Parse plan and run full validation (including payload readiness)."))
def check(
    plan: Path | None = typer.Option(None, help=_t("规划表路径", "Plan file path")),
    token: str | None = typer.Option(None, help=_t("访问 SmartX API 的令牌，用于自动扫描主机", "SmartX API token for host scan")),
    base_url: str | None = typer.Option(None, help=_t("可选：统一 API Base URL，缺省按主机管理地址访问", "Optional unified API base URL; default per-host mgmt IP")),
    timeout: int | None = typer.Option(None, help=_t("可选：主机扫描超时（秒），缺省读取配置", "Optional host scan timeout (seconds); defaults from config")),
    max_retries: int | None = typer.Option(None, help=_t("可选：主机扫描重试次数，缺省读取配置", "Optional host scan retries; defaults from config")),
    no_scan: bool = typer.Option(False, "--no-scan", help=_t("跳过主机扫描与部署载荷校验", "Skip host scan and payload readiness")),
    artifact_dir: Path | None = typer.Option(None, help=_t("保存校验时生成的部署载荷的目录", "Directory to save generated payload during validation")),
):
    _ensure_cwd_repo_root()
    setup_logging()
    base = Path.cwd()
    f = plan or find_plan_file(base)
    if not f:
        console.print(_t("[red]未找到匹配的规划表文件[/red]", "[red]No matching plan file found[/red]"))
        raise typer.Exit(code=1)

    defaults = get_host_scan_defaults()
    effective_timeout = defaults.get("timeout") if timeout is None else timeout
    effective_retries = defaults.get("max_retries") if max_retries is None else max_retries

    data = parse_plan(f)
    model = to_model(data)
    report = validate(data)
    report["plan_summary"] = _build_check_summary(model, data)

    payload_check = _payload_readiness(
        model,
        data,
        token=token,
        base_url=base_url,
        timeout=effective_timeout,
        max_retries=effective_retries,
        artifact_dir=artifact_dir,
        skip_scan=no_scan,
    )
    report["payload_check"] = payload_check
    report["ok"] = report.get("ok", True) and (payload_check["ok"] or payload_check["skipped"])

    console.print_json(data=report)
    if not report.get("ok"):
        raise typer.Exit(code=2)


@app.command(help=_t("执行指定阶段（新增 dry-run 与严格验证开关）。", "Execute selected stages (with dry-run and strict options)."))
def run(
    stages: str = typer.Option("prepare,init_cluster,deploy_obs", help=_t("逗号分隔阶段列表", "Comma-separated stages")),
    dry_run: bool | None = typer.Option(None, "--dry-run/--no-dry-run", help=_t("部署提交阶段是否仅dry-run预览载荷", "Whether deploy step is dry-run only")),
    strict_validation: bool | None = typer.Option(None, "--strict-validation/--no-strict-validation", help=_t("严格验证：警告视为错误", "Strict validation: treat warnings as errors")),
    debug: bool | None = typer.Option(None, "--debug/--no-debug", help=_t("调试模式：启用额外调试日志", "Debug mode: enable extra logging")),
):
    _ensure_cwd_repo_root()
    tokens = [part.strip() for part in stages.split(",") if part.strip()]
    if not tokens:
        console.print(_t("[red]请至少指定一个阶段[/red]", "[red]Please specify at least one stage[/red]"))
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
        console.print(_t(f"[red]执行失败: {exc}[/red]", f"[red]Execution failed: {exc}[/red]"))
        raise typer.Exit(code=2) from exc

    console.print_json(data={"status": "ok", **result.to_dict()})


@app.command(help=_t("扫描规划表内的所有主机并输出硬件信息。", "Scan all hosts in plan and output inventory."))
def scan(
    plan: Path | None = typer.Option(None, help=_t("规划表路径", "Plan file path")),
    token: str | None = typer.Option(None, help=_t("访问 SmartX API 所需的令牌", "Token for SmartX API")),
    timeout: int = typer.Option(10, help=_t("单个主机扫描超时时间（秒）", "Per-host scan timeout (seconds)")),
    base_url: str | None = typer.Option(None, help=_t("可选的统一 API Base URL，缺省使用每个主机管理地址", "Optional unified API base URL; default per-host mgmt IP")),
):
    _ensure_cwd_repo_root()
    setup_logging()
    f = plan or find_plan_file(Path.cwd())
    if not f:
        console.print(_t("[red]未找到规划表文件[/red]", "[red]Plan file not found[/red]"))
        raise typer.Exit(1)
    parsed = parse_plan(f)
    model = to_model(parsed)

    console.print(_t("[cyan]开始主机扫描，共 {0} 台[/cyan]".format(len(model.hosts)), "[cyan]Start host scan, total {0}[/cyan]".format(len(model.hosts))))
    inventory, warnings = scan_hosts(model, token=token, timeout=timeout, base_url=base_url)

    payload = {
        "count": len(inventory),
        "hosts": inventory,
    }
    if warnings:
        payload["warnings"] = warnings

    console.print_json(data=payload)


@app.command(help=_t("交互式选择阶段并执行生产部署（无 mock）。", "Interactive stage selection and production deployment."))
def deploy(plan: Path | None = typer.Option(None, help=_t("规划表路径", "Plan file path"))):
    _ensure_cwd_repo_root()
    setup_logging()

    # 解析规划表（prepare 阶段内部也会处理，此处预先校验输入）
    f = plan or find_plan_file(Path.cwd())
    if not f:
        console.print(_t("[red]未找到规划表文件[/red]", "[red]Plan file not found[/red]"))
        raise typer.Exit(1)

    stage_infos = list_stage_infos()
    _print_stage_menu(stage_infos)
    default_choice = f"1-{len(stage_infos)}"
    selection = typer.prompt(_t("请输入要执行的阶段序号", "Enter stage numbers to run"), default=default_choice).strip()

    try:
        chosen_infos = _parse_stage_selection(selection, stage_infos)
    except ValueError as exc:
        console.print(_t(f"[red]{exc}[/red]", f"[red]{exc}[/red]"))
        raise typer.Exit(1)

    stages = resolve_stages([info.name for info in chosen_infos])

    try:
        result = execute_run(stages, options=RunOptions())
    except Exception as exc:  # pragma: no cover - 向用户表面化错误
        console.print(_t(f"[red]部署执行失败: {exc}[/red]", f"[red]Deployment failed: {exc}[/red]"))
        raise typer.Exit(2) from exc

    console.print_json(data={"status": "ok", **result.to_dict()})


@app.command(help=_t("列出所有可用阶段及说明。", "List all available stages with descriptions."))
def stages_list():
    _ensure_cwd_repo_root()
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