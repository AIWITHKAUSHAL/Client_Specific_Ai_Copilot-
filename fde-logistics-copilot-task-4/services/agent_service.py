"""Agent service - the orchestration entry point used by every channel.

The CLI (``app.py``) and the REST API (``api/``) both go through this
service instead of calling tools directly.  Anything that must happen for
*every* interaction regardless of channel - routing, monitoring, uniform
error handling - happens here exactly once.

The direct tool wrappers (:meth:`track`, :meth:`price`, ...) exist for the
REST endpoints that address one capability explicitly.  They are still
monitored, so the audit trail covers structured API traffic as well as
natural language queries.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

# NOTE: imported as a module (not ``from agent import ...``) so that the
# service layer and the agent module can import each other safely.
import agent as agent_module
from core.exceptions import ValidationError
from services.monitoring_service import monitoring
from tools.escalation import escalate_issue, list_escalations
from tools.policy import get_policy
from tools.pricing import calculate_delivery_cost
from tools.tracking import get_delayed_shipments, track_shipment


class AgentService:
    """Channel-independent facade over the agent and the tools."""

    # -- natural language ---------------------------------------------------
    def handle(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Route and answer a natural language query (monitored)."""
        return agent_module.handle_query(query, context=context)

    # -- direct tool access (monitored) -------------------------------------
    def track(self, shipment_id: str) -> Dict[str, Any]:
        """Look up a single shipment."""
        return self._run(f"[api] track shipment {shipment_id}", "shipment_tracking",
                         lambda: track_shipment(shipment_id))

    def delayed(self) -> Dict[str, Any]:
        """List delayed shipments."""
        return self._run("[api] list delayed shipments", "delayed_shipments",
                         get_delayed_shipments)

    def price(self, weight: float, distance: float, priority: str = "standard") -> Dict[str, Any]:
        """Calculate a delivery cost."""
        return self._run(
            f"[api] calculate cost weight={weight} distance={distance} priority={priority}",
            "cost_calculation",
            lambda: calculate_delivery_cost(weight, distance, priority),
        )

    def policy(self, topic: str) -> Dict[str, Any]:
        """Look up a policy by name or topic."""
        return self._run(f"[api] policy {topic}", "policy_lookup", lambda: get_policy(topic))

    def escalate(self, reason: str = "") -> Dict[str, Any]:
        """Raise an escalation to the operations team."""
        return self._run(f"[api] escalate: {reason}", "escalation",
                         lambda: escalate_issue(reason))

    def escalations(self) -> List[Dict[str, Any]]:
        """Return escalations raised in this process."""
        return list_escalations()

    # -- monitoring ---------------------------------------------------------
    def metrics(self) -> Dict[str, Any]:
        """Return aggregate monitoring metrics."""
        return monitoring.snapshot()

    def recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return the most recent monitored interactions."""
        return monitoring.recent(limit)

    # -- internals ----------------------------------------------------------
    def _run(self, label: str, intent: str, call) -> Dict[str, Any]:
        """Execute a tool call with timing, monitoring and error handling."""
        started = time.perf_counter()
        try:
            result = call()
            elapsed_ms = (time.perf_counter() - started) * 1000
            monitoring.record_query(
                query=label,
                intent=intent,
                tool_selected=str(result.get("tool", "unknown")),
                execution_time_ms=elapsed_ms,
                success=bool(result.get("success")),
                response=str(result.get("message", "")),
            )
            result["execution_time_ms"] = round(elapsed_ms, 3)
            return result
        except ValidationError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            monitoring.record_query(
                query=label,
                intent=intent,
                tool_selected=intent,
                execution_time_ms=elapsed_ms,
                success=False,
                response=str(exc),
                error=str(exc),
            )
            raise


# Process-wide service instance shared by the CLI and the API.
agent_service = AgentService()
