"""Operational policy knowledge base for the prototype.

Production replacement
----------------------
The prototype stores seven curated policies as structured records and looks
them up with deterministic keyword matching.  That is intentional: it is
auditable, instant, free and needs no model.

The production path keeps the same ``get_policy_record`` seam:

    policy PDFs / Confluence / SharePoint
        -> chunking
        -> embeddings
        -> vector database (pgvector, OpenSearch, Pinecone, ...)
        -> retrieval
        -> LLM answer grounded in the retrieved chunks + citation

See docs/HLD.md ("Policy / RAG service") for the target design.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Each record carries the keywords that route a natural-language question to
# it.  Keywords live next to the policy so adding a policy never requires
# editing the tool implementation.
POLICIES: Dict[str, Dict[str, object]] = {
    "delivery": {
        "name": "delivery",
        "title": "Standard Delivery Policy",
        "summary": (
            "Standard deliveries are completed within 3-5 business days for "
            "domestic lanes and 7-10 business days for cross-border lanes. "
            "Delivery is attempted twice; after a second failed attempt the "
            "shipment is returned to the origin hub and the shipper is billed "
            "the return leg."
        ),
        "keywords": [
            "delivery",
            "deliver",
            "delivery time",
            "delivery timeline",
            "standard delivery",
            "sla",
            "attempt",
        ],
        "owner": "Operations",
        "last_updated": "2026-06-01",
        "source_document": "OPS-POL-001 Standard Delivery Policy v4",
    },
    "delayed_shipment": {
        "name": "delayed_shipment",
        "title": "Delayed Shipment Policy",
        "summary": (
            "A shipment is flagged Delayed when it passes its estimated "
            "delivery date without a delivery scan. Operations must add a "
            "delay reason within 4 hours, notify the customer within 24 "
            "hours, and offer a revised ETA. Delays beyond 72 hours are "
            "escalated to the Operations Supervisor automatically."
        ),
        "keywords": [
            "delayed",
            "delay",
            "late",
            "behind schedule",
            "missed eta",
            "overdue",
        ],
        "owner": "Operations",
        "last_updated": "2026-06-01",
        "source_document": "OPS-POL-002 Delay Management Policy v3",
    },
    "damaged_shipment": {
        "name": "damaged_shipment",
        "title": "Damaged Shipment Policy",
        "summary": (
            "Damage must be reported within 48 hours of delivery with photo "
            "evidence and the packing list. Claims are assessed within 7 "
            "business days. Approved claims are settled at declared value up "
            "to the insured limit; uninsured shipments are capped at USD 100 "
            "per consignment."
        ),
        "keywords": [
            "damaged",
            "damage",
            "broken",
            "defective",
            "claim",
            "photo evidence",
        ],
        "owner": "Claims",
        "last_updated": "2026-05-18",
        "source_document": "OPS-POL-003 Damage & Claims Policy v2",
    },
    "refund": {
        "name": "refund",
        "title": "Refund Policy",
        "summary": (
            "Refunds are issued for service failures such as a missed "
            "guaranteed delivery window, a lost consignment, or a duplicate "
            "charge. Requests must be raised within 30 days of the invoice "
            "date and are credited to the original payment method within 7-10 "
            "business days after approval. Fuel surcharge is non-refundable."
        ),
        "keywords": ["refund", "money back", "reimbursement", "credit note", "chargeback"],
        "owner": "Finance",
        "last_updated": "2026-04-22",
        "source_document": "FIN-POL-011 Refund Policy v5",
    },
    "cancellation": {
        "name": "cancellation",
        "title": "Cancellation Policy",
        "summary": (
            "A booking can be cancelled free of charge before the first pickup "
            "scan. After pickup but before line-haul departure a 25% "
            "cancellation fee applies. Once a shipment has departed the origin "
            "hub it cannot be cancelled and must be processed as a return."
        ),
        "keywords": ["cancel", "cancellation", "cancelled", "call off booking", "void booking"],
        "owner": "Operations",
        "last_updated": "2026-04-22",
        "source_document": "OPS-POL-004 Booking Cancellation Policy v2",
    },
    "insurance": {
        "name": "insurance",
        "title": "Shipment Insurance Policy",
        "summary": (
            "Optional transit insurance covers declared value up to USD "
            "50,000 per consignment at a premium of 0.5% of declared value. "
            "It must be purchased at booking time and cannot be added after "
            "pickup. High-value electronics and fragile goods require "
            "insurance before the booking is accepted."
        ),
        "keywords": ["insurance", "insure", "insured", "coverage", "declared value", "premium"],
        "owner": "Finance",
        "last_updated": "2026-03-30",
        "source_document": "FIN-POL-014 Transit Insurance Policy v3",
    },
    "priority_shipping": {
        "name": "priority_shipping",
        "title": "Priority Shipping Policy",
        "summary": (
            "Express shipments are billed at 1.5x the standard rate and "
            "target next-business-day delivery on serviceable domestic lanes. "
            "Urgent shipments are billed at 2.0x, are hand-carried where "
            "possible and are guaranteed same-day dispatch when booked before "
            "14:00 local time. Priority upgrades require Supervisor approval."
        ),
        "keywords": [
            "priority",
            "express",
            "urgent",
            "expedite",
            "expedited",
            "same day",
            "next day",
            "rush",
        ],
        "owner": "Operations",
        "last_updated": "2026-06-01",
        "source_document": "OPS-POL-005 Priority Service Policy v2",
    },
}


def get_policy_record(name: str) -> Optional[Dict[str, object]]:
    """Return a copy of one policy record by its canonical name."""
    record = POLICIES.get(name.strip().lower().replace(" ", "_").replace("-", "_"))
    return dict(record) if record else None


def get_all_policies() -> List[Dict[str, object]]:
    """Return copies of every policy record."""
    return [dict(record) for record in POLICIES.values()]


def list_policy_names() -> List[str]:
    """Return the canonical names of the available policies."""
    return list(POLICIES.keys())
