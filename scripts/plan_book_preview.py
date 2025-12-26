#!/usr/bin/env python3
"""Parse a planning sheet and print a readable summary to stdout."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # Ensure project root is importable when run directly
    sys.path.insert(0, str(ROOT))

from cxvoyager.library.integrations.excel.planning_sheet_parser import find_plan_file, parse_plan, to_model


def _stringify(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _stringify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_stringify(v) for v in obj]
    if obj is None:
        return None
    try:
        return str(obj)
    except Exception:  # noqa: BLE001
        return obj


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview parsed planning sheet content.")
    parser.add_argument("plan", nargs="?", help="Path to planning sheet (.xlsx). If omitted, auto-detect in CWD.")
    args = parser.parse_args()

    plan_path: Path | None
    if args.plan:
        plan_path = Path(args.plan).expanduser().resolve()
        if not plan_path.exists():
            raise SystemExit(f"规划表不存在: {plan_path}")
    else:
        project_root = Path(__file__).resolve().parent.parent
        plan_path = find_plan_file(project_root)
        if not plan_path:
            raise SystemExit("未在项目根目录找到规划表，请指定路径。")

    parsed = parse_plan(plan_path)
    model = to_model(parsed)

    summary: Dict[str, Any] = {
        "plan_file": str(plan_path),
        "virtual_network_records": len(parsed.get("virtual_network", {}).get("records", [])),
        "host_records": len(parsed.get("hosts", {}).get("records", [])),
        "mgmt_records": len(parsed.get("mgmt", {}).get("records", [])),
        "mgmt_record_sample": parsed.get("mgmt", {}).get("records", [None])[0],
        "PlanModel.mgmt": model.mgmt.model_dump() if model.mgmt else None,
    }

    print(json.dumps(_stringify(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
