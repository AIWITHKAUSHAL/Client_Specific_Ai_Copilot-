"""In-process metrics registry.

Every employee query produces one :class:`QueryRecord`.  Records are written
to ``logs/copilot.log`` by :mod:`services.monitoring_service` and aggregated
here so the CLI (``stats``) and the API (``GET /api/v1/metrics``) can show
live operational health without any external system.

This is deliberately the smallest thing that works.  In production the same
records feed Prometheus counters/histograms or a managed APM agent - see
docs/production-readiness.md ("Observability").
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

MAX_RECENT_RECORDS = 200


@dataclass
class QueryRecord:
    """One monitored copilot interaction.

    Captures exactly what the assignment requires: the query, the tool that
    was selected, how long it took, whether it succeeded and what was
    returned - plus the detected intent and a timestamp.
    """

    query: str
    intent: str
    tool_selected: str
    execution_time_ms: float
    success: bool
    response: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    )
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return the record as a plain dictionary."""
        return asdict(self)


class MetricsRegistry:
    """Aggregates :class:`QueryRecord` instances for the current process."""

    def __init__(self, max_recent: int = MAX_RECENT_RECORDS) -> None:
        self._recent: Deque[QueryRecord] = deque(maxlen=max_recent)
        self._tool_counts: Counter = Counter()
        self._intent_counts: Counter = Counter()
        self._total = 0
        self._successes = 0
        self._duration_total_ms = 0.0

    def record(self, record: QueryRecord) -> QueryRecord:
        """Register one query record."""
        self._recent.append(record)
        self._tool_counts[record.tool_selected] += 1
        self._intent_counts[record.intent] += 1
        self._total += 1
        self._successes += int(record.success)
        self._duration_total_ms += record.execution_time_ms
        return record

    def recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent query records, newest last."""
        records = list(self._recent)[-limit:]
        return [record.to_dict() for record in records]

    def snapshot(self) -> Dict[str, Any]:
        """Return aggregate counters for dashboards and health checks."""
        total = self._total
        durations = sorted(r.execution_time_ms for r in self._recent)
        return {
            "total_queries": total,
            "successful": self._successes,
            "failed": total - self._successes,
            "success_rate": round(self._successes / total, 4) if total else 0.0,
            "avg_execution_time_ms": round(self._duration_total_ms / total, 3) if total else 0.0,
            "max_execution_time_ms": round(durations[-1], 3) if durations else 0.0,
            "p95_execution_time_ms": round(_percentile(durations, 95), 3) if durations else 0.0,
            "queries_by_tool": dict(self._tool_counts),
            "queries_by_intent": dict(self._intent_counts),
        }

    def reset(self) -> None:
        """Clear all metrics (used by tests)."""
        self._recent.clear()
        self._tool_counts.clear()
        self._intent_counts.clear()
        self._total = 0
        self._successes = 0
        self._duration_total_ms = 0.0


def _percentile(sorted_values: List[float], percentile: float) -> float:
    """Nearest-rank percentile over an already sorted list."""
    if not sorted_values:
        return 0.0
    index = max(0, min(len(sorted_values) - 1, round(percentile / 100 * len(sorted_values)) - 1))
    return sorted_values[index]


# Process-wide registry shared by the CLI and the API.
metrics = MetricsRegistry()
