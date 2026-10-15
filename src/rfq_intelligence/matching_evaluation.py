import json
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rfq_intelligence.matching import MatchStatus, match_sku
from rfq_intelligence.normalization import normalize_sku
from rfq_intelligence.product import Product


class MatchingCaseCategory(StrEnum):
    EXACT_SKU = "EXACT_SKU"
    FORMATTING = "FORMATTING"
    TYPO = "TYPO"
    DESCRIPTION = "DESCRIPTION"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class MatchingEvalCase:
    case_id: str
    category: MatchingCaseCategory
    query: str
    expected_status: MatchStatus
    expected_sku: str | None


@dataclass(frozen=True, slots=True)
class MatchingEvalResult:
    case: MatchingEvalCase
    actual_status: MatchStatus
    actual_sku: str | None
    passed: bool
    unsafe_automation: bool


@dataclass(frozen=True, slots=True)
class CategoryMetrics:
    category: MatchingCaseCategory
    total: int
    passed: int
    automated: int
    unsafe_automations: int


@dataclass(frozen=True, slots=True)
class MatchingEvaluationReport:
    results: tuple[MatchingEvalResult, ...]
    categories: tuple[CategoryMetrics, ...]
    total_cases: int
    passed_cases: int
    automated_cases: int
    unsafe_automations: int
    automation_coverage: float
    auto_match_error_rate: float
    pass_rate: float


def generate_matching_eval_cases(
    products: Sequence[Product],
) -> list[MatchingEvalCase]:
    cases: list[MatchingEvalCase] = []
    valid_normalized_skus = {normalize_sku(product.sku) for product in products}

    for index, product in enumerate(products, start=1):
        cases.append(
            MatchingEvalCase(
                case_id=f"EXACT-{index:03d}",
                category=MatchingCaseCategory.EXACT_SKU,
                query=product.sku,
                expected_status=MatchStatus.EXACT_MATCH,
                expected_sku=product.sku,
            )
        )

        for variant_index, query in enumerate(
            _formatting_variants(product.sku),
            start=1,
        ):
            cases.append(
                MatchingEvalCase(
                    case_id=f"FORMAT-{index:03d}-{variant_index:02d}",
                    category=MatchingCaseCategory.FORMATTING,
                    query=query,
                    expected_status=MatchStatus.MATCHED,
                    expected_sku=product.sku,
                )
            )

        typo = _make_controlled_typo(
            sku=product.sku,
            valid_normalized_skus=valid_normalized_skus,
        )

        if typo is not None:
            cases.append(
                MatchingEvalCase(
                    case_id=f"TYPO-{index:03d}",
                    category=MatchingCaseCategory.TYPO,
                    query=typo,
                    expected_status=MatchStatus.MATCHED,
                    expected_sku=product.sku,
                )
            )

        cases.append(
            MatchingEvalCase(
                case_id=f"DESC-{index:03d}",
                category=MatchingCaseCategory.DESCRIPTION,
                query=product.name,
                expected_status=MatchStatus.MATCHED,
                expected_sku=product.sku,
            )
        )

        cases.append(
            MatchingEvalCase(
                case_id=f"UNKNOWN-{index:03d}",
                category=MatchingCaseCategory.UNKNOWN,
                query=f"ZZZ-UNKNOWN-{index:03d}",
                expected_status=MatchStatus.NOT_FOUND,
                expected_sku=None,
            )
        )

    cases.extend(_ambiguous_cases())

    return cases


def evaluate_matching(
    cases: Sequence[MatchingEvalCase],
    products: Sequence[Product],
) -> MatchingEvaluationReport:
    results: list[MatchingEvalResult] = []

    for case in cases:
        match = match_sku(
            query=case.query,
            products=products,
        )

        actual_sku = match.product.sku if match.product is not None else None

        passed = match.status == case.expected_status and actual_sku == case.expected_sku

        automated = _is_automated(match.status)

        unsafe_automation = automated and (
            case.expected_sku is None or actual_sku != case.expected_sku
        )

        results.append(
            MatchingEvalResult(
                case=case,
                actual_status=match.status,
                actual_sku=actual_sku,
                passed=passed,
                unsafe_automation=unsafe_automation,
            )
        )

    category_metrics = tuple(
        _build_category_metrics(
            category=category,
            results=results,
        )
        for category in MatchingCaseCategory
    )

    total_cases = len(results)
    passed_cases = sum(result.passed for result in results)

    automated_cases = sum(_is_automated(result.actual_status) for result in results)

    unsafe_automations = sum(result.unsafe_automation for result in results)

    automation_coverage = automated_cases / total_cases if total_cases else 0.0

    auto_match_error_rate = unsafe_automations / automated_cases if automated_cases else 0.0

    pass_rate = passed_cases / total_cases if total_cases else 0.0

    return MatchingEvaluationReport(
        results=tuple(results),
        categories=category_metrics,
        total_cases=total_cases,
        passed_cases=passed_cases,
        automated_cases=automated_cases,
        unsafe_automations=unsafe_automations,
        automation_coverage=automation_coverage,
        auto_match_error_rate=auto_match_error_rate,
        pass_rate=pass_rate,
    )


def format_matching_evaluation_report(
    report: MatchingEvaluationReport,
) -> str:
    lines = [
        "RFQ INTELLIGENCE — MATCHING EVALUATION",
        "=" * 60,
        f"Cases:                   {report.total_cases}",
        f"Passed:                  {report.passed_cases}",
        f"Automated:               {report.automated_cases}",
        f"Unsafe automations:      {report.unsafe_automations}",
        "",
        f"Automation coverage:     {report.automation_coverage:.1%}",
        f"Auto-match error rate:   {report.auto_match_error_rate:.1%}",
        f"Pass rate:               {report.pass_rate:.1%}",
        "",
        "BY CATEGORY",
        "-" * 60,
    ]

    for metrics in report.categories:
        category_pass_rate = metrics.passed / metrics.total if metrics.total else 0.0

        lines.append(
            f"{metrics.category.value:<14} "
            f"cases={metrics.total:<4} "
            f"pass={category_pass_rate:>6.1%} "
            f"auto={metrics.automated:<4} "
            f"unsafe={metrics.unsafe_automations}"
        )

    failures = [result for result in report.results if not result.passed]

    if failures:
        lines.extend(
            [
                "",
                "FAILURES",
                "-" * 60,
            ]
        )

        for result in failures:
            lines.append(
                f"{result.case.case_id} [{result.case.category.value}] query={result.case.query!r}"
            )
            lines.append(
                f"  expected: {result.case.expected_status.value} {result.case.expected_sku!r}"
            )
            lines.append(f"  actual:   {result.actual_status.value} {result.actual_sku!r}")

            if result.unsafe_automation:
                lines.append("  !!! UNSAFE AUTOMATION !!!")

    return "\n".join(lines)


def _formatting_variants(sku: str) -> tuple[str, ...]:
    raw_variants = (
        sku.lower(),
        sku.replace("-", " "),
        sku.replace("-", "_"),
        sku.replace("-", ""),
        f"  {sku.lower()}  ",
        sku.replace("-", "."),
        sku.replace("-", "/"),
        sku.replace("-", "\t"),
        sku.replace("-", " -- "),
    )

    unique: list[str] = []

    for variant in raw_variants:
        if variant != sku and variant not in unique:
            unique.append(variant)

    return tuple(unique)


def _make_controlled_typo(
    sku: str,
    valid_normalized_skus: set[str],
) -> str | None:
    if "0" not in sku:
        return None

    typo = sku.replace("0", "O", 1)

    if normalize_sku(typo) in valid_normalized_skus:
        return None

    return typo


def _ambiguous_cases() -> list[MatchingEvalCase]:
    return [
        MatchingEvalCase(
            case_id="AMBIG-001",
            category=MatchingCaseCategory.AMBIGUOUS,
            query="vanne 1/2",
            expected_status=MatchStatus.AMBIGUOUS,
            expected_sku=None,
        ),
        MatchingEvalCase(
            case_id="AMBIG-002",
            category=MatchingCaseCategory.AMBIGUOUS,
            query="raccord droit G1/4",
            expected_status=MatchStatus.AMBIGUOUS,
            expected_sku=None,
        ),
        MatchingEvalCase(
            case_id="AMBIG-003",
            category=MatchingCaseCategory.AMBIGUOUS,
            query="tube 6 x 4 mm",
            expected_status=MatchStatus.AMBIGUOUS,
            expected_sku=None,
        ),
        MatchingEvalCase(
            case_id="AMBIG-004",
            category=MatchingCaseCategory.AMBIGUOUS,
            query="coupleur femelle G1/4",
            expected_status=MatchStatus.AMBIGUOUS,
            expected_sku=None,
        ),
    ]


def _build_category_metrics(
    category: MatchingCaseCategory,
    results: Sequence[MatchingEvalResult],
) -> CategoryMetrics:
    category_results = [result for result in results if result.case.category == category]

    return CategoryMetrics(
        category=category,
        total=len(category_results),
        passed=sum(result.passed for result in category_results),
        automated=sum(_is_automated(result.actual_status) for result in category_results),
        unsafe_automations=sum(result.unsafe_automation for result in category_results),
    )


def _is_automated(status: MatchStatus) -> bool:
    return status in {
        MatchStatus.EXACT_MATCH,
        MatchStatus.MATCHED,
    }


def load_matching_eval_cases(
    path: Path,
) -> list[MatchingEvalCase]:
    raw_data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(raw_data, list):
        raise ValueError("Matching evaluation dataset must contain a JSON list.")

    cases: list[MatchingEvalCase] = []

    for raw_case in raw_data:
        cases.append(
            MatchingEvalCase(
                case_id=raw_case["id"],
                category=MatchingCaseCategory.DESCRIPTION,
                query=raw_case["query"],
                expected_status=MatchStatus(raw_case["expected_status"]),
                expected_sku=raw_case["expected_sku"],
            )
        )

    return cases
