import csv
from pathlib import Path

from rfq_intelligence.product import Product


def load_catalog(path: Path) -> list[Product]:
    if not path.exists():
        raise FileNotFoundError(f"Catalog file not found: {path}")

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        products = [Product.from_csv_row(row) for row in reader]

    _validate_unique_skus(products)

    return products


def _validate_unique_skus(products: list[Product]) -> None:
    seen: set[str] = set()

    for product in products:
        if product.sku in seen:
            raise ValueError(f"Duplicate product SKU: {product.sku}")

        seen.add(product.sku)
