# ADR-003 — Prefer abstention over forced automation

| Field  | Value      |
| ------ | ---------- |
| Status | Accepted   |
| Date   | 2026-10-15 |

---

## Context

RFQ Intelligence processes requests that may contain incomplete, ambiguous,
contradictory, or operationally unsafe information.

Examples include:

- unknown products;
- ambiguous product descriptions;
- missing quantities;
- missing units;
- insufficient stock;
- pack-size conflicts;
- substitution requests;
- unverified delivery constraints;
- contradictory product attributes.

A system optimized only for automation rate could attempt to infer, guess, or
silently repair these cases.

That would increase **apparent** automation coverage, but it would also
increase the risk of preparing incorrect quotations.

---

## Decision

RFQ Intelligence **explicitly supports abstention**.

When the system does not have enough evidence to safely prepare the request,
it returns `REVIEW_REQUIRED` rather than forcing a product match, business
decision, or quotation.

### Reason codes

The system uses explicit reason codes to explain why review is required:

| Reason code                      | Meaning                                    |
| -------------------------------- | ------------------------------------------ |
| `CUSTOMER_NOT_FOUND`             | Sender does not match a known customer     |
| `INACTIVE_CUSTOMER`              | Customer exists but is inactive            |
| `MISSING_QUANTITY`               | No quantity could be extracted             |
| `MISSING_UNIT`                   | No unit could be extracted                 |
| `AMBIGUOUS`                      | Several plausible product candidates       |
| `NOT_FOUND`                      | No acceptable product candidate            |
| `INSUFFICIENT_STOCK`             | Requested quantity exceeds available stock |
| `PACK_SIZE_MISMATCH`             | Quantity incompatible with pack size       |
| `SUBSTITUTION_REQUESTED`         | Customer asks for a substitute product     |
| `DELIVERY_CONSTRAINT_UNVERIFIED` | Delivery requirement cannot be verified    |

### Objective

The objective is **not**:

```text
maximize automatic decisions
```

but:

```text
maximize useful automation
subject to controlled business risk
```

### Automation policy

Automatic quotation preparation requires sufficient evidence across the
**entire** processing chain:

```text
  valid customer
+ valid extraction
+ acceptable product match
+ valid business conditions
+ deterministic pricing
─────────────────────────────
= READY_FOR_QUOTE
```

If any required condition is not satisfied, the result is `REVIEW_REQUIRED`.

> A review decision is a normal and expected business outcome. It is not
> treated as a model failure or application error.

---

## Alternatives considered

### 1. Force the best available match

**Rejected.**

A highest-scoring candidate is not necessarily the correct product. Similarity
scores are ranking signals, not calibrated guarantees of correctness. Forcing
the best candidate would convert uncertainty into hidden business risk.

### 2. Ask the LLM to resolve ambiguous cases

**Rejected as the default V1 behavior.**

The model could provide an opinion, but it would not create stronger business
evidence. Ambiguity should remain visible unless additional trusted
information is available.

### 3. Lower matching thresholds to increase automation coverage

**Rejected.**

Thresholds should be changed because evaluation demonstrates a useful
trade-off, not because a higher automation percentage looks better.

### 4. Automatically repair incomplete RFQs

**Rejected for critical fields.**

The system may normalize known representations, but it must not invent missing
quantities, product references, units, or business constraints.

---

## Consequences

### Positive

- Uncertainty remains explicit.
- Unsafe guesses are less likely to become quotations.
- Human review is integrated into the normal workflow.
- Evaluation can measure automation coverage separately from safety.
- Matching thresholds do not need to pretend to be probabilities.
- The system can improve automation gradually without changing its safety
  model.
- Business users receive reason codes explaining why intervention is required.

### Negative

- Automation coverage is intentionally lower than the theoretical maximum.
- Some requests that a human could resolve quickly are still escalated.
- Operational deployment requires a human-review process outside the current
  V1.
- Conservative rules may create false reviews.

---

## Evaluation implications

RFQ Intelligence reports several metrics **separately**:

- automation coverage
- correct automations
- correct review decisions
- wrong reviews
- unsafe automations
- auto-decision error rate
- exact case pass rate

These metrics must not be collapsed into a single accuracy number, because
errors do not carry the same cost:

| Error type                                       | Effect                       | Severity        |
| ------------------------------------------------ | ---------------------------- | --------------- |
| `REVIEW_REQUIRED` on an automatable case         | Reduces useful automation    | Undesirable     |
| Incorrect `READY_FOR_QUOTE`                      | Can create business risk     | **More serious** |

The evaluation framework therefore treats **unsafe automation** as a distinct
outcome.

---

## Result

RFQ Intelligence is designed as a **selective automation system** rather than
a system that must always produce an answer.

> **Guiding principle:** when evidence is insufficient, expose uncertainty
> instead of hiding it behind a confident automatic decision.

---

## Related decisions

- [ADR-001 — Restrict the LLM to structured extraction](ADR-001-restrict-llm-to-structured-extraction.md)
- [ADR-002 — Keep pricing and business rules deterministic](002-deterministic-business-rules.md)
