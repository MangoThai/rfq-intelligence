# ADR-002 — Keep pricing and business rules deterministic

| Field  | Value      |
| ------ | ---------- |
| Status | Accepted   |
| Date   | 2026-10-15 |

---

## Context

RFQ Intelligence must decide whether an RFQ line can be prepared
automatically and, when it can, calculate the corresponding price.

These decisions depend on business-critical data such as:

- product activity status;
- customer activity status;
- requested sales unit;
- integer quantity requirements;
- pack-size constraints;
- available stock;
- substitution requests;
- delivery constraints;
- catalogue unit prices;
- customer discounts.

These values directly affect whether the system can prepare a valid
quotation.

Using probabilistic model output for these decisions would make the system
harder to **reason about**, **test**, **audit**, and **reproduce**.

---

## Decision

Business rules and pricing are implemented in **deterministic Python code**.

The LLM does **not** decide:

- whether stock is sufficient;
- whether a pack size is valid;
- whether a customer is active;
- whether a product is active;
- whether a substitution requires review;
- whether delivery constraints are verified;
- which discount applies;
- what the final unit price is;
- what the final subtotal is.

### Business rules

The system evaluates explicit rules over validated application data:

| Condition                          | Outcome           |
| ---------------------------------- | ----------------- |
| Inactive product                   | `REVIEW_REQUIRED` |
| Inactive customer                  | `REVIEW_REQUIRED` |
| Piece quantity is non-integer      | `REVIEW_REQUIRED` |
| Quantity conflicts with pack size  | `REVIEW_REQUIRED` |
| Insufficient stock                 | `REVIEW_REQUIRED` |
| Substitution requested             | `REVIEW_REQUIRED` |
| Unverified delivery constraint     | `REVIEW_REQUIRED` |

### Pricing

Pricing follows a deterministic sequence:

```text
catalogue unit price
        ↓
customer discount
        ↓
discounted unit price
        ↓
× quantity
        ↓
line subtotal
```

Monetary calculations use Python `Decimal`.

---

## Alternatives considered

### 1. Let the LLM calculate prices and totals

**Rejected.**

Language models can perform arithmetic, but they are not the correct source of
truth for financial calculations. Using the model would also make pricing
behavior harder to reproduce and test exactly.

### 2. Let the LLM decide business exceptions

**Rejected for V1.**

The rules currently used by RFQ Intelligence are explicit and deterministic.
Encoding them directly in Python provides clearer behavior and better
auditability.

### 3. Store all business rules in prompts

**Rejected.**

Prompts are not an appropriate policy engine for critical business invariants.
A prompt change or model change could alter behavior without an intentional
application-level rule change.

### 4. Introduce a dedicated business-rules framework

**Not required for V1.**

The number and complexity of current rules do not justify adding a rules
engine or another framework. Simple typed Python code is easier to maintain
and test at this stage.

---

## Consequences

### Positive

- Pricing is reproducible.
- Financial calculations are testable with exact expected values.
- Business decisions do not change because of model variation.
- Rules can be reviewed independently from prompts.
- Critical values cannot be overridden by adversarial email content.
- Failures produce explicit reason codes.
- The architecture is easier to explain and audit.

### Negative

- Business-rule changes require code changes.
- Rule logic must be maintained explicitly.
- As the number of business rules grows, the current implementation may
  eventually require a more structured policy layer.

---

## Result

The language model may help interpret the RFQ, but deterministic application
code remains responsible for deciding whether the request can be safely
automated and for calculating all monetary values.

> **Guiding principle:** probabilistic extraction can inform the workflow, but
> deterministic code owns the business decision.

---

## Related decisions

- [ADR-001 — Restrict the LLM to structured extraction](ADR-001-restrict-llm-to-structured-extraction.md)
