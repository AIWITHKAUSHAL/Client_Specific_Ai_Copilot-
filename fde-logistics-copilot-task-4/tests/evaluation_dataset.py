"""Deterministic evaluation set for the copilot agent.

34 realistic operations questions with the tool that *should* answer each
one.  The set is the regression gate for routing behaviour: it runs in CI
(``tests/test_evaluation.py``) and is the template a client extends with
their own phrasing during deployment (see client-customization.md).

Fields
------
query            : what an employee types
expected_intent  : the intent the router must detect
expected_tool    : the tool that must be selected
expected_success : whether the copilot should be able to answer it
must_contain     : substring the response must contain (optional)
category         : grouping used in the evaluation report
"""

from __future__ import annotations

from typing import Any, Dict, List

EVALUATION_SET: List[Dict[str, Any]] = [
    # --- shipment tracking ------------------------------------------------
    {"query": "Where is shipment SH1024?", "expected_intent": "shipment_tracking",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "SH1024",
     "category": "tracking"},
    {"query": "Track SH1002", "expected_intent": "shipment_tracking",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "Bengaluru",
     "category": "tracking"},
    {"query": "What is the status of shipment SH1001?", "expected_intent": "shipment_tracking",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "Delivered",
     "category": "tracking"},
    {"query": "Locate sh-1005 please", "expected_intent": "shipment_tracking",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "SH1005",
     "category": "tracking"},
    {"query": "eta for SH1024", "expected_intent": "shipment_tracking",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "2026-09-03",
     "category": "tracking"},
    {"query": "status of shipment id: SH 1002", "expected_intent": "shipment_tracking",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "SH1002",
     "category": "tracking"},
    {"query": "Is SH1003 delayed?", "expected_intent": "shipment_tracking",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "Delayed",
     "category": "tracking"},
    {"query": "Where is shipment SH9999?", "expected_intent": "shipment_tracking",
     "expected_tool": "tracking", "expected_success": False, "must_contain": "not found",
     "category": "tracking (unknown id)"},

    # --- delayed shipments ------------------------------------------------
    {"query": "Which shipments are delayed?", "expected_intent": "delayed_shipments",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "SH1003",
     "category": "delayed"},
    {"query": "Show me all late shipments", "expected_intent": "delayed_shipments",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "delayed shipment",
     "category": "delayed"},
    {"query": "Are any consignments behind schedule?", "expected_intent": "delayed_shipments",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "SH1004",
     "category": "delayed"},
    {"query": "list overdue deliveries", "expected_intent": "delayed_shipments",
     "expected_tool": "tracking", "expected_success": True, "must_contain": "Delayed",
     "category": "delayed"},

    # --- cost calculation -------------------------------------------------
    {"query": "Calculate delivery cost.", "expected_intent": "cost_calculation",
     "expected_tool": "pricing", "expected_success": True, "must_contain": "weight",
     "category": "pricing (needs input)"},
    {"query": "How much to ship 20 kg over 300 km?", "expected_intent": "cost_calculation",
     "expected_tool": "pricing", "expected_success": True, "must_contain": "400.00",
     "category": "pricing"},
    {"query": "What is the price for an urgent 5 kg shipment over 120 km?",
     "expected_intent": "cost_calculation", "expected_tool": "pricing",
     "expected_success": True, "must_contain": "320.00", "category": "pricing"},
    {"query": "quote for express delivery of 10 kg over 200 km",
     "expected_intent": "cost_calculation", "expected_tool": "pricing",
     "expected_success": True, "must_contain": "375.00", "category": "pricing"},
    {"query": "What does it cost to send 2.5 kg 45 km?", "expected_intent": "cost_calculation",
     "expected_tool": "pricing", "expected_success": True, "must_contain": "97.50",
     "category": "pricing"},
    {"query": "rate for an urgent shipment", "expected_intent": "cost_calculation",
     "expected_tool": "pricing", "expected_success": True, "must_contain": "distance",
     "category": "pricing (needs input)"},

    # --- policy lookup ----------------------------------------------------
    {"query": "What is our delivery policy?", "expected_intent": "policy_lookup",
     "expected_tool": "policy", "expected_success": True, "must_contain": "Standard Delivery Policy",
     "category": "policy"},
    {"query": "What is the refund policy?", "expected_intent": "policy_lookup",
     "expected_tool": "policy", "expected_success": True, "must_contain": "Refund Policy",
     "category": "policy"},
    {"query": "Tell me about the cancellation policy", "expected_intent": "policy_lookup",
     "expected_tool": "policy", "expected_success": True, "must_contain": "Cancellation Policy",
     "category": "policy"},
    {"query": "Do we insure high value shipments?", "expected_intent": "policy_lookup",
     "expected_tool": "policy", "expected_success": True, "must_contain": "Insurance",
     "category": "policy"},
    {"query": "What happens if a parcel is damaged in transit?", "expected_intent": "policy_lookup",
     "expected_tool": "policy", "expected_success": True, "must_contain": "Damaged Shipment Policy",
     "category": "policy"},
    {"query": "How long does standard delivery take?", "expected_intent": "policy_lookup",
     "expected_tool": "policy", "expected_success": True, "must_contain": "business days",
     "category": "policy"},
    {"query": "What is our priority shipping cost policy?", "expected_intent": "policy_lookup",
     "expected_tool": "policy", "expected_success": True, "must_contain": "Priority Shipping Policy",
     "category": "policy (pricing wording)"},
    {"query": "What is the delayed shipment policy?", "expected_intent": "policy_lookup",
     "expected_tool": "policy", "expected_success": True, "must_contain": "Delayed Shipment Policy",
     "category": "policy (delay wording)"},
    {"query": "Which rules apply to booking cancellations?", "expected_intent": "policy_lookup",
     "expected_tool": "policy", "expected_success": True, "must_contain": "Cancellation Policy",
     "category": "policy"},

    # --- escalation -------------------------------------------------------
    {"query": "Escalate this issue.", "expected_intent": "escalation",
     "expected_tool": "escalation", "expected_success": True,
     "must_contain": "Escalated to Operations Team", "category": "escalation"},
    {"query": "I need to speak to a human about SH1003", "expected_intent": "escalation",
     "expected_tool": "escalation", "expected_success": True,
     "must_contain": "Escalated to Operations Team", "category": "escalation"},
    {"query": "Please raise a ticket for this customer complaint",
     "expected_intent": "escalation", "expected_tool": "escalation", "expected_success": True,
     "must_contain": "Escalated to Operations Team", "category": "escalation"},
    {"query": "Can I get a supervisor to review this refund?", "expected_intent": "escalation",
     "expected_tool": "escalation", "expected_success": True,
     "must_contain": "Escalated to Operations Team", "category": "escalation"},

    # --- unknown -> safe fallback ----------------------------------------
    {"query": "What is the capital of France?", "expected_intent": "unknown",
     "expected_tool": "escalation", "expected_success": True,
     "must_contain": "Escalated to Operations Team", "category": "unknown fallback"},
    {"query": "Book me a flight to Paris", "expected_intent": "unknown",
     "expected_tool": "escalation", "expected_success": True,
     "must_contain": "Escalated to Operations Team", "category": "unknown fallback"},
    {"query": "Reset my email password", "expected_intent": "unknown",
     "expected_tool": "escalation", "expected_success": True,
     "must_contain": "Escalated to Operations Team", "category": "unknown fallback"},
]
