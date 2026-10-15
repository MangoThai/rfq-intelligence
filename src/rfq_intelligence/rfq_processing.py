from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from openai import OpenAI

from rfq_intelligence.customer import Customer
from rfq_intelligence.customer_resolution import (
    CustomerContact,
    CustomerResolutionStatus,
    resolve_customer_by_email,
)
from rfq_intelligence.decision import LineDecisionStatus
from rfq_intelligence.extraction import (
    DEFAULT_EXTRACTION_MODEL,
    extract_rfq_email_with_metrics,
)
from rfq_intelligence.extraction_adapter import (
    RFQLineConversion,
    convert_extracted_rfq,
)
from rfq_intelligence.observability import ModelCallMetrics
from rfq_intelligence.processing import (
    LineProcessingResult,
    process_line,
)
from rfq_intelligence.product import Product


class RFQProcessingStatus(StrEnum):
    READY_FOR_QUOTE = "READY_FOR_QUOTE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class RFQIssue(StrEnum):
    CUSTOMER_NOT_FOUND = "CUSTOMER_NOT_FOUND"
    INACTIVE_CUSTOMER = "INACTIVE_CUSTOMER"
    NO_LINES_EXTRACTED = "NO_LINES_EXTRACTED"


@dataclass(frozen=True, slots=True)
class ProcessedRFQLine:
    conversion: RFQLineConversion
    processing: LineProcessingResult | None


@dataclass(frozen=True, slots=True)
class RFQProcessingResult:
    status: RFQProcessingStatus
    lines: tuple[ProcessedRFQLine, ...]
    customer: Customer | None = None
    issues: tuple[RFQIssue, ...] = ()
    model_metrics: ModelCallMetrics | None = None


def process_rfq_email(
    email_text: str,
    sender_email: str,
    products: Sequence[Product],
    customers: Sequence[Customer],
    contacts: Sequence[CustomerContact],
    client: OpenAI,
    model: str = DEFAULT_EXTRACTION_MODEL,
) -> RFQProcessingResult:
    customer_resolution = resolve_customer_by_email(
        sender_email=sender_email,
        customers=customers,
        contacts=contacts,
    )

    if customer_resolution.status == CustomerResolutionStatus.NOT_FOUND:
        return RFQProcessingResult(
            status=RFQProcessingStatus.REVIEW_REQUIRED,
            lines=(),
            customer=None,
            issues=(RFQIssue.CUSTOMER_NOT_FOUND,),
            model_metrics=None,
        )

    customer = customer_resolution.customer

    if customer is None:
        raise RuntimeError("Matched customer resolution returned no customer.")

    if not customer.active:
        return RFQProcessingResult(
            status=RFQProcessingStatus.REVIEW_REQUIRED,
            lines=(),
            customer=customer,
            issues=(RFQIssue.INACTIVE_CUSTOMER,),
            model_metrics=None,
        )

    extraction_result = extract_rfq_email_with_metrics(
        email_text=email_text,
        client=client,
        model=model,
    )

    conversions = convert_extracted_rfq(extraction_result.rfq)

    if not conversions:
        return RFQProcessingResult(
            status=RFQProcessingStatus.REVIEW_REQUIRED,
            lines=(),
            customer=customer,
            issues=(RFQIssue.NO_LINES_EXTRACTED,),
            model_metrics=extraction_result.metrics,
        )

    processed_lines: list[ProcessedRFQLine] = []
    rfq_status = RFQProcessingStatus.READY_FOR_QUOTE

    for conversion in conversions:
        if conversion.line is None:
            processed_lines.append(
                ProcessedRFQLine(
                    conversion=conversion,
                    processing=None,
                )
            )

            rfq_status = RFQProcessingStatus.REVIEW_REQUIRED
            continue

        processing = process_line(
            line=conversion.line,
            products=products,
            customer=customer,
        )

        processed_lines.append(
            ProcessedRFQLine(
                conversion=conversion,
                processing=processing,
            )
        )

        if processing.status == LineDecisionStatus.REVIEW_REQUIRED:
            rfq_status = RFQProcessingStatus.REVIEW_REQUIRED

    return RFQProcessingResult(
        status=rfq_status,
        lines=tuple(processed_lines),
        customer=customer,
        model_metrics=extraction_result.metrics,
    )
