"""API schemas.

Pydantic models are the API contract: they validate every inbound payload
at the edge (rejecting bad input with HTTP 422 before it reaches business
logic) and document every response in the generated OpenAPI spec.

These schemas are only used by the optional FastAPI layer - the CLI
prototype has no Pydantic dependency.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.config import MAX_QUERY_LENGTH

Priority = Literal["standard", "express", "urgent"]


# ---------------------------------------------------------------------------
# Copilot query
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    """Natural language question from an employee."""

    model_config = ConfigDict(json_schema_extra={
        "example": {"query": "Where is shipment SH1024?"}
    })

    query: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUERY_LENGTH,
        description="The employee's question in plain English.",
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional pre-resolved parameters, e.g. {'weight': 10, 'distance': 100}.",
    )


class QueryResponse(BaseModel):
    """Uniform copilot answer envelope."""

    query: str
    intent: str = Field(description="Detected intent, e.g. 'shipment_tracking'.")
    tool_selected: str = Field(description="Tool that produced the answer.")
    routing_reason: Optional[str] = Field(
        default=None, description="Why the router chose this tool (explainability)."
    )
    success: bool
    response: str
    data: Optional[Dict[str, Any]] = None
    execution_time_ms: float


# ---------------------------------------------------------------------------
# Shipments
# ---------------------------------------------------------------------------
class ShipmentModel(BaseModel):
    """One shipment record."""

    model_config = ConfigDict(extra="allow")

    shipment_id: str
    status: str
    origin: str
    destination: str
    estimated_delivery: Optional[str] = None


class ShipmentResponse(BaseModel):
    """Response for a single shipment lookup."""

    success: bool
    shipment: ShipmentModel
    message: str


class DelayedShipmentsResponse(BaseModel):
    """Response for the delayed shipment list."""

    success: bool
    count: int
    shipments: List[ShipmentModel]
    message: str


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------
class PricingRequest(BaseModel):
    """Delivery cost calculation request."""

    model_config = ConfigDict(json_schema_extra={
        "example": {"weight": 12.5, "distance": 450, "priority": "express"}
    })

    weight: float = Field(..., gt=0, description="Chargeable weight in kilograms.")
    distance: float = Field(..., gt=0, description="Lane distance in kilometres.")
    priority: Priority = Field(default="standard", description="Service level.")


class PricingResponse(BaseModel):
    """Delivery cost breakdown."""

    success: bool
    weight_kg: float
    distance_km: float
    priority: str
    base_charge: float
    weight_charge: float
    distance_charge: float
    subtotal: float
    priority_multiplier: float
    total_cost: float
    currency: str
    message: str


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
class PolicyResponse(BaseModel):
    """A single policy answer."""

    success: bool
    name: str
    title: str
    summary: str
    owner: Optional[str] = None
    last_updated: Optional[str] = None
    source_document: Optional[str] = None
    message: str


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------
class EscalationRequest(BaseModel):
    """Escalation request payload."""

    model_config = ConfigDict(json_schema_extra={
        "example": {"reason": "Customer disputes the delay reason for SH1003"}
    })

    reason: str = Field(default="", max_length=MAX_QUERY_LENGTH)


class EscalationResponse(BaseModel):
    """Escalation confirmation. ``message`` always contains the required phrase."""

    success: bool
    ticket_id: str
    reason: str
    queue: str
    status: str
    created_at: str
    message: str


# ---------------------------------------------------------------------------
# Operational
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    """Liveness/readiness payload used by load balancers and Kubernetes."""

    status: str
    app: str
    version: str
    environment: str
    agent_mode: str


class ErrorResponse(BaseModel):
    """Uniform error payload."""

    detail: str
    error_type: str = "error"
