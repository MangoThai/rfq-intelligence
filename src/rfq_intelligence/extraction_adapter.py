from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from rfq_intelligence.extraction import ExtractedRFQ, ExtractedRFQLine
from rfq_intelligence.rfq import RFQLine


class ExtractionIssue(StrEnum):
    EMPTY_PRODUCT_QUERY = "EMPTY_PRODUCT_QUERY"
    MISSING_QUANTITY = "MISSING_QUANTITY"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    MISSING_UNIT = "MISSING_UNIT"


@dataclass(frozen=True, slots=True)
class RFQLineConversion:
    extracted: ExtractedRFQLine
    line: RFQLine | None
    issues: tuple[ExtractionIssue, ...]


def convert_extracted_line(extracted: ExtractedRFQLine) -> RFQLineConversion:
    issues: list[ExtractionIssue] = []

    product_query = extracted.product_query.strip()

    if not product_query:
        issues.append(ExtractionIssue.EMPTY_PRODUCT_QUERY)

    quantity = _parse_quantity(extracted.quantity)

    if extracted.quantity is None:
        issues.append(ExtractionIssue.MISSING_QUANTITY)
    elif quantity is None:
        issues.append(ExtractionIssue.INVALID_QUANTITY)

    if extracted.unit is None:
        issues.append(ExtractionIssue.MISSING_UNIT)

    if issues:
        return RFQLineConversion(
            extracted=extracted,
            line=None,
            issues=tuple(issues),
        )

    assert quantity is not None
    assert extracted.unit is not None

    line = RFQLine(
        product_query=product_query,
        quantity=quantity,
        unit=extracted.unit,
        substitution_requested=extracted.substitution_requested,
        delivery_constraint=extracted.delivery_constraint,
    )

    return RFQLineConversion(
        extracted=extracted,
        line=line,
        issues=(),
    )


def convert_extracted_rfq(extracted: ExtractedRFQ) -> list[RFQLineConversion]:
    return [convert_extracted_line(line) for line in extracted.lines]


def _parse_quantity(value: str | None) -> Decimal | None:
    if value is None:
        return None

    normalized = value.strip().replace(",", ".")

    try:
        quantity = Decimal(normalized)
    except InvalidOperation:
        return None

    if not quantity.is_finite() or quantity <= 0:
        return None

    return quantity
