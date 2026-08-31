# Client Customization Guide

**What a Forward Deployment Engineer changes to deploy this Operations Copilot
for a different logistics customer.**

The guiding principle of the codebase: **client differences live in adapters
and configuration, not in the agent.** The router, the tool contracts, the
monitoring path and the API shape should survive every customer. If a new
client forces a change to `agent.py`, that is a signal the seam is in the wrong
place - fix the seam, do not fork the agent.

| Layer | Client-specific? | Where it changes |
|---|---|---|
| Agent routing pipeline | No | `agent.py` (keywords may be tuned via config) |
| Tool contracts | No | `tools/base.py` |
| Data access | **Yes** | `data/*.py` -> client adapters |
| Business rules (rates, SLAs) | **Yes** | `core/config.py` + client pricing service |
| Vocabulary and identifiers | **Yes** | `core/config.py` |
| Auth, deployment, monitoring | **Yes** | Infrastructure and configuration |

---

## 1. Client discovery

Nothing is customised before these questions are answered.

| Area | Questions |
|---|---|
| Business | Which questions consume the most operator time today? What does a wrong answer cost? Who owns the escalation queue? |
| Users | How many operators, which roles, which regions, what shift pattern? |
| Volume | Queries per day, peak hour, expected growth |
| Systems | Which TMS/WMS/ERP? Which helpdesk? Where do policies live? Where does pricing come from? |
| Data | Identifier formats, status vocabulary, field names, refresh frequency, data quality issues |
| Access | Who may see which shipments? Any regional or customer-level restrictions? |
| Security | SSO provider, network topology, data residency, retention rules, compliance obligations |
| Operations | SLA expectations, support hours, incident process, change windows |

Deliverable: an updated PRD in which every assumption in the register at
docs/PRD.md §23.2 (`[A-1]` to `[A-16]`) is replaced by a validated client fact,
using the validation method that register names for each one.

## 2. API integrations

Replace the prototype's in-process data with client APIs behind an adapter:

```python
# adapters/tracking_adapter.py (client specific)
class TmsTrackingAdapter:
    """Implements the same two functions data/shipments.py exposes."""

    def get_shipment_record(self, shipment_id: str) -> dict | None:
        raw = self._client.get(f"/shipments/{shipment_id}", timeout=3)   # retries, circuit breaker
        return None if raw is None else self._map(raw)

    def get_all_shipments(self) -> list[dict]:
        return [self._map(r) for r in self._client.get("/shipments?status=active")]

    def _map(self, raw: dict) -> dict:
        return {
            "shipment_id": raw["consignmentNo"],
            "status": STATUS_MAP[raw["statusCode"]],
            "origin": raw["originCity"],
            "destination": raw["destCity"],
            "estimated_delivery": raw["promisedDate"][:10],
        }
```

`tools/tracking.py` is unchanged: it only calls `get_shipment_record` and
`get_all_shipments`.

Every adapter owns: authentication, field mapping, status normalisation,
timeouts, retry with backoff, a circuit breaker, caching and its own contract
tests against the client's sandbox.

## 3. TMS / WMS / ERP differences

| Difference | Typical variants | How to absorb it |
|---|---|---|
| Protocol | REST/JSON, SOAP/XML, EDI (EDIFACT/X12), flat-file SFTP, database view | Adapter per protocol; EDI and file drops usually need a scheduled sync into a read model |
| Freshness | Real-time API vs nightly batch | If batch, cache in PostgreSQL and **state the data age in the answer** |
| Granularity | Shipment vs order vs package vs container | Decide the copilot's primary entity with the client; map the rest |
| Status vocabulary | `IN_TRANSIT`, `ON_ROAD`, `04`, `Out for delivery` | `STATUS_MAP` in the adapter -> canonical statuses |
| Multi-system truth | Tracking in the TMS, inventory in the WMS, billing in the ERP | Route per capability; never merge silently - say which system answered |
| Rate limits | Strict quotas on legacy systems | Cache + backoff; consider a read replica or nightly extract |

## 4. Data and schema mapping

Produce a mapping table during discovery and keep it in the client's repo:

| Copilot field | Client field | Transform | Notes |
|---|---|---|---|
| `shipment_id` | `consignmentNo` | uppercase, strip dashes | Primary key |
| `status` | `statusCode` | `STATUS_MAP` lookup | Unmapped codes must fail loudly, not silently pass through |
| `origin` | `originCity` + `originCountry` | concatenate | |
| `destination` | `destCity` + `destCountry` | concatenate | |
| `estimated_delivery` | `promisedDate` | ISO-8601 date, client timezone | Confirm timezone semantics |
| `delay_reason` | `exceptionText` | trim, redact PII | Only populated for delayed shipments |

Rules: map explicitly (never `**raw`), fail loudly on unknown codes, keep the
mapping in one place, and version it - a client's field rename is a
configuration change with a test, not a hunt through the codebase.

## 5. Shipment identifier differences

The prototype uses `SH1024`. Clients use AWB numbers, container numbers, order
IDs, barcodes.

```bash
COPILOT_SHIPMENT_ID_PATTERN='\b(\d{10,12})\b'          # numeric AWB
COPILOT_SHIPMENT_ID_PATTERN='\b([A-Z]{4}\d{7})\b'      # ISO container number
```

Also confirm: check-digit validation, whether operators paste with spaces or
dashes (`normalize_shipment_id` already strips them), whether one shipment has
several identifiers (customer reference vs internal ID - the adapter should
accept both), and case sensitivity.

## 6. Authentication

| Client situation | Approach |
|---|---|
| Entra ID / Okta / Ping SSO | OAuth2/OIDC; validate JWT signature, issuer, audience and expiry in a FastAPI dependency |
| Internal portal already authenticated | Accept a signed token from the portal; never trust a plain header |
| Slack / Teams deployment | Verify the platform signature, then map the platform user to the corporate identity |
| Service-to-service | Client credentials flow with its own scoped identity |

Prototype has no authentication (see docs/security.md §2). This is always the
first production addition.

## 7. Authorisation and RBAC

Start from the matrix in docs/HLD.md §8 and adjust to the client's actual
roles. Typical client-specific dimensions:

- **Regional scoping** - an operator sees only their hub's shipments.
- **Customer scoping** - a 3PL operator sees only their assigned accounts.
- **Pricing sensitivity** - only supervisors may quote urgent/contract rates.
- **Escalation rights** - who may close, not just create, an escalation.

Enforce in two places: the endpoint (may this role use this tool?) and the
adapter (may this user see this record?). Never rely on the UI.

## 8. Pricing and business rules

The prototype formula is illustrative. For a real client:

| Option | When | Effort |
|---|---|---|
| Call the client's pricing engine | They have one - **strongly preferred** | Adapter only; the copilot must never disagree with the system that bills |
| Rate card table in the database | Rates vary by lane/customer but no service exists | Data model + admin process |
| Configuration constants | Simple flat model, pilot only | `core/config.py` |

Real rate cards typically add: lane-based rates, volumetric (dimensional)
weight, fuel surcharge, customer contract discounts, accessorials (liftgate,
residential, waiting time), tax/VAT, currency and minimum charges. Every one of
these must be traceable in the breakdown - operators need to justify a quote,
so keep the itemisation the prototype already produces.

Other business rules to confirm: what counts as "delayed" (past ETA? past ETA
by N hours? exception-coded?), business-day calendars and holidays, and cut-off
times.

## 9. Policy and document sources

| Source | Integration |
|---|---|
| SharePoint / Confluence | API sync with change detection; respect source permissions |
| PDF / DOCX on a file share | Scheduled extraction; watch for scanned documents needing OCR |
| Existing knowledge base | Read via its API; keep it the system of record |
| Tribal knowledge | The hardest case - run policy workshops and write the policies down first |

Non-negotiables: every answer cites its source document and version; superseded
documents are removed from the index; and document permissions are respected -
if a policy is restricted, the copilot must not surface it to everyone.

## 10. RAG configuration (when policy volume justifies it)

| Decision | Options | Guidance |
|---|---|---|
| Chunking | Fixed size, semantic, section-aware | Section-aware works best for policy documents |
| Chunk size / overlap | 300-800 tokens, 10-20% overlap | Tune against the client's evaluation set |
| Embedding model | Managed or self-hosted | Data residency often decides this |
| Vector store | pgvector, OpenSearch, managed service | pgvector avoids a new system if PostgreSQL is already there |
| Retrieval | top-k, hybrid keyword+vector, re-ranking | Hybrid is the reliable default for policy jargon |
| Metadata filters | client, region, document version, effective date | Essential for multi-tenant or multi-region deployments |
| Grounding | Answer only from retrieved context, always cite | No context -> escalate, never improvise |
| Refresh | On document change, or scheduled | Stale policy answers are worse than none |

The switch is contained inside `tools/policy.py`; the agent, API and tests do
not change.

## 11. Escalation workflow

Confirm with the client: which queue, what priority mapping, what fields are
mandatory, who is on call, what SLA applies, whether the employee needs the
ticket ID back (yes, always), and whether escalation is create-only or also
update/close.

## 12. Helpdesk integration

| System | Integration |
|---|---|
| ServiceNow | Table API (`POST /api/now/table/incident`), OAuth2; map queue -> assignment group |
| Zendesk | Tickets API, API token or OAuth; map queue -> group, priority -> priority |
| Jira Service Management | REST v3 request creation; map queue -> request type in a service desk project |
| Internal tool | Whatever it offers - REST, database insert, even email as a last resort |

Implementation: `tools/escalation.py` keeps its signature and its required
phrase; the adapter replaces the in-memory store and returns the real ticket
ID. Requirements: idempotency key so a retry never opens a duplicate ticket,
and a durable local record even if the helpdesk call fails - a lost escalation
is the worst possible failure mode for this system.

## 13. Security and compliance

Per client: SSO provider, network placement (public, VPC-only, on-prem), data
residency, PII handling and redaction rules, retention periods, audit export
format, penetration test requirements, and any certification the client must
maintain (SOC 2, ISO 27001, customs/trade rules). Details in docs/security.md.

## 14. Deployment environment

Confirm: environments (dev/staging/prod), change windows, release approval
process, infrastructure-as-code standard (Terraform, CloudFormation, Helm),
existing CI/CD platform (the copilot should use it rather than introduce a new
one), and who operates the service after handover.

## 15. Cloud vs on-premises

| Client posture | Deployment | Consequences |
|---|---|---|
| Cloud-first | Managed k8s / ECS / Cloud Run + managed PostgreSQL | Fastest path; managed services reduce operational load |
| Hybrid | Copilot in cloud, private link to on-prem systems | Network design and latency become design constraints |
| On-prem only | Containers on client hardware | Client operates it; sizing and upgrades become their responsibility |
| Air-gapped | On-prem + self-hosted models only | No external LLM API; plan for a self-hosted model or stay rule-based |

## 16. Monitoring

Send the copilot's logs and metrics to the tooling the client already uses -
CloudWatch, Datadog, Splunk, ELK/OpenSearch, Prometheus/Grafana. Agree
dashboards (volume by intent, success rate, latency, escalation rate,
unanswered questions), alert thresholds, alert routing (who gets paged), and
log retention. Add client-specific fields to every record: user ID, region,
business unit, request ID.

## 17. SLA

Agree and write down: availability target, p95 latency target, support hours,
incident severity definitions, response and resolution times per severity,
maintenance windows, and the reporting cadence. These numbers drive
architecture (multi-AZ? standby? 24/7 on-call?) and cost - agree them before
sizing, not after.

## 18. Evaluation dataset

The single most valuable client-specific artefact after the adapters.

1. Collect 100-300 real questions from chat logs, tickets and shadowing sessions.
2. Label each with the correct tool and the correct answer.
3. Include the client's abbreviations, misspellings, local language and shorthand.
4. Include adversarial and out-of-scope cases - the copilot must escalate, not improvise.
5. Run it in CI as a release gate (`tests/evaluation_dataset.py` is the template).
6. Grow it every time an operator reports a wrong answer.

## 19. Scaling requirements

Size from real numbers: queries/day, peak hour concurrency, growth plan, number
of regions and languages, and the client systems' own rate limits - which are
usually the real ceiling, not the copilot.

## 20. Support model

Define: L1 (client operations team, using the copilot's own escalation path),
L2 (client IT for system and access issues), L3 (engineering for defects and
model/routing changes). Agree the feedback loop for wrong answers, the cadence
for reviewing unanswered questions, the release process for routing changes,
and the handover/training plan.

## 21. Cost model

Follow docs/cost-estimation.md: build the estimate from the client's volumes,
their cloud pricing and their SLA. Agree who pays for what (infrastructure,
LLM usage, support), decide the chargeback model if several business units use
it, and re-baseline after the pilot with measured numbers.

---

## Onboarding checklist for a new client

- [ ] Discovery complete; PRD assumptions replaced with facts
- [ ] Identifier pattern and status vocabulary configured
- [ ] Tracking adapter implemented and contract-tested
- [ ] Pricing source connected (client engine preferred over a local formula)
- [ ] Policy documents indexed with citations and versioning
- [ ] Escalation adapter writing to the real helpdesk, with idempotency
- [ ] SSO + RBAC configured and verified with real accounts
- [ ] Security review passed; PII and retention rules implemented
- [ ] Client evaluation dataset built and green in CI
- [ ] Monitoring, dashboards and alerts wired into the client's tooling
- [ ] SLA, support model and cost model agreed in writing
- [ ] Pilot team trained; feedback loop running
