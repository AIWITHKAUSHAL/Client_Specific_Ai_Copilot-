"""Tests for the policy lookup tool."""

from __future__ import annotations

import pytest

from data.policies import POLICIES
from tools.policy import available_policies, find_policy, get_policy


def test_at_least_five_policies_are_published():
    """The assignment requires a minimum of five policies."""
    assert len(POLICIES) >= 5


@pytest.mark.parametrize(
    "name",
    ["delivery", "delayed_shipment", "damaged_shipment", "refund", "cancellation",
     "insurance", "priority_shipping"],
)
def test_every_policy_is_retrievable_by_name(name):
    result = get_policy(name)
    assert result["success"] is True
    assert result["data"]["policy"]["name"] == name


@pytest.mark.parametrize(
    "query,expected",
    [
        ("What is our delivery policy?", "delivery"),
        ("What happens when a shipment is delayed?", "delayed_shipment"),
        ("The parcel arrived damaged, what do we do?", "damaged_shipment"),
        ("How do refunds work?", "refund"),
        ("Can the customer cancel this booking?", "cancellation"),
        ("Do we offer insurance on high value goods?", "insurance"),
        ("What does express shipping cost the customer in time?", "priority_shipping"),
    ],
)
def test_natural_language_policy_routing(query, expected):
    assert find_policy(query)["name"] == expected


def test_policy_answer_includes_source_and_owner():
    message = get_policy("refund")["message"]
    assert "Refund Policy" in message
    assert "Source:" in message and "Owner:" in message


def test_unknown_policy_returns_the_available_list():
    result = get_policy("what is the weather in Paris")
    assert result["success"] is False
    assert result["data"]["matched"] is False
    assert "Standard Delivery Policy" in result["message"]


def test_empty_query_is_handled():
    assert get_policy("")["success"] is False


def test_available_policies_lists_titles():
    titles = available_policies()
    assert len(titles) >= 5
    assert "Refund Policy" in titles
