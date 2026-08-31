"""Copilot tools.

Each tool is a small, independently testable unit that answers exactly one
kind of operational question.  Tools never know about the CLI, the API or
the agent - they take plain arguments and return a plain result dictionary
(see :mod:`tools.base`).  That is what makes them reusable across the CLI,
the REST API and any future channel (Slack, Teams, web).
"""

from tools.base import tool_result
from tools.escalation import escalate_issue
from tools.policy import get_policy
from tools.pricing import calculate_delivery_cost
from tools.tracking import get_delayed_shipments, track_shipment

__all__ = [
    "calculate_delivery_cost",
    "escalate_issue",
    "get_delayed_shipments",
    "get_policy",
    "tool_result",
    "track_shipment",
]
