from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from rfq_intelligence.customer import Customer
from rfq_intelligence.product import Product
from rfq_intelligence.rfq import RFQLine

_CURRENCY_QUANTUM = Decimal("0.01")
_PERCENT = Decimal("100")


@dataclass(frozen=True, slots=True)
class LinePrice:
    quantity: Decimal
    catalog_unit_price_eur: Decimal
    discount_pct: Decimal
    unit_price_eur: Decimal
    subtotal_eur: Decimal


def calculate_line_price(
    line: RFQLine,
    product: Product,
    customer: Customer | None = None,
) -> LinePrice:
    if line.unit != product.sales_unit:
        raise ValueError(
            f"Cannot price {product.sku}: "
            f"requested unit {line.unit!r} does not match "
            f"sales unit {product.sales_unit!r}."
        )

    if customer is not None and not customer.active:
        raise ValueError(f"Cannot price for inactive customer {customer.customer_id}.")

    discount_pct = customer.discount_pct if customer is not None else Decimal("0")

    unit_price = _apply_discount(
        price=product.base_price_eur,
        discount_pct=discount_pct,
    )

    subtotal = (line.quantity * unit_price).quantize(
        _CURRENCY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )

    return LinePrice(
        quantity=line.quantity,
        catalog_unit_price_eur=product.base_price_eur,
        discount_pct=discount_pct,
        unit_price_eur=unit_price,
        subtotal_eur=subtotal,
    )


def _apply_discount(
    price: Decimal,
    discount_pct: Decimal,
) -> Decimal:
    multiplier = Decimal("1") - (discount_pct / _PERCENT)

    return (price * multiplier).quantize(
        _CURRENCY_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
