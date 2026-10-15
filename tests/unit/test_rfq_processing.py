from decimal import Decimal
from typing import cast

import pytest
from openai import OpenAI

import rfq_intelligence.rfq_processing as rfq_processing
from rfq_intelligence.customer import Customer
from rfq_intelligence.customer_resolution import CustomerContact
from rfq_intelligence.extraction import (
    ExtractedRFQ,
    ExtractedRFQLine,
    ExtractionResult,
)
from rfq_intelligence.observability import (
    ModelCallMetrics,
    ModelUsage,
)
from rfq_intelligence.product import Product
from rfq_intelligence.rfq_processing import (
    RFQIssue,
    RFQProcessingStatus,
    process_rfq_email,
)


def make_product(
    sku: str = "VAN-BR-050",
) -> Product:
    return Product(
        sku=sku,
        name='Vanne à boisseau sphérique laiton 1/2"',
        family="valve",
        material="brass",
        thread_type="G",
        thread_size="1/2",
        tube_outer_mm=None,
        tube_inner_mm=None,
        color=None,
        profile=None,
        connection_gender=None,
        sales_unit="piece",
        pack_size=1,
        base_price_eur=Decimal("12.80"),
        stock_qty=100,
        lead_time_days=2,
        active=True,
    )


def make_active_customer() -> Customer:
    return Customer(
        customer_id="CUST-001",
        company_name="Atelier Delta",
        price_tier="STANDARD",
        discount_pct=Decimal("0"),
        payment_terms="30 days",
        active=True,
    )


def make_inactive_customer() -> Customer:
    return Customer(
        customer_id="CUST-005",
        company_name="Industries Valmont",
        price_tier="STANDARD",
        discount_pct=Decimal("2"),
        payment_terms="30 days",
        active=False,
    )


def make_contact(
    email: str = "achats@atelier-delta.example",
    customer_id: str = "CUST-001",
) -> CustomerContact:
    return CustomerContact(
        email=email,
        customer_id=customer_id,
    )


def make_metrics() -> ModelCallMetrics:
    usage = ModelUsage(
        input_tokens=500,
        cached_input_tokens=0,
        cache_write_tokens=0,
        output_tokens=100,
        reasoning_tokens=0,
        total_tokens=600,
    )

    return ModelCallMetrics(
        model="test-model",
        response_id="resp_test_123",
        latency_ms=250.0,
        usage=usage,
        estimated_cost_usd=Decimal("0.00010000"),
    )


def make_extraction_result(
    lines: list[ExtractedRFQLine],
) -> ExtractionResult:
    return ExtractionResult(
        rfq=ExtractedRFQ(lines=lines),
        metrics=make_metrics(),
    )


def test_process_rfq_email_returns_ready_for_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction_result = make_extraction_result(
        [
            ExtractedRFQLine(
                product_query="VAN-BR-050",
                quantity="10",
                unit="piece",
            )
        ]
    )

    def fake_extract_rfq_email_with_metrics(
        email_text: str,
        client: OpenAI,
        model: str,
    ) -> ExtractionResult:
        del email_text, client, model
        return extraction_result

    monkeypatch.setattr(
        rfq_processing,
        "extract_rfq_email_with_metrics",
        fake_extract_rfq_email_with_metrics,
    )

    customer = make_active_customer()

    result = process_rfq_email(
        email_text="Bonjour, 10 VAN-BR-050 svp.",
        sender_email="achats@atelier-delta.example",
        products=[make_product()],
        customers=[customer],
        contacts=[make_contact()],
        client=cast(OpenAI, object()),
    )

    assert result.status == RFQProcessingStatus.READY_FOR_QUOTE
    assert result.customer == customer
    assert result.issues == ()
    assert len(result.lines) == 1

    assert result.lines[0].processing is not None
    assert result.lines[0].processing.price is not None

    assert result.model_metrics == extraction_result.metrics
    assert result.model_metrics.response_id == "resp_test_123"
    assert result.model_metrics.latency_ms == 250.0


def test_process_rfq_email_requires_review_for_incomplete_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction_result = make_extraction_result(
        [
            ExtractedRFQLine(
                product_query="VAN-BR-050",
                quantity=None,
                unit=None,
            )
        ]
    )

    def fake_extract_rfq_email_with_metrics(
        email_text: str,
        client: OpenAI,
        model: str,
    ) -> ExtractionResult:
        del email_text, client, model
        return extraction_result

    monkeypatch.setattr(
        rfq_processing,
        "extract_rfq_email_with_metrics",
        fake_extract_rfq_email_with_metrics,
    )

    result = process_rfq_email(
        email_text="Pouvez-vous faire un prix pour VAN-BR-050 ?",
        sender_email="achats@atelier-delta.example",
        products=[make_product()],
        customers=[make_active_customer()],
        contacts=[make_contact()],
        client=cast(OpenAI, object()),
    )

    assert result.status == RFQProcessingStatus.REVIEW_REQUIRED
    assert len(result.lines) == 1
    assert result.lines[0].processing is None

    assert result.model_metrics == extraction_result.metrics


def test_process_rfq_email_requires_review_for_unknown_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction_result = make_extraction_result(
        [
            ExtractedRFQLine(
                product_query="ZX-900",
                quantity="5",
                unit="piece",
            )
        ]
    )

    def fake_extract_rfq_email_with_metrics(
        email_text: str,
        client: OpenAI,
        model: str,
    ) -> ExtractionResult:
        del email_text, client, model
        return extraction_result

    monkeypatch.setattr(
        rfq_processing,
        "extract_rfq_email_with_metrics",
        fake_extract_rfq_email_with_metrics,
    )

    result = process_rfq_email(
        email_text="Bonjour, besoin de 5 ZX-900.",
        sender_email="achats@atelier-delta.example",
        products=[make_product()],
        customers=[make_active_customer()],
        contacts=[make_contact()],
        client=cast(OpenAI, object()),
    )

    assert result.status == RFQProcessingStatus.REVIEW_REQUIRED
    assert len(result.lines) == 1

    processing = result.lines[0].processing

    assert processing is not None
    assert processing.match.product is None
    assert processing.price is None

    assert result.model_metrics == extraction_result.metrics


def test_process_rfq_email_requires_review_when_no_lines_extracted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extraction_result = make_extraction_result([])

    def fake_extract_rfq_email_with_metrics(
        email_text: str,
        client: OpenAI,
        model: str,
    ) -> ExtractionResult:
        del email_text, client, model
        return extraction_result

    monkeypatch.setattr(
        rfq_processing,
        "extract_rfq_email_with_metrics",
        fake_extract_rfq_email_with_metrics,
    )

    result = process_rfq_email(
        email_text="Bonjour, merci pour votre retour.",
        sender_email="achats@atelier-delta.example",
        products=[make_product()],
        customers=[make_active_customer()],
        contacts=[make_contact()],
        client=cast(OpenAI, object()),
    )

    assert result.status == RFQProcessingStatus.REVIEW_REQUIRED
    assert result.lines == ()
    assert result.issues == (RFQIssue.NO_LINES_EXTRACTED,)

    assert result.model_metrics == extraction_result.metrics


def test_process_rfq_email_rejects_unknown_sender_before_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_extraction(
        email_text: str,
        client: OpenAI,
        model: str,
    ) -> ExtractionResult:
        del email_text, client, model

        raise AssertionError("OpenAI extraction must not run for an unknown sender.")

    monkeypatch.setattr(
        rfq_processing,
        "extract_rfq_email_with_metrics",
        unexpected_extraction,
    )

    result = process_rfq_email(
        email_text="Bonjour, 10 VAN-BR-050.",
        sender_email="unknown@example.com",
        products=[make_product()],
        customers=[make_active_customer()],
        contacts=[make_contact()],
        client=cast(OpenAI, object()),
    )

    assert result.status == RFQProcessingStatus.REVIEW_REQUIRED
    assert result.customer is None
    assert result.lines == ()
    assert result.issues == (RFQIssue.CUSTOMER_NOT_FOUND,)

    assert result.model_metrics is None


def test_process_rfq_email_rejects_inactive_customer_before_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_extraction(
        email_text: str,
        client: OpenAI,
        model: str,
    ) -> ExtractionResult:
        del email_text, client, model

        raise AssertionError("OpenAI extraction must not run for an inactive customer.")

    monkeypatch.setattr(
        rfq_processing,
        "extract_rfq_email_with_metrics",
        unexpected_extraction,
    )

    customer = make_inactive_customer()
    contact = make_contact(
        email="achats@industries-valmont.example",
        customer_id="CUST-005",
    )

    result = process_rfq_email(
        email_text="Bonjour, 10 VAN-BR-050.",
        sender_email="achats@industries-valmont.example",
        products=[make_product()],
        customers=[customer],
        contacts=[contact],
        client=cast(OpenAI, object()),
    )

    assert result.status == RFQProcessingStatus.REVIEW_REQUIRED
    assert result.customer == customer
    assert result.lines == ()
    assert result.issues == (RFQIssue.INACTIVE_CUSTOMER,)

    assert result.model_metrics is None
