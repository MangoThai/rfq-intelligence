from decimal import Decimal

from rfq_intelligence.customer import Customer
from rfq_intelligence.decision import LineDecisionStatus, ReviewReason
from rfq_intelligence.matching import MatchStatus
from rfq_intelligence.processing import process_line
from rfq_intelligence.product import Product
from rfq_intelligence.rfq import RFQLine


def make_product(
    *,
    sku: str,
    sales_unit: str = "piece",
    pack_size: int = 1,
    stock_qty: int = 100,
    base_price_eur: Decimal = Decimal("10.00"),
) -> Product:
    return Product(
        sku=sku,
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
        base_price_eur=base_price_eur,
        stock_qty=stock_qty,
        lead_time_days=2,
        active=True,
    )


def make_customer(
    *,
    discount_pct: Decimal = Decimal("0"),
    active: bool = True,
) -> Customer:
    return Customer(
        customer_id="CUST-001",
        company_name="Test Customer",
        price_tier="STANDARD",
        discount_pct=discount_pct,
        payment_terms="30 days",
        active=active,
    )


def test_process_line_returns_ready_for_quote() -> None:
    products = [
        make_product(
            sku="VAN-BR-050",
            base_price_eur=Decimal("12.80"),
        )
    ]
    customer = make_customer(discount_pct=Decimal("7.5"))

    line = RFQLine(
        product_query="van br 050",
        quantity=Decimal("20"),
        unit="piece",
    )

    result = process_line(
        line=line,
        products=products,
        customer=customer,
    )

    assert result.status == LineDecisionStatus.READY_FOR_QUOTE
    assert result.match.status == MatchStatus.MATCHED
    assert result.match.product is products[0]
    assert result.decision is not None
    assert result.decision.reasons == ()
    assert result.price is not None

    assert result.price.catalog_unit_price_eur == Decimal("12.80")
    assert result.price.discount_pct == Decimal("7.5")
    assert result.price.unit_price_eur == Decimal("11.84")
    assert result.price.subtotal_eur == Decimal("236.80")


def test_process_line_requires_review_when_product_is_not_found() -> None:
    products = [make_product(sku="VAN-BR-050")]
    customer = make_customer()

    line = RFQLine(
        product_query="UNKNOWN-999",
        quantity=Decimal("10"),
        unit="piece",
    )

    result = process_line(
        line=line,
        products=products,
        customer=customer,
    )

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.match.status == MatchStatus.NOT_FOUND
    assert result.match.product is None
    assert result.decision is None
    assert result.price is None


def test_process_line_requires_review_when_match_is_ambiguous() -> None:
    products = [
        make_product(sku="ABC-123"),
        make_product(sku="ABC123"),
    ]
    customer = make_customer()

    line = RFQLine(
        product_query="abc 123",
        quantity=Decimal("10"),
        unit="piece",
    )

    result = process_line(
        line=line,
        products=products,
        customer=customer,
    )

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.match.status == MatchStatus.AMBIGUOUS
    assert result.match.product is None
    assert result.match.candidates == (products[0], products[1])
    assert result.decision is None
    assert result.price is None


def test_process_line_requires_review_when_business_rule_blocks_quote() -> None:
    products = [
        make_product(
            sku="TUB-PU-BL-064",
            sales_unit="meter",
            pack_size=25,
            stock_qty=500,
            base_price_eur=Decimal("1.35"),
        )
    ]
    customer = make_customer()

    line = RFQLine(
        product_query="TUB-PU-BL-064",
        quantity=Decimal("30"),
        unit="meter",
    )

    result = process_line(
        line=line,
        products=products,
        customer=customer,
    )

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.match.status == MatchStatus.EXACT_MATCH
    assert result.decision is not None
    assert result.decision.reasons == (ReviewReason.PACK_SIZE_MISMATCH,)
    assert result.price is None


def test_process_line_requires_review_for_inactive_customer() -> None:
    products = [make_product(sku="VAN-BR-050")]
    customer = make_customer(active=False)

    line = RFQLine(
        product_query="VAN-BR-050",
        quantity=Decimal("10"),
        unit="piece",
    )

    result = process_line(
        line=line,
        products=products,
        customer=customer,
    )

    assert result.status == LineDecisionStatus.REVIEW_REQUIRED
    assert result.decision is not None
    assert result.decision.reasons == (ReviewReason.INACTIVE_CUSTOMER,)
    assert result.price is None
