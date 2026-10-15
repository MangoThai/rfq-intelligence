from dataclasses import dataclass
from time import perf_counter
from typing import Annotated, Literal

from openai import OpenAI
from pydantic import BaseModel, Field, StringConstraints

from rfq_intelligence.observability import (
    GPT_6_LUNA_STANDARD_PRICING,
    ModelCallMetrics,
    ModelUsage,
    estimate_model_cost_usd,
)

DEFAULT_EXTRACTION_MODEL = "gpt-6-luna"


QuantityText = Annotated[
    str,
    StringConstraints(
        pattern=r"^\d+(?:[.,]\d+)?$",
    ),
]


class ExtractedRFQLine(BaseModel):
    product_query: str = Field(
        description=(
            "Exact product reference or product description from the customer. "
            "Preserve the customer's wording. Do not correct or normalize it."
        )
    )
    quantity: QuantityText | None = Field(
        description=(
            "Requested numeric quantity only. "
            "Return only digits with an optional decimal separator, "
            'for example "20", "50", "2.5", or "2,5". '
            "Never include the unit or other words. "
            "Return null when the quantity cannot be determined reliably."
        )
    )
    unit: Literal["piece", "meter"] | None = Field(
        description=(
            "Requested sales unit when explicit or clearly implied. "
            "Use piece for countable products and meter for tubing. "
            "Return null if unreliable."
        )
    )
    substitution_requested: bool = Field(
        default=False,
        description=(
            "True only when the customer explicitly asks for or allows "
            "a substitute, alternative, equivalent, or replacement product."
        ),
    )
    delivery_constraint: str | None = Field(
        default=None,
        description=(
            "Exact delivery deadline, urgency, or delivery constraint "
            "explicitly stated by the customer. Otherwise null."
        ),
    )


class ExtractedRFQ(BaseModel):
    lines: list[ExtractedRFQLine]


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    rfq: ExtractedRFQ
    metrics: ModelCallMetrics


_EXTRACTION_INSTRUCTIONS = """
You extract requested product lines from French B2B industrial RFQ emails.

Rules:
- Return one structured line for each requested product.
- Preserve the customer's product reference or description in product_query.
- Never correct, normalize, invent, or replace a customer product reference.
- quantity must contain only the numeric quantity.
- Never include units or words inside quantity.
- Examples:
  - "20 pièces" -> quantity="20", unit="piece"
  - "50 mètres" -> quantity="50", unit="meter"
  - "2,5 mètres" -> quantity="2,5", unit="meter"
- If quantity is missing or unreliable, return null.
- Use unit="piece" for countable products when the request clearly refers
  to a number of items.
- Use unit="meter" when tubing is explicitly requested by length in meters.
- If the unit cannot be determined reliably, return null.
- substitution_requested is true only when the customer explicitly asks for
  or permits a substitute, alternative, equivalent, or replacement.
- Preserve an explicit delivery constraint such as "demain matin",
  "avant vendredi", or "urgent" in delivery_constraint.
- Do not infer price, stock, availability, discount, delivery feasibility,
  or whether a substitution is acceptable.
- Ignore greetings, signatures, and unrelated email content.
""".strip()


def extract_rfq_email(
    email_text: str,
    client: OpenAI,
    model: str = DEFAULT_EXTRACTION_MODEL,
) -> ExtractedRFQ:
    return extract_rfq_email_with_metrics(
        email_text=email_text,
        client=client,
        model=model,
    ).rfq


def extract_rfq_email_with_metrics(
    email_text: str,
    client: OpenAI,
    model: str = DEFAULT_EXTRACTION_MODEL,
) -> ExtractionResult:
    if not email_text.strip():
        raise ValueError("RFQ email text cannot be empty.")

    started_at = perf_counter()

    response = client.responses.parse(
        model=model,
        reasoning={"effort": "none"},
        store=False,
        input=[
            {
                "role": "system",
                "content": _EXTRACTION_INSTRUCTIONS,
            },
            {
                "role": "user",
                "content": email_text,
            },
        ],
        text_format=ExtractedRFQ,
    )

    latency_ms = (perf_counter() - started_at) * 1000

    extracted = response.output_parsed

    if extracted is None:
        raise RuntimeError("OpenAI returned no parsed RFQ extraction.")

    usage = _build_model_usage(response.usage)

    metrics = ModelCallMetrics(
        model=model,
        response_id=response.id,
        latency_ms=latency_ms,
        usage=usage,
        estimated_cost_usd=estimate_model_cost_usd(
            usage=usage,
            pricing=GPT_6_LUNA_STANDARD_PRICING,
        ),
    )

    return ExtractionResult(
        rfq=extracted,
        metrics=metrics,
    )


def _build_model_usage(
    response_usage: object | None,
) -> ModelUsage:
    if response_usage is None:
        raise RuntimeError("OpenAI response did not include token usage.")

    input_tokens = _read_int(
        response_usage,
        "input_tokens",
    )
    output_tokens = _read_int(
        response_usage,
        "output_tokens",
    )
    total_tokens = _read_int(
        response_usage,
        "total_tokens",
    )

    input_details = getattr(
        response_usage,
        "input_tokens_details",
        None,
    )
    output_details = getattr(
        response_usage,
        "output_tokens_details",
        None,
    )

    cached_input_tokens = _read_optional_int(
        input_details,
        "cached_tokens",
    )
    cache_write_tokens = _read_optional_int(
        input_details,
        "cache_write_tokens",
    )
    reasoning_tokens = _read_optional_int(
        output_details,
        "reasoning_tokens",
    )

    return ModelUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_write_tokens=cache_write_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
    )


def _read_int(
    source: object,
    attribute: str,
) -> int:
    value = getattr(
        source,
        attribute,
        None,
    )

    if not isinstance(value, int):
        raise RuntimeError(f"OpenAI usage field {attribute!r} is missing.")

    return value


def _read_optional_int(
    source: object | None,
    attribute: str,
) -> int:
    if source is None:
        return 0

    value = getattr(
        source,
        attribute,
        None,
    )

    if value is None:
        return 0

    if not isinstance(value, int):
        raise RuntimeError(f"OpenAI usage field {attribute!r} is invalid.")

    return value
