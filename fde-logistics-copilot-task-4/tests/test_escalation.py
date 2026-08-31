"""Tests for the escalation tool.

The exact phrase 'Escalated to Operations Team' is a hard assignment
requirement and is asserted in several ways on purpose.
"""

from __future__ import annotations

from core.config import ESCALATION_PHRASE
from tools.escalation import escalate_issue, list_escalations

REQUIRED_PHRASE = "Escalated to Operations Team"


def test_config_phrase_matches_the_assignment():
    assert ESCALATION_PHRASE == REQUIRED_PHRASE


def test_escalation_contains_the_required_phrase():
    assert REQUIRED_PHRASE in escalate_issue("Customer is unhappy")["message"]


def test_escalation_without_a_reason_still_contains_the_phrase():
    result = escalate_issue()
    assert REQUIRED_PHRASE in result["message"]
    assert result["success"] is True


def test_escalation_creates_a_local_reference():
    result = escalate_issue("Damaged pallet on SH1003")
    assert result["data"]["ticket_id"].startswith("ESC-")
    assert result["data"]["status"] == "open"
    assert result["data"]["reason"] == "Damaged pallet on SH1003"


def test_escalation_references_increment():
    first = escalate_issue("one")["data"]["ticket_id"]
    second = escalate_issue("two")["data"]["ticket_id"]
    assert first == "ESC-0001"
    assert second == "ESC-0002"


def test_escalations_are_recorded():
    escalate_issue("first issue")
    escalate_issue("second issue")
    tickets = list_escalations()
    assert len(tickets) == 2
    assert tickets[0]["reason"] == "first issue"


def test_blank_reason_is_normalised():
    assert "No reason provided" in escalate_issue("   ")["message"]
