#!/usr/bin/env python3
import argparse
import json
import logging

from cxvoyager.process.workflow.login_cloudtower import login_cloudtower
from cxvoyager.process.workflow.runtime_context import RunContext
from cxvoyager.library.models.planning_sheet_models import PlanModel, MgmtInfo

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_login")

parser = argparse.ArgumentParser(description="Test login_cloudtower and print returned cookie/token")
parser.add_argument("base_url", help="CloudTower base url, e.g. http://10.0.20.10")
parser.add_argument("--root-password", dest="root_password", help="CloudTower root password (plain)")
parser.add_argument("--timeout", type=int, default=10, help="API timeout seconds")
args = parser.parse_args()

mgmt = MgmtInfo(root密码=args.root_password) if args.root_password else None
plan = PlanModel(mgmt=mgmt)
ctx = RunContext(plan=plan)
api_cfg = {"timeout": args.timeout, "verify_ssl": False}

try:
    res = login_cloudtower(ctx, base_url=args.base_url, api_cfg=api_cfg, stage_logger=logger)
    print(json.dumps(res, ensure_ascii=False, indent=2))
except Exception as e:
    print("ERROR:", str(e))
    raise
