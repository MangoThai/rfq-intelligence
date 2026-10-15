from decimal import Decimal

from rfq_intelligence.decision import (
    LineDecisionStatus,
    ReviewReason,
    assess_line,
)
from rfq_intelligence.product import Product
from rfq_intelligence.rfq import RFQLine


def make_product(
    *,
    sales_unit: str = "piece",
    pack_size: int = 1,
    stock_qty: int = 100,
    active: bool = True,
) -> Product:
    return Product(
        sku="TEST-001",
        name="Test product",
        family="valve",
        material="brass",
        thread_type="G",
        thread_size="1/2",
        tube_outer_mm=None,
        tube_inner_mm=None,
        color=None,
        profile=None,
        connection_gender=None,
        sales_unit=sales_unit,  # type: ignore[arg-type]
        pack_size=pack_size,
        base_price_eur=Decimal("10.00"),
        stock_qty=stock_qty,
        lead_time_days=2,
        active=active,
    )


def test_assess_line_returns_ready_for_valid_request() -> None:
    product = make_product(stock_qty=100)
    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("20"),
        unit="piece",
    )

    result = assess_line(line, product)

    assert result.status == LineDecisionStatus.READY_FOR_QUOTE
    assert result.reasons == ()


def test_assess_line_requires_review_for_unit_mismatch() -> None:
    product = make_product(sales_unit="piece")
    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("20"),
        unit="meter",
    )

    result = assess_line(line, product)

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.reasons == (ReviewReason.UNIT_MISMATCH,)


def test_assess_line_requires_review_for_non_integer_piece_quantity() -> None:
    product = make_product()
    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("1.5"),
        unit="piece",
    )

    result = assess_line(line, product)

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert ReviewReason.NON_INTEGER_PIECE_QUANTITY in result.reasons


def test_assess_line_requires_review_for_pack_size_mismatch() -> None:
    product = make_product(
        sales_unit="meter",
        pack_size=25,
        stock_qty=500,
    )
    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("30"),
        unit="meter",
    )

    result = assess_line(line, product)

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.reasons == (ReviewReason.PACK_SIZE_MISMATCH,)


def test_assess_line_requires_review_for_insufficient_stock() -> None:
    product = make_product(
        sales_unit="meter",
        pack_size=25,
        stock_qty=50,
    )
    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("75"),
        unit="meter",
    )

    result = assess_line(line, product)

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.reasons == (ReviewReason.INSUFFICIENT_STOCK,)


def test_assess_line_can_return_multiple_review_reasons() -> None:
    product = make_product(
        sales_unit="meter",
        pack_size=25,
        stock_qty=20,
    )
    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("30"),
        unit="meter",
    )

    result = assess_line(line, product)

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.reasons == (
        ReviewReason.PACK_SIZE_MISMATCH,
        ReviewReason.INSUFFICIENT_STOCK,
    )


def test_assess_line_requires_review_for_inactive_product() -> None:
    product = make_product(active=False)
    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("10"),
        unit="piece",
    )

    result = assess_line(line, product)

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.reasons == (ReviewReason.INACTIVE_PRODUCT,)


def test_assess_line_requires_review_when_substitution_is_requested() -> None:
    product = make_product()

    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("10"),
        unit="piece",
        substitution_requested=True,
    )

    result = assess_line(line, product)

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.reasons == (ReviewReason.SUBSTITUTION_REQUESTED,)


def test_assess_line_requires_review_for_delivery_constraint() -> None:
    product = make_product()

    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("10"),
        unit="piece",
        delivery_constraint="demain matin",
    )

    result = assess_line(line, product)

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.reasons == (ReviewReason.DELIVERY_CONSTRAINT_UNVERIFIED,)
