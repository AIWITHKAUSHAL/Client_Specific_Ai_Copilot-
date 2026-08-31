"""Tests for the shipment tracking tool."""

from __future__ import annotations

import pytest

from data.shipments import SHIPMENTS
from tools.tracking import get_delayed_shipments, normalize_shipment_id, track_shipment


def test_required_assignment_shipments_exist():
    """SH1001/SH1002/SH1003/SH1024 are mandated by the assignment."""
    for shipment_id in ("SH1001", "SH1002", "SH1003", "SH1024"):
        assert shipment_id in SHIPMENTS


@pytest.mark.parametrize(
    "raw,expected",
    [("SH1024", "SH1024"), ("sh1024", "SH1024"), (" sh-1024 ", "SH1024"), ("SH 1024", "SH1024")],
)
def test_normalize_shipment_id(raw, expected):
    assert normalize_shipment_id(raw) == expected


def test_track_shipment_found():
    result = track_shipment("SH1024")
    assert result["success"] is True
    assert result["tool"] == "tracking"
    assert result["data"]["shipment"]["status"] == "In Transit"
    assert "SH1024" in result["message"]
    assert "Pune" in result["message"] and "Jaipur" in result["message"]


def test_track_shipment_is_case_and_format_insensitive():
    assert track_shipment("sh-1024")["data"]["shipment"]["shipment_id"] == "SH1024"


def test_track_shipment_delivered_status():
    result = track_shipment("SH1001")
    assert result["data"]["shipment"]["status"] == "Delivered"


def test_track_shipment_not_found_is_handled_cleanly():
    result = track_shipment("SH9999")
    assert result["success"] is False
    assert "not found" in result["message"].lower()
    assert result["data"]["found"] is False


def test_track_shipment_missing_id_is_handled_cleanly():
    result = track_shipment("")
    assert result["success"] is False
    assert "shipment id" in result["message"].lower()


def test_track_shipment_does_not_mutate_source_data():
    result = track_shipment("SH1024")
    result["data"]["shipment"]["status"] = "TAMPERED"
    assert SHIPMENTS["SH1024"]["status"] == "In Transit"


def test_get_delayed_shipments_returns_only_delayed():
    result = get_delayed_shipments()
    assert result["success"] is True
    assert result["data"]["count"] >= 1
    ids = [s["shipment_id"] for s in result["data"]["shipments"]]
    assert "SH1003" in ids
    assert all(s["status"] == "Delayed" for s in result["data"]["shipments"])
    assert "SH1001" not in ids  # delivered shipments must not appear
