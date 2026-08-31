"""REST endpoints for the Operations Copilot.

Every endpoint is a thin adapter: validate input (Pydantic), call
:data:`services.agent_service.agent_service`, shape the response.  All
business logic stays in the tools and the agent, which is why the CLI and
the API can never drift apart.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status

from core.config import API_PREFIX
from core.exceptions import ValidationError
from data.policies import list_policy_names
from models.schemas import (
    DelayedShipmentsResponse,
    EscalationRequest,
    EscalationResponse,
    PolicyResponse,
    PricingRequest,
    PricingResponse,
    QueryRequest,
    QueryResponse,
    ShipmentResponse,
)
from services.agent_service import agent_service

router = APIRouter(prefix=API_PREFIX)


# ---------------------------------------------------------------------------
# Main entry point: natural language
# ---------------------------------------------------------------------------
@router.post(
    "/copilot/query",
    response_model=QueryResponse,
    summary="Ask the Operations Copilot a question",
    tags=["copilot"],
)
def copilot_query(payload: QueryRequest) -> Dict[str, Any]:
    """Route a natural language query to the right tool and answer it."""
    return agent_service.handle(payload.query, context=payload.context)


# ---------------------------------------------------------------------------
# Shipments
# ---------------------------------------------------------------------------
# NOTE: the static '/shipments/delayed' route must be declared before the
# '/shipments/{shipment_id}' route, otherwise 'delayed' is captured as an id.
@router.get(
    "/shipments/delayed",
    response_model=DelayedShipmentsResponse,
    summary="List delayed shipments",
    tags=["shipments"],
)
def delayed_shipments() -> Dict[str, Any]:
    """Return every shipment currently marked as Delayed."""
    result = agent_service.delayed()
    return {
        "success": result["success"],
        "count": result["data"]["count"],
        "shipments": result["data"]["shipments"],
        "message": result["message"],
    }


@router.get(
    "/shipments/{shipment_id}",
    response_model=ShipmentResponse,
    responses={404: {"description": "Shipment not found"}},
    summary="Track one shipment",
    tags=["shipments"],
)
def get_shipment(shipment_id: str) -> Dict[str, Any]:
    """Return the tracking record for ``shipment_id``."""
    result = agent_service.track(shipment_id)
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["message"])
    return {
        "success": True,
        "shipment": result["data"]["shipment"],
        "message": result["message"],
    }


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------
@router.post(
    "/pricing/calculate",
    response_model=PricingResponse,
    responses={400: {"description": "Invalid pricing input"}},
    summary="Calculate a delivery cost",
    tags=["pricing"],
)
def calculate_price(payload: PricingRequest) -> Dict[str, Any]:
    """Return a full delivery cost breakdown."""
    try:
        result = agent_service.price(payload.weight, payload.distance, payload.priority)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"success": result["success"], **result["data"], "message": result["message"]}


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------
@router.get("/policies", summary="List available policies", tags=["policies"])
def list_policies() -> Dict[str, List[str]]:
    """Return the canonical names of every published policy."""
    return {"policies": list_policy_names()}


@router.get(
    "/policies/{policy_name}",
    response_model=PolicyResponse,
    responses={404: {"description": "Policy not found"}},
    summary="Retrieve one policy",
    tags=["policies"],
)
def get_policy_endpoint(policy_name: str) -> Dict[str, Any]:
    """Return a policy by canonical name or topic keyword."""
    result = agent_service.policy(policy_name)
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["message"])
    policy = result["data"]["policy"]
    return {"success": True, **{k: v for k, v in policy.items() if k != "keywords"},
            "message": result["message"]}


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------
@router.post(
    "/escalations",
    response_model=EscalationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Escalate an issue to the operations team",
    tags=["escalations"],
)
def create_escalation(payload: EscalationRequest) -> Dict[str, Any]:
    """Raise an escalation; the message contains 'Escalated to Operations Team'."""
    result = agent_service.escalate(payload.reason)
    return {"success": True, **result["data"], "message": result["message"]}


@router.get("/escalations", summary="List escalations raised in this process", tags=["escalations"])
def list_escalations_endpoint() -> Dict[str, Any]:
    """Return the in-memory escalation log (production: the helpdesk API)."""
    tickets = agent_service.escalations()
    return {"count": len(tickets), "escalations": tickets}


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------
@router.get("/metrics", summary="Copilot monitoring metrics", tags=["monitoring"])
def get_metrics() -> Dict[str, Any]:
    """Return aggregate query metrics for this process."""
    return agent_service.metrics()


@router.get("/metrics/recent", summary="Recent monitored interactions", tags=["monitoring"])
def get_recent(limit: int = 10) -> Dict[str, Any]:
    """Return the most recent monitored interactions (audit trail preview)."""
    limit = max(1, min(limit, 100))
    return {"records": agent_service.recent(limit)}
