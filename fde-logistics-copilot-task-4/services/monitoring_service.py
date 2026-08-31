"""Monitoring service.

Responsible for the assignment's monitoring requirement: every employee
query is recorded with its timestamp, text, selected tool, execution time,
success flag and final response.

Records go to two places:

* ``logs/copilot.log`` - one JSON object per line, so the log is both human
  readable and machine parsable (``grep``, ``jq``, or a log shipper);
* :data:`monitoring.metrics.metrics` - in-process aggregates for the CLI
  ``stats`` command and the ``/api/v1/metrics`` endpoint.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from core.logging_config import get_logger
from monitoring.metrics import QueryRecord, metrics

_LOG_PREVIEW_CHARS = 400


class MonitoringService:
    """Records copilot interactions to the log file and the metrics registry."""

    def __init__(self) -> None:
        self._logger = get_logger("copilot.monitoring")

    def record_query(
        self,
        query: str,
        intent: str,
        tool_selected: str,
        execution_time_ms: float,
        success: bool,
        response: str,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record one interaction and return it as a dictionary."""
        record = QueryRecord(
            query=query,
            intent=intent,
            tool_selected=tool_selected,
            execution_time_ms=round(execution_time_ms, 3),
            success=success,
            response=response,
            error=error,
        )
        metrics.record(record)
        self._logger.info(self._serialize(record))
        return record.to_dict()

    def _serialize(self, record: QueryRecord) -> str:
        """Render a record as a single-line JSON payload for the log file."""
        payload = record.to_dict()
        response = payload.get("response") or ""
        if len(response) > _LOG_PREVIEW_CHARS:
            payload["response"] = response[:_LOG_PREVIEW_CHARS] + "...[truncated]"
        # Newlines would break one-record-per-line parsing.
        payload["response"] = str(payload["response"]).replace("\n", " | ")
        return json.dumps(payload, ensure_ascii=False)

    def recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent recorded interactions."""
        return metrics.recent(limit)

    def snapshot(self) -> Dict[str, Any]:
        """Return aggregate metrics for the current process."""
        return metrics.snapshot()


# Process-wide monitoring service shared by the CLI and the API.
monitoring = MonitoringService()
