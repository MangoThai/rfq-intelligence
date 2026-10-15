from collections.abc import Sequence
from dataclasses import dataclass

from rfq_intelligence.customer import Customer
from rfq_intelligence.decision import (
    LineDecision,
    LineDecisionStatus,
    ReviewReason,
    assess_line,
)
from rfq_intelligence.matching import MatchResult, match_sku
from rfq_intelligence.pricing import LinePrice, calculate_line_price
from rfq_intelligence.product import Product
from rfq_intelligence.rfq import RFQLine


@dataclass(frozen=True, slots=True)
class LineProcessingResult:
    status: LineDecisionStatus
    match: MatchResult
    decision: LineDecision | None
    price: LinePrice | None


def process_line(
    line: RFQLine,
    products: Sequence[Product],
    customer: Customer,
) -> LineProcessingResult:
    match = match_sku(line.product_query, products)

    if match.product is None:
        return LineProcessingResult(
            status=LineDecisionStatus.REVIEW_REQUIRED,
            match=match,
            decision=None,
            price=None,
        )

    product_decision = assess_line(line, match.product)
    reasons = list(product_decision.reasons)

    if not customer.active:
        reasons.append(ReviewReason.INACTIVE_CUSTOMER)

    if reasons:
        decision = LineDecision(
            status=LineDecisionStatus.REVIEW_REQUIRED,
            reasons=tuple(reasons),
        )

        return LineProcessingResult(
            status=LineDecisionStatus.REVIEW_REQUIRED,
            match=match,
            decision=decision,
            price=None,
        )

    decision = LineDecision(
        status=LineDecisionStatus.READY_FOR_QUOTE,
        reasons=(),
    )

    price = calculate_line_price(
        line=line,
        product=match.product,
        customer=customer,
    )

    return LineProcessingResult(
        status=LineDecisionStatus.READY_FOR_QUOTE,
        match=match,
        decision=decision,
        price=price,
    )
