from dataclasses import dataclass
from decimal import Decimal

from rfq_intelligence.rfq_processing import (
    RFQProcessingResult,
    RFQProcessingStatus,
)


@dataclass(frozen=True, slots=True)
class QuoteSummary:
    subtotal_eur: Decimal
    line_count: int


def build_quote_summary(result: RFQProcessingResult) -> QuoteSummary:
    if result.status != RFQProcessingStatus.READY_FOR_QUOTE:
        raise ValueError("Cannot build quote summary from an RFQ that requires review.")

    subtotals: list[Decimal] = []

    for item in result.lines:
        if item.processing is None or item.processing.price is None:
            raise ValueError("READY_FOR_QUOTE RFQ contains an unpriced line.")

        subtotals.append(item.processing.price.subtotal_eur)

    return QuoteSummary(
        subtotal_eur=sum(subtotals, start=Decimal("0.00")),
        line_count=len(subtotals),
    )
