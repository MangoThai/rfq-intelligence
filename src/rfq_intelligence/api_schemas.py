from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

RFQStatusValue = Literal[
    "READY_FOR_QUOTE",
    "REVIEW_REQUIRED",
]

MatchStatusValue = Literal[
    "EXACT_MATCH",
    "MATCHED",
    "AMBIGUOUS",
    "NOT_FOUND",
]

LineStatusValue = Literal[
    "READY_FOR_QUOTE",
    "REVIEW_REQUIRED",
]


class ProcessRFQRequest(BaseModel):
    sender_email: str = Field(
        min_length=1,
        description="Email address of the RFQ sender.",
    )
    email_text: str = Field(
        min_length=1,
        description="Raw text content of the RFQ email.",
    )


class CustomerAPIResponse(BaseModel):
    customer_id: str
    company_name: str
    discount_pct: Decimal


class MatchAPIResponse(BaseModel):
    status: MatchStatusValue
    method: str | None = None

    sku: str | None = None
    product_name: str | None = None

    candidate_skus: list[str] = Field(default_factory=list)

    best_score: float | None = None
    second_best_score: float | None = None


class DecisionAPIResponse(BaseModel):
    status: LineStatusValue
    reason_codes: list[str] = Field(default_factory=list)


class PriceAPIResponse(BaseModel):
    catalog_unit_price_eur: Decimal
    discount_pct: Decimal
    unit_price_eur: Decimal
    subtotal_eur: Decimal


class RFQLineAPIResponse(BaseModel):
    product_query: str

    quantity: Decimal | None = None
    unit: str | None = None

    extraction_issues: list[str] = Field(default_factory=list)

    match: MatchAPIResponse | None = None
    decision: DecisionAPIResponse | None = None
    price: PriceAPIResponse | None = None


class QuoteAPIResponse(BaseModel):
    line_count: int
    subtotal_eur: Decimal


class ModelUsageAPIResponse(BaseModel):
    input_tokens: int
    cached_input_tokens: int
    cache_write_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int


class ModelMetricsAPIResponse(BaseModel):
    model: str
    response_id: str
    latency_ms: float
    estimated_cost_usd: Decimal
    usage: ModelUsageAPIResponse


class ProcessRFQResponse(BaseModel):
    status: RFQStatusValue

    customer: CustomerAPIResponse | None = None

    reason_codes: list[str] = Field(default_factory=list)

    lines: list[RFQLineAPIResponse] = Field(default_factory=list)

    quote: QuoteAPIResponse | None = None

    model_metrics: ModelMetricsAPIResponse | None = None
