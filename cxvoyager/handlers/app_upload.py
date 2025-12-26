# SPDX-License-Identifier: GPL-3.0-or-later
# Shared helpers for application package uploads.
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from cxvoyager.common.config import load_config
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE, PROJECT_ROOT
from cxvoyager.workflow.progress import create_stage_progress_logger
from cxvoyager.workflow.runtime_context import RunContext
from cxvoyager.workflow.stage_manager import Stage
from cxvoyager.common.i18n import tr
from cxvoyager.integrations.smartx.api_client import APIClient
from cxvoyager.cloudtower import cloudtower_login
from cxvoyager.integrations.excel.planning_sheet_parser import find_plan_file, parse_plan, to_model

logger = logging.getLogger(__name__)

OBS_UPLOAD_ENDPOINT = "/api/ovm-operator/api/v3/chunkedUploads"
BAK_UPLOAD_ENDPOINT = "/api"
ER_UPLOAD_ENDPOINT = "/api"
SFS_UPLOAD_ENDPOINT = "/api"
SKS_UPLOAD_ENDPOINT = "/api"



@dataclass(frozen=True)
class AppSpec:
    abbr: str
    label: str
    package_pattern: str
    name_regex: re.Pattern[str]
    endpoint: str = OBS_UPLOAD_ENDPOINT
    base_url_key: str = "obs_base_url"


def _parse_version_parts(version: str) -> Sequence[int]:
    parts: List[int] = []
    for piece in version.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return parts


def _version_key(path: Path, regex: re.Pattern[str]) -> Tuple:
    match = regex.match(path.name)
    if not match:
        return (0, 0, 0, 0, 0, path.name)

    version_parts = tuple(_parse_version_parts(match.group("version")))
    group_dict = match.groupdict()
    date_raw = group_dict.get("date")
    build_raw = group_dict.get("build")

    try:
        date_part = int(date_raw) if date_raw is not None else 0
    except ValueError:
        date_part = 0

    try:
        build_part = int(build_raw) if build_raw is not None else 0
    except ValueError:
        build_part = 0

    if len(version_parts) < 3:
        padded_version: Tuple[int, ...] = tuple(list(version_parts) + [0] * (3 - len(version_parts)))
    else:
        padded_version = version_parts

    return (*padded_version, date_part, build_part, path.name)


def find_latest_package(app: AppSpec, search_roots: Iterable[Path]) -> Path:
    candidates: List[Path] = []
    seen: set[Path] = set()
    for root in search_roots:
        try:
            for pkg in Path(root).glob(app.package_pattern):
                resolved = pkg.resolve()
                if not pkg.is_file():
                    continue
                if resolved in seen:
                    continue
                seen.add(resolved)
                candidates.append(pkg)
        except FileNotFoundError:
            continue

    if not candidates:
        raise RuntimeError(f"未找到 {app.package_pattern} 包")

    candidates.sort(key=lambda p: _version_key(p, app.name_regex), reverse=True)
    return candidates[0]


def normalize_base_url(base_url: str, *, default_scheme: str = "https") -> str:
    stripped = base_url.strip().rstrip("/")
    if stripped.startswith(("http://", "https://")):
        return stripped
    return f"{default_scheme}://{stripped}"


def _resolve_cloudtower_base_url(ctx: RunContext, api_cfg: Mapping[str, object]) -> str | None:
    # 优先级：1) 显式配置；2) 规划表模型（ctx.plan）；3) 解析结果（ctx.extra['parsed_plan']）；
    # 4) 最后退回到 deploy_cloudtower 阶段产物（可能为临时/自动发现的地址）。
    explicit = api_cfg.get("cloudtower_base_url") or api_cfg.get("base_url") if isinstance(api_cfg, dict) else None
    if explicit:
        return str(explicit)

    # 规划表模型优先（如果已经加载）
    plan = getattr(ctx, "plan", None)
    if plan and getattr(plan, "mgmt", None):
        mgmt = plan.mgmt
        ip_value = getattr(mgmt, "Cloudtower_IP", None) or getattr(mgmt, "cloudtower_ip", None)
        if ip_value:
            return str(ip_value)

    # 解析结果字典优先于 deploy 阶段产物
    parsed_plan = ctx.extra.get("parsed_plan") if isinstance(ctx.extra, dict) else None
    if isinstance(parsed_plan, dict):
        mgmt_section = parsed_plan.get("mgmt", {}) if isinstance(parsed_plan, dict) else {}
        records = mgmt_section.get("records") if isinstance(mgmt_section, dict) else None
        if isinstance(records, list) and records:
            record = records[0]
            ip_value = record.get("Cloudtower IP") or record.get("cloudtower_ip") or record.get("Cloudtower_IP")
            if ip_value:
                return str(ip_value)

    # 回退到 deploy_cloudtower 输出（旧行为）
    if isinstance(ctx.extra, dict):
        deploy_cloudtower = ctx.extra.get("deploy_cloudtower")
        if isinstance(deploy_cloudtower, dict):
            base = deploy_cloudtower.get("base_url") or deploy_cloudtower.get("ip")
            if base:
                return str(base)

    return None


def _resolve_cloudtower_credentials(ctx: RunContext) -> Tuple[str, str]:
    """Pick CloudTower login credentials; fall back to defaults."""
    username = "root"
    password = "HC!r0cks"

    # 1) 规划表 mgmt root 密码
    plan = getattr(ctx, "plan", None)
    mgmt = getattr(plan, "mgmt", None)
    if mgmt and getattr(mgmt, "root密码", None):
        password = str(getattr(mgmt, "root密码"))

    # 2) parsed_plan（若存在）
    parsed_plan = ctx.extra.get("parsed_plan") if isinstance(ctx.extra, dict) else None
    if isinstance(parsed_plan, dict):
        mgmt_section = parsed_plan.get("mgmt", {}) if isinstance(parsed_plan, dict) else {}
        records = mgmt_section.get("records") if isinstance(mgmt_section, dict) else None
        if isinstance(records, list) and records:
            record = records[0] or {}
            pwd_candidate = record.get("root密码") or record.get("cloudtower_root_password")
            if pwd_candidate:
                password = str(pwd_candidate)

    return username, password


def _resolve_cloudtower_token(
    *,
    ctx: RunContext,
    api_cfg: Mapping[str, object],
    cloudtower_base_url: str,
    stage_logger,
) -> str | None:
    # 始终调用 CloudTower 登录获取全新 token，避免复用旧会话引起冲突。
    parsed = urlparse(cloudtower_base_url)
    host = parsed.hostname
    if not host:
        return None
    raw_timeout = api_cfg.get("timeout", 10) if isinstance(api_cfg, dict) else 10
    timeout = 10
    if isinstance(raw_timeout, (int, float, str)):
        try:
            timeout = int(raw_timeout)
        except Exception:
            timeout = 10
    client = APIClient(base_url=f"https://{host}", mock=False, timeout=timeout, verify=False)
    username, password = _resolve_cloudtower_credentials(ctx)
    try:
        cloudtower_token = cloudtower_login(
            client=client,
            ip=host,
            username=username,
            password=password,
            logger_adapter=stage_logger,
        )
    except Exception as exc:  # noqa: BLE001
        stage_logger.error(tr("deploy.app_upload.login_token_failed"), extra={"error": str(exc)})
        return None

    return cloudtower_token


def _reset_plan_context(ctx: RunContext, *, keep_source: bool = True) -> None:
    """Clear cached plan parsing state so a fresh parse will be performed."""

    ctx.plan = None
    if isinstance(ctx.extra, dict):
        ctx.extra.pop("parsed_plan", None)
        if not keep_source:
            ctx.extra.pop("plan_source", None)


def _ensure_plan_loaded(ctx: RunContext) -> None:
    """保证 ctx.plan / ctx.extra['parsed_plan'] 可用于解析 CloudTower IP。

    - 若 ctx.plan 缺失或缺少 mgmt，则尝试定位并解析规划表；
    - 优先使用 ctx.extra['plan_source']，否则在 work_dir 下自动查找。
    """

    plan_missing = not getattr(ctx, "plan", None)
    mgmt_missing = not getattr(getattr(ctx, "plan", None), "mgmt", None)
    parsed_missing = not (isinstance(ctx.extra, dict) and ctx.extra.get("parsed_plan"))

    if not (plan_missing or mgmt_missing or parsed_missing):
        return

    work_dir = ctx.work_dir if isinstance(ctx.work_dir, Path) else Path.cwd()

    plan_path: Path | None = None
    if isinstance(ctx.extra, dict) and ctx.extra.get("plan_source"):
        candidate = Path(str(ctx.extra["plan_source"]))
        if candidate.exists():
            plan_path = candidate
    if plan_path is None:
        located = find_plan_file(work_dir)
        if located and located.exists():
            plan_path = located

    if plan_path is None:
        return

    try:
        parsed = parse_plan(plan_path)
        model = to_model(parsed)
    except Exception:
        return

    if not getattr(model, "source_file", None):
        try:
            setattr(model, "source_file", str(plan_path))
        except Exception:
            pass

    ctx.plan = model
    if isinstance(ctx.extra, dict):
        ctx.extra.setdefault("parsed_plan", parsed)
        ctx.extra.setdefault("plan_source", str(plan_path))


def upload_app(ctx_dict: Dict[str, object], app: AppSpec, stage: Stage) -> Mapping[str, object]:
    """通用上传流程：定位最新包、构造基址、提交 chunkedUploads。
    - 结果写入 ctx.extra['deploy_results'][abbr] 以及 deploy_<abbr>_result。
    """

    ctx: RunContext = ctx_dict["ctx"]  # type: ignore[index]
    stage_logger = create_stage_progress_logger(ctx, stage.value, logger=logger, prefix=f"[{stage.value}]")

    _ensure_plan_loaded(ctx)

    cfg = ctx.config or load_config(DEFAULT_CONFIG_FILE)
    cfg_dict = cfg if isinstance(cfg, dict) else {}
    api_cfg = cfg_dict.get("api", {}) if isinstance(cfg_dict, dict) else {}
    deploy_cfg = cfg_dict.get("deploy", {}) if isinstance(cfg_dict, dict) else {}

    timeout = int(api_cfg.get("timeout", 10))
    verify_ssl = api_cfg.get("verify_ssl", False)
    token = api_cfg.get("token") or api_cfg.get("x-smartx-token")

    cli_opts = ctx.extra.get("cli_options", {}) if isinstance(ctx.extra, dict) else {}
    dry_run = cli_opts.get("dry_run")
    if dry_run is None:
        dry_run = deploy_cfg.get("dry_run", False)
    dry_run = bool(dry_run)

    work_dir = ctx.work_dir if isinstance(ctx.work_dir, Path) else Path(ctx.work_dir)
    search_roots = [work_dir, PROJECT_ROOT, PROJECT_ROOT / "release", PROJECT_ROOT / "resources"]

    package_path = find_latest_package(app, search_roots)

    base_url = _resolve_cloudtower_base_url(ctx, api_cfg)
    if not base_url:
        raise RuntimeError(f"无法确定 {app.abbr} 上传基址（缺少 CloudTower IP）")

    token = _resolve_cloudtower_token(
        ctx=ctx,
        api_cfg=api_cfg,
        cloudtower_base_url=base_url,
        stage_logger=stage_logger,
    )
    base_url = normalize_base_url(base_url)

    if not token and not dry_run:
        raise RuntimeError(f"缺少 {app.abbr} 上传所需的鉴权令牌")

    headers: Dict[str, str] = {"Authorization": token} if token else {}
    client = APIClient(base_url=base_url, mock=False, timeout=timeout, verify=verify_ssl)

    stage_logger.info(
        tr("deploy.app_upload.prepare_upload", abbr=app.abbr),
        progress_extra={
            "file": package_path.name,
            "base_url": base_url,
            "endpoint": app.endpoint,
            "dry_run": bool(dry_run),
        },
    )

    if dry_run:
        result: Dict[str, object] = {
            "dry_run": True,
            "package": package_path.name,
            "base_url": base_url,
            "endpoint": app.endpoint,
        }
    else:
        payload = {"origin_file_name": package_path.name}
        try:
            resp = client.post(app.endpoint, payload, headers=headers)
        except Exception as exc:  # pragma: no cover - surfaced
            stage_logger.error(tr("deploy.app_upload.upload_failed", abbr=app.abbr), progress_extra={"error": str(exc)})
            raise RuntimeError(f"{app.abbr} 应用包上传失败: {exc}")

        stage_logger.info(
            tr("deploy.app_upload.upload_submitted", abbr=app.abbr),
            progress_extra={
                "id": resp.get("id"),
                "status": resp.get("status"),
                "origin_file_name": resp.get("origin_file_name", package_path.name),
            },
        )
        result = resp

    deploy_results: Dict[str, object] = ctx.extra.setdefault("deploy_results", {})  # type: ignore[assignment]
    deploy_results[app.abbr] = result
    ctx.extra[f"deploy_{app.abbr.lower()}_result"] = result
    ctx.extra["deploy_result"] = result

    return result
