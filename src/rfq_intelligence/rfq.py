from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

RequestedUnit = Literal["piece", "meter"]


@dataclass(frozen=True, slots=True)
class RFQLine:
    product_query: str
    quantity: Decimal
    unit: RequestedUnit
    substitution_requested: bool = False
    delivery_constraint: str | None = None

    def __post_init__(self) -> None:
        if not self.product_query.strip():
            raise ValueError("RFQ product query cannot be empty.")

        if self.quantity <= 0:
            raise ValueError("RFQ quantity must be positive.")
