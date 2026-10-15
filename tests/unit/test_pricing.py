from decimal import Decimal

import pytest

from rfq_intelligence.pricing import calculate_line_price
from rfq_intelligence.product import Product
from rfq_intelligence.rfq import RFQLine


def make_product(
    *,
    sales_unit: str = "piece",
    base_price_eur: Decimal = Decimal("12.80"),
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
        pack_size=1,
        base_price_eur=base_price_eur,
        stock_qty=100,
        lead_time_days=2,
        active=True,
    )


def test_calculate_line_price_returns_expected_subtotal() -> None:
    product = make_product(base_price_eur=Decimal("12.80"))
    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("20"),
        unit="piece",
    )

    result = calculate_line_price(line, product)

    assert result.quantity == Decimal("20")
    assert result.unit_price_eur == Decimal("12.80")
    assert result.subtotal_eur == Decimal("256.00")


def test_calculate_line_price_rounds_to_currency_precision() -> None:
    product = make_product(
        sales_unit="meter",
        base_price_eur=Decimal("1.35"),
    )
    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("2.5"),
        unit="meter",
    )

    result = calculate_line_price(line, product)

    assert result.subtotal_eur == Decimal("3.38")


def test_calculate_line_price_rejects_unit_mismatch() -> None:
    product = make_product(sales_unit="piece")
    line = RFQLine(
        product_query="TEST-001",
        quantity=Decimal("10"),
        unit="meter",
    )

    with pytest.raises(ValueError, match="requested unit"):
        calculate_line_price(line, product)
