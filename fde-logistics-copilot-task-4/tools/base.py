"""Shared result contract for every copilot tool.

All tools return the same shape so the agent, the CLI, the REST API and the
monitoring layer can treat them uniformly::

    {
        "tool":    "tracking",       # which tool produced this result
        "success": True,             # did the tool answer the question?
        "message": "Shipment ...",   # human readable answer
        "data":    {...} | None,     # structured payload for machines/UI
    }

``success`` means "the tool produced the answer that was asked for".
A clean miss (unknown shipment id, unknown policy) is ``success=False`` with
a helpful message - not an exception - because that is normal operational
traffic that monitoring should be able to count.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

ToolResult = Dict[str, Any]


def tool_result(
    tool: str,
    success: bool,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """Build a tool result dictionary."""
    return {"tool": tool, "success": success, "message": message, "data": data}
