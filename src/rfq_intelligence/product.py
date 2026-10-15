from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Self

ProductFamily = Literal["valve", "fitting", "tube", "coupler"]
SalesUnit = Literal["piece", "meter"]
ConnectionGender = Literal["female", "male"]


@dataclass(frozen=True, slots=True)
class Product:
    sku: str
    name: str
    family: ProductFamily
    material: str | None
    thread_type: str | None
    thread_size: str | None
    tube_outer_mm: int | None
    tube_inner_mm: int | None
    color: str | None
    profile: str | None
    connection_gender: ConnectionGender | None
    sales_unit: SalesUnit
    pack_size: int
    base_price_eur: Decimal
    stock_qty: int
    lead_time_days: int
    active: bool

    @classmethod
    def from_csv_row(cls, row: Mapping[str, str]) -> Self:
        product = cls(
            sku=row["sku"].strip(),
            name=row["name"].strip(),
            family=_parse_family(row["family"]),
            material=_optional_str(row["material"]),
            thread_type=_optional_str(row["thread_type"]),
            thread_size=_optional_str(row["thread_size"]),
            tube_outer_mm=_optional_int(row["tube_outer_mm"]),
            tube_inner_mm=_optional_int(row["tube_inner_mm"]),
            color=_optional_str(row["color"]),
            profile=_optional_str(row["profile"]),
            connection_gender=_parse_connection_gender(row["connection_gender"]),
            sales_unit=_parse_sales_unit(row["sales_unit"]),
            pack_size=int(row["pack_size"]),
            base_price_eur=Decimal(row["base_price_eur"]),
            stock_qty=int(row["stock_qty"]),
            lead_time_days=int(row["lead_time_days"]),
            active=_parse_bool(row["active"]),
        )

        product._validate()
        return product

    def _validate(self) -> None:
        if not self.sku:
            raise ValueError("Product SKU cannot be empty.")

        if not self.name:
            raise ValueError(f"Product {self.sku}: name cannot be empty.")

        if self.pack_size <= 0:
            raise ValueError(f"Product {self.sku}: pack_size must be positive.")

        if self.base_price_eur < 0:
            raise ValueError(f"Product {self.sku}: base_price_eur cannot be negative.")

        if self.stock_qty < 0:
            raise ValueError(f"Product {self.sku}: stock_qty cannot be negative.")

        if self.lead_time_days < 0:
            raise ValueError(f"Product {self.sku}: lead_time_days cannot be negative.")


def _optional_str(value: str) -> str | None:
    value = value.strip()
    return value or None


def _optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()

    if normalized == "true":
        return True

    if normalized == "false":
        return False

    raise ValueError(f"Invalid boolean value: {value!r}")


def _parse_family(value: str) -> ProductFamily:
    normalized = value.strip()

    if normalized in {"valve", "fitting", "tube", "coupler"}:
        return normalized  # type: ignore[return-value]

    raise ValueError(f"Invalid product family: {value!r}")


def _parse_sales_unit(value: str) -> SalesUnit:
    normalized = value.strip()

    if normalized in {"piece", "meter"}:
        return normalized  # type: ignore[return-value]

    raise ValueError(f"Invalid sales unit: {value!r}")


def _parse_connection_gender(value: str) -> ConnectionGender | None:
    normalized = value.strip()

    if not normalized:
        return None

    if normalized in {"female", "male"}:
        return normalized  # type: ignore[return-value]

    raise ValueError(f"Invalid connection gender: {value!r}")
