import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, Field

from rfq_intelligence.customer import Customer
from rfq_intelligence.customer_resolution import CustomerContact
from rfq_intelligence.extraction import DEFAULT_EXTRACTION_MODEL
from rfq_intelligence.observability import (
    ModelCallMetrics,
    ObservabilitySummary,
    summarize_model_metrics,
)
from rfq_intelligence.product import Product
from rfq_intelligence.quote import build_quote_summary
from rfq_intelligence.rfq_processing import (
    ProcessedRFQLine,
    RFQProcessingResult,
    RFQProcessingStatus,
    process_rfq_email,
)

ExpectedStatus = Literal[
    "READY_FOR_QUOTE",
    "REVIEW_REQUIRED",
]

ExpectedMatchStatus = Literal[
    "EXACT_MATCH",
    "MATCHED",
    "AMBIGUOUS",
    "NOT_FOUND",
]


class ExpectedLine(BaseModel):
    expected_sku: str | None = None
    expected_match_status: ExpectedMatchStatus | None = None
    expected_status: ExpectedStatus
    expected_reason_codes: list[str] = Field(default_factory=list)
    expected_subtotal_eur: Decimal | None = None


class ExpectedRFQ(BaseModel):
    status: ExpectedStatus
    customer_id: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    quote_total_eur: Decimal | None = None
    lines: list[ExpectedLine] = Field(default_factory=list)


class EvalCase(BaseModel):
    id: str
    description: str
    sender_email: str
    email_text: str
    expected: ExpectedRFQ


@dataclass(frozen=True, slots=True)
class EvalCaseResult:
    case_id: str
    description: str
    expected_status: ExpectedStatus
    actual_status: str | None

    passed: bool
    unsafe_automation: bool

    mismatches: tuple[str, ...]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    cases: tuple[EvalCaseResult, ...]

    total_cases: int
    passed_cases: int

    expected_automations: int
    actual_automations: int
    correct_automations: int
    correct_review_decisions: int

    wrong_reviews: int
    unsafe_automations: int

    automation_coverage: float
    auto_decision_error_rate: float
    case_pass_rate: float

    observability: ObservabilitySummary


def load_eval_cases(
    path: Path,
) -> list[EvalCase]:
    raw_data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw_data, list):
        raise ValueError("RFQ evaluation dataset must contain a JSON list.")

    return [EvalCase.model_validate(item) for item in raw_data]


def evaluate_cases(
    cases: Sequence[EvalCase],
    products: Sequence[Product],
    customers: Sequence[Customer],
    contacts: Sequence[CustomerContact],
    client: OpenAI,
    model: str = DEFAULT_EXTRACTION_MODEL,
) -> EvaluationReport:
    results: list[EvalCaseResult] = []

    model_metrics: list[ModelCallMetrics | None] = []

    for case in cases:
        try:
            result = process_rfq_email(
                email_text=case.email_text,
                sender_email=case.sender_email,
                products=products,
                customers=customers,
                contacts=contacts,
                client=client,
                model=model,
            )

            model_metrics.append(result.model_metrics)

            mismatches = _compare_case(
                case=case,
                result=result,
            )

            unsafe_automation = _has_unsafe_automation(
                case=case,
                result=result,
            )

            results.append(
                EvalCaseResult(
                    case_id=case.id,
                    description=case.description,
                    expected_status=case.expected.status,
                    actual_status=result.status.value,
                    passed=not mismatches,
                    unsafe_automation=unsafe_automation,
                    mismatches=tuple(mismatches),
                )
            )

        except Exception as exc:
            model_metrics.append(None)

            results.append(
                EvalCaseResult(
                    case_id=case.id,
                    description=case.description,
                    expected_status=case.expected.status,
                    actual_status=None,
                    passed=False,
                    unsafe_automation=False,
                    mismatches=(),
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    return _build_report(
        results=results,
        observability=summarize_model_metrics(model_metrics),
    )


def format_evaluation_report(
    report: EvaluationReport,
) -> str:
    observability = report.observability

    lines = [
        "RFQ INTELLIGENCE — END-TO-END EVALUATION",
        "=" * 64,
        "",
        "QUALITY & SAFETY",
        "-" * 64,
        f"Cases:                       {report.total_cases}",
        f"Exact case passes:           {report.passed_cases}",
        (f"Expected automations:        {report.expected_automations}"),
        (f"Actual automations:          {report.actual_automations}"),
        (f"Correct automations:         {report.correct_automations}"),
        (f"Correct review decisions:   {report.correct_review_decisions}"),
        (f"Wrong reviews:               {report.wrong_reviews}"),
        (f"Unsafe automations:          {report.unsafe_automations}"),
        "",
        (f"Automation coverage:         {report.automation_coverage:.1%}"),
        (f"Auto-decision error rate:    {report.auto_decision_error_rate:.1%}"),
        (f"Exact case pass rate:        {report.case_pass_rate:.1%}"),
        "",
        "OPENAI OBSERVABILITY",
        "-" * 64,
        (f"Evaluated requests:           {observability.total_requests}"),
        (f"Model calls:                  {observability.model_calls}"),
        (f"Skipped model calls:          {observability.skipped_model_calls}"),
        (f"Model call rate:              {observability.model_call_rate:.1%}"),
        "",
        (f"Total input tokens:           {observability.total_input_tokens}"),
        (f"Cached input tokens:          {observability.total_cached_input_tokens}"),
        (f"Cache-write tokens:           {observability.total_cache_write_tokens}"),
        (f"Total output tokens:          {observability.total_output_tokens}"),
        (f"Reasoning tokens:             {observability.total_reasoning_tokens}"),
        (f"Total tokens:                 {observability.total_tokens}"),
        "",
        (f"Average tokens / call:        {observability.average_tokens_per_call:.1f}"),
        (f"Average latency:              {observability.average_latency_ms:.0f} ms"),
        (f"P95 latency:                  {observability.p95_latency_ms:.0f} ms"),
        (f"Total estimated cost:         ${observability.total_cost_usd:.8f}"),
        (f"Average cost / call:          ${observability.average_cost_per_call_usd:.8f}"),
    ]

    failures = [result for result in report.cases if not result.passed]

    if failures:
        lines.extend(
            [
                "",
                "FAILURES",
                "-" * 64,
            ]
        )

        for result in failures:
            lines.append(f"{result.case_id} — {result.description}")

            lines.append(f"  expected status: {result.expected_status}")

            lines.append(f"  actual status:   {result.actual_status}")

            if result.unsafe_automation:
                lines.append("  !!! UNSAFE AUTOMATION !!!")

            if result.error is not None:
                lines.append(f"  error:           {result.error}")

            for mismatch in result.mismatches:
                lines.append(f"  - {mismatch}")

    return "\n".join(lines)


def _compare_case(
    case: EvalCase,
    result: RFQProcessingResult,
) -> list[str]:
    mismatches: list[str] = []

    expected = case.expected

    if result.status.value != expected.status:
        mismatches.append(f"RFQ status: expected {expected.status}, got {result.status.value}")

    actual_customer_id = result.customer.customer_id if result.customer is not None else None

    if actual_customer_id != expected.customer_id:
        mismatches.append(
            f"customer_id: expected {expected.customer_id!r}, got {actual_customer_id!r}"
        )

    actual_reason_codes = [issue.value for issue in result.issues]

    if actual_reason_codes != expected.reason_codes:
        mismatches.append(
            f"RFQ reason codes: expected {expected.reason_codes!r}, got {actual_reason_codes!r}"
        )

    if len(result.lines) != len(expected.lines):
        mismatches.append(f"line count: expected {len(expected.lines)}, got {len(result.lines)}")

    for index, (
        expected_line,
        actual_line,
    ) in enumerate(
        zip(
            expected.lines,
            result.lines,
            strict=False,
        ),
        start=1,
    ):
        mismatches.extend(
            _compare_line(
                index=index,
                expected=expected_line,
                actual=actual_line,
            )
        )

    actual_quote_total: Decimal | None = None

    if result.status == RFQProcessingStatus.READY_FOR_QUOTE:
        summary = build_quote_summary(result)

        actual_quote_total = summary.subtotal_eur

    if actual_quote_total != expected.quote_total_eur:
        mismatches.append(
            f"quote total: expected {expected.quote_total_eur!r}, got {actual_quote_total!r}"
        )

    return mismatches


def _compare_line(
    index: int,
    expected: ExpectedLine,
    actual: ProcessedRFQLine,
) -> list[str]:
    mismatches: list[str] = []

    conversion = actual.conversion
    processing = actual.processing

    if conversion.line is None:
        actual_status = "REVIEW_REQUIRED"
        actual_sku = None
        actual_match_status = None

        actual_reason_codes = [issue.value for issue in conversion.issues]

        actual_subtotal = None

    elif processing is None:
        actual_status = "REVIEW_REQUIRED"
        actual_sku = None
        actual_match_status = None
        actual_reason_codes = []
        actual_subtotal = None

    else:
        actual_status = processing.status.value

        actual_match_status = processing.match.status.value

        actual_sku = processing.match.product.sku if processing.match.product is not None else None

        actual_reason_codes = (
            [reason.value for reason in processing.decision.reasons]
            if processing.decision is not None
            else []
        )

        actual_subtotal = processing.price.subtotal_eur if processing.price is not None else None

    if actual_status != expected.expected_status:
        mismatches.append(
            f"line {index} status: expected {expected.expected_status}, got {actual_status}"
        )

    if actual_match_status != expected.expected_match_status:
        mismatches.append(
            f"line {index} match status: "
            f"expected "
            f"{expected.expected_match_status!r}, "
            f"got {actual_match_status!r}"
        )

    if actual_sku != expected.expected_sku:
        mismatches.append(
            f"line {index} SKU: expected {expected.expected_sku!r}, got {actual_sku!r}"
        )

    if actual_reason_codes != expected.expected_reason_codes:
        mismatches.append(
            f"line {index} reason codes: "
            f"expected "
            f"{expected.expected_reason_codes!r}, "
            f"got {actual_reason_codes!r}"
        )

    if actual_subtotal != expected.expected_subtotal_eur:
        mismatches.append(
            f"line {index} subtotal: "
            f"expected "
            f"{expected.expected_subtotal_eur!r}, "
            f"got {actual_subtotal!r}"
        )

    return mismatches


def _has_unsafe_automation(
    case: EvalCase,
    result: RFQProcessingResult,
) -> bool:
    if result.status != RFQProcessingStatus.READY_FOR_QUOTE:
        return False

    expected = case.expected

    # Automatisation alors qu'une revue humaine était attendue.
    if expected.status != "READY_FOR_QUOTE":
        return True

    actual_customer_id = result.customer.customer_id if result.customer is not None else None

    if actual_customer_id != expected.customer_id:
        return True

    if len(result.lines) != len(expected.lines):
        return True

    for expected_line, actual_line in zip(
        expected.lines,
        result.lines,
        strict=True,
    ):
        if expected_line.expected_status != "READY_FOR_QUOTE":
            return True

        processing = actual_line.processing

        if processing is None:
            return True

        actual_sku = processing.match.product.sku if processing.match.product is not None else None

        if actual_sku != expected_line.expected_sku:
            return True

        actual_subtotal = processing.price.subtotal_eur if processing.price is not None else None

        if actual_subtotal != expected_line.expected_subtotal_eur:
            return True

    summary = build_quote_summary(result)

    return summary.subtotal_eur != expected.quote_total_eur


def _build_report(
    results: Sequence[EvalCaseResult],
    observability: ObservabilitySummary,
) -> EvaluationReport:
    total_cases = len(results)

    passed_cases = sum(result.passed for result in results)

    expected_automations = sum(result.expected_status == "READY_FOR_QUOTE" for result in results)

    actual_automations = sum(result.actual_status == "READY_FOR_QUOTE" for result in results)

    correct_automations = sum(
        result.expected_status == "READY_FOR_QUOTE"
        and result.actual_status == "READY_FOR_QUOTE"
        and not result.unsafe_automation
        for result in results
    )

    correct_review_decisions = sum(
        result.expected_status == "REVIEW_REQUIRED" and result.actual_status == "REVIEW_REQUIRED"
        for result in results
    )

    wrong_reviews = sum(
        result.expected_status == "READY_FOR_QUOTE" and result.actual_status == "REVIEW_REQUIRED"
        for result in results
    )

    unsafe_automations = sum(result.unsafe_automation for result in results)

    automation_coverage = actual_automations / total_cases if total_cases else 0.0

    auto_decision_error_rate = (
        unsafe_automations / actual_automations if actual_automations else 0.0
    )

    case_pass_rate = passed_cases / total_cases if total_cases else 0.0

    return EvaluationReport(
        cases=tuple(results),
        total_cases=total_cases,
        passed_cases=passed_cases,
        expected_automations=expected_automations,
        actual_automations=actual_automations,
        correct_automations=correct_automations,
        correct_review_decisions=correct_review_decisions,
        wrong_reviews=wrong_reviews,
        unsafe_automations=unsafe_automations,
        automation_coverage=automation_coverage,
        auto_decision_error_rate=auto_decision_error_rate,
        case_pass_rate=case_pass_rate,
        observability=observability,
    )
