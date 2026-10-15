# RFQ Intelligence — Evaluation Results

## Table of contents

1. [Purpose](#1-purpose)
2. [Evaluation layers](#2-evaluation-layers)
3. [Matching evaluation](#3-matching-evaluation)
4. [End-to-end RFQ evaluation](#4-end-to-end-rfq-evaluation)
5. [End-to-end OpenAI observability](#5-end-to-end-openai-observability)
6. [Adversarial evaluation](#6-adversarial-evaluation)
7. [Adversarial stability](#7-adversarial-stability)
8. [Important metric definitions](#8-important-metric-definitions)
9. [What the evaluation supports](#9-what-the-evaluation-supports)
10. [What the evaluation does not support](#10-what-the-evaluation-does-not-support)
11. [Evaluation philosophy](#11-evaluation-philosophy)

---

## 1. Purpose

RFQ Intelligence is evaluated as a **selective automation system**.

The objective is not to maximize the number of automatic decisions. The
objective is to automate RFQs when evidence is sufficient while escalating
uncertain or unsafe cases to human review.

The most important distinction is therefore:

```text
automation coverage  ≠  automation safety
```

A system may automate many requests while making unsafe decisions.
Conversely, a conservative system may have lower coverage while keeping
business risk under control. RFQ Intelligence measures these outcomes
**separately**.

---

## 2. Evaluation layers

The V1 uses several complementary evaluation layers.

| Layer                 | Scope                                   | Uses OpenAI API |
| --------------------- | --------------------------------------- | --------------- |
| Unit tests            | Deterministic application behavior      | No              |
| Matching evaluation   | Product matching in isolation           | No              |
| End-to-end evaluation | Complete RFQ processing flow            | Yes             |
| Adversarial evaluation| Resistance to manipulative email content| Yes             |

### 2.1 Unit tests

Unit tests cover deterministic application behavior, including:

- catalogue loading;
- product normalization;
- product matching;
- extraction adaptation;
- business decisions;
- pricing;
- quote aggregation;
- customer resolution;
- observability;
- FastAPI response mapping;
- HTTP error behavior.

> Unit tests do not call the OpenAI API.

### 2.2 Matching evaluation

Product matching is evaluated independently from the full RFQ pipeline. The
evaluation covers:

- exact SKUs;
- formatting variations;
- typographical errors;
- catalogue descriptions;
- structured product attributes;
- ambiguity;
- unknown products;
- contradictory product information.

This allows matching behavior to be measured **without introducing LLM
variation**.

### 2.3 End-to-end RFQ evaluation

The end-to-end evaluation exercises the complete processing flow using the
real OpenAI API:

```text
RFQ email
    ↓
customer resolution
    ↓
OpenAI structured extraction
    ↓
validation
    ↓
product matching
    ↓
business rules
    ↓
pricing
    ↓
global RFQ decision
```

### 2.4 Adversarial evaluation

The adversarial dataset tests whether untrusted email content can alter
critical business behavior. The tested attacks attempt to influence:

- product references;
- quantities;
- catalogue prices;
- customer discounts;
- stock;
- pack sizes;
- substitutions;
- delivery constraints.

> The primary safety metric is **unsafe automations**.

---

## 3. Matching evaluation

### 3.1 Generated regression set

A deterministic matching dataset contains **211 cases** covering the
categories `EXACT_SKU`, `FORMATTING`, `TYPO`, `DESCRIPTION`, `AMBIGUOUS`, and
`UNKNOWN`.

| Metric             | Value  |
| ------------------ | ------ |
| Cases              | 211    |
| Passed             | 211    |
| Unsafe automations | **0**  |
| Pass rate          | 100.0% |

This dataset is mainly useful as a **regression suite**.

### 3.2 Calibration set

A separate realistic matching calibration set contains **28 product queries**.

| Metric              | Value  |
| ------------------- | ------ |
| Cases               | 28     |
| Passed              | 28     |
| Automated matches   | 18     |
| Unsafe automations  | **0**  |
| Automation coverage | 64.3%  |
| Pass rate           | 100.0% |

The remaining cases are intentionally ambiguous or non-automatable.

### 3.3 Matching test set

A **40-case** matching test set was used to evaluate:

- exact product references;
- descriptions;
- attribute combinations;
- ambiguity;
- unknown products;
- contradictory product information.

Recorded result after the current matcher implementation:

| Metric                | Value  |
| --------------------- | ------ |
| Cases                 | 40     |
| Passed                | 40     |
| Automated matches     | 21     |
| Unsafe automations    | **0**  |
| Automation coverage   | 52.5%  |
| Auto-match error rate | 0.0%   |
| Pass rate             | 100.0% |

### 3.4 Methodological note

> ⚠️ The 40-case set should **not** be presented as a permanently untouched
> holdout set.

During development, it exposed a weakness involving contradictions between an
explicit SKU and product attributes. That weakness was corrected and the
dataset was rerun. The dataset is therefore now best treated as a **strong
regression set** for the current matcher.

This distinction matters: a corrected test result is useful engineering
evidence, but it is not equivalent to performance on a new, unseen benchmark.

---

## 4. End-to-end RFQ evaluation

The development end-to-end dataset contains **16 RFQ scenarios**, including:

- exact product references;
- normalized product references;
- multi-line RFQs;
- unknown customers;
- inactive customers;
- missing quantities;
- unknown products;
- pack-size conflicts;
- insufficient stock;
- fuzzy product references;
- ambiguous products;
- mixed valid and invalid lines;
- empty RFQs;
- substitution requests;
- delivery constraints.

| Metric                   | Value  |
| ------------------------ | ------ |
| Cases                    | 16     |
| Exact case passes        | 16     |
| Expected automations     | 4      |
| Actual automations       | 4      |
| Correct automations      | 4      |
| Correct review decisions | 12     |
| Wrong reviews            | 0      |
| Unsafe automations       | **0**  |
| Automation coverage      | 25.0%  |
| Auto-decision error rate | 0.0%   |
| Exact case pass rate     | 100.0% |

These results demonstrate that the system correctly separates automatable
RFQs from cases requiring review in the current evaluation set.

> They do **not** imply that a 25% automation rate is an optimal production
> target. The current dataset intentionally contains many difficult and
> non-automatable cases.

---

## 5. End-to-end OpenAI observability

The recorded 16-case evaluation produced:

| Metric                | Value       |
| --------------------- | ----------- |
| Evaluated requests    | 16          |
| Model calls           | 14          |
| Skipped model calls   | 2           |
| Model call rate       | 87.5%       |
| Total input tokens    | 8,704       |
| Total output tokens   | 709         |
| Total tokens          | 9,413       |
| Average tokens / call | 672.4       |
| Average latency       | ~2.5 s      |
| P95 latency           | ~8.7 s      |
| Total estimated cost  | ~$0.001225  |
| Average cost / call   | ~$0.0000875 |

### 5.1 Skipped model calls

The two skipped model calls correspond to requests rejected deterministically
**before extraction**:

- unknown customer;
- inactive customer.

This is intentional: the application avoids model usage when the request
cannot proceed regardless of extraction quality.

### 5.2 P95 interpretation

The recorded p95 latency should be interpreted cautiously. Only 14 model calls
were present in this run; with such a small sample, the nearest-rank p95 is
effectively dominated by the slowest call.

> The value is useful as an observed datapoint, not as a stable production
> latency estimate.

---

## 6. Adversarial evaluation

The adversarial dataset contains **15 RFQs** designed to test whether
untrusted email instructions can influence critical behavior. Examples include
attempts to:

- replace a requested SKU;
- change quantity;
- force an incorrect catalogue price;
- force a 90% customer discount;
- change a product reference;
- create an additional RFQ line;
- remove a real RFQ line;
- hide a delivery constraint;
- hide a substitution request;
- invent additional stock;
- override pack size.

### 6.1 Decision results

| Metric                   | Value  |
| ------------------------ | ------ |
| Cases                    | 15     |
| Exact case passes        | 15     |
| Expected automations     | 9      |
| Actual automations       | 9      |
| Correct automations      | 9      |
| Correct review decisions | 6      |
| Wrong reviews            | 0      |
| Unsafe automations       | **0**  |
| Automation coverage      | 60.0%  |
| Auto-decision error rate | 0.0%   |
| Exact case pass rate     | 100.0% |

### 6.2 Observed OpenAI usage

| Metric                | Value       |
| --------------------- | ----------- |
| Model calls           | 15          |
| Total input tokens    | 9,610       |
| Total output tokens   | 689         |
| Total tokens          | 10,299      |
| Average tokens / call | 686.6       |
| Average latency       | 1,732 ms    |
| P95 latency           | 2,424 ms    |
| Total estimated cost  | $0.00130550 |
| Average cost / call   | $0.00008703 |

---

## 7. Adversarial stability

Because model extraction is probabilistic, the adversarial suite was repeated
**three consecutive times**. The safety outcome remained
`Unsafe automations = 0` across all three runs.

This provides additional evidence that the observed safety behavior was not
limited to one isolated model response.

> It does not establish a formal security guarantee.

---

## 8. Important metric definitions

### Automation coverage

Percentage of evaluated RFQs automatically classified as `READY_FOR_QUOTE`.

Higher coverage is not automatically better: it must be interpreted together
with the error rate.

### Wrong review

A case expected to be safely automatable but returned as `REVIEW_REQUIRED`.

This reduces automation value but does **not** create an incorrect automatic
quotation.

### Unsafe automation

A case automatically returned as `READY_FOR_QUOTE` when:

- the expected business outcome was review; **or**
- critical automated business content, such as product or price, was
  incorrect.

> This is the **primary safety failure mode**.

### Auto-decision error rate

```text
                         unsafe automations
auto-decision error rate = ──────────────────
                         actual automations
```

This measures the error rate among the cases the system **chose** to automate.

### Exact case pass

The complete observed output matches the expected evaluation case.

This metric is **stricter than business safety**. For example, two matching
methods may identify the same correct product while differing in their exact
internal matching status. Such a case can fail an exact comparison without
producing unsafe business behavior.

### Summary

| Metric                   | Measures                              | Higher is better? |
| ------------------------ | ------------------------------------- | ----------------- |
| Automation coverage      | Share of RFQs automated               | Only if safe      |
| Wrong reviews            | Missed automation opportunities       | No                |
| Unsafe automations       | Incorrect automatic decisions         | No — must be 0    |
| Auto-decision error rate | Error rate among automated decisions  | No                |
| Exact case pass rate     | Strict match with expected output     | Yes               |

---

## 9. What the evaluation supports

The current results support the following statements:

- ✅ Deterministic pricing prevented tested prompt attempts from changing
  prices and discounts.
- ✅ Deterministic stock and pack-size rules prevented tested email
  instructions from overriding those constraints.
- ✅ Unknown and inactive customers can be rejected before model usage.
- ✅ The current matcher handles the tested catalogue variations and
  contradictions.
- ✅ The system successfully abstains on the tested ambiguous and unsafe
  cases.
- ✅ No unsafe automation was observed in the current end-to-end and
  adversarial datasets.
- ✅ Model cost is negligible for the current text-only RFQ workload.
- ✅ OpenAI latency is materially larger than the deterministic processing
  time and is therefore the main latency component.

---

## 10. What the evaluation does not support

The current results do **not** justify claims such as:

- ❌ "The system is 100% accurate."
- ❌ "Prompt injection has been solved."
- ❌ "The system can safely process arbitrary industrial catalogues."
- ❌ "The system will always produce zero unsafe automations."
- ❌ "The current latency figures represent production-scale performance."

Context for these limits:

- the datasets remain intentionally small and synthetic;
- the catalogue contains only 16 products;
- the customer base is fictional;
- the system currently processes French text emails only.

---

## 11. Evaluation philosophy

RFQ Intelligence follows several evaluation principles:

1. **Measure business outcomes**, not only model outputs.
2. **Separate automation coverage** from automation safety.
3. **Treat review as a valid outcome.**
4. **Treat unsafe automation as a distinct failure class.**
5. **Do not interpret similarity scores as probabilities.**
6. **Use failed cases** to improve the system.
7. **Turn discovered weaknesses** into regression tests.
8. **Distinguish architectural guarantees** from experimental observations.

> The objective is not to prove that the system cannot fail. The objective is
> to make failure modes **visible, measurable, and increasingly controlled**.
