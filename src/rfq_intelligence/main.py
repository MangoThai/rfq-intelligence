import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from secrets import compare_digest
from time import perf_counter
from uuid import uuid4

import openai
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Security,
)
from fastapi.security import APIKeyHeader
from openai import OpenAI
from starlette.responses import Response

from rfq_intelligence.api_schemas import (
    CustomerAPIResponse,
    DecisionAPIResponse,
    MatchAPIResponse,
    ModelMetricsAPIResponse,
    ModelUsageAPIResponse,
    PriceAPIResponse,
    ProcessRFQRequest,
    ProcessRFQResponse,
    QuoteAPIResponse,
    RFQLineAPIResponse,
)
from rfq_intelligence.catalog import load_catalog
from rfq_intelligence.customer_resolution import (
    load_customer_contacts,
)
from rfq_intelligence.customers import load_customers
from rfq_intelligence.logging_config import (
    configure_logging,
    get_logger,
    reset_request_id,
    set_request_id,
)
from rfq_intelligence.quote import build_quote_summary
from rfq_intelligence.rfq_processing import (
    ProcessedRFQLine,
    RFQProcessingResult,
    RFQProcessingStatus,
    process_rfq_email,
)

_DATA_DIR = Path(
    os.getenv(
        "RFQ_DATA_DIR",
        "data",
    )
).resolve()

_CATALOG_PATH = _DATA_DIR / "catalog.csv"

_CUSTOMERS_PATH = _DATA_DIR / "customers.csv"

_CONTACTS_PATH = _DATA_DIR / "customer_contacts.csv"

_OPENAI_TIMEOUT_SECONDS = 20.0
_OPENAI_MAX_RETRIES = 1

_TRANSIENT_OPENAI_STATUS_CODES = {
    408,
    409,
    429,
}


logger = get_logger("rfq_intelligence.main")


_api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="RFQApiKey",
    description="API key required to process RFQs.",
    auto_error=False,
)


def require_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> None:
    expected_api_key: str = request.app.state.rfq_api_key

    if api_key is None or not compare_digest(
        api_key,
        expected_api_key,
    ):
        logger.warning(
            "api_authentication_failed",
            extra={
                "event": "api_authentication_failed",
            },
        )

        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_API_KEY",
                "message": "A valid API key is required.",
            },
            headers={
                "WWW-Authenticate": "APIKey",
            },
        )


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    configure_logging()

    rfq_api_key = os.getenv("RFQ_API_KEY")

    if not rfq_api_key:
        raise RuntimeError("RFQ_API_KEY environment variable is required.")

    app.state.rfq_api_key = rfq_api_key

    app.state.products = load_catalog(_CATALOG_PATH)

    app.state.customers = load_customers(_CUSTOMERS_PATH)

    app.state.contacts = load_customer_contacts(_CONTACTS_PATH)

    app.state.openai_client = OpenAI(
        timeout=_OPENAI_TIMEOUT_SECONDS,
        max_retries=_OPENAI_MAX_RETRIES,
    )

    logger.info(
        "service_started",
        extra={
            "event": "service_started",
        },
    )

    yield

    app.state.openai_client.close()

    logger.info(
        "service_stopped",
        extra={
            "event": "service_stopped",
        },
    )


app = FastAPI(
    title="RFQ Intelligence",
    version="0.1.0",
    description=("AI-assisted processing of industrial B2B requests for quotation."),
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context_middleware(
    request: Request,
    call_next: Callable[
        [Request],
        Awaitable[Response],
    ],
) -> Response:
    request_id = str(uuid4())

    token = set_request_id(request_id)

    started_at = perf_counter()

    try:
        response = await call_next(request)

        duration_ms = (perf_counter() - started_at) * 1000

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "http_request_completed",
            extra={
                "event": "http_request_completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(
                    duration_ms,
                    2,
                ),
            },
        )

        return response

    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000

        logger.exception(
            "http_request_failed",
            extra={
                "event": "http_request_failed",
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": round(
                    duration_ms,
                    2,
                ),
            },
        )

        raise

    finally:
        reset_request_id(token)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "rfq-intelligence",
    }


@app.post(
    "/rfq/process",
    response_model=ProcessRFQResponse,
    dependencies=[Depends(require_api_key)],
)
def process_rfq(
    request: ProcessRFQRequest,
) -> ProcessRFQResponse:
    try:
        result = process_rfq_email(
            email_text=request.email_text,
            sender_email=request.sender_email,
            products=app.state.products,
            customers=app.state.customers,
            contacts=app.state.contacts,
            client=app.state.openai_client,
        )

    except openai.APIConnectionError as exc:
        _log_ai_dependency_failure(
            error=exc,
            upstream_status_code=None,
        )

        raise _ai_dependency_unavailable() from exc

    except openai.APIStatusError as exc:
        if not _is_transient_openai_status(exc.status_code):
            raise

        _log_ai_dependency_failure(
            error=exc,
            upstream_status_code=exc.status_code,
        )

        raise _ai_dependency_unavailable() from exc

    _log_rfq_result(result)

    return _to_api_response(result)


def _is_transient_openai_status(
    status_code: int,
) -> bool:
    return status_code in _TRANSIENT_OPENAI_STATUS_CODES or status_code >= 500


def _ai_dependency_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "AI_DEPENDENCY_UNAVAILABLE",
            "message": ("AI extraction service is temporarily unavailable."),
        },
    )


def _log_ai_dependency_failure(
    error: Exception,
    upstream_status_code: int | None,
) -> None:
    logger.warning(
        ("ai_dependency_unavailable error_type=%s upstream_status_code=%s"),
        type(error).__name__,
        upstream_status_code,
        extra={
            "event": "ai_dependency_unavailable",
        },
    )


def _log_rfq_result(
    result: RFQProcessingResult,
) -> None:
    extra: dict[str, object] = {
        "event": "rfq_processed",
        "rfq_status": result.status.value,
    }

    if result.customer is not None:
        extra["customer_id"] = result.customer.customer_id

    if result.model_metrics is not None:
        metrics = result.model_metrics

        extra["model"] = metrics.model
        extra["model_response_id"] = metrics.response_id
        extra["model_latency_ms"] = round(
            metrics.latency_ms,
            2,
        )
        extra["estimated_cost_usd"] = str(metrics.estimated_cost_usd)

    logger.info(
        "rfq_processed",
        extra=extra,
    )


def _to_api_response(
    result: RFQProcessingResult,
) -> ProcessRFQResponse:
    customer = None

    if result.customer is not None:
        customer = CustomerAPIResponse(
            customer_id=(result.customer.customer_id),
            company_name=(result.customer.company_name),
            discount_pct=(result.customer.discount_pct),
        )

    lines = [_line_to_api_response(line) for line in result.lines]

    quote = None

    if result.status == RFQProcessingStatus.READY_FOR_QUOTE:
        summary = build_quote_summary(result)

        quote = QuoteAPIResponse(
            line_count=summary.line_count,
            subtotal_eur=summary.subtotal_eur,
        )

    model_metrics = None

    if result.model_metrics is not None:
        metrics = result.model_metrics
        usage = metrics.usage

        model_metrics = ModelMetricsAPIResponse(
            model=metrics.model,
            response_id=metrics.response_id,
            latency_ms=metrics.latency_ms,
            estimated_cost_usd=(metrics.estimated_cost_usd),
            usage=ModelUsageAPIResponse(
                input_tokens=usage.input_tokens,
                cached_input_tokens=(usage.cached_input_tokens),
                cache_write_tokens=(usage.cache_write_tokens),
                output_tokens=(usage.output_tokens),
                reasoning_tokens=(usage.reasoning_tokens),
                total_tokens=(usage.total_tokens),
            ),
        )

    return ProcessRFQResponse(
        status=result.status.value,
        customer=customer,
        reason_codes=[issue.value for issue in result.issues],
        lines=lines,
        quote=quote,
        model_metrics=model_metrics,
    )


def _line_to_api_response(
    processed_line: ProcessedRFQLine,
) -> RFQLineAPIResponse:
    conversion = processed_line.conversion
    processing = processed_line.processing

    quantity = None
    unit = None

    if conversion.line is not None:
        quantity = conversion.line.quantity
        unit = conversion.line.unit

    match_response = None
    decision_response = None
    price_response = None

    if processing is not None:
        match = processing.match

        match_response = MatchAPIResponse(
            status=match.status.value,
            method=(match.method.value if match.method is not None else None),
            sku=(match.product.sku if match.product is not None else None),
            product_name=(match.product.name if match.product is not None else None),
            candidate_skus=[product.sku for product in match.candidates],
            best_score=match.best_score,
            second_best_score=(match.second_best_score),
        )

        if processing.decision is not None:
            decision = processing.decision

            decision_response = DecisionAPIResponse(
                status=decision.status.value,
                reason_codes=[reason.value for reason in decision.reasons],
            )

        if processing.price is not None:
            price = processing.price

            price_response = PriceAPIResponse(
                catalog_unit_price_eur=(price.catalog_unit_price_eur),
                discount_pct=(price.discount_pct),
                unit_price_eur=(price.unit_price_eur),
                subtotal_eur=(price.subtotal_eur),
            )

    return RFQLineAPIResponse(
        product_query=(conversion.extracted.product_query),
        quantity=quantity,
        unit=unit,
        extraction_issues=[issue.value for issue in conversion.issues],
        match=match_response,
        decision=decision_response,
        price=price_response,
    )
