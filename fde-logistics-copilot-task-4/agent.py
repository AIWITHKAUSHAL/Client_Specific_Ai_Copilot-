"""Operations Copilot agent - decides which tool answers an employee query.

The agent is a five-stage pipeline::

    query -> 1. intent detection
          -> 2. tool selection
          -> 3. tool execution
          -> 4. response generation
          -> 5. monitoring

Routing is **deterministic and rule based** by default (``COPILOT_AGENT_MODE
= rule_based``): no API key, no model, no network, identical output for
identical input.  For an operations team that is a feature - answers are
explainable and testable.

The router is a pluggable function (:func:`set_router`).  A future
LLM/function-calling router only has to return the same
:class:`RoutingDecision`; tools, monitoring and the API stay untouched.

Routing priority (highest first):

1. explicit escalation      "escalate this issue"
2. cost calculation         "calculate delivery cost"
3. delayed shipments        "which shipments are delayed?"
4. shipment tracking        "where is shipment SH1024?"
5. policy lookup            "what is our delivery policy?"
6. unknown                  -> safe fallback to escalation
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from core.config import AGENT_MODE, DEFAULT_PRIORITY, SHIPMENT_ID_PATTERN
from core.exceptions import CopilotError, ValidationError
from core.logging_config import get_logger
from services.monitoring_service import monitoring
from tools.escalation import escalate_issue
from tools.policy import find_policy, get_policy
from tools.pricing import calculate_delivery_cost
from tools.tracking import get_delayed_shipments, track_shipment

logger = get_logger("copilot.agent")

# ---------------------------------------------------------------------------
# Intents and tools
# ---------------------------------------------------------------------------
INTENT_ESCALATION = "escalation"
INTENT_PRICING = "cost_calculation"
INTENT_DELAYED = "delayed_shipments"
INTENT_TRACKING = "shipment_tracking"
INTENT_POLICY = "policy_lookup"
INTENT_UNKNOWN = "unknown"

TOOL_FOR_INTENT: Dict[str, str] = {
    INTENT_ESCALATION: "escalation",
    INTENT_PRICING: "pricing",
    INTENT_DELAYED: "tracking",
    INTENT_TRACKING: "tracking",
    INTENT_POLICY: "policy",
    INTENT_UNKNOWN: "escalation",  # unknown questions go to a human, never guessed
}

# ---------------------------------------------------------------------------
# Keyword vocabulary (the only thing most clients need to tune)
# ---------------------------------------------------------------------------
ESCALATION_KEYWORDS = (
    "escalate",
    "escalation",
    "raise a ticket",
    "open a ticket",
    "human agent",
    "talk to a human",
    "speak to a human",
    "speak to someone",
    "supervisor",
    "manager",
    "complaint",
)
PRICING_KEYWORDS = (
    "cost",
    "price",
    "pricing",
    "quote",
    "charge",
    "how much",
    "rate",
    "fee",
    "tariff",
    "freight cost",
)
DELAY_KEYWORDS = ("delayed", "delay", "late", "behind schedule", "overdue", "stuck")
TRACKING_KEYWORDS = (
    "track",
    "tracking",
    "where is",
    "where's",
    "status of",
    "shipment status",
    "locate",
    "eta",
)
POLICY_KEYWORDS = ("policy", "policies", "rule", "rules", "guideline", "sop")

_SHIPMENT_ID_RE = re.compile(SHIPMENT_ID_PATTERN)
_CONTEXT_ID_RE = re.compile(
    r"(?:shipment|consignment|tracking|awb|order)\s*(?:id|number|no\.?)\s*[:#]?\s*"
    r"([A-Za-z]{2,4}[\s-]?\d{3,8})",
    re.IGNORECASE,
)
_WEIGHT_RE = re.compile(
    r"(?:(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilogram|kilograms|kilos?)\b)"
    r"|(?:weight\s*(?:of|is|=|:)?\s*(\d+(?:\.\d+)?))",
    re.IGNORECASE,
)
_DISTANCE_RE = re.compile(
    r"(?:(\d+(?:\.\d+)?)\s*(?:km|kms|kilometer|kilometre|kilometers|kilometres|miles?)\b)"
    r"|(?:distance\s*(?:of|is|=|:)?\s*(\d+(?:\.\d+)?))",
    re.IGNORECASE,
)
_PRIORITY_RE = re.compile(r"\b(standard|express|urgent)\b", re.IGNORECASE)


@dataclass
class RoutingDecision:
    """What the router decided, and why.

    ``reason`` is kept so every routing decision is explainable to the
    client - a requirement whenever an assistant touches operations.
    """

    intent: str
    tool: str
    reason: str
    params: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1. Intent detection
# ---------------------------------------------------------------------------
def _contains_any(text: str, keywords: tuple) -> Optional[str]:
    """Return the first keyword found in ``text``, else ``None``."""
    for keyword in keywords:
        if keyword in text:
            return keyword
    return None


def extract_shipment_id(query: str) -> Optional[str]:
    """Extract a shipment identifier such as ``SH1024`` from free text."""
    if not query:
        return None
    contextual = _CONTEXT_ID_RE.search(query)
    if contextual:
        return re.sub(r"[\s-]", "", contextual.group(1)).upper()
    plain = _SHIPMENT_ID_RE.search(query)
    if plain:
        return re.sub(r"[\s-]", "", plain.group(1)).upper()
    return None


def extract_pricing_params(query: str) -> Dict[str, Any]:
    """Extract weight / distance / priority from a pricing question."""
    params: Dict[str, Any] = {}

    weight = _WEIGHT_RE.search(query)
    if weight:
        params["weight"] = float(weight.group(1) or weight.group(2))

    distance = _DISTANCE_RE.search(query)
    if distance:
        params["distance"] = float(distance.group(1) or distance.group(2))

    priority = _PRIORITY_RE.search(query)
    if priority:
        params["priority"] = priority.group(1).lower()

    return params


def rule_based_router(query: str) -> RoutingDecision:
    """Deterministic keyword/regex router (the default agent brain)."""
    text = (query or "").lower().strip()
    shipment_id = extract_shipment_id(query or "")
    mentions_policy = _contains_any(text, POLICY_KEYWORDS) is not None

    # 1 - explicit escalation always wins: a human asked for a human.
    keyword = _contains_any(text, ESCALATION_KEYWORDS)
    if keyword:
        return RoutingDecision(
            INTENT_ESCALATION,
            TOOL_FOR_INTENT[INTENT_ESCALATION],
            f"explicit escalation keyword: '{keyword}'",
        )

    # 2 - cost calculation (a policy question about pricing is not a quote).
    keyword = _contains_any(text, PRICING_KEYWORDS)
    if keyword and not mentions_policy:
        return RoutingDecision(
            INTENT_PRICING,
            TOOL_FOR_INTENT[INTENT_PRICING],
            f"pricing keyword: '{keyword}'",
            extract_pricing_params(query or ""),
        )

    # 3 - delayed shipment list.  A concrete shipment id means the employee
    #     wants that one shipment, not the whole delayed list.
    keyword = _contains_any(text, DELAY_KEYWORDS)
    if keyword and not mentions_policy and shipment_id is None:
        return RoutingDecision(
            INTENT_DELAYED,
            TOOL_FOR_INTENT[INTENT_DELAYED],
            f"delay keyword: '{keyword}' with no specific shipment id",
        )

    # 4 - single shipment tracking.
    keyword = _contains_any(text, TRACKING_KEYWORDS)
    if shipment_id is not None or (keyword and not mentions_policy):
        return RoutingDecision(
            INTENT_TRACKING,
            TOOL_FOR_INTENT[INTENT_TRACKING],
            f"shipment id '{shipment_id}'" if shipment_id else f"tracking keyword: '{keyword}'",
            {"shipment_id": shipment_id},
        )

    # 5 - policy lookup: an explicit "policy" word, or a question that maps
    #     onto a published policy topic (e.g. "how do I claim for damage?").
    if mentions_policy or find_policy(text) is not None:
        return RoutingDecision(
            INTENT_POLICY,
            TOOL_FOR_INTENT[INTENT_POLICY],
            "policy keyword" if mentions_policy else "matched a published policy topic",
            {"topic": query},
        )

    # 6 - unknown: never guess, hand over to a human.
    return RoutingDecision(
        INTENT_UNKNOWN,
        TOOL_FOR_INTENT[INTENT_UNKNOWN],
        "no rule matched; falling back to human escalation",
    )


# The router is swappable: an LLM based router only needs to return a
# RoutingDecision.  Tools, monitoring and the API do not change.
Router = Callable[[str], RoutingDecision]
_router: Router = rule_based_router


def set_router(router: Router) -> None:
    """Replace the routing strategy (e.g. with an LLM based router)."""
    global _router
    _router = router


def get_router() -> Router:
    """Return the active routing strategy."""
    return _router


def detect_intent(query: str) -> RoutingDecision:
    """Stage 1+2: detect the intent and select the tool for ``query``."""
    decision = _router(query)
    logger.debug("mode=%s intent=%s reason=%s", AGENT_MODE, decision.intent, decision.reason)
    return decision


# ---------------------------------------------------------------------------
# 3. Tool execution
# ---------------------------------------------------------------------------
_PRICING_HELP = (
    "I can calculate a delivery cost. I need three inputs:\n"
    "  - weight in kg (for example 12.5)\n"
    "  - distance in km (for example 450)\n"
    f"  - priority: standard, express or urgent (default: {DEFAULT_PRIORITY})\n\n"
    "Formula: (base 50 + weight x 10 + distance x 0.50) x priority multiplier "
    "(standard 1.0 / express 1.5 / urgent 2.0).\n"
    "Example: 'Calculate delivery cost for 12.5 kg over 450 km express'."
)


def _execute(decision: RoutingDecision, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 3: run the selected tool and return its result."""
    params = {**decision.params, **context}

    if decision.intent == INTENT_ESCALATION:
        return escalate_issue(reason=params.get("reason") or query)

    if decision.intent == INTENT_PRICING:
        weight, distance = params.get("weight"), params.get("distance")
        if weight is None or distance is None:
            result = {
                "tool": "pricing",
                "success": True,
                "message": _PRICING_HELP,
                "data": {"needs_input": ["weight", "distance"], "provided": params},
            }
            return result
        return calculate_delivery_cost(
            weight, distance, params.get("priority", DEFAULT_PRIORITY)
        )

    if decision.intent == INTENT_DELAYED:
        return get_delayed_shipments()

    if decision.intent == INTENT_TRACKING:
        return track_shipment(params.get("shipment_id") or "")

    if decision.intent == INTENT_POLICY:
        return get_policy(params.get("topic") or query)

    # INTENT_UNKNOWN - safe fallback, the employee still gets a human.
    result = escalate_issue(
        reason=f"Copilot could not answer this query automatically: '{query}'"
    )
    result["message"] = (
        "I could not match that request to shipment tracking, pricing or a "
        "published policy, so I have handed it to a human.\n\n" + result["message"]
    )
    return result


# ---------------------------------------------------------------------------
# 4 + 5. Response generation and monitoring
# ---------------------------------------------------------------------------
def handle_query(query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Answer one employee query end to end.

    Args:
        query: The employee's natural language question.
        context: Optional pre-resolved parameters (the CLI uses this to pass
            weight/distance/priority collected interactively). Channel
            supplied context always overrides values parsed from the text.

    Returns:
        A dictionary with the query, detected intent, selected tool, success
        flag, final response text, structured data and the execution time in
        milliseconds.  The same dictionary is recorded by the monitoring
        service and returned by ``POST /api/v1/copilot/query``.
    """
    context = dict(context or {})
    started = time.perf_counter()
    error: Optional[str] = None

    if not query or not str(query).strip():
        decision = RoutingDecision(INTENT_UNKNOWN, "none", "empty query")
        elapsed_ms = (time.perf_counter() - started) * 1000
        response = "Please type a question, for example: 'Where is shipment SH1024?'"
        monitoring.record_query(
            query=str(query or ""),
            intent=decision.intent,
            tool_selected=decision.tool,
            execution_time_ms=elapsed_ms,
            success=False,
            response=response,
            error="empty query",
        )
        return _envelope(str(query or ""), decision, False, response, None, elapsed_ms, "empty query")

    decision = detect_intent(query)

    try:
        result = _execute(decision, query, context)
        success = bool(result.get("success"))
        response = str(result.get("message", ""))
        data = result.get("data")
    except ValidationError as exc:
        error = str(exc)
        success = False
        data = None
        response = f"I could not complete that request: {exc}"
        logger.warning("validation error for query=%r: %s", query, exc)
    except CopilotError as exc:  # pragma: no cover - defensive
        error = str(exc)
        success = False
        data = None
        response = f"The {decision.tool} tool could not complete this request: {exc}"
        logger.error("tool error for query=%r: %s", query, exc)
    except Exception as exc:  # pragma: no cover - never crash the copilot
        error = f"{type(exc).__name__}: {exc}"
        logger.exception("unexpected error for query=%r", query)
        fallback = escalate_issue(reason=f"Unexpected copilot error on query '{query}': {exc}")
        success = False
        data = fallback.get("data")
        response = (
            "Something went wrong while answering that request, so it has been "
            "handed to a human.\n\n" + str(fallback["message"])
        )

    elapsed_ms = (time.perf_counter() - started) * 1000
    monitoring.record_query(
        query=query,
        intent=decision.intent,
        tool_selected=decision.tool,
        execution_time_ms=elapsed_ms,
        success=success,
        response=response,
        error=error,
    )
    return _envelope(query, decision, success, response, data, elapsed_ms, error)


def _envelope(
    query: str,
    decision: RoutingDecision,
    success: bool,
    response: str,
    data: Optional[Dict[str, Any]],
    elapsed_ms: float,
    error: Optional[str],
) -> Dict[str, Any]:
    """Build the uniform response envelope returned by the agent."""
    return {
        "query": query,
        "intent": decision.intent,
        "tool_selected": decision.tool,
        "routing_reason": decision.reason,
        "success": success,
        "response": response,
        "data": data,
        "execution_time_ms": round(elapsed_ms, 3),
        "error": error,
    }
