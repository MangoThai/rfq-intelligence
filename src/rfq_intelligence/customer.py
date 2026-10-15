from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Self

PriceTier = Literal["STANDARD", "PRO", "KEY"]


@dataclass(frozen=True, slots=True)
class Customer:
    customer_id: str
    company_name: str
    price_tier: PriceTier
    discount_pct: Decimal
    payment_terms: str
    active: bool

    @classmethod
    def from_csv_row(cls, row: Mapping[str, str]) -> Self:
        customer = cls(
            customer_id=row["customer_id"].strip(),
            company_name=row["company_name"].strip(),
            price_tier=_parse_price_tier(row["price_tier"]),
            discount_pct=Decimal(row["discount_pct"]),
            payment_terms=row["payment_terms"].strip(),
            active=_parse_bool(row["active"]),
        )

        customer._validate()
        return customer

    def _validate(self) -> None:
        if not self.customer_id:
            raise ValueError("Customer ID cannot be empty.")

        if not self.company_name:
            raise ValueError(f"Customer {self.customer_id}: company_name cannot be empty.")

        if self.discount_pct < 0 or self.discount_pct > 100:
            raise ValueError(
                f"Customer {self.customer_id}: discount_pct must be between 0 and 100."
            )

        if not self.payment_terms:
            raise ValueError(f"Customer {self.customer_id}: payment_terms cannot be empty.")


def _parse_price_tier(value: str) -> PriceTier:
    normalized = value.strip().upper()

    if normalized in {"STANDARD", "PRO", "KEY"}:
        return normalized  # type: ignore[return-value]

    raise ValueError(f"Invalid price tier: {value!r}")


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()

    if normalized == "true":
        return True

    if normalized == "false":
        return False

    raise ValueError(f"Invalid boolean value: {value!r}")
