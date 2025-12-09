# SPDX-License-Identifier: GPL-3.0-or-later
"""Run-only CloudTower deployment stage for ISO upload validation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cxvoyager.common.config import Config, load_config
from cxvoyager.common.logging_config import setup_logging
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE
from cxvoyager.core.deployment.handlers import deploy_cloudtower
from cxvoyager.core.deployment.host_discovery_scanner import scan_hosts
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.integrations.excel.planning_sheet_parser import find_plan_file, parse_plan, to_model


def _resolve_plan(path: str | None) -> Path:
    if path:
        candidate = Path(path).expanduser().resolve()
        if not candidate.is_file():
            raise SystemExit(f"指定的规划表不存在: {candidate}")
        return candidate

    auto = find_plan_file(Path.cwd())
    if not auto:
        raise SystemExit("未在当前目录找到规划表，请使用 --plan 指定。")
    return auto


def _update_config(cfg: Config, *, iso: Path | None, base_url: str | None, token: str | None) -> None:
    if iso:
        cloud_cfg = dict(cfg.get("cloudtower", {}) or {})
        cloud_cfg["iso_path"] = str(iso.resolve())
        cfg["cloudtower"] = cloud_cfg

    if base_url or token:
        api_cfg = dict(cfg.get("api", {}) or {})
        if base_url:
            api_cfg["base_url"] = base_url.rstrip("/")
        if token:
            api_cfg["x-smartx-token"] = token
        cfg["api"] = api_cfg


def _load_host_scan_from_file(path: Path) -> Dict[str, Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"读取主机扫描文件失败: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise SystemExit("主机扫描文件内容必须为非空字典，键为主机 IP。")
    normalized: Dict[str, Dict[str, Any]] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            normalized[str(key)] = value
    if not normalized:
        raise SystemExit("主机扫描数据为空或格式不正确。")
    return normalized


def _stub_host_scan(base_url: str | None, plan_model) -> Dict[str, Dict[str, Any]]:
    host_ip: str | None = None
    if base_url:
        parsed = urlparse(base_url)
        host_ip = parsed.hostname
    if not host_ip and plan_model and getattr(plan_model, "hosts", None):
        for host in plan_model.hosts:
            candidate = getattr(host, "管理地址", None)
            if candidate:
                host_ip = str(candidate)
                break
    if not host_ip and plan_model and getattr(plan_model, "mgmt", None):
        candidate = getattr(plan_model.mgmt, "Cloudtower_IP", None)
        if candidate:
            host_ip = str(candidate)
    if not host_ip:
        raise SystemExit("无法从配置或规划表推导主机 IP，请使用 --host-scan-json 或 --host-ip 显式提供。")
    return {host_ip: {"host_ip": host_ip}}


def _resolve_host_scan(
    *,
    plan_model,
    cfg: Config,
    host_scan_json: Path | None,
    real_scan: bool,
    host_ip: str | None,
) -> Tuple[Dict[str, Dict[str, Any]], str | None]:
    if host_scan_json:
        data = _load_host_scan_from_file(host_scan_json)
        return data, next(iter(data.keys()))

    base_url = cfg.get("api", {}).get("base_url") if isinstance(cfg.get("api"), dict) else None
    token = cfg.get("api", {}).get("x-smartx-token") if isinstance(cfg.get("api"), dict) else None
    timeout = cfg.get("api", {}).get("timeout") if isinstance(cfg.get("api"), dict) else 10

    if real_scan:
        try:
            scan_data, warnings = scan_hosts(plan_model, base_url=base_url, token=token, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"主机扫描失败: {exc}") from exc
        if not scan_data:
            raise SystemExit("主机扫描未返回任何主机信息，请检查 API 配置或使用 --host-scan-json。")
        if warnings:
            print("扫描警告:")
            for msg in warnings:
                print(f"  - {msg}")
        return scan_data, next(iter(scan_data.keys()))

    if host_ip:
        return {host_ip: {"host_ip": host_ip}}, host_ip

    stub = _stub_host_scan(base_url, plan_model)
    return stub, next(iter(stub.keys()))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="单独运行 CloudTower ISO 上传阶段")
    parser.add_argument("--plan", help="规划表路径，不提供则自动查找")
    parser.add_argument("--iso", type=str, help="CloudTower ISO 文件路径，覆盖配置文件")
    parser.add_argument("--base-url", type=str, help="SmartX/CloudTower API 的基础 URL，覆盖配置文件")
    parser.add_argument("--token", type=str, help="API 访问令牌，覆盖配置文件")
    parser.add_argument("--host-scan-json", type=str, help="复用已有主机扫描 JSON 文件")
    parser.add_argument("--host-ip", type=str, help="当不进行主机扫描时用于构造最小主机数据的 IP")
    parser.add_argument("--real-scan", action="store_true", help="调用 scan_hosts 执行真实主机扫描")
    parser.add_argument("--debug", action="store_true", help="启用 DEBUG 日志输出")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    iso_path = Path(args.iso).expanduser().resolve() if args.iso else None
    if iso_path and not iso_path.is_file():
        raise SystemExit(f"指定的 ISO 文件不存在: {iso_path}")

    host_scan_path = Path(args.host_scan_json).expanduser().resolve() if args.host_scan_json else None
    plan_path = _resolve_plan(args.plan)

    cfg = load_config(DEFAULT_CONFIG_FILE)
    _update_config(cfg, iso=iso_path, base_url=args.base_url, token=args.token)

    log_level = "DEBUG" if args.debug else cfg.get("logging", {}).get("level", "INFO")
    setup_logging(log_level)

    parsed_plan = parse_plan(plan_path)
    plan_model = to_model(parsed_plan)
    if not getattr(plan_model, "mgmt", None):
        raise SystemExit("规划表缺少管理信息，无法确定 CloudTower IP。")

    host_scan, host_key = _resolve_host_scan(
        plan_model=plan_model,
        cfg=cfg,
        host_scan_json=host_scan_path,
        real_scan=args.real_scan,
        host_ip=args.host_ip,
    )

    ctx = RunContext(plan=plan_model, work_dir=plan_path.parent, config=cfg)
    ctx.extra["host_scan"] = host_scan

    try:
        deploy_cloudtower.handle_deploy_cloudtower({"ctx": ctx})
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"CloudTower ISO 上传失败: {exc}") from exc

    summary = ctx.extra.get("deploy_cloudtower") or {}
    payload = {
        "status": summary.get("status"),
        "cloudtower_ip": summary.get("ip"),
        "iso": summary.get("iso"),
        "host_used": host_key,
        "work_dir": str(ctx.work_dir),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
