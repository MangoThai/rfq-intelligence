from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from rfq_intelligence.product import Product
from rfq_intelligence.rfq import RFQLine


class LineDecisionStatus(StrEnum):
    READY_FOR_QUOTE = "READY_FOR_QUOTE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ReviewReason(StrEnum):
    INACTIVE_PRODUCT = "INACTIVE_PRODUCT"
    INACTIVE_CUSTOMER = "INACTIVE_CUSTOMER"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    NON_INTEGER_PIECE_QUANTITY = "NON_INTEGER_PIECE_QUANTITY"
    PACK_SIZE_MISMATCH = "PACK_SIZE_MISMATCH"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    SUBSTITUTION_REQUESTED = "SUBSTITUTION_REQUESTED"
    DELIVERY_CONSTRAINT_UNVERIFIED = "DELIVERY_CONSTRAINT_UNVERIFIED"


@dataclass(frozen=True, slots=True)
class LineDecision:
    status: LineDecisionStatus
    reasons: tuple[ReviewReason, ...]


def assess_line(line: RFQLine, product: Product) -> LineDecision:
    reasons: list[ReviewReason] = []

    if line.substitution_requested:
        reasons.append(ReviewReason.SUBSTITUTION_REQUESTED)

    if line.delivery_constraint is not None:
        reasons.append(ReviewReason.DELIVERY_CONSTRAINT_UNVERIFIED)

    if not product.active:
        reasons.append(ReviewReason.INACTIVE_PRODUCT)

    if line.unit != product.sales_unit:
        reasons.append(ReviewReason.UNIT_MISMATCH)
    else:
        if line.unit == "piece" and line.quantity != line.quantity.to_integral_value():
            reasons.append(ReviewReason.NON_INTEGER_PIECE_QUANTITY)

        pack_size = Decimal(product.pack_size)

        if line.quantity % pack_size != 0:
            reasons.append(ReviewReason.PACK_SIZE_MISMATCH)

        if line.quantity > Decimal(product.stock_qty):
            reasons.append(ReviewReason.INSUFFICIENT_STOCK)

    if reasons:
        return LineDecision(
            status=LineDecisionStatus.REVIEW_REQUIRED,
            reasons=tuple(reasons),
        )

    return LineDecision(
        status=LineDecisionStatus.READY_FOR_QUOTE,
        reasons=(),
    )
