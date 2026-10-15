from decimal import Decimal

import pytest

from rfq_intelligence.customer import Customer
from rfq_intelligence.extraction import ExtractedRFQLine
from rfq_intelligence.extraction_adapter import RFQLineConversion
from rfq_intelligence.processing import process_line
from rfq_intelligence.product import Product
from rfq_intelligence.quote import build_quote_summary
from rfq_intelligence.rfq import RFQLine
from rfq_intelligence.rfq_processing import (
    ProcessedRFQLine,
    RFQProcessingResult,
    RFQProcessingStatus,
)


def make_product(
    sku: str,
    base_price_eur: Decimal,
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
        sales_unit="piece",
        pack_size=1,
        base_price_eur=base_price_eur,
        stock_qty=100,
        lead_time_days=2,
        active=True,
    )


def make_customer() -> Customer:
    return Customer(
        customer_id="CUST-002",
        company_name="MecaPro Industrie",
        price_tier="PRO",
        discount_pct=Decimal("7.5"),
        payment_terms="30 days",
        active=True,
    )


def make_processed_line(
    *,
    sku: str,
    quantity: Decimal,
    base_price_eur: Decimal,
) -> ProcessedRFQLine:
    product = make_product(
        sku=sku,
        base_price_eur=base_price_eur,
    )

    line = RFQLine(
        product_query=sku,
        quantity=quantity,
        unit="piece",
    )

    processing = process_line(
        line=line,
        products=[product],
        customer=make_customer(),
    )

    conversion = RFQLineConversion(
        extracted=ExtractedRFQLine(
            product_query=sku,
            quantity=str(quantity),
            unit="piece",
        ),
        line=line,
        issues=(),
    )

    return ProcessedRFQLine(
        conversion=conversion,
        processing=processing,
    )


def test_build_quote_summary_returns_total() -> None:
    result = RFQProcessingResult(
        status=RFQProcessingStatus.READY_FOR_QUOTE,
        lines=(
            make_processed_line(
                sku="VAN-BR-050",
                quantity=Decimal("20"),
                base_price_eur=Decimal("12.80"),
            ),
            make_processed_line(
                sku="RAC-G14-06",
                quantity=Decimal("25"),
                base_price_eur=Decimal("3.20"),
            ),
        ),
    )

    summary = build_quote_summary(result)

    assert summary.line_count == 2
    assert summary.subtotal_eur == Decimal("310.80")


def test_build_quote_summary_rejects_rfq_requiring_review() -> None:
    result = RFQProcessingResult(
        status=RFQProcessingStatus.REVIEW_REQUIRED,
        lines=(),
    )

    with pytest.raises(
        ValueError,
        match="requires review",
    ):
        build_quote_summary(result)
