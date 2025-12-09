"""预检通用工具函数。"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, Mapping


def update_level(current: str, candidate: str) -> str:
    """根据优先级（error > warning > info > ok）合并级别。"""

    priority = {"error": 3, "warning": 2, "info": 1, "ok": 0}
    return candidate if priority.get(candidate, 0) > priority.get(current, 0) else current


def log_debug(logger: logging.Logger, title: str, payload: Dict[str, Any]) -> None:
    """在 DEBUG 等级下输出 JSON 格式的日志，便于排查。"""

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(title, extra={"detail": json.dumps(payload, ensure_ascii=False)})


def get_section(config: Mapping[str, Any] | None, name: str) -> Dict[str, Any]:
    """获取配置中的子字典，若不存在则返回空字典。"""

    if not isinstance(config, Mapping):
        return {}
    section = config.get(name, {})
    if isinstance(section, Mapping):
        return dict(section)
    return {}


def first(iterable: Iterable[Any]) -> Any | None:
    """返回迭代器中的第一个元素，无则 None。"""

    for item in iterable:
        return item
    return None
