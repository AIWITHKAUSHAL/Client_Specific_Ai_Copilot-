# Testing and Agent Evaluation

Two distinct activities, deliberately kept separate:

* **Testing** - does each unit of code behave as specified? (`pytest`)
* **Evaluation** - does the *agent* choose the right tool and give the right
  answer for the questions employees actually ask? (`tests/test_evaluation.py`)

Classic software testing alone does not tell you whether an assistant is
useful. Evaluation does, and it must be a dataset that grows with the client.

---

## 1. How to run

```bash
pip install -r requirements.txt
pytest -q                        # everything: unit, API and evaluation
pytest tests/test_evaluation.py -v   # the agent evaluation set only
python app.py --demo             # the five demo queries, no dependencies
```

## 2. Current results (measured on this repository)

| Suite | Cases | Result |
|---|---|---|
| Tool tests (`test_tracking` 12, `test_pricing` 18, `test_policy` 19, `test_escalation` 7) | 56 | pass |
| Agent tests (`test_agent`) | 26 | pass |
| API tests (`test_api`, skipped automatically without FastAPI) | 19 | pass |
| Evaluation set (`test_evaluation`, 34 queries + 3 aggregate checks) | 37 | pass |
| **Total** | **138** | **138 passed** |

Measured on Python 3.14, macOS, in-process (no network, no database):

| Metric | Value |
|---|---|
| Routing accuracy on the evaluation set | 34/34 = 100% |
| Mean agent latency | 0.036 ms |
| p95 agent latency | 0.116 ms |
| Max agent latency | 0.134 ms |

> These numbers describe the **local prototype** with in-memory data. They are
> not a prediction of production latency: real deployments add network calls to
> the client's TMS, database round-trips and (if enabled) LLM inference, which
> dominate everything measured above. Production performance must be measured
> against the client's systems, not extrapolated from here.

## 3. Test coverage by requirement

| Requirement | Test |
|---|---|
| Shipment found | `test_track_shipment_found` |
| Shipment not found handled cleanly | `test_track_shipment_not_found_is_handled_cleanly` |
| Missing shipment ID handled cleanly | `test_track_shipment_missing_id_is_handled_cleanly` |
| ID normalisation (`sh-1024` -> `SH1024`) | `test_normalize_shipment_id`, `test_track_shipment_is_case_and_format_insensitive` |
| Delayed shipment list | `test_get_delayed_shipments_returns_only_delayed` |
| Required shipment IDs present | `test_required_assignment_shipments_exist` |
| Standard pricing | `test_standard_pricing_matches_the_documented_formula` |
| Express pricing | `test_express_pricing_applies_1_5_multiplier` |
| Urgent pricing | `test_urgent_pricing_applies_2_0_multiplier` |
| Itemised breakdown | `test_breakdown_is_fully_itemised` |
| Invalid weight | `test_invalid_weight_is_rejected` (0, negative, text, None) |
| Invalid distance | `test_invalid_distance_is_rejected` (0, negative, text, None) |
| Invalid priority | `test_invalid_priority_is_rejected` |
| Guard rails on absurd values | `test_absurd_values_are_rejected_by_guard_rails` |
| At least five policies | `test_at_least_five_policies_are_published` |
| Policy retrieval by name | `test_every_policy_is_retrievable_by_name` (7 policies) |
| Policy retrieval by natural language | `test_natural_language_policy_routing` |
| Unknown policy handled | `test_unknown_policy_returns_the_available_list` |
| Escalation exact phrase | `test_escalation_contains_the_required_phrase` + `test_config_phrase_matches_the_assignment` |
| Escalation reference | `test_escalation_creates_a_local_reference`, `test_escalation_references_increment` |
| All five agent routes | `test_mandatory_demo_queries_route_correctly` |
| Unknown request fallback | `test_unknown_query_falls_back_to_escalation` |
| Empty query | `test_empty_query_is_handled_without_crashing` |
| Monitoring fields recorded | `test_every_query_is_monitored_with_the_required_fields` |
| Monitoring aggregates | `test_metrics_aggregate_successes_and_failures` |
| Router is pluggable (LLM seam) | `test_router_can_be_replaced` |
| API endpoints | `tests/test_api.py` (11 endpoint tests + OpenAPI contract) |

## 4. Evaluation dataset

`tests/evaluation_dataset.py` holds 34 realistic operations questions with the
tool that should answer each one. Every case asserts intent, tool, success and
a required substring of the answer.

| # | Query | Expected intent | Expected tool | Answer must contain |
|---|---|---|---|---|
| 1 | Where is shipment SH1024? | shipment_tracking | tracking | SH1024 |
| 2 | Track SH1002 | shipment_tracking | tracking | Bengaluru |
| 3 | What is the status of shipment SH1001? | shipment_tracking | tracking | Delivered |
| 4 | Locate sh-1005 please | shipment_tracking | tracking | SH1005 |
| 5 | eta for SH1024 | shipment_tracking | tracking | 2026-09-03 |
| 6 | status of shipment id: SH 1002 | shipment_tracking | tracking | SH1002 |
| 7 | Is SH1003 delayed? | shipment_tracking | tracking | Delayed |
| 8 | Where is shipment SH9999? | shipment_tracking | tracking | not found (success=false) |
| 9 | Which shipments are delayed? | delayed_shipments | tracking | SH1003 |
| 10 | Show me all late shipments | delayed_shipments | tracking | delayed shipment |
| 11 | Are any consignments behind schedule? | delayed_shipments | tracking | SH1004 |
| 12 | list overdue deliveries | delayed_shipments | tracking | Delayed |
| 13 | Calculate delivery cost. | cost_calculation | pricing | weight (asks for input) |
| 14 | How much to ship 20 kg over 300 km? | cost_calculation | pricing | 400.00 |
| 15 | What is the price for an urgent 5 kg shipment over 120 km? | cost_calculation | pricing | 320.00 |
| 16 | quote for express delivery of 10 kg over 200 km | cost_calculation | pricing | 375.00 |
| 17 | What does it cost to send 2.5 kg 45 km? | cost_calculation | pricing | 97.50 |
| 18 | rate for an urgent shipment | cost_calculation | pricing | distance (asks for input) |
| 19 | What is our delivery policy? | policy_lookup | policy | Standard Delivery Policy |
| 20 | What is the refund policy? | policy_lookup | policy | Refund Policy |
| 21 | Tell me about the cancellation policy | policy_lookup | policy | Cancellation Policy |
| 22 | Do we insure high value shipments? | policy_lookup | policy | Insurance |
| 23 | What happens if a parcel is damaged in transit? | policy_lookup | policy | Damaged Shipment Policy |
| 24 | How long does standard delivery take? | policy_lookup | policy | business days |
| 25 | What is our priority shipping cost policy? | policy_lookup | policy | Priority Shipping Policy |
| 26 | What is the delayed shipment policy? | policy_lookup | policy | Delayed Shipment Policy |
| 27 | Which rules apply to booking cancellations? | policy_lookup | policy | Cancellation Policy |
| 28 | Escalate this issue. | escalation | escalation | Escalated to Operations Team |
| 29 | I need to speak to a human about SH1003 | escalation | escalation | Escalated to Operations Team |
| 30 | Please raise a ticket for this customer complaint | escalation | escalation | Escalated to Operations Team |
| 31 | Can I get a supervisor to review this refund? | escalation | escalation | Escalated to Operations Team |
| 32 | What is the capital of France? | unknown | escalation | Escalated to Operations Team |
| 33 | Book me a flight to Paris | unknown | escalation | Escalated to Operations Team |
| 34 | Reset my email password | unknown | escalation | Escalated to Operations Team |

Cases 7, 25 and 26 are the deliberate hard cases: a shipment ID must beat the
delayed-shipment list, and policy wording must beat pricing/delay keywords.

## 5. Evaluation metrics

| Metric | Definition | Prototype value | Production target |
|---|---|---|---|
| Routing accuracy | Correct tool / total queries | 100% (34/34) | >= 95%, tracked per release |
| Shipment lookup accuracy | Correct record returned for a valid ID | 100% | 100% (deterministic once the adapter is correct) |
| Pricing correctness | Computed cost matches the rate card | 100% vs the documented formula | 100% vs the client's pricing engine |
| Policy retrieval accuracy | Correct policy returned | 100% (9/9 policy queries) | >= 90% on the client's phrasing set |
| Escalation accuracy | Escalates when it should, phrase always present | 100% | 100% |
| Unknown fallback safety | Unmatched queries handed to a human, never guessed | 100% | 100% |
| Error handling rate | Invalid input reported cleanly, no crash | 100% | 100% |
| Response latency | Agent time per query | mean 0.036 ms / p95 0.116 ms | p95 target agreed in the SLA |

## 6. Evaluating an LLM-based version (when one ships)

The prototype is deterministic, so accuracy is a pass/fail assertion. As soon
as an LLM router or RAG answering is introduced, evaluation must be extended:

| Dimension | Method |
|---|---|
| Routing accuracy | Same dataset, re-run per model/prompt version; regression gate in CI |
| Answer groundedness | Every claim traceable to a retrieved chunk; automatic citation check |
| Retrieval quality | recall@k and MRR against labelled question -> document pairs |
| Hallucination rate | Human review of a sampled set + automated "no citation -> fail" check |
| Refusal correctness | Out-of-scope questions must escalate, not improvise |
| Prompt-injection resistance | Adversarial cases in the dataset (documents that tell the model to misbehave) |
| Latency and cost | p50/p95 latency, tokens and cost per query |
| Determinism drift | Same query re-run N times; flag unstable routing |

Release gate: no LLM change ships unless routing accuracy is >= the current
baseline, groundedness has no regressions, and every adversarial case passes.

## 7. Test pyramid and CI

```
        /\        Evaluation set (37)  - does the agent choose and answer correctly?
       /  \       API tests (19)       - contract, status codes, validation
      /    \      Agent tests (26)     - routing, errors, monitoring, fallbacks
     /______\     Tool tests (56)      - each tool, happy path + every failure mode
```

`.github/workflows/ci.yml` runs three jobs on every push and pull request:

1. **prototype-stdlib-only** - runs `python app.py --demo` on a bare Python with
   no `pip install`, and greps for `Escalated to Operations Team`. This proves
   the assignment prototype never acquires a hidden dependency.
2. **test** - installs requirements and runs the whole suite on Python 3.10-3.12.
3. **lint** - `ruff check` (non-blocking).

## 8. What is deliberately not tested

- Client system integrations (none exist yet - adapters will need contract tests and recorded fixtures).
- Load and soak behaviour (meaningless against in-memory data; belongs to the performance test phase in docs/production-readiness.md).
- Authentication and authorisation (not implemented in the prototype).
- Any claim about production accuracy or latency - those must be measured with the client, on the client's data.
