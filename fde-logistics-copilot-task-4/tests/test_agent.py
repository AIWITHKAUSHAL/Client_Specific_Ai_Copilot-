"""Tests for the agent: routing, execution, monitoring and fallbacks."""

from __future__ import annotations

import pytest

from agent import (
    INTENT_DELAYED,
    INTENT_ESCALATION,
    INTENT_POLICY,
    INTENT_PRICING,
    INTENT_TRACKING,
    INTENT_UNKNOWN,
    RoutingDecision,
    extract_pricing_params,
    extract_shipment_id,
    handle_query,
    rule_based_router,
    set_router,
)
from monitoring.metrics import metrics

REQUIRED_PHRASE = "Escalated to Operations Team"


# ---------------------------------------------------------------------------
# The five mandatory demo queries
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "query,intent,tool",
    [
        ("Where is shipment SH1024?", INTENT_TRACKING, "tracking"),
        ("Which shipments are delayed?", INTENT_DELAYED, "tracking"),
        ("What is our delivery policy?", INTENT_POLICY, "policy"),
        ("Calculate delivery cost.", INTENT_PRICING, "pricing"),
        ("Escalate this issue.", INTENT_ESCALATION, "escalation"),
    ],
)
def test_mandatory_demo_queries_route_correctly(query, intent, tool):
    result = handle_query(query)
    assert result["intent"] == intent
    assert result["tool_selected"] == tool


def test_tracking_query_returns_shipment_details():
    result = handle_query("Where is shipment SH1024?")
    assert result["success"] is True
    assert "SH1024" in result["response"]
    assert "In Transit" in result["response"]


def test_delayed_query_includes_sh1003():
    result = handle_query("Which shipments are delayed?")
    assert result["success"] is True
    assert "SH1003" in result["response"]


def test_policy_query_returns_the_delivery_policy():
    assert "Standard Delivery Policy" in handle_query("What is our delivery policy?")["response"]


def test_pricing_query_without_numbers_asks_for_inputs():
    result = handle_query("Calculate delivery cost.")
    assert result["data"]["needs_input"] == ["weight", "distance"]
    assert "weight" in result["response"].lower()


def test_pricing_query_with_numbers_calculates_immediately():
    result = handle_query("Calculate delivery cost for 10 kg over 100 km express")
    assert result["success"] is True
    assert result["data"]["total_cost"] == 300.0


def test_pricing_context_from_the_cli_is_used():
    result = handle_query(
        "Calculate delivery cost.",
        context={"weight": 10, "distance": 100, "priority": "urgent"},
    )
    assert result["data"]["total_cost"] == 400.0


def test_escalation_response_contains_the_required_phrase():
    assert REQUIRED_PHRASE in handle_query("Escalate this issue.")["response"]


# ---------------------------------------------------------------------------
# Fallback and edge cases
# ---------------------------------------------------------------------------
def test_unknown_query_falls_back_to_escalation():
    result = handle_query("What is the capital of France?")
    assert result["intent"] == INTENT_UNKNOWN
    assert result["tool_selected"] == "escalation"
    assert REQUIRED_PHRASE in result["response"]


def test_empty_query_is_handled_without_crashing():
    result = handle_query("")
    assert result["success"] is False
    assert result["intent"] == INTENT_UNKNOWN


def test_unknown_shipment_id_reports_failure():
    result = handle_query("Where is shipment SH8888?")
    assert result["intent"] == INTENT_TRACKING
    assert result["success"] is False


def test_invalid_pricing_input_is_reported_not_raised():
    result = handle_query("Calculate delivery cost.", context={"weight": -5, "distance": 100})
    assert result["success"] is False
    assert "greater than 0" in result["response"]


def test_specific_shipment_id_wins_over_the_delayed_list():
    """'Is SH1003 delayed?' is about one shipment, not the whole delayed list."""
    result = handle_query("Is SH1003 delayed?")
    assert result["intent"] == INTENT_TRACKING
    assert "SH1003" in result["response"]


def test_policy_question_about_pricing_is_not_a_quote():
    result = handle_query("What is our priority shipping cost policy?")
    assert result["intent"] == INTENT_POLICY


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "query,expected",
    [
        ("Where is shipment SH1024?", "SH1024"),
        ("track sh-1003 please", "SH1003"),
        ("status of shipment id: SH 1002", "SH1002"),
        ("Which shipments are delayed?", None),
    ],
)
def test_extract_shipment_id(query, expected):
    assert extract_shipment_id(query) == expected


def test_extract_pricing_params():
    params = extract_pricing_params("cost for 12.5 kg over 450 km urgent")
    assert params == {"weight": 12.5, "distance": 450.0, "priority": "urgent"}


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
def test_every_query_is_monitored_with_the_required_fields():
    handle_query("Where is shipment SH1024?")
    record = metrics.recent(1)[0]
    for field in ("timestamp", "query", "tool_selected", "execution_time_ms", "success", "response"):
        assert field in record
    assert record["tool_selected"] == "tracking"
    assert record["execution_time_ms"] >= 0


def test_metrics_aggregate_successes_and_failures():
    handle_query("Where is shipment SH1024?")
    handle_query("Where is shipment SH8888?")
    snapshot = metrics.snapshot()
    assert snapshot["total_queries"] == 2
    assert snapshot["successful"] == 1
    assert snapshot["failed"] == 1
    assert snapshot["queries_by_tool"]["tracking"] == 2


# ---------------------------------------------------------------------------
# Pluggable router (the seam an LLM router would use)
# ---------------------------------------------------------------------------
def test_router_can_be_replaced():
    def always_escalate(query: str) -> RoutingDecision:
        return RoutingDecision(INTENT_ESCALATION, "escalation", "stub router")

    set_router(always_escalate)
    try:
        result = handle_query("Where is shipment SH1024?")
        assert result["tool_selected"] == "escalation"
        assert REQUIRED_PHRASE in result["response"]
    finally:
        set_router(rule_based_router)

    assert handle_query("Where is shipment SH1024?")["tool_selected"] == "tracking"
