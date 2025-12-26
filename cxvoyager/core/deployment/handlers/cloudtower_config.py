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

# Stage 6 cloudtower_config – CloudTower 配置
from __future__ import annotations

import logging
import math
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, cast

from cxvoyager.common.config import load_config
from cxvoyager.common.network_utils import check_port
from cxvoyager.common.system_constants import DEFAULT_CONFIG_FILE
from cxvoyager.common.i18n import tr
from cxvoyager.core.deployment.progress import create_stage_progress_logger
from cxvoyager.core.deployment.runtime_context import RunContext
from cxvoyager.core.deployment.stage_manager import Stage, stage_handler
from cxvoyager.integrations.smartx.api_client import APIClient
from cxvoyager.integrations.excel.planning_sheet_parser import find_plan_file, parse_plan, to_model

from .deploy_cloudtower import (
    CLOUDTOWER_GRAPHQL_ENDPOINT,
    CLOUDTOWER_GET_CLUSTERS_ENDPOINT,
    _cloudtower_login,
    _post_cloudtower_graphql,
    _resolve_cloudtower_ip,
)

logger = logging.getLogger(__name__)

# --- GraphQL 文本常量 ---

CLOUDTOWER_GQL_UPDATE_CLUSTER_SETTINGS = """
mutation updateClusterSettings($data: ClusterSettingsUpdateInput!, $where: ClusterSettingsWhereUniqueInput!) {
  updateClusterSettings(where: $where, data: $data) {
    id
    default_storage_policy
    default_storage_policy_replica_num
    default_storage_policy_thin_provision
    __typename
  }
}
""".strip()

CLOUDTOWER_GQL_LIST_ALERT_RULES = """
query globalAlertRules($where: GlobalAlertRuleWhereInput, $orderBy: GlobalAlertRuleOrderByInput, $skip: Int, $first: Int) {
    globalAlertRules(where: $where, orderBy: $orderBy, skip: $skip, first: $first) {
        message
        thresholds {
            value
            severity
            __typename
        }
        object
        id
        disabled
        name
        alert_rules {
            id
            customized
            disabled
            thresholds {
                severity
                value
                __typename
            }
            cluster {
                id
                name
                __typename
            }
            __typename
        }
        __typename
    }
    globalAlertRulesConnection(where: $where) {
        aggregate {
            count
            __typename
        }
        __typename
    }
}
""".strip()

# 与官方过滤示例对齐的默认查询变量，避免系统/内置规则干扰阈值更新。
DEFAULT_GLOBAL_ALERT_RULES_VARIABLES = {
        "skip": 0,
        "first": 50,
        "where": {
                "AND": [
                        {
                                "AND": [
                                        {"alert_rules_some": {}},
                                        {"name_not_starts_with": "elf_"},
                                        {"name_not_starts_with": "scvm_"},
                                        {"name_not_starts_with": "vsphere_"},
                                        {"name_not_starts_with": "witness_"},
                                        {"name_not_starts_with": "zone"},
                                        {"name_not_starts_with": "metro_"},
                                        {"name_not_starts_with": "system."},
                                        {
                                                "object_not_in": [
                                                        "SKS_SERVICE",
                                                        "SKS_REGISTRY",
                                                        "SKS_CLUSTER",
                                                        "SKS_CLUSTER_NODE",
                                                        "SKS_PV",
                                                        "SKS_PVC",
                                                ]
                                        },
                                ]
                        }
                ]
        },
        "orderBy": "id_ASC",
}

CLOUDTOWER_GQL_UPDATE_GLOBAL_ALERT_RULE = """
mutation updateGlobalAlertRule($data: GlobalAlertRuleUpdateInput!, $where: GlobalAlertRuleWhereUniqueInput!) {
    updateGlobalAlertRule(data: $data, where: $where) {
        id
        disabled
        thresholds {
            value
            severity
            __typename
        }
        alert_rules {
            id
            disabled
            customized
            thresholds {
                value
                severity
                __typename
            }
            cluster {
                id
                name
                __typename
            }
            __typename
        }
        __typename
    }
}
""".strip()


def _ensure_plan_for_config(ctx: RunContext, stage_logger: logging.LoggerAdapter):
        """确保独立运行阶段 06 时也能获得规划表模型与解析结果。"""

        plan_model = getattr(ctx, "plan", None)
        parsed_plan = ctx.extra.get('parsed_plan') if isinstance(ctx.extra, dict) else None
        if plan_model or parsed_plan:
                return plan_model, parsed_plan

        try:
                from pathlib import Path

                base_dir = ctx.work_dir if hasattr(ctx, "work_dir") and ctx.work_dir else Path.cwd()
                plan_path = find_plan_file(base_dir=base_dir)
                if plan_path:
                        parsed_plan = parse_plan(plan_path)
                        plan_model = to_model(parsed_plan)
                        ctx.plan = plan_model
                        if isinstance(ctx.extra, dict):
                                ctx.extra['parsed_plan'] = parsed_plan
                        stage_logger.info(tr("deploy.cloudtower_config.plan_auto_loaded"), progress_extra={"plan_path": str(plan_path)})
                else:
                        stage_logger.warning(tr("deploy.cloudtower_config.plan_not_found"), progress_extra={"base_dir": str(base_dir) if base_dir else ""})
        except Exception as exc:  # noqa: BLE001
                    stage_logger.warning(tr("deploy.cloudtower_config.plan_load_failed", error=exc), progress_extra={"error": str(exc)})

        return plan_model, parsed_plan


@dataclass
class Stage06Config:
    """阶段 06 配置项集合。"""

    storage_policy: str = "REPLICA_2_THIN_PROVISION"
    replica_num: int = 2
    enable_thin: bool = True
    alert_rule_name: str = "zbs_cluster_data_space_use_rate"
    alert_critical: int = 90
    alert_notice_floor: int = 50


@stage_handler(Stage.cloudtower_config)
def handle_cloudtower_config(ctx_dict: Dict[str, Any]) -> None:
    """阶段 06：调用 CloudTower API 完成集群级别的后续配置。"""

    ctx: RunContext = ctx_dict['ctx']
    stage_logger = create_stage_progress_logger(
        ctx,
        Stage.cloudtower_config.value,
        logger=logger,
        prefix="[cloudtower_config]",
    )

    cfg = ctx.config or load_config(DEFAULT_CONFIG_FILE)
    cfg_dict = cfg if isinstance(cfg, dict) else {}
    stage06_cfg = _parse_stage06_config(cfg_dict)

    plan_model, parsed_plan = _ensure_plan_for_config(ctx, stage_logger)

    deploy_info = ctx.extra.get('deploy_cloudtower') or {}
    if deploy_info.get('status') != 'SERVICE_READY':
        stage_logger.info(tr("deploy.cloudtower_config.probe_no_stage4"))
        cloud_cfg = cfg_dict.get('cloudtower', {}) if isinstance(cfg_dict, dict) else {}
        cloudtower_ip = _resolve_cloudtower_ip(plan_model, parsed_plan, cloud_cfg, stage_logger)
        if not cloudtower_ip:
            raise RuntimeError("缺少 CloudTower IP，无法执行探测与配置。")

        stage_logger.info(
            tr("deploy.cloudtower_config.probe_port"),
            progress_extra={"ip": cloudtower_ip, "port": 443},
        )
        if not check_port(cloudtower_ip, 443, timeout=5.0):
            raise RuntimeError("CloudTower 443 端口不可达，无法执行配置。")

        client_probe = APIClient(
            base_url=f"https://{cloudtower_ip}",
            mock=False,
            timeout=int(cfg_dict.get('api', {}).get('timeout', 10)),
            verify=False,
        )
        token = _cloudtower_login(client=client_probe, ip=cloudtower_ip, stage_logger=stage_logger)
        client_probe.session.headers['Authorization'] = token

        deploy_info = {
            "status": "SERVICE_READY",
            "ip": cloudtower_ip,
            "cloudtower": {
                "session": {"token": token, "username": "root"},
            },
        }
        ctx.extra['deploy_cloudtower'] = deploy_info
        stage_logger.info(tr("deploy.cloudtower_config.probe_ready"), progress_extra={"ip": cloudtower_ip})

    attach_info = ctx.extra.get('attach_cluster') or {}
    cloudtower_ip = deploy_info.get('ip')
    if not cloudtower_ip:
        raise RuntimeError("缺少 CloudTower 访问 IP，请先完成部署阶段。")

    session = (deploy_info.get('cloudtower') or {}).get('session') or {}
    token = session.get('token')

    timeout = int(cfg_dict.get('api', {}).get('timeout', 10))
    client = APIClient(
        base_url=f"https://{cloudtower_ip}",
        mock=False,
        timeout=timeout,
        verify=False,  # CloudTower 使用自签证书
    )
    if token:
        client.session.headers['Authorization'] = token
    else:
        stage_logger.warning(tr("deploy.cloudtower_config.token_missing_retry"))
        token = _cloudtower_login(client=client, ip=cloudtower_ip, stage_logger=stage_logger)
        client.session.headers['Authorization'] = token

    headers = {
        "Authorization": token,
        "content-type": "application/json",
    }

    cluster_info = _ensure_cluster_info(
        attach_info=attach_info,
        client=client,
        headers=headers,
        stage_logger=stage_logger,
    )

    cluster_id = cluster_info['id']
    host_count = cluster_info.get('host_num') or 0
    settings_id = cluster_info.get('settings_id')
    if not settings_id:
        raise RuntimeError("未获取到集群设置 ID，无法更新默认存储策略。")

    stage_logger.info(
        tr("deploy.cloudtower_config.start"),
        progress_extra={
            "cloudtower_ip": cloudtower_ip,
            "cluster_id": cluster_id,
            "host_count": host_count,
        },
    )

    results: Dict[str, Any] = {
        "cluster_id": cluster_id,
        "host_count": host_count,
        "operations": [],
    }

    storage_result = _update_default_storage_policy(
        client=client,
        settings_id=settings_id,
        cfg=stage06_cfg,
        stage_logger=stage_logger,
    )
    results['operations'].append(storage_result)

    alert_result = _update_cluster_capacity_alert(
        client=client,
        headers=headers,
        cluster_id=cluster_id,
        host_count=host_count,
        cfg=stage06_cfg,
        stage_logger=stage_logger,
    )
    results['operations'].append(alert_result)

    dashboard_result = _setup_monitoring_dashboards(
        client=client,
        headers=headers,
        cluster_id=cluster_id,
        stage_logger=stage_logger,
    )
    results['operations'].append(dashboard_result)

    ctx.extra['cloudtower_config'] = {
        "status": "SUCCESS",
        **results,
    }

    stage_logger.info(
        tr("deploy.cloudtower_config.done"),
        progress_extra={
            "cluster_id": cluster_id,
            "operation_count": len(results['operations']),
        },
    )


def _parse_stage06_config(cfg_dict: Dict[str, Any]) -> Stage06Config:
    """从配置文件解析阶段 06 相关开关。"""

    cloud_cfg = dict(cfg_dict.get('cloudtower', {}) or {})
    raw_stage = cloud_cfg.get('stage06') or {}

    def _bool(data: Dict[str, Any], key: str, default: bool) -> bool:
        value = data.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    storage_cfg = raw_stage.get('storage_policy') or {}
    alert_cfg = raw_stage.get('alert_threshold') or {}

    storage_policy = _normalize_storage_policy(storage_cfg.get('name'))

    return Stage06Config(
        storage_policy=storage_policy,
        replica_num=int(storage_cfg.get('replica_num', 2) or 2),
        enable_thin=_bool(storage_cfg, 'thin_provision', True),
        alert_rule_name=str(alert_cfg.get('name', "zbs_cluster_data_space_use_rate")).strip() or "zbs_cluster_data_space_use_rate",
        alert_critical=int(alert_cfg.get('critical_threshold', 90) or 90),
        alert_notice_floor=int(alert_cfg.get('notice_floor', 50) or 50),
    )


def _ensure_cluster_info(
    *,
    attach_info: Dict[str, Any],
    client: APIClient,
    headers: Dict[str, str],
    stage_logger: logging.LoggerAdapter,
) -> Dict[str, Any]:
    """综合阶段 05 缓存与实时查询，确保获得集群设置 ID 与主机数量。"""

    cluster = attach_info.get('cluster') if isinstance(attach_info, dict) else None
    if isinstance(cluster, dict):
        cluster_id = cluster.get('id') or cluster.get('cluster_id')
        if cluster_id:
            settings = cluster.get('settings') or {}
            settings_id = settings.get('id') if isinstance(settings, dict) else cluster.get('settings_id')
            host_num = cluster.get('host_num')
            if settings_id and host_num is not None:
                return {
                    "id": str(cluster_id),
                    "settings_id": str(settings_id),
                    "host_num": int(host_num),
                }

    stage_logger.info(tr("deploy.cloudtower_config.cluster_info_cache_miss"))
    response = client.post(CLOUDTOWER_GET_CLUSTERS_ENDPOINT, payload={}, headers=headers)
    clusters = _extract_cluster_list(response)
    if not clusters:
        raise RuntimeError("未能从 CloudTower 查询到任何集群信息。")

    target_id = (cluster or {}).get('id') if isinstance(cluster, dict) else None
    target_ip = (cluster or {}).get('ip') if isinstance(cluster, dict) else None
    chosen = _select_cluster(clusters, target_id=target_id, target_ip=target_ip)
    if not chosen:
        raise RuntimeError("CloudTower 查询结果中缺少目标集群，请先确认阶段 05 是否成功。")

    settings_obj = chosen.get('settings') if isinstance(chosen, dict) else None
    settings_id = settings_obj.get('id') if isinstance(settings_obj, dict) else chosen.get('settings_id')
    if not settings_id:
        raise RuntimeError("CloudTower 集群详情缺少 settings.id 字段。")

    return {
        "id": str(chosen.get('id')),
        "settings_id": str(settings_id),
        "host_num": int(chosen.get('host_num') or 0),
    }


def _normalize_storage_policy(value: Any) -> str:
    """归一化存储策略名称，防止传入 GraphQL 无效枚举（如 default）。"""

    default_policy = "REPLICA_2_THIN_PROVISION"
    if not value:
        return default_policy

    name = str(value).strip().upper()
    if name == "DEFAULT":
        return default_policy

    allowed = {
        "REPLICA_2_THIN_PROVISION",
        "REPLICA_3_THIN_PROVISION",
        "EC_4_2_THIN_PROVISION",
        "EC_6_2_THIN_PROVISION",
    }

    if name in allowed:
        return name

    logger.warning("存储策略名称不被识别，已回退为默认双副本精简", extra={"input": name})
    return default_policy


def _extract_cluster_list(response: Any) -> List[Dict[str, Any]]:
    """解析列表返回的集群数据，仅处理 list 形态。"""

    if not isinstance(response, list):
        return []

    clusters: List[Dict[str, Any]] = []
    for item in response:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get('data'), dict) and isinstance(item['data'].get('clusters'), list):
            clusters.extend([cluster for cluster in item['data']['clusters'] if isinstance(cluster, dict)])
        else:
            clusters.append(item)
    return clusters


def _select_cluster(
    clusters: Iterable[Dict[str, Any]],
    *,
    target_id: Optional[str],
    target_ip: Optional[str],
) -> Optional[Dict[str, Any]]:
    """根据 ID 或 IP 从列表中挑选目标集群。"""

    for cluster in clusters:
        cid = str(cluster.get('id')) if cluster.get('id') else None
        if target_id and cid == str(target_id):
            return cluster
    for cluster in clusters:
        ip = str(cluster.get('ip')) if cluster.get('ip') else None
        if target_ip and ip == str(target_ip):
            return cluster
    cluster_list = list(clusters)
    return cluster_list[0] if cluster_list else None


def _update_default_storage_policy(
    *,
    client: APIClient,
    settings_id: str,
    cfg: Stage06Config,
    stage_logger: logging.LoggerAdapter,
) -> Dict[str, Any]:
    """调用 GraphQL 更新默认存储策略为双副本精简部署。"""

    payload = {
        "operationName": "updateClusterSettings",
        "variables": {
            "data": {
                "default_storage_policy": cfg.storage_policy,
                "default_storage_policy_replica_num": cfg.replica_num,
                "default_storage_policy_ec_k": None,
                "default_storage_policy_ec_m": None,
                "default_storage_policy_thin_provision": cfg.enable_thin,
            },
            "where": {"id": settings_id},
        },
        "query": CLOUDTOWER_GQL_UPDATE_CLUSTER_SETTINGS,
    }

    data = _post_cloudtower_graphql(
        client=client,
        payload=payload,
        stage_logger=stage_logger,
        description=tr("deploy.cloudtower_config.action_update_storage_policy"),
        ignore_messages=(),
    )

    updated = data.get('updateClusterSettings') if isinstance(data, dict) else {}
    if not isinstance(updated, dict):
        updated = {}
    stage_logger.info(
        tr("deploy.cloudtower_config.storage_policy_updated"),
        progress_extra={
            "settings_id": settings_id,
            "policy": updated.get('default_storage_policy', cfg.storage_policy),
            "replica": updated.get('default_storage_policy_replica_num', cfg.replica_num),
            "thin_provision": updated.get('default_storage_policy_thin_provision', cfg.enable_thin),
        },
    )

    return {
        "type": "storage_policy",
        "settings_id": settings_id,
        "response": updated,
    }


def _update_cluster_capacity_alert(
    *,
    client: APIClient,
    headers: Dict[str, str],
    cluster_id: str,
    host_count: int,
    cfg: Stage06Config,
    stage_logger: logging.LoggerAdapter,
) -> Dict[str, Any]:
    """计算容量告警阈值并尝试写回 CloudTower。"""

    if host_count <= 0:
        stage_logger.warning(tr("deploy.cloudtower_config.alert_host_missing"))
        return {"type": "alert_threshold", "skipped": True, "reason": "host_count_missing"}

    ratio = ((host_count - 1) / host_count) - 0.05
    notice_value = max(cfg.alert_notice_floor, min(cfg.alert_critical - 1, math.floor(max(ratio, 0.1) * 100)))
    stage_logger.info(
        tr("deploy.cloudtower_config.alert_compute_threshold"),
        progress_extra={
            "host_count": host_count,
            "notice_threshold": notice_value,
            "critical_threshold": cfg.alert_critical,
        },
    )

    rules_payload = {
        "operationName": "globalAlertRules",
        "variables": deepcopy(DEFAULT_GLOBAL_ALERT_RULES_VARIABLES),
        "query": CLOUDTOWER_GQL_LIST_ALERT_RULES,
    }
    data = client.post(CLOUDTOWER_GRAPHQL_ENDPOINT, payload=rules_payload, headers=headers)
    rule_list = (data or {}).get('data', {}).get('globalAlertRules', []) if isinstance(data, dict) else []

    target_rule = None
    target_alert = None
    for rule in rule_list:
        if not isinstance(rule, dict):
            continue
        if str(rule.get('name')) != cfg.alert_rule_name:
            continue
        target_rule = rule
        for alert in rule.get('alert_rules', []) or []:
            if isinstance(alert, dict) and str(alert.get('cluster', {}).get('id')) == cluster_id:
                target_alert = alert
                break
        break

    if not target_rule or not target_alert:
        stage_logger.warning(tr("deploy.cloudtower_config.alert_rule_missing"))
        return {
            "type": "alert_threshold",
            "skipped": True,
            "reason": "rule_missing",
            "computed_notice": notice_value,
        }

    alert_id = target_alert.get('id')
    if not alert_id:
        stage_logger.warning(tr("deploy.cloudtower_config.alert_id_missing"))
        return {
            "type": "alert_threshold",
            "skipped": True,
            "reason": "alert_id_missing",
            "computed_notice": notice_value,
        }

    thresholds = [
        {
            "value": cfg.alert_critical,
            "severity": "CRITICAL",
            "quantile": 0,
            "__typename": "Thresholds",
        },
        {
            "value": notice_value,
            "severity": "NOTICE",
            "quantile": 0,
            "__typename": "Thresholds",
        },
    ]

    stage_logger.info(
        tr("deploy.cloudtower_config.alert_prepare_update"),
        progress_extra={
            "global_rule_id": target_rule.get('id') if isinstance(target_rule, dict) else None,
            "alert_rule_id": alert_id,
            "notice": notice_value,
            "critical": cfg.alert_critical,
        },
    )

    payload = {
        "operationName": "updateGlobalAlertRule",
        "variables": {
            "where": {"id": target_rule.get('id')},
            "data": {
                "thresholds": thresholds,
                "alert_rules": {
                    "update": [
                        {
                            "where": {"id": alert_id},
                            "data": {
                                "customized": True,
                                "disabled": False,
                                "thresholds": thresholds,
                            },
                        }
                    ]
                },
                "disabled": False,
            },
        },
        "query": CLOUDTOWER_GQL_UPDATE_GLOBAL_ALERT_RULE,
    }

    response = client.post(CLOUDTOWER_GRAPHQL_ENDPOINT, payload=payload, headers=headers)
    result = (response or {}).get('data', {}).get('updateGlobalAlertRule') if isinstance(response, dict) else None

    if not result:
        stage_logger.warning(tr("deploy.cloudtower_config.alert_update_warn"))
    else:
        stage_logger.info(
            tr("deploy.cloudtower_config.alert_update_done"),
            progress_extra={
                "alert_rule_id": alert_id,
                "notice": notice_value,
                "critical": cfg.alert_critical,
            },
        )

    return {
        "type": "alert_threshold",
        "alert_rule_id": alert_id,
        "global_rule_id": target_rule.get('id') if isinstance(target_rule, dict) else None,
        "notice": notice_value,
        "critical": cfg.alert_critical,
        "response": result or response,
    }


def _setup_monitoring_dashboards(
    *,
    client: APIClient,
    headers: Dict[str, str],
    cluster_id: str,
    stage_logger: logging.LoggerAdapter,
) -> Dict[str, Any]:
    """自动创建监控面板视图与图表"""

    views: Dict[str, Optional[str]] = {}
    view_names = ["Cluster", "Host", "VM"]

    for name in view_names:
        view_id, created = _find_or_create_view(
            client=client,
            headers=headers,
            cluster_id=cluster_id,
            view_name=name,
            stage_logger=stage_logger,
        )
        views[name] = view_id
        stage_logger.info(
            tr("deploy.cloudtower_config.views_ready"),
            progress_extra={"view_name": name, "view_id": view_id, "created": created},
        )

    host_ids = _fetch_host_ids(client=client, headers=headers, cluster_id=cluster_id, stage_logger=stage_logger)

    graph_batches: List[Dict[str, Any]] = []

    cluster_view = views.get("Cluster")
    if cluster_view:
        count = _create_cluster_graphs(
            client=client,
            headers=headers,
            cluster_id=cluster_id,
            view_id=cluster_view,
            stage_logger=stage_logger,
        )
        graph_batches.append({"view": "Cluster", "created": count})

    host_view = views.get("Host")
    if host_view:
        count = _create_host_graphs(
            client=client,
            headers=headers,
            cluster_id=cluster_id,
            view_id=host_view,
            host_ids=host_ids,
            stage_logger=stage_logger,
        )
        graph_batches.append({"view": "Host", "created": count, "host_count": len(host_ids)})

    vm_view = views.get("VM")
    if vm_view:
        count = _create_vm_graphs(
            client=client,
            headers=headers,
            cluster_id=cluster_id,
            view_id=vm_view,
            stage_logger=stage_logger,
        )
        graph_batches.append({"view": "VM", "created": count})

    stage_logger.info(
        tr("deploy.cloudtower_config.dashboards_done"),
        progress_extra={"views": views, "graph_batches": graph_batches},
    )

    return {
        "type": "monitoring_dashboards",
        "views": views,
        "graph_batches": graph_batches,
        "host_count": len(host_ids),
    }


def _find_or_create_view(
    *,
    client: APIClient,
    headers: Dict[str, str],
    cluster_id: str,
    view_name: str,
    stage_logger: logging.LoggerAdapter,
) -> Tuple[Optional[str], bool]:
    payload = {
        "where": {
            "cluster": {"id": cluster_id},
            "name": view_name,
        }
    }
    response = client.post("/v2/api/get-views", payload=payload, headers=headers)
    view_id = None
    if isinstance(response, list) and response:
        first = cast(List[Any], response)[0]
        if isinstance(first, dict):
            view_id = first.get('id')

    created = False
    if not view_id:
        create_payload = [
            {
                "time_unit": "HOUR",
                "time_span": 2,
                "cluster_id": cluster_id,
                "name": view_name,
            }
        ]
        _ = client.post("/v2/api/create-view", payload=cast(Dict[str, Any], create_payload), headers=headers)
        created = True
        # 再次查询以获取 ID
        response = client.post("/v2/api/get-views", payload=payload, headers=headers)
        if isinstance(response, list) and response:
            first = cast(List[Any], response)[0]
            if isinstance(first, dict):
                view_id = first.get('id')

    return view_id, created


def _fetch_host_ids(
    *,
    client: APIClient,
    headers: Dict[str, str],
    cluster_id: str,
    stage_logger: logging.LoggerAdapter,
) -> List[str]:
    payload = {"where": {"cluster": {"id": cluster_id}}}
    response = client.post("/v2/api/get-hosts", payload=payload, headers=headers)
    host_ids: List[str] = []

    candidates: List[Any] = []
    if isinstance(response, list):
        candidates = response
    elif isinstance(response, dict):
        data = response.get('data')
        if isinstance(data, list):
            candidates = data

    for item in candidates:
        if isinstance(item, dict) and item.get('id'):
            host_ids.append(str(item['id']))

    stage_logger.info(
        tr("deploy.cloudtower_config.host_list_done"),
        progress_extra={"host_count": len(host_ids)},
    )

    return host_ids


def _create_cluster_graphs(
    *,
    client: APIClient,
    headers: Dict[str, str],
    cluster_id: str,
    view_id: str,
    stage_logger: logging.LoggerAdapter,
) -> int:
    graphs = [
        {
            "type": "AREA",
            "resource_type": "cluster",
            "view_id": view_id,
            "title": "集群 CPU 使用率 %",
            "cluster_id": cluster_id,
            "connect_id": [cluster_id],
            "metric_name": "cluster_cpu_usage_percent",
        },
        {
            "type": "AREA",
            "resource_type": "cluster",
            "view_id": view_id,
            "title": "集群 内存 使用率 %",
            "cluster_id": cluster_id,
            "connect_id": [cluster_id],
            "metric_name": "cluster_memory_usage_percent",
        },
        {
            "type": "AREA",
            "resource_type": "cluster",
            "view_id": view_id,
            "title": "集群 已使用数据空间",
            "cluster_id": cluster_id,
            "connect_id": [cluster_id],
            "metric_name": "zbs_cluster_provisioned_data_space_bytes",
        },
    ]
    client.post("/v2/api/create-graph", payload=cast(Dict[str, Any], graphs), headers=headers)
    stage_logger.info(tr("deploy.cloudtower_config.cluster_graphs_created"), progress_extra={"view_id": view_id, "count": len(graphs)})
    return len(graphs)


def _create_host_graphs(
    *,
    client: APIClient,
    headers: Dict[str, str],
    cluster_id: str,
    view_id: str,
    host_ids: List[str],
    stage_logger: logging.LoggerAdapter,
) -> int:
    if not host_ids:
        stage_logger.warning(tr("deploy.cloudtower_config.host_graphs_skip_no_host"))
        return 0

    graphs = [
        {
            "type": "AREA",
            "resource_type": "host",
            "view_id": view_id,
            "title": "主机 CPU 使用率 %",
            "cluster_id": cluster_id,
            "connect_id": host_ids,
            "metric_name": "host_cpu_overall_usage_percent",
        },
        {
            "type": "AREA",
            "resource_type": "host",
            "view_id": view_id,
            "title": "分配给运行（含暂停）虚拟机逻辑核数量",
            "cluster_id": cluster_id,
            "connect_id": host_ids,
            "metric_name": "elf_host_vcpus_provisioned_running",
        },
        {
            "type": "AREA",
            "resource_type": "host",
            "view_id": view_id,
            "title": "主机 CPU 温度",
            "cluster_id": cluster_id,
            "connect_id": host_ids,
            "metric_name": "host_cpu_temperature_celsius",
        },
        {
            "type": "AREA",
            "resource_type": "host",
            "view_id": view_id,
            "title": "主机 内存 使用率 %",
            "cluster_id": cluster_id,
            "connect_id": host_ids,
            "metric_name": "host_memory_usage_percent",
        },
        {
            "type": "AREA",
            "resource_type": "host",
            "view_id": view_id,
            "title": "缓存命中率 - 读",
            "cluster_id": cluster_id,
            "connect_id": host_ids,
            "metric_name": "zbs_chunk_read_cache_hit_ratio",
        },
        {
            "type": "AREA",
            "resource_type": "host",
            "view_id": view_id,
            "title": "缓存命中率 - 写",
            "cluster_id": cluster_id,
            "connect_id": host_ids,
            "metric_name": "zbs_chunk_write_cache_hit_ratio",
        },
        {
            "type": "AREA",
            "resource_type": "host",
            "view_id": view_id,
            "title": "已使用数据空间（物理）",
            "cluster_id": cluster_id,
            "connect_id": host_ids,
            "metric_name": "zbs_chunk_used_data_space_bytes",
        },
    ]

    client.post("/v2/api/create-graph", payload=cast(Dict[str, Any], graphs), headers=headers)
    stage_logger.info(
        tr("deploy.cloudtower_config.host_graphs_created"),
        progress_extra={"view_id": view_id, "count": len(graphs), "host_count": len(host_ids)},
    )
    return len(graphs)


def _create_vm_graphs(
    *,
    client: APIClient,
    headers: Dict[str, str],
    cluster_id: str,
    view_id: str,
    stage_logger: logging.LoggerAdapter,
) -> int:
    graphs = [
        {
            "type": "AREA",
            "resource_type": "vm",
            "metric_type": "TOPK",
            "metric_count": "5",
            "view_id": view_id,
            "title": "虚拟机 CPU 使用率 Top N",
            "cluster_id": cluster_id,
            "connect_id": [],
            "metric_name": "elf_vm_cpu_overall_usage_percent",
        },
        {
            "type": "AREA",
            "resource_type": "vm",
            "metric_type": "TOPK",
            "metric_count": "5",
            "view_id": view_id,
            "title": "虚拟机 CPU 就绪等待时间占比 Top N",
            "cluster_id": cluster_id,
            "connect_id": [],
            "metric_name": "elf_vm_cpu_overall_steal_time_percent",
        },
        {
            "type": "AREA",
            "resource_type": "vm",
            "metric_type": "TOPK",
            "metric_count": "5",
            "view_id": view_id,
            "title": "虚拟机 内存 使用率 Top N",
            "cluster_id": cluster_id,
            "connect_id": [],
            "metric_name": "elf_vm_memory_usage_percent",
        },
        {
            "type": "AREA",
            "resource_type": "vm",
            "metric_type": "TOPK",
            "metric_count": "5",
            "view_id": view_id,
            "title": "虚拟机写带宽 Top N",
            "cluster_id": cluster_id,
            "connect_id": [],
            "metric_name": "elf_vm_disk_overall_write_speed_bps",
        },
        {
            "type": "AREA",
            "resource_type": "vm",
            "metric_type": "TOPK",
            "metric_count": "5",
            "view_id": view_id,
            "title": "虚拟机 读写延迟 Top N",
            "cluster_id": cluster_id,
            "connect_id": [],
            "metric_name": "elf_vm_disk_overall_avg_read_write_latency_ns",
        },
    ]

    client.post("/v2/api/create-graph", payload=cast(Dict[str, Any], graphs), headers=headers)
    stage_logger.info(tr("deploy.cloudtower_config.vm_graphs_created"), progress_extra={"view_id": view_id, "count": len(graphs)})
    return len(graphs)

