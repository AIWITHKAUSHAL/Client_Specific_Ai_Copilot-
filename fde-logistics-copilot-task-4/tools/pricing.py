"""Delivery cost calculator tool.

Prototype formula (transparent and fully auditable)::

    base charge     = 50
    weight charge   = weight_kg   * 10
    distance charge = distance_km * 0.50

    total = (base + weight charge + distance charge) * priority multiplier

    standard = 1.0   express = 1.5   urgent = 2.0

Every number lives in :mod:`core.config` rather than inline, so a client
rate card change is a configuration change.

Production note
---------------
Real logistics pricing depends on lane, fuel surcharge, volumetric weight,
customer contract, taxes and accessorials.  In production this tool becomes
a thin client of the customer's pricing engine / rate-card API and keeps the
same signature, so the agent and tests do not change.
"""

from __future__ import annotations

import math

from core.config import (
    BASE_CHARGE,
    CURRENCY,
    DEFAULT_PRIORITY,
    DISTANCE_RATE_PER_KM,
    MAX_DISTANCE_KM,
    MAX_WEIGHT_KG,
    PRIORITY_MULTIPLIERS,
    WEIGHT_RATE_PER_KG,
)
from core.exceptions import ValidationError
from tools.base import ToolResult, tool_result

TOOL_NAME = "pricing"

Number = int | float | str


def _coerce_positive(value: Number, field: str, maximum: float) -> float:
    """Validate that ``value`` is a positive number within ``maximum``."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number, got: {value!r}") from None

    if not math.isfinite(number):
        raise ValidationError(f"{field} must be a finite number, got: {value!r}")
    if number <= 0:
        raise ValidationError(f"{field} must be greater than 0, got: {number}")
    if number > maximum:
        raise ValidationError(f"{field} must not exceed {maximum:g}, got: {number}")
    return number


def normalize_priority(priority: str) -> str:
    """Validate and canonicalise a priority level."""
    candidate = (priority or DEFAULT_PRIORITY).strip().lower()
    if candidate not in PRIORITY_MULTIPLIERS:
        allowed = ", ".join(sorted(PRIORITY_MULTIPLIERS))
        raise ValidationError(
            f"priority must be one of: {allowed}. Got: {priority!r}"
        )
    return candidate


def calculate_delivery_cost(
    weight: Number,
    distance: Number,
    priority: str = DEFAULT_PRIORITY,
) -> ToolResult:
    """Calculate the delivery cost for a shipment.

    Args:
        weight: Chargeable weight in kilograms (> 0).
        distance: Lane distance in kilometres (> 0).
        priority: One of ``standard``, ``express`` or ``urgent``.

    Returns:
        A tool result whose ``data`` holds the full cost breakdown, so the
        answer can be audited line by line rather than trusted blindly.

    Raises:
        ValidationError: If weight, distance or priority is invalid.  It also
            subclasses :class:`ValueError`.
    """
    weight_kg = _coerce_positive(weight, "weight", MAX_WEIGHT_KG)
    distance_km = _coerce_positive(distance, "distance", MAX_DISTANCE_KM)
    level = normalize_priority(priority)
    multiplier = PRIORITY_MULTIPLIERS[level]

    weight_charge = round(weight_kg * WEIGHT_RATE_PER_KG, 2)
    distance_charge = round(distance_km * DISTANCE_RATE_PER_KM, 2)
    subtotal = round(BASE_CHARGE + weight_charge + distance_charge, 2)
    total = round(subtotal * multiplier, 2)

    breakdown = {
        "weight_kg": weight_kg,
        "distance_km": distance_km,
        "priority": level,
        "base_charge": BASE_CHARGE,
        "weight_charge": weight_charge,
        "distance_charge": distance_charge,
        "subtotal": subtotal,
        "priority_multiplier": multiplier,
        "total_cost": total,
        "currency": CURRENCY,
    }

    message = (
        f"Delivery cost estimate ({level}):\n"
        f"  Base charge       : {CURRENCY} {BASE_CHARGE:.2f}\n"
        f"  Weight charge     : {CURRENCY} {weight_charge:.2f} "
        f"({weight_kg:g} kg x {WEIGHT_RATE_PER_KG:g})\n"
        f"  Distance charge   : {CURRENCY} {distance_charge:.2f} "
        f"({distance_km:g} km x {DISTANCE_RATE_PER_KM:g})\n"
        f"  Subtotal          : {CURRENCY} {subtotal:.2f}\n"
        f"  Priority multiplier: x{multiplier:g} ({level})\n"
        f"  TOTAL             : {CURRENCY} {total:.2f}"
    )
    return tool_result(TOOL_NAME, True, message, breakdown)
