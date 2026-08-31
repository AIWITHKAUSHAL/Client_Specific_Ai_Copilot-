"""Escalation tool - the human-in-the-loop safety valve.

Whenever the copilot cannot answer safely (or the employee explicitly asks
for a human), the request is escalated instead of guessed at.  The response
always contains the exact phrase required by the assignment:

    Escalated to Operations Team

Production note
---------------
The prototype records escalations in memory and in the copilot log.  In
production :func:`escalate_issue` becomes an adapter that opens a real
ticket in the client's helpdesk (ServiceNow, Zendesk, Jira Service
Management or an internal tool) and returns that system's ticket id - the
function signature and the required phrase stay the same.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from typing import Any, Dict, List

from core.config import ESCALATION_PHRASE, ESCALATION_QUEUE, ESCALATION_TICKET_PREFIX
from tools.base import ToolResult, tool_result

TOOL_NAME = "escalation"

_ticket_counter = count(1)

# In-memory stand-in for the client's ticketing system.  Useful for the demo,
# for tests and for the ``GET /api/v1/escalations`` endpoint.
_ESCALATIONS: List[Dict[str, Any]] = []


def _next_ticket_id() -> str:
    """Return the next local escalation reference, e.g. ``ESC-0001``."""
    return f"{ESCALATION_TICKET_PREFIX}-{next(_ticket_counter):04d}"


def escalate_issue(reason: str = "") -> ToolResult:
    """Escalate an issue to the operations team.

    Args:
        reason: Optional free-text description of what needs a human.

    Returns:
        A tool result whose ``message`` always contains the exact phrase
        ``"Escalated to Operations Team"``.
    """
    clean_reason = (reason or "").strip() or "No reason provided by the employee."
    ticket_id = _next_ticket_id()
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    ticket = {
        "ticket_id": ticket_id,
        "reason": clean_reason,
        "queue": ESCALATION_QUEUE,
        "status": "open",
        "created_at": created_at,
    }
    _ESCALATIONS.append(ticket)

    message = (
        f"{ESCALATION_PHRASE}.\n"
        f"  Reference : {ticket_id}\n"
        f"  Queue     : {ESCALATION_QUEUE}\n"
        f"  Reason    : {clean_reason}\n"
        "A human operations specialist will follow up on this request."
    )
    return tool_result(TOOL_NAME, True, message, ticket)


def list_escalations() -> List[Dict[str, Any]]:
    """Return every escalation raised in the current process."""
    return [dict(ticket) for ticket in _ESCALATIONS]


def reset_escalations() -> None:
    """Clear the in-memory escalation store (used by tests)."""
    global _ticket_counter
    _ESCALATIONS.clear()
    _ticket_counter = count(1)
