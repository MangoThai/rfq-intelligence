from decimal import Decimal

from sqlalchemy.orm import Session

from rfq_intelligence.db_models import (
    RFQLineRecord,
    RFQRequestRecord,
)
from rfq_intelligence.quote import build_quote_summary
from rfq_intelligence.rfq_processing import (
    RFQProcessingResult,
    RFQProcessingStatus,
)


def persist_rfq_result(
    *,
    session: Session,
    request_id: str,
    result: RFQProcessingResult,
) -> None:
    quote_subtotal_eur = None

    if result.status == RFQProcessingStatus.READY_FOR_QUOTE:
        quote_subtotal_eur = build_quote_summary(result).subtotal_eur

    customer_id = None

    if result.customer is not None:
        customer_id = result.customer.customer_id

    model = None
    model_response_id = None
    model_latency_ms = None
    estimated_cost_usd = None

    if result.model_metrics is not None:
        metrics = result.model_metrics

        model = metrics.model
        model_response_id = metrics.response_id
        model_latency_ms = Decimal(str(metrics.latency_ms))
        estimated_cost_usd = metrics.estimated_cost_usd

    rfq_record = RFQRequestRecord(
        request_id=request_id,
        customer_id=customer_id,
        status=result.status.value,
        reason_codes=[issue.value for issue in result.issues],
        quote_subtotal_eur=quote_subtotal_eur,
        model=model,
        model_response_id=model_response_id,
        model_latency_ms=model_latency_ms,
        estimated_cost_usd=estimated_cost_usd,
    )

    session.add(rfq_record)

    # We need the database-generated parent ID
    # before inserting the child rows.
    session.flush()

    for line_number, processed_line in enumerate(
        result.lines,
        start=1,
    ):
        conversion = processed_line.conversion
        processing = processed_line.processing

        quantity = None
        unit = None

        if conversion.line is not None:
            quantity = conversion.line.quantity
            unit = conversion.line.unit

        match_status = None
        matched_sku = None
        decision_status = None
        decision_reason_codes: list[str] = []
        subtotal_eur = None

        if processing is not None:
            match_status = processing.match.status.value

            if processing.match.product is not None:
                matched_sku = processing.match.product.sku

            if processing.decision is not None:
                decision_status = processing.decision.status.value

                decision_reason_codes = [reason.value for reason in processing.decision.reasons]

            if processing.price is not None:
                subtotal_eur = processing.price.subtotal_eur

        line_record = RFQLineRecord(
            rfq_id=rfq_record.id,
            line_number=line_number,
            product_query=(conversion.extracted.product_query),
            quantity=quantity,
            unit=unit,
            extraction_issues=[issue.value for issue in conversion.issues],
            match_status=match_status,
            matched_sku=matched_sku,
            decision_status=decision_status,
            decision_reason_codes=(decision_reason_codes),
            subtotal_eur=subtotal_eur,
        )

        session.add(line_record)
