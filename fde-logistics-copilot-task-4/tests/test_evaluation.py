"""Agent evaluation harness.

Runs the 34-query evaluation set through the agent and asserts routing
accuracy, answer content and the safety property that nothing is ever
guessed.  This is the regression gate: a routing change that helps one
phrasing and breaks another shows up here, in CI, before the client sees it.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from agent import handle_query
from tests.evaluation_dataset import EVALUATION_SET

REQUIRED_PHRASE = "Escalated to Operations Team"


def _run(case: Dict[str, Any]) -> Dict[str, Any]:
    return handle_query(case["query"])


@pytest.mark.parametrize("case", EVALUATION_SET, ids=lambda c: c["query"])
def test_evaluation_case(case):
    """Each evaluation query routes to the expected tool and answers correctly."""
    result = _run(case)
    assert result["intent"] == case["expected_intent"], result["routing_reason"]
    assert result["tool_selected"] == case["expected_tool"]
    assert result["success"] is case["expected_success"]
    if case.get("must_contain"):
        assert case["must_contain"].lower() in result["response"].lower()


def test_overall_routing_accuracy_is_100_percent():
    """Routing accuracy over the whole evaluation set."""
    results: List[bool] = [
        _run(case)["tool_selected"] == case["expected_tool"] for case in EVALUATION_SET
    ]
    accuracy = sum(results) / len(results)
    assert accuracy == 1.0, f"routing accuracy dropped to {accuracy:.2%}"


def test_no_query_is_ever_left_unanswered():
    """Every query produces a response; unmatched ones hand over to a human."""
    for case in EVALUATION_SET:
        result = _run(case)
        assert result["response"].strip()
        if result["intent"] == "unknown":
            assert REQUIRED_PHRASE in result["response"]


def test_evaluation_set_covers_every_intent():
    intents = {case["expected_intent"] for case in EVALUATION_SET}
    assert intents == {
        "shipment_tracking",
        "delayed_shipments",
        "cost_calculation",
        "policy_lookup",
        "escalation",
        "unknown",
    }
