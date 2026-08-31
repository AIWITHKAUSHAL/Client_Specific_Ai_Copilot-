"""Policy lookup tool.

Prototype: deterministic keyword retrieval over the curated policy records
in :mod:`data.policies`.  No model, no network, no API key - the same
question always returns the same answer, which is exactly what an
operations team needs from a policy assistant.

Production: swap the retrieval step for documents -> chunking -> embeddings
-> vector database -> retrieval -> LLM answer grounded in the retrieved
chunks, keeping this function's signature and result shape.  See
docs/HLD.md and client-customization.md.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from data.policies import POLICIES, get_all_policies, get_policy_record
from tools.base import ToolResult, tool_result

TOOL_NAME = "policy"


def _keyword_hit(keyword: str, query: str) -> bool:
    """Return True when ``keyword`` occurs in ``query`` on word boundaries."""
    return re.search(rf"\b{re.escape(keyword)}", query) is not None


def _score_policy(record: Dict[str, Any], query: str) -> Tuple[int, int]:
    """Score one policy against the query.

    Returns ``(number of matching keywords, longest matching keyword)`` so
    that a specific match ("damaged shipment") beats a generic one
    ("shipment").
    """
    hits = [kw for kw in record["keywords"] if _keyword_hit(kw.lower(), query)]
    if record["name"].replace("_", " ") in query:
        hits.append(record["name"])
    if not hits:
        return (0, 0)
    return (len(hits), max(len(kw) for kw in hits))


def find_policy(query: str) -> Optional[Dict[str, Any]]:
    """Return the best matching policy record, or ``None``."""
    normalized = (query or "").strip().lower()
    if not normalized:
        return None

    # Direct hit on a canonical policy name, e.g. "refund" or "priority_shipping".
    direct = get_policy_record(normalized)
    if direct is not None:
        return direct

    ranked: List[Tuple[Tuple[int, int], Dict[str, Any]]] = []
    for record in get_all_policies():
        score = _score_policy(record, normalized)
        if score[0] > 0:
            ranked.append((score, record))

    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1]


def available_policies() -> List[str]:
    """Return the human-readable titles of every available policy."""
    return [str(record["title"]) for record in get_all_policies()]


def get_policy(query: str) -> ToolResult:
    """Answer a policy question.

    Args:
        query: Either a canonical policy name (``"refund"``) or a natural
            language question (``"What is our delivery policy?"``).

    Returns:
        A tool result containing the matching policy text, or - when nothing
        matches - the list of policies this copilot can answer.
    """
    record = find_policy(query)

    if record is None:
        options = "\n".join(f"  - {title}" for title in available_policies())
        return tool_result(
            TOOL_NAME,
            False,
            "I could not match that question to a published policy.\n"
            f"I can answer questions about:\n{options}",
            {"matched": False, "available": list(POLICIES.keys())},
        )

    message = (
        f"{record['title']}\n\n"
        f"{record['summary']}\n\n"
        f"Source: {record['source_document']} | Owner: {record['owner']} | "
        f"Last updated: {record['last_updated']}"
    )
    return tool_result(
        TOOL_NAME,
        True,
        message,
        {"matched": True, "policy": record},
    )
