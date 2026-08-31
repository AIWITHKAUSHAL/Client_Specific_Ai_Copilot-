"""In-memory shipment dataset for the prototype.

Production replacement
----------------------
This module is deliberately thin: it exposes *functions* rather than the raw
dictionary, so the storage mechanism can change without touching the tools.

    prototype : dict in this module
    production: TrackingAdapter -> client TMS/WMS/ERP REST API or Postgres

``tools/tracking.py`` only depends on :func:`get_shipment_record` and
:func:`get_all_shipments`; re-implementing those two functions against a
client system is the whole integration effort for shipment tracking.
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Status vocabulary used by the prototype.  Client systems usually have a
# richer set of codes that an adapter maps onto these canonical values.
STATUS_DELIVERED = "Delivered"
STATUS_IN_TRANSIT = "In Transit"
STATUS_DELAYED = "Delayed"
STATUS_OUT_FOR_DELIVERY = "Out for Delivery"

# NOTE: SH1001, SH1002, SH1003 and SH1024 are required by the assignment and
# must not be removed or renamed.
SHIPMENTS: Dict[str, Dict[str, object]] = {
    "SH1001": {
        "shipment_id": "SH1001",
        "status": STATUS_DELIVERED,
        "origin": "Mumbai, IN",
        "destination": "Pune, IN",
        "estimated_delivery": "2026-08-24",
        "delivered_on": "2026-08-24",
        "carrier": "BlueDart Surface",
        "weight_kg": 12.5,
        "service_level": "standard",
        "last_scan": "Delivered to consignee - Pune hub",
    },
    "SH1002": {
        "shipment_id": "SH1002",
        "status": STATUS_IN_TRANSIT,
        "origin": "Delhi, IN",
        "destination": "Bengaluru, IN",
        "estimated_delivery": "2026-09-02",
        "delivered_on": None,
        "carrier": "Gati Air",
        "weight_kg": 4.0,
        "service_level": "express",
        "last_scan": "Departed Delhi sorting facility",
    },
    "SH1003": {
        "shipment_id": "SH1003",
        "status": STATUS_DELAYED,
        "origin": "Chennai, IN",
        "destination": "Hyderabad, IN",
        "estimated_delivery": "2026-08-29",
        "delivered_on": None,
        "carrier": "Safexpress Surface",
        "weight_kg": 88.0,
        "service_level": "standard",
        "last_scan": "Held at Chennai hub - vehicle breakdown",
        "delay_reason": "Vehicle breakdown at Chennai hub",
    },
    "SH1004": {
        "shipment_id": "SH1004",
        "status": STATUS_DELAYED,
        "origin": "Kolkata, IN",
        "destination": "Guwahati, IN",
        "estimated_delivery": "2026-08-30",
        "delivered_on": None,
        "carrier": "Delhivery Surface",
        "weight_kg": 32.0,
        "service_level": "standard",
        "last_scan": "Route blocked - regional weather advisory",
        "delay_reason": "Weather advisory on NH-27",
    },
    "SH1005": {
        "shipment_id": "SH1005",
        "status": STATUS_OUT_FOR_DELIVERY,
        "origin": "Ahmedabad, IN",
        "destination": "Surat, IN",
        "estimated_delivery": "2026-08-31",
        "delivered_on": None,
        "carrier": "BlueDart Surface",
        "weight_kg": 2.2,
        "service_level": "express",
        "last_scan": "Out for delivery - Surat local hub",
    },
    "SH1024": {
        "shipment_id": "SH1024",
        "status": STATUS_IN_TRANSIT,
        "origin": "Pune, IN",
        "destination": "Jaipur, IN",
        "estimated_delivery": "2026-09-03",
        "delivered_on": None,
        "carrier": "VRL Surface",
        "weight_kg": 18.75,
        "service_level": "standard",
        "last_scan": "In transit - Ahmedabad transit hub",
    },
}


def get_shipment_record(shipment_id: str) -> Optional[Dict[str, object]]:
    """Return a copy of one shipment record, or ``None`` when unknown.

    A copy is returned so callers cannot mutate the prototype dataset - the
    same guarantee a real API client would give.
    """
    record = SHIPMENTS.get(shipment_id)
    return dict(record) if record else None


def get_all_shipments() -> List[Dict[str, object]]:
    """Return copies of every shipment record known to the prototype."""
    return [dict(record) for record in SHIPMENTS.values()]


def get_shipments_by_status(status: str) -> List[Dict[str, object]]:
    """Return every shipment whose status matches ``status`` (case-insensitive)."""
    wanted = status.strip().lower()
    return [
        dict(record)
        for record in SHIPMENTS.values()
        if str(record["status"]).lower() == wanted
    ]
