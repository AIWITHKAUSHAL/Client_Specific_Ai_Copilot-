# High Level Design - Logistics Operations Copilot

This document describes the system in two layers:

* **Prototype (built)** - what runs today with `python app.py`.
* **Production (designed)** - the target architecture for a client deployment.

Nothing marked *designed* is claimed to be implemented.

---

## 1. Context

```mermaid
flowchart LR
    E["Operations employee"] --> C["Operations Copilot"]
    C --> T["Shipment tracking<br/>(TMS / WMS / ERP)"]
    C --> P["Pricing<br/>(rate card / pricing engine)"]
    C --> D["Policy documents<br/>(SharePoint / Confluence)"]
    C --> H["Helpdesk<br/>(ServiceNow / Zendesk / Jira)"]
    C --> M["Monitoring<br/>(logs / metrics / traces)"]
```

The copilot is a **thin intelligence layer over systems of record**. It owns no
operational truth: it retrieves, computes, explains and escalates.

## 2. Prototype architecture (what runs today)

```mermaid
flowchart TD
    CLI["app.py - CLI"] --> AG
    API["api/ - FastAPI (optional)"] --> SVC["services/agent_service.py"]
    SVC --> AG["agent.py - router"]

    AG --> R{"Rule-based routing<br/>priority order"}
    R -->|"1 escalate / human"| ESC["tools/escalation.py"]
    R -->|"2 cost / price / quote"| PRI["tools/pricing.py"]
    R -->|"3 delayed (no ID)"| TRK["tools/tracking.py"]
    R -->|"4 shipment ID / track"| TRK
    R -->|"5 policy topic"| POL["tools/policy.py"]
    R -->|"6 unknown"| ESC

    TRK --> DS["data/shipments.py"]
    POL --> DP["data/policies.py"]
    PRI --> CFG["core/config.py - rate constants"]

    AG --> MON["services/monitoring_service.py"]
    MON --> LOG["logs/copilot.log"]
    MON --> MET["monitoring/metrics.py"]
```

Key property: **the CLI and the API share one agent, one set of tools and one
monitoring path**. A new channel is an adapter, never a fork of the logic.

## 3. Production architecture (designed)

```mermaid
flowchart TD
    subgraph Channels
      W["Web app"]
      S["Slack"]
      TM["MS Teams"]
      MB["Mobile"]
      CL["CLI"]
    end

    Channels --> GW["API Gateway<br/>TLS, rate limiting, WAF"]
    GW --> AUTH["Enterprise SSO / OAuth2 / OIDC<br/>token validation"]
    AUTH --> APP["FastAPI Operations Copilot<br/>(stateless, autoscaled)"]

    APP --> RBAC["Authorisation / RBAC<br/>role -> allowed tools & data"]
    RBAC --> ROUTER["Agent router<br/>rule-based, or LLM function calling"]

    ROUTER --> T1["Tracking tool"]
    ROUTER --> T2["Pricing tool"]
    ROUTER --> T3["Policy / RAG tool"]
    ROUTER --> T4["Escalation tool"]

    T1 --> AD1["Tracking adapter"] --> TMS["Client TMS / WMS / ERP API"]
    T2 --> AD2["Pricing adapter"] --> PE["Client pricing engine / rate card"]
    T3 --> VDB["Vector DB<br/>(pgvector / OpenSearch / managed)"]
    T3 --> LLM["LLM<br/>grounded answer + citations"]
    T4 --> AD4["Helpdesk adapter"] --> HD["ServiceNow / Zendesk / Jira"]

    APP --> DB["PostgreSQL<br/>audit log, escalations, cache"]
    APP --> OBS["Observability<br/>logs, metrics, traces"]
    OBS --> DASH["Prometheus + Grafana / CloudWatch / Datadog"]
```

### Layer responsibilities

| Layer | Responsibility | Prototype | Production |
|---|---|---|---|
| Channel | Capture the question, render the answer | CLI | Web, Slack, Teams, mobile |
| Gateway | TLS, rate limiting, WAF, routing | None | API Gateway / ingress |
| AuthN | Prove who the employee is | None | Enterprise SSO (OIDC), JWT validation |
| AuthZ | Decide what they may see or do | None | RBAC per role, per tool, per data scope |
| Agent | Choose the tool, explain the choice | Rule-based | Rule-based + optional LLM router |
| Tools | Do one job well | 4 tools, local data | Same 4 tools, client adapters |
| Data | Systems of record | In-process dicts | Client APIs, PostgreSQL, vector DB |
| Observability | Prove what happened | File log + in-process metrics | Central logs, metrics, traces, alerts |

## 4. Request flow

```mermaid
sequenceDiagram
    participant U as Employee
    participant C as Channel (CLI / API)
    participant A as Agent
    participant T as Tool
    participant D as Data source
    participant M as Monitoring

    U->>C: "Where is shipment SH1024?"
    C->>A: handle_query(query)
    A->>A: 1. detect intent (regex + keywords)
    A->>A: 2. select tool (priority order)
    A->>T: 3. track_shipment("SH1024")
    T->>D: get_shipment_record("SH1024")
    D-->>T: record
    T-->>A: {success, message, data}
    A->>A: 4. build response envelope
    A->>M: 5. record(query, tool, ms, success, response)
    A-->>C: envelope
    C-->>U: rendered answer
```

## 5. AI / LLM architecture (designed, not implemented)

The prototype answers policy questions with deterministic keyword retrieval.
The production path keeps the same tool boundary and upgrades what happens
inside it:

```mermaid
flowchart LR
    DOC["Policy documents<br/>PDF / Confluence / SharePoint"] --> CH["Chunking<br/>~500 tokens, overlap"]
    CH --> EM["Embedding model"]
    EM --> VDB["Vector database<br/>pgvector / OpenSearch"]
    Q["Employee question"] --> QE["Embed question"]
    QE --> RET["Retrieve top-k chunks<br/>+ metadata filter (client, version)"]
    VDB --> RET
    RET --> PR["Prompt: question + retrieved chunks<br/>+ 'answer only from context'"]
    PR --> LLM["LLM"]
    LLM --> ANS["Grounded answer + citations"]
    ANS --> GRD["Guardrails:<br/>no context -> escalate"]
```

Two independent upgrades, each optional and each gated by evaluation:

1. **LLM router** - replaces `rule_based_router` via `agent.set_router()`. Same
   `RoutingDecision` contract, so tools, monitoring and tests are unaffected.
2. **RAG policy answers** - replaces keyword lookup inside `tools/policy.py`.

Guardrails that must ship with either upgrade: retrieval-grounded answers only,
citations shown, low-confidence -> escalate, prompt-injection filtering on
retrieved content, and no PII in prompts (docs/security.md).

## 6. Database architecture (designed, not required by the prototype)

The prototype persists nothing except the monitoring log. A production
deployment adds PostgreSQL:

```mermaid
erDiagram
    SHIPMENTS {
        varchar shipment_id PK
        varchar status
        varchar origin
        varchar destination
        date    eta
        timestamptz updated_at
    }
    ESCALATIONS {
        varchar ticket_id PK
        text    query
        text    reason
        varchar status
        varchar assigned_queue
        timestamptz created_at
    }
    AUDIT_LOGS {
        bigserial id PK
        timestamptz timestamp
        varchar user_id
        text    query
        varchar tool
        numeric duration_ms
        boolean success
        text    response
    }
    ESCALATIONS ||--o{ AUDIT_LOGS : "raised from"
```

| Table | Purpose | Notes |
|---|---|---|
| `shipments` | Read model / cache of tracking data | Source of truth stays the TMS; refreshed by sync or read-through cache |
| `escalations` | Local record of every escalation | Mirrors the helpdesk ticket id for reconciliation |
| `audit_logs` | One row per query - the monitoring requirement, durably | Partition by month; retention per client policy |

Indexes: `shipments(status)` for the delayed list, `audit_logs(timestamp)` and
`audit_logs(tool)` for dashboards, `escalations(status, created_at)`.

**Policy retrieval storage** - one option is PostgreSQL with the `pgvector`
extension, which keeps documents and embeddings in the database already being
operated. A managed vector service is equally valid. This is a client-by-client
choice, not a mandate.

## 7. Integration architecture

```mermaid
flowchart LR
    TOOL["Tool (stable interface)"] --> AD["Adapter (client specific)"]
    AD --> SYS["Client system"]
    AD -.-> MAP["Field mapping + status vocabulary"]
    AD -.-> RES["Resilience: timeout, retry with backoff,<br/>circuit breaker, cache"]
```

Every external system is reached through an adapter that owns authentication,
field mapping, status normalisation, timeouts, retries and caching. Tools stay
client-agnostic; onboarding a new client means writing adapters and mapping
configuration - not editing the agent. See client-customization.md.

## 8. Authentication and authorisation architecture (designed)

```mermaid
flowchart LR
    E["Employee"] --> IDP["Enterprise SSO<br/>(Entra ID / Okta / Ping) - OAuth2 / OIDC"]
    IDP --> TOK["Access token (JWT)<br/>roles, scopes, expiry"]
    TOK --> API["FastAPI dependency:<br/>validate signature, issuer, audience, expiry"]
    API --> RBAC{"RBAC check"}
    RBAC -->|"allowed"| TOOLS["Tool execution<br/>(scoped data access)"]
    RBAC -->|"denied"| DENY["403 + audit event"]
```

| Role | Tracking | Delayed list | Pricing | Policy | Escalation | Metrics / admin |
|---|---|---|---|---|---|---|
| Operations User | Own region's shipments | Yes | Standard quotes | Yes | Create | No |
| Supervisor | All shipments | Yes | All service levels | Yes | Create + close | Read |
| Administrator | All | Yes | All | Yes + edit sources | All | Full |

Enforcement points: token validation at the API edge, role check per endpoint
(FastAPI dependency), and data scoping inside the adapters so a user never
receives records outside their scope. Every allow and deny is audited.

## 9. Deployment view (designed)

```mermaid
flowchart TD
    U["Employees"] --> LB["HTTPS load balancer / ingress"]
    LB --> P1["Copilot pod 1"]
    LB --> P2["Copilot pod 2"]
    LB --> PN["Copilot pod N (HPA)"]
    P1 --> PG["PostgreSQL (managed, multi-AZ)"]
    P1 --> SEC["Secrets manager"]
    P1 --> OBS["Logs / metrics / traces"]
    P1 --> EXT["Client systems (TMS, helpdesk, pricing)"]
```

The application is stateless: all state lives in PostgreSQL or the client's
systems, so horizontal scaling and rolling deployments are straightforward.
Container image -> registry -> Kubernetes or ECS. See docs/production-readiness.md.

## 10. Design decisions

| # | Decision | Why | Trade-off |
|---|---|---|---|
| D1 | Deterministic router by default | Explainable, testable, free, offline | Less flexible with unusual phrasing |
| D2 | Uniform tool result contract | One monitoring path, one API shape | Slightly more ceremony per tool |
| D3 | Data access behind functions, not raw dicts | Adapter swap without touching tools | One extra indirection in the POC |
| D4 | Unknown -> escalate, never guess | Safety in an operational context | Some answerable questions escalate |
| D5 | FastAPI layer optional | Grader runs `python app.py` with zero installs | Two entry points to keep in sync (mitigated by the shared service layer) |
| D6 | Pricing constants in config | Client rate changes are configuration | Real pricing still needs the client engine |
