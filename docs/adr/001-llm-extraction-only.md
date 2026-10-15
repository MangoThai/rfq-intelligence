# ADR-001 — Restrict the LLM to structured extraction

| Field  | Value      |
| ------ | ---------- |
| Status | Accepted   |
| Date   | 2026-10-15 |

---

## Context

RFQ Intelligence processes unstructured industrial RFQ emails.

A language model is useful for understanding variable natural-language
requests, including:

- product descriptions;
- product references;
- quantities;
- units;
- substitution requests;
- delivery constraints.

However, the system also handles business-critical information such as:

- catalogue prices;
- customer discounts;
- available stock;
- pack sizes;
- customer eligibility;
- quote totals;
- final automation decisions.

Allowing the language model to generate or modify these values would increase
the risk of **hallucinations**, **prompt injection**, and **inconsistent
business decisions**.

---

## Decision

The LLM is restricted to **structured extraction** from the RFQ email.

| The LLM **may extract**  | The LLM **does not determine or modify** |
| ------------------------ | ---------------------------------------- |
| `product_query`          | price                                    |
| `quantity`               | discount                                 |
| `unit`                   | stock                                    |
| `substitution_requested` | pack size                                |
| `delivery_constraint`    | customer eligibility                     |
|                          | business rules                           |
|                          | quote totals                             |

- The extraction output is constrained by a **Pydantic schema**.
- All business values are retrieved or calculated by **deterministic
  application code**.

The processing flow is therefore:

```text
RFQ email
    ↓
LLM structured extraction
    ↓
validation
    ↓
deterministic matching
    ↓
deterministic business rules
    ↓
deterministic pricing
```

---

## Alternatives considered

### 1. Let the LLM produce the complete quote

**Rejected.**

This would simplify orchestration but would give the model authority over
business-critical values and calculations. It would also make automated
evaluation and safety guarantees more difficult.

### 2. Give the LLM access to business tools

**Not required for V1.**

Tool calling could be useful in a future system, but the current workflow does
not require the model to decide when or how critical business data should be
retrieved. The application can invoke deterministic business logic directly.

### 3. Fully deterministic parsing without an LLM

**Rejected for the current use case.**

RFQ emails contain enough linguistic variation that natural-language
extraction provides useful value. The goal is therefore not to remove the LLM,
but to restrict it to the part of the problem where language understanding is
actually needed.

---

## Consequences

### Positive

- Critical business invariants remain deterministic.
- Prompt injection has limited authority over business data.
- Pricing and stock behavior can be unit tested precisely.
- Model changes have less impact on downstream business rules.
- The system can abstain after extraction if evidence is insufficient.
- Evaluation can distinguish extraction quality from business safety.

### Negative

- The application requires more orchestration code.
- Extracted model output must be validated and converted into domain objects.
- Some decisions that an LLM could theoretically make are deliberately
  implemented in Python instead.

---

## Result

This architecture makes the LLM a **bounded component** rather than the
decision authority of the application.

> **Guiding principle:** use the LLM for language uncertainty, not for
> business invariants.
