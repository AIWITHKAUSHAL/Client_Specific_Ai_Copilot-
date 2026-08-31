"""Tests for the optional FastAPI layer.

Skipped automatically when FastAPI is not installed, so the assignment
prototype can still be tested with a bare standard-library environment.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI is an optional dependency")
from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402

REQUIRED_PHRASE = "Escalated to Operations Team"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_copilot_query_endpoint_tracks_a_shipment(client):
    response = client.post("/api/v1/copilot/query", json={"query": "Where is shipment SH1024?"})
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "shipment_tracking"
    assert body["tool_selected"] == "tracking"
    assert body["success"] is True
    assert "SH1024" in body["response"]
    assert body["execution_time_ms"] >= 0


def test_copilot_query_endpoint_escalates(client):
    body = client.post("/api/v1/copilot/query", json={"query": "Escalate this issue."}).json()
    assert REQUIRED_PHRASE in body["response"]


def test_copilot_query_rejects_empty_payload(client):
    assert client.post("/api/v1/copilot/query", json={"query": ""}).status_code == 422


def test_get_shipment(client):
    body = client.get("/api/v1/shipments/SH1024").json()
    assert body["shipment"]["destination"] == "Jaipur, IN"


def test_get_shipment_not_found(client):
    assert client.get("/api/v1/shipments/SH9999").status_code == 404


def test_delayed_shipments_endpoint(client):
    body = client.get("/api/v1/shipments/delayed").json()
    assert body["count"] >= 1
    assert any(s["shipment_id"] == "SH1003" for s in body["shipments"])


def test_pricing_endpoint(client):
    body = client.post(
        "/api/v1/pricing/calculate", json={"weight": 10, "distance": 100, "priority": "express"}
    ).json()
    assert body["total_cost"] == 300.0
    assert body["priority_multiplier"] == 1.5


@pytest.mark.parametrize(
    "payload",
    [
        {"weight": 0, "distance": 100},
        {"weight": 10, "distance": -3},
        {"weight": 10, "distance": 100, "priority": "overnight"},
        {"distance": 100},
    ],
)
def test_pricing_endpoint_validates_input(client, payload):
    assert client.post("/api/v1/pricing/calculate", json=payload).status_code == 422


def test_policy_endpoint(client):
    body = client.get("/api/v1/policies/refund").json()
    assert body["title"] == "Refund Policy"


def test_policy_endpoint_not_found(client):
    assert client.get("/api/v1/policies/space-travel").status_code == 404


def test_policy_list_endpoint(client):
    assert len(client.get("/api/v1/policies").json()["policies"]) >= 5


def test_escalation_endpoint(client):
    response = client.post("/api/v1/escalations", json={"reason": "API test"})
    assert response.status_code == 201
    body = response.json()
    assert REQUIRED_PHRASE in body["message"]
    assert body["ticket_id"].startswith("ESC-")


def test_metrics_endpoint_counts_traffic(client):
    client.post("/api/v1/copilot/query", json={"query": "Which shipments are delayed?"})
    body = client.get("/api/v1/metrics").json()
    assert body["total_queries"] >= 1
    assert "queries_by_tool" in body


def test_recent_metrics_endpoint(client):
    client.post("/api/v1/copilot/query", json={"query": "What is our refund policy?"})
    records = client.get("/api/v1/metrics/recent?limit=5").json()["records"]
    assert records
    assert "execution_time_ms" in records[-1]


def test_openapi_schema_is_generated(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path in ("/health", "/api/v1/copilot/query", "/api/v1/shipments/{shipment_id}",
                 "/api/v1/shipments/delayed", "/api/v1/pricing/calculate",
                 "/api/v1/policies/{policy_name}", "/api/v1/escalations"):
        assert path in paths
