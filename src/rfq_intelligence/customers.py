import csv
from pathlib import Path

from rfq_intelligence.customer import Customer


def load_customers(path: Path) -> list[Customer]:
    if not path.exists():
        raise FileNotFoundError(f"Customers file not found: {path}")

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        customers = [Customer.from_csv_row(row) for row in reader]

    _validate_unique_customer_ids(customers)

    return customers


def _validate_unique_customer_ids(customers: list[Customer]) -> None:
    seen: set[str] = set()

    for customer in customers:
        if customer.customer_id in seen:
            raise ValueError(f"Duplicate customer ID: {customer.customer_id}")

        seen.add(customer.customer_id)
