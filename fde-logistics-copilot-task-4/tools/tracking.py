"""Shipment tracking tool.

Answers "Where is shipment SH1024?" and "Which shipments are delayed?".

Integration note
----------------
The tool reads through :mod:`data.shipments`, never through a global
dictionary of its own.  For a real client the FDE implements a tracking
adapter with the same two functions - ``get_shipment_record`` and
``get_all_shipments`` - against the client's TMS / WMS / ERP REST API (or a
replicated Postgres table) and this module keeps working unchanged.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from data.shipments import STATUS_DELAYED, get_all_shipments, get_shipment_record
from tools.base import ToolResult, tool_result

TOOL_NAME = "tracking"

# Characters clients and employees sprinkle into identifiers: "sh-1024",
# "SH 1024", "sh1024 ".
_ID_NOISE = re.compile(r"[\s\-_/]")


def normalize_shipment_id(shipment_id: str) -> str:
    """Return a canonical shipment id (``' sh-1024 '`` -> ``'SH1024'``)."""
    if shipment_id is None:
        return ""
    return _ID_NOISE.sub("", str(shipment_id)).strip().upper()


def _format_shipment(record: Dict[str, Any]) -> str:
    """Render one shipment record as an operator-friendly block of text."""
    lines = [
        f"Shipment {record['shipment_id']}",
        f"  Status            : {record['status']}",
        f"  Origin            : {record['origin']}",
        f"  Destination       : {record['destination']}",
        f"  Estimated delivery: {record['estimated_delivery']}",
    ]
    if record.get("delivered_on"):
        lines.append(f"  Delivered on      : {record['delivered_on']}")
    if record.get("carrier"):
        lines.append(f"  Carrier           : {record['carrier']}")
    if record.get("last_scan"):
        lines.append(f"  Last scan         : {record['last_scan']}")
    if record.get("delay_reason"):
        lines.append(f"  Delay reason      : {record['delay_reason']}")
    return "\n".join(lines)


def track_shipment(shipment_id: str) -> ToolResult:
    """Look up a single shipment by identifier.

    Args:
        shipment_id: Shipment identifier in any common form (``SH1024``,
            ``sh-1024``, ``sh 1024``).

    Returns:
        A tool result.  ``success`` is ``False`` when the identifier is
        missing or unknown; the message then explains what to do next.
    """
    normalized = normalize_shipment_id(shipment_id)

    if not normalized:
        return tool_result(
            TOOL_NAME,
            False,
            "No shipment ID was provided. Please ask again with an ID, for example: "
            "'Where is shipment SH1024?'",
            {"shipment_id": None},
        )

    record = get_shipment_record(normalized)
    if record is None:
        known = ", ".join(sorted(r["shipment_id"] for r in get_all_shipments()))
        return tool_result(
            TOOL_NAME,
            False,
            f"Shipment {normalized} was not found in the tracking system.\n"
            f"Known shipment IDs in this prototype dataset: {known}",
            {"shipment_id": normalized, "found": False},
        )

    return tool_result(
        TOOL_NAME,
        True,
        _format_shipment(record),
        {"shipment_id": normalized, "found": True, "shipment": record},
    )


def get_delayed_shipments() -> ToolResult:
    """Return every shipment currently in the ``Delayed`` state."""
    delayed: List[Dict[str, Any]] = [
        record
        for record in get_all_shipments()
        if str(record.get("status", "")).lower() == STATUS_DELAYED.lower()
    ]

    if not delayed:
        return tool_result(
            TOOL_NAME,
            True,
            "Good news: no shipments are currently marked as Delayed.",
            {"count": 0, "shipments": []},
        )

    header = f"{len(delayed)} delayed shipment(s) found:"
    body = "\n\n".join(_format_shipment(record) for record in delayed)
    return tool_result(
        TOOL_NAME,
        True,
        f"{header}\n\n{body}",
        {"count": len(delayed), "shipments": delayed},
    )
