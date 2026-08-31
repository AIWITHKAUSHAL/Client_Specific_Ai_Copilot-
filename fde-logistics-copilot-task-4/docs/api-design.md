# API Design - Logistics Operations Copilot

The REST API is the production interface. It is **optional** for the
assignment: the prototype runs entirely through `python app.py`. Both entry
points call the same agent and tools, so their behaviour cannot drift.

```bash
pip install -r requirements.txt
uvicorn api.main:app --reload
# Swagger UI: http://127.0.0.1:8000/docs
```

Base path: `/api/v1` (`/health` sits outside the version prefix, as probes
should not be versioned).

---

## 1. Endpoint summary

| Method | Path | Purpose | Success | Errors |
|---|---|---|---|---|
| GET | `/health` | Liveness / readiness probe | 200 | - |
| POST | `/api/v1/copilot/query` | **Main endpoint** - natural language question | 200 | 422 |
| GET | `/api/v1/shipments/delayed` | List delayed shipments | 200 | - |
| GET | `/api/v1/shipments/{shipment_id}` | Track one shipment | 200 | 404 |
| POST | `/api/v1/pricing/calculate` | Delivery cost breakdown | 200 | 400, 422 |
| GET | `/api/v1/policies` | List published policy names | 200 | - |
| GET | `/api/v1/policies/{policy_name}` | Retrieve one policy | 200 | 404 |
| POST | `/api/v1/escalations` | Escalate to the operations team | 201 | 422 |
| GET | `/api/v1/escalations` | Escalations raised in this process | 200 | - |
| GET | `/api/v1/metrics` | Aggregate monitoring metrics | 200 | - |
| GET | `/api/v1/metrics/recent?limit=n` | Recent monitored interactions | 200 | - |

Route order note: `/shipments/delayed` is declared before
`/shipments/{shipment_id}`, otherwise `delayed` would be captured as an ID.

## 2. The main endpoint

### `POST /api/v1/copilot/query`

Request

```json
{ "query": "Where is shipment SH1024?" }
```

Optional `context` supplies pre-resolved parameters (used by the CLI's
interactive pricing prompts and by any UI that has form fields):

```json
{ "query": "Calculate delivery cost.",
  "context": { "weight": 12.5, "distance": 450, "priority": "express" } }
```

Response `200`

```json
{
  "query": "Where is shipment SH1024?",
  "intent": "shipment_tracking",
  "tool_selected": "tracking",
  "routing_reason": "shipment id 'SH1024'",
  "success": true,
  "response": "Shipment SH1024\n  Status            : In Transit\n  ...",
  "data": { "shipment_id": "SH1024", "found": true, "shipment": { "...": "..." } },
  "execution_time_ms": 0.078
}
```

| Field | Meaning |
|---|---|
| `intent` | `shipment_tracking` \| `delayed_shipments` \| `cost_calculation` \| `policy_lookup` \| `escalation` \| `unknown` |
| `tool_selected` | `tracking` \| `pricing` \| `policy` \| `escalation` |
| `routing_reason` | Why the router chose that tool - explainability for the client |
| `success` | Whether the question was answered |
| `response` | Text shown to the employee |
| `data` | Structured payload for a UI |
| `execution_time_ms` | Server-side execution time |

Validation: `query` is required, 1-500 characters (`COPILOT_MAX_QUERY_LENGTH`).
An empty string returns 422 from Pydantic before any logic runs.

Note: a query the copilot cannot answer still returns **200** with
`intent: "unknown"` and an escalation response. That is a successful
interaction with a human handover, not an HTTP error.

## 3. Capability endpoints

### `GET /api/v1/shipments/{shipment_id}`

```json
{ "success": true,
  "shipment": { "shipment_id": "SH1024", "status": "In Transit",
                "origin": "Pune, IN", "destination": "Jaipur, IN",
                "estimated_delivery": "2026-09-03" },
  "message": "Shipment SH1024\n  Status ..." }
```

`404` when unknown: `{ "detail": "Shipment SH9999 was not found ..." }`.
IDs are normalised, so `sh-1024` and `SH1024` resolve identically.

### `GET /api/v1/shipments/delayed`

```json
{ "success": true, "count": 2, "shipments": [ { "shipment_id": "SH1003", "...": "..." } ],
  "message": "2 delayed shipment(s) found: ..." }
```

### `POST /api/v1/pricing/calculate`

Request

```json
{ "weight": 10, "distance": 100, "priority": "express" }
```

Response `200`

```json
{ "success": true, "weight_kg": 10.0, "distance_km": 100.0, "priority": "express",
  "base_charge": 50.0, "weight_charge": 100.0, "distance_charge": 50.0,
  "subtotal": 200.0, "priority_multiplier": 1.5, "total_cost": 300.0,
  "currency": "USD", "message": "Delivery cost estimate (express): ..." }
```

Validation (`422`): `weight > 0`, `distance > 0`, `priority` in
`standard|express|urgent`. Domain guard-rail breaches (e.g. weight above
`MAX_WEIGHT_KG`) return `400`.

### `GET /api/v1/policies/{policy_name}`

Accepts a canonical name (`refund`) or a topic keyword (`damaged`). `404` when
nothing matches, with the list of answerable policies in the message.

### `POST /api/v1/escalations`

Request `{ "reason": "Customer disputes the delay reason for SH1003" }` ->
`201`

```json
{ "success": true, "ticket_id": "ESC-0001", "reason": "...",
  "queue": "operations-team", "status": "open",
  "created_at": "2026-08-31T17:02:56+00:00",
  "message": "Escalated to Operations Team.\n  Reference : ESC-0001 ..." }
```

The `message` always contains the exact phrase `Escalated to Operations Team`.

### `GET /health`

```json
{ "status": "ok", "app": "Logistics Operations Copilot", "version": "1.0.0",
  "environment": "local", "agent_mode": "rule_based" }
```

Used by the Docker `HEALTHCHECK`, load balancers and Kubernetes probes.

## 4. Status code policy

| Code | When |
|---|---|
| 200 | Request handled (including "answered with an escalation") |
| 201 | Escalation created |
| 400 | Domain validation failed (`ValidationError` from a tool) |
| 401 | **Production**: missing or invalid token |
| 403 | **Production**: authenticated but not authorised for that tool/scope |
| 404 | Shipment or policy not found |
| 422 | Payload failed schema validation (Pydantic) |
| 429 | **Production**: rate limit exceeded |
| 500 | Unexpected server error (logged, no internals leaked) |

## 5. Conventions

- **Versioned path** (`/api/v1`) so a breaking change ships as `/api/v2` while v1 continues.
- **Uniform envelope** for copilot answers; capability endpoints return their resource plus a `message`.
- **Errors** are `{"detail": "...", "error_type": "..."}` - never a stack trace.
- **Idempotency**: all `GET`s are safe and repeatable. `POST /escalations` is not idempotent today; production should accept an `Idempotency-Key` header so a retried request does not open a second ticket.
- **OpenAPI** is generated from the Pydantic models (`/openapi.json`, `/docs`) - the client gets a machine-readable contract for free.

## 6. Production hardening (not in the prototype)

| Concern | Design |
|---|---|
| Authentication | OAuth2 / OIDC bearer token from enterprise SSO, validated in a FastAPI dependency (signature, issuer, audience, expiry) |
| Authorisation | Role check per endpoint + data scoping inside adapters (docs/HLD.md §8) |
| Rate limiting | Per-user and per-IP quotas at the gateway; 429 with `Retry-After` |
| Transport | TLS 1.2+ only, HSTS, no plaintext listener |
| CORS | Explicit allow-list of client origins (the prototype adds no CORS middleware) |
| Request tracing | `X-Request-ID` accepted or generated, echoed in responses and every log line |
| Payload limits | Max body size at the gateway; query length capped in the schema |
| Pagination | `limit` / `cursor` on list endpoints once real volumes replace the demo dataset |
