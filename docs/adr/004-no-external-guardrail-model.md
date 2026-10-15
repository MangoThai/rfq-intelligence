# ADR-004 — Do not add an external guardrail model in V1

| Field  | Value      |
| ------ | ---------- |
| Status | Accepted   |
| Date   | 2026-10-15 |

---

## Context

RFQ Intelligence receives **untrusted natural-language content** from customer
emails.

Such content may contain instructions attempting to influence the AI system,
including requests to:

- replace product references;
- change quantities;
- override catalogue prices;
- change customer discounts;
- invent stock availability;
- ignore pack-size constraints;
- suppress substitution flags;
- suppress delivery constraints.

External guardrail systems could be added to classify or block potentially
malicious input before it reaches the extraction model. Possible technologies
considered included dedicated prompt-injection classifiers and external
guardrail models.

However, adding another model would introduce:

- additional latency;
- additional cost;
- another external dependency;
- another source of false positives and false negatives;
- additional evaluation and operational complexity.

The architecture already limits the authority of the extraction model: the LLM
cannot directly control critical business invariants such as price, discount,
stock, pack size, or quote totals.

---

## Decision

RFQ Intelligence V1 **will not include an external guardrail model**.

Instead, V1 relies on **layered controls**:

```text
untrusted RFQ email
        ↓
bounded LLM extraction
        ↓
Pydantic structured output
        ↓
validation
        ↓
deterministic matching
        ↓
deterministic business rules
        ↓
deterministic pricing
        ↓
READY_FOR_QUOTE or REVIEW_REQUIRED
```

- Critical business values remain outside the model's authority.
- The decision not to add an external guardrail model was made **after
  evaluation**, not by assumption.

---

## Evidence

A dedicated adversarial evaluation set was created to test attempts to
manipulate:

- product references
- quantities
- prices
- discounts
- stock
- pack sizes
- substitution requests
- delivery constraints

The recorded adversarial evaluation contained **15 cases**:

| Metric                   | Value  |
| ------------------------ | ------ |
| Cases                    | 15     |
| Expected automations     | 9      |
| Actual automations       | 9      |
| Correct automations      | 9      |
| Correct reviews          | 6      |
| Unsafe automations       | **0**  |
| Auto-decision error rate | 0.0%   |
| Exact case pass rate     | 100.0% |

The adversarial suite was then repeated **three consecutive times**. The safety
result remained `Unsafe automations = 0`.

> This does not prove that prompt injection is impossible. It only shows that,
> for the current V1 architecture and evaluated attack set, no tested attack
> produced an unsafe automatic business decision.

---

## Alternatives considered

### 1. Add a dedicated prompt-injection classifier

**Not selected for V1.**

A classifier could identify suspicious text, but classification alone would
not guarantee safe downstream business behavior. It would also introduce
another probabilistic component requiring its own thresholds, evaluation set,
latency monitoring, and failure policy.

### 2. Add a Hugging Face guardrail model

**Not selected for V1.**

The additional dependency and operational complexity are not currently
justified by measured failures. This option remains open if future evaluations
reveal attack classes that the current architecture cannot safely contain.

### 3. Block all suspicious-looking instructions with rules

**Not selected as a general solution.**

Natural-language RFQs may legitimately contain unusual wording. Broad blocking
rules could create significant false positives without addressing the
underlying authority problem.

### 4. Rely only on the system prompt

**Rejected as a sufficient security strategy.**

Prompt instructions are useful but are not treated as a hard security
boundary. The primary protection comes from architectural constraints and
deterministic downstream validation.

---

## Consequences

### Positive

- No unnecessary inference service is added.
- Latency and cost remain low.
- The architecture stays easier to operate and explain.
- Critical business safety does not depend on a second probabilistic model.
- Guardrail complexity can be introduced later based on measured need.
- The project demonstrates evaluation-driven technology selection.

### Negative

- Some malicious or irrelevant input may still reach the extraction model.
- The system does not claim comprehensive prompt-injection detection.
- Future attack patterns may reveal weaknesses not present in the current
  evaluation set.
- Adversarial evaluations must continue as the system evolves.

---

## Reconsideration criteria

This decision should be revisited if evaluation demonstrates that adversarial
input can cause unacceptable behavior, for example:

- unsafe automatic product selection;
- incorrect quantities reaching pricing;
- business constraints being bypassed;
- meaningful increases in unsafe automation rate;
- new input channels with higher attack exposure.

> An external guardrail should be added only if it provides **measurable risk
> reduction** that justifies its operational cost.

---

## Result

RFQ Intelligence V1 uses **architecture and deterministic validation** as its
primary safety boundary rather than adding another AI model by default.

> **Guiding principle:** add guardrails because evaluation reveals a risk, not
> because a guardrail framework exists.

---

## Related decisions

- [ADR-001 — Restrict the LLM to structured extraction](ADR-001-restrict-llm-to-structured-extraction.md)
- [ADR-002 — Keep pricing and business rules deterministic](002-deterministic-business-rules.md)
- [ADR-003 — Prefer abstention over forced automation](003-abstention-over-forced-automation.md)
