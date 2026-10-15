import json
import logging
from decimal import Decimal
from io import StringIO
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

import rfq_intelligence.main as api
from rfq_intelligence.customer import Customer
from rfq_intelligence.decision import (
    LineDecision,
    LineDecisionStatus,
)
from rfq_intelligence.extraction import ExtractedRFQLine
from rfq_intelligence.extraction_adapter import RFQLineConversion
from rfq_intelligence.logging_config import (
    JsonFormatter,
    RequestContextFilter,
)
from rfq_intelligence.matching import (
    MatchMethod,
    MatchResult,
    MatchStatus,
)
from rfq_intelligence.observability import (
    ModelCallMetrics,
    ModelUsage,
)
from rfq_intelligence.pricing import LinePrice
from rfq_intelligence.processing import LineProcessingResult
from rfq_intelligence.product import Product
from rfq_intelligence.rfq import RFQLine
from rfq_intelligence.rfq_processing import (
    ProcessedRFQLine,
    RFQIssue,
    RFQProcessingResult,
    RFQProcessingStatus,
)


class FakeOpenAIClient:
    def close(self) -> None:
        pass


def make_product() -> Product:
    return Product(
        sku="VAN-BR-050",
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
        stock_qty=86,
        lead_time_days=2,
        active=True,
    )


def make_customer() -> Customer:
    return Customer(
        customer_id="CUST-001",
        company_name="Atelier Delta",
        price_tier="STANDARD",
        discount_pct=Decimal("0"),
        payment_terms="30 days",
        active=True,
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
        response_id="resp_test_api",
        latency_ms=250.0,
        usage=usage,
        estimated_cost_usd=Decimal("0.00010000"),
    )


def make_ready_result() -> RFQProcessingResult:
    product = make_product()

    extracted = ExtractedRFQLine(
        product_query="VAN-BR-050",
        quantity="10",
        unit="piece",
    )

    line = RFQLine(
        product_query="VAN-BR-050",
        quantity=Decimal("10"),
        unit="piece",
    )

    conversion = RFQLineConversion(
        extracted=extracted,
        line=line,
        issues=(),
    )

    match = MatchResult(
        status=MatchStatus.EXACT_MATCH,
        product=product,
        method=MatchMethod.EXACT_SKU,
        best_score=100.0,
    )

    decision = LineDecision(
        status=LineDecisionStatus.READY_FOR_QUOTE,
        reasons=(),
    )

    price = LinePrice(
        quantity=Decimal("10"),
        catalog_unit_price_eur=Decimal("12.80"),
        discount_pct=Decimal("0"),
        unit_price_eur=Decimal("12.80"),
        subtotal_eur=Decimal("128.00"),
    )

    processing = LineProcessingResult(
        status=LineDecisionStatus.READY_FOR_QUOTE,
        match=match,
        decision=decision,
        price=price,
    )

    processed_line = ProcessedRFQLine(
        conversion=conversion,
        processing=processing,
    )

    return RFQProcessingResult(
        status=RFQProcessingStatus.READY_FOR_QUOTE,
        lines=(processed_line,),
        customer=make_customer(),
        issues=(),
        model_metrics=make_metrics(),
    )


def make_review_result() -> RFQProcessingResult:
    return RFQProcessingResult(
        status=RFQProcessingStatus.REVIEW_REQUIRED,
        lines=(),
        customer=None,
        issues=(RFQIssue.CUSTOMER_NOT_FOUND,),
        model_metrics=None,
    )


def prepare_test_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api,
        "load_catalog",
        lambda path: [],
    )

    monkeypatch.setattr(
        api,
        "load_customers",
        lambda path: [],
    )

    monkeypatch.setattr(
        api,
        "load_customer_contacts",
        lambda path: [],
    )

    monkeypatch.setattr(
        api,
        "OpenAI",
        lambda **_: FakeOpenAIClient(),
    )


def test_health_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_test_app(monkeypatch)

    with TestClient(api.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "rfq-intelligence",
    }


def test_health_endpoint_returns_request_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_test_app(monkeypatch)

    with TestClient(api.app) as client:
        response = client.get("/health")

    request_id = response.headers["X-Request-ID"]

    parsed_uuid = UUID(request_id)

    assert str(parsed_uuid) == request_id


def test_process_rfq_returns_ready_quote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_test_app(monkeypatch)

    expected_result = make_ready_result()

    def fake_process_rfq_email(
        **kwargs: object,
    ) -> RFQProcessingResult:
        assert kwargs["sender_email"] == ("achats@atelier-delta.example")
        assert kwargs["email_text"] == ("Bonjour, 10 VAN-BR-050 svp.")

        return expected_result

    monkeypatch.setattr(
        api,
        "process_rfq_email",
        fake_process_rfq_email,
    )

    with TestClient(api.app) as client:
        response = client.post(
            "/rfq/process",
            json={
                "sender_email": ("achats@atelier-delta.example"),
                "email_text": ("Bonjour, 10 VAN-BR-050 svp."),
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "READY_FOR_QUOTE"

    assert body["customer"] == {
        "customer_id": "CUST-001",
        "company_name": "Atelier Delta",
        "discount_pct": "0",
    }

    assert body["reason_codes"] == []

    assert len(body["lines"]) == 1

    line = body["lines"][0]

    assert line["product_query"] == "VAN-BR-050"
    assert line["quantity"] == "10"
    assert line["unit"] == "piece"
    assert line["extraction_issues"] == []

    assert line["match"]["status"] == "EXACT_MATCH"
    assert line["match"]["method"] == "EXACT_SKU"
    assert line["match"]["sku"] == "VAN-BR-050"

    assert line["decision"] == {
        "status": "READY_FOR_QUOTE",
        "reason_codes": [],
    }

    assert line["price"] == {
        "catalog_unit_price_eur": "12.80",
        "discount_pct": "0",
        "unit_price_eur": "12.80",
        "subtotal_eur": "128.00",
    }

    assert body["quote"] == {
        "line_count": 1,
        "subtotal_eur": "128.00",
    }

    assert body["model_metrics"]["model"] == "test-model"
    assert body["model_metrics"]["response_id"] == "resp_test_api"
    assert body["model_metrics"]["latency_ms"] == 250.0

    assert body["model_metrics"]["estimated_cost_usd"] == "0.00010000"

    assert body["model_metrics"]["usage"] == {
        "input_tokens": 500,
        "cached_input_tokens": 0,
        "cache_write_tokens": 0,
        "output_tokens": 100,
        "reasoning_tokens": 0,
        "total_tokens": 600,
    }


def test_process_rfq_returns_review_without_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_test_app(monkeypatch)

    def fake_process_rfq_email(
        **kwargs: object,
    ) -> RFQProcessingResult:
        return make_review_result()

    monkeypatch.setattr(
        api,
        "process_rfq_email",
        fake_process_rfq_email,
    )

    with TestClient(api.app) as client:
        response = client.post(
            "/rfq/process",
            json={
                "sender_email": "unknown@example.com",
                "email_text": "Bonjour, 10 VAN-BR-050.",
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "REVIEW_REQUIRED"
    assert body["customer"] is None

    assert body["reason_codes"] == ["CUSTOMER_NOT_FOUND"]

    assert body["lines"] == []
    assert body["quote"] is None
    assert body["model_metrics"] is None


def test_process_rfq_rejects_empty_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_test_app(monkeypatch)

    with TestClient(api.app) as client:
        response = client.post(
            "/rfq/process",
            json={
                "sender_email": "",
                "email_text": "",
            },
        )

    assert response.status_code == 422


def test_process_rfq_correlates_structured_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_test_app(monkeypatch)

    monkeypatch.setattr(
        api,
        "process_rfq_email",
        lambda **kwargs: make_ready_result(),
    )

    with TestClient(api.app) as client:
        stream = StringIO()

        handler = logging.StreamHandler(stream)

        handler.addFilter(RequestContextFilter())

        handler.setFormatter(JsonFormatter())

        base_logger = logging.getLogger("rfq_intelligence")

        base_logger.addHandler(handler)

        try:
            response = client.post(
                "/rfq/process",
                json={
                    "sender_email": ("achats@atelier-delta.example"),
                    "email_text": ("Bonjour, 10 VAN-BR-050 svp."),
                },
            )
        finally:
            base_logger.removeHandler(handler)

    assert response.status_code == 200

    request_id = response.headers["X-Request-ID"]

    log_entries = [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]

    rfq_log = next(entry for entry in log_entries if entry.get("event") == "rfq_processed")

    http_log = next(
        entry for entry in log_entries if entry.get("event") == "http_request_completed"
    )

    assert rfq_log["request_id"] == request_id
    assert http_log["request_id"] == request_id

    assert rfq_log["rfq_status"] == ("READY_FOR_QUOTE")

    assert rfq_log["customer_id"] == ("CUST-001")

    assert rfq_log["model"] == "test-model"

    assert rfq_log["model_response_id"] == ("resp_test_api")

    assert http_log["method"] == "POST"
    assert http_log["path"] == "/rfq/process"
    assert http_log["status_code"] == 200

    assert http_log["duration_ms"] >= 0


def test_process_rfq_returns_503_when_openai_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_test_app(monkeypatch)

    def fake_process_rfq_email(
        **_: object,
    ) -> RFQProcessingResult:
        request = httpx.Request(
            "POST",
            "https://api.openai.com/v1/responses",
        )

        raise api.openai.APIConnectionError(request=request)

    monkeypatch.setattr(
        api,
        "process_rfq_email",
        fake_process_rfq_email,
    )

    with TestClient(api.app) as client:
        response = client.post(
            "/rfq/process",
            json={
                "sender_email": ("achats@atelier-delta.example"),
                "email_text": ("Bonjour, 10 VAN-BR-050 svp."),
            },
        )

    assert response.status_code == 503

    assert response.json() == {
        "detail": {
            "code": "AI_DEPENDENCY_UNAVAILABLE",
            "message": ("AI extraction service is temporarily unavailable."),
        }
    }

    request_id = response.headers["X-Request-ID"]

    parsed_uuid = UUID(request_id)

    assert str(parsed_uuid) == request_id
