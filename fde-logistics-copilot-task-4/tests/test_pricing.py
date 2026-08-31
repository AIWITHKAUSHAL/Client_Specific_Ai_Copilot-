"""Tests for the delivery cost calculator tool."""

from __future__ import annotations

import pytest

from core.exceptions import ValidationError
from tools.pricing import calculate_delivery_cost, normalize_priority


def test_standard_pricing_matches_the_documented_formula():
    # (50 + 10*10 + 100*0.50) * 1.0 = 200
    result = calculate_delivery_cost(10, 100)
    assert result["success"] is True
    assert result["data"]["total_cost"] == 200.0
    assert result["data"]["priority"] == "standard"


def test_express_pricing_applies_1_5_multiplier():
    # (50 + 100 + 50) * 1.5 = 300
    assert calculate_delivery_cost(10, 100, "express")["data"]["total_cost"] == 300.0


def test_urgent_pricing_applies_2_0_multiplier():
    # (50 + 100 + 50) * 2.0 = 400
    assert calculate_delivery_cost(10, 100, "urgent")["data"]["total_cost"] == 400.0


def test_breakdown_is_fully_itemised():
    data = calculate_delivery_cost(12.5, 450, "express")["data"]
    assert data["base_charge"] == 50.0
    assert data["weight_charge"] == 125.0
    assert data["distance_charge"] == 225.0
    assert data["subtotal"] == 400.0
    assert data["total_cost"] == 600.0


def test_priority_is_case_insensitive():
    assert calculate_delivery_cost(1, 1, "EXPRESS")["data"]["priority"] == "express"


def test_numeric_strings_from_the_cli_are_accepted():
    assert calculate_delivery_cost("10", "100", "standard")["data"]["total_cost"] == 200.0


@pytest.mark.parametrize("weight", [0, -5, "abc", None])
def test_invalid_weight_is_rejected(weight):
    with pytest.raises(ValidationError):
        calculate_delivery_cost(weight, 100)


@pytest.mark.parametrize("distance", [0, -1, "xyz", None])
def test_invalid_distance_is_rejected(distance):
    with pytest.raises(ValidationError):
        calculate_delivery_cost(10, distance)


def test_invalid_priority_is_rejected():
    with pytest.raises(ValidationError) as exc:
        calculate_delivery_cost(10, 100, "overnight")
    assert "standard" in str(exc.value)


def test_validation_error_is_also_a_value_error():
    with pytest.raises(ValueError):
        calculate_delivery_cost(-1, 100)


def test_absurd_values_are_rejected_by_guard_rails():
    with pytest.raises(ValidationError):
        calculate_delivery_cost(999_999, 100)


def test_normalize_priority_defaults_to_standard():
    assert normalize_priority("") == "standard"
