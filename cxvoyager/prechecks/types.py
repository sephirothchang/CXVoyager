"""预检数据结构定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List


@dataclass
class ProbeRecord:
    """单条探测记录，便于统一汇总与序列化。"""

    category: str
    target: str
    level: str
    message: str
    probes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "target": self.target,
            "level": self.level,
            "message": self.message,
            "probes": self.probes,
        }


@dataclass
class PrecheckReport:
    """预检汇总结果，包含全部探测记录。"""

    records: List[ProbeRecord] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return any(record.level == "error" for record in self.records)

    def extend(self, records: Iterable[ProbeRecord]) -> None:
        self.records.extend(list(records))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "records": [r.to_dict() for r in self.records],
            "has_error": self.has_error,
        }
