import csv
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from rfq_intelligence.customer import Customer


@dataclass(frozen=True, slots=True)
class CustomerContact:
    email: str
    customer_id: str


class CustomerResolutionStatus(StrEnum):
    MATCHED = "MATCHED"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True, slots=True)
class CustomerResolution:
    status: CustomerResolutionStatus
    customer: Customer | None
    contact: CustomerContact | None


def load_customer_contacts(path: Path) -> list[CustomerContact]:
    if not path.exists():
        raise FileNotFoundError(f"Customer contacts file not found: {path}")

    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        contacts = [
            CustomerContact(
                email=_normalize_email(row["email"]),
                customer_id=row["customer_id"].strip(),
            )
            for row in reader
        ]

    _validate_contacts(contacts)

    return contacts


def resolve_customer_by_email(
    sender_email: str,
    customers: Sequence[Customer],
    contacts: Sequence[CustomerContact],
) -> CustomerResolution:
    normalized_email = _normalize_email(sender_email)

    contact = next(
        (contact for contact in contacts if contact.email == normalized_email),
        None,
    )

    if contact is None:
        return CustomerResolution(
            status=CustomerResolutionStatus.NOT_FOUND,
            customer=None,
            contact=None,
        )

    customer = next(
        (customer for customer in customers if customer.customer_id == contact.customer_id),
        None,
    )

    if customer is None:
        raise ValueError(
            f"Customer contact {contact.email} references unknown customer {contact.customer_id}."
        )

    return CustomerResolution(
        status=CustomerResolutionStatus.MATCHED,
        customer=customer,
        contact=contact,
    )


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _validate_contacts(contacts: Sequence[CustomerContact]) -> None:
    seen: set[str] = set()

    for contact in contacts:
        if not contact.email:
            raise ValueError("Customer contact email cannot be empty.")

        if not contact.customer_id:
            raise ValueError(f"Customer contact {contact.email}: customer_id cannot be empty.")

        if contact.email in seen:
            raise ValueError(f"Duplicate customer contact email: {contact.email}")

        seen.add(contact.email)
