from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from math import ceil

_ONE_MILLION = Decimal("1000000")


@dataclass(frozen=True, slots=True)
class ModelPricing:
    input_per_million_usd: Decimal
    cached_input_per_million_usd: Decimal
    cache_write_per_million_usd: Decimal
    output_per_million_usd: Decimal


@dataclass(frozen=True, slots=True)
class ModelUsage:
    input_tokens: int
    cached_input_tokens: int
    cache_write_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class ModelCallMetrics:
    model: str
    response_id: str
    latency_ms: float
    usage: ModelUsage
    estimated_cost_usd: Decimal


@dataclass(frozen=True, slots=True)
class ObservabilitySummary:
    total_requests: int
    model_calls: int
    skipped_model_calls: int

    total_input_tokens: int
    total_cached_input_tokens: int
    total_cache_write_tokens: int
    total_output_tokens: int
    total_reasoning_tokens: int
    total_tokens: int

    total_cost_usd: Decimal

    average_latency_ms: float
    p95_latency_ms: float

    average_tokens_per_call: float
    average_cost_per_call_usd: Decimal

    model_call_rate: float


GPT_6_LUNA_STANDARD_PRICING = ModelPricing(
    input_per_million_usd=Decimal("0.10"),
    cached_input_per_million_usd=Decimal("0.01"),
    cache_write_per_million_usd=Decimal("0.125"),
    output_per_million_usd=Decimal("0.50"),
)


def estimate_model_cost_usd(
    usage: ModelUsage,
    pricing: ModelPricing,
) -> Decimal:
    ordinary_input_tokens = (
        usage.input_tokens - usage.cached_input_tokens - usage.cache_write_tokens
    )

    if ordinary_input_tokens < 0:
        raise ValueError("Cached and cache-write tokens cannot exceed input tokens.")

    ordinary_input_cost = (
        Decimal(ordinary_input_tokens) * pricing.input_per_million_usd / _ONE_MILLION
    )

    cached_input_cost = (
        Decimal(usage.cached_input_tokens) * pricing.cached_input_per_million_usd / _ONE_MILLION
    )

    cache_write_cost = (
        Decimal(usage.cache_write_tokens) * pricing.cache_write_per_million_usd / _ONE_MILLION
    )

    output_cost = Decimal(usage.output_tokens) * pricing.output_per_million_usd / _ONE_MILLION

    return ordinary_input_cost + cached_input_cost + cache_write_cost + output_cost


def summarize_model_metrics(
    metrics: Sequence[ModelCallMetrics | None],
) -> ObservabilitySummary:
    total_requests = len(metrics)

    model_calls = tuple(metric for metric in metrics if metric is not None)

    model_call_count = len(model_calls)
    skipped_model_calls = total_requests - model_call_count

    if not model_calls:
        return ObservabilitySummary(
            total_requests=total_requests,
            model_calls=0,
            skipped_model_calls=skipped_model_calls,
            total_input_tokens=0,
            total_cached_input_tokens=0,
            total_cache_write_tokens=0,
            total_output_tokens=0,
            total_reasoning_tokens=0,
            total_tokens=0,
            total_cost_usd=Decimal("0"),
            average_latency_ms=0.0,
            p95_latency_ms=0.0,
            average_tokens_per_call=0.0,
            average_cost_per_call_usd=Decimal("0"),
            model_call_rate=0.0,
        )

    total_input_tokens = sum(metric.usage.input_tokens for metric in model_calls)

    total_cached_input_tokens = sum(metric.usage.cached_input_tokens for metric in model_calls)

    total_cache_write_tokens = sum(metric.usage.cache_write_tokens for metric in model_calls)

    total_output_tokens = sum(metric.usage.output_tokens for metric in model_calls)

    total_reasoning_tokens = sum(metric.usage.reasoning_tokens for metric in model_calls)

    total_tokens = sum(metric.usage.total_tokens for metric in model_calls)

    total_cost_usd = sum(
        (metric.estimated_cost_usd for metric in model_calls),
        start=Decimal("0"),
    )

    average_latency_ms = sum(metric.latency_ms for metric in model_calls) / model_call_count

    p95_latency_ms = _percentile_nearest_rank(
        values=[metric.latency_ms for metric in model_calls],
        percentile=0.95,
    )

    average_tokens_per_call = total_tokens / model_call_count

    average_cost_per_call_usd = total_cost_usd / Decimal(model_call_count)

    model_call_rate = model_call_count / total_requests if total_requests else 0.0

    return ObservabilitySummary(
        total_requests=total_requests,
        model_calls=model_call_count,
        skipped_model_calls=skipped_model_calls,
        total_input_tokens=total_input_tokens,
        total_cached_input_tokens=total_cached_input_tokens,
        total_cache_write_tokens=total_cache_write_tokens,
        total_output_tokens=total_output_tokens,
        total_reasoning_tokens=total_reasoning_tokens,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd,
        average_latency_ms=average_latency_ms,
        p95_latency_ms=p95_latency_ms,
        average_tokens_per_call=average_tokens_per_call,
        average_cost_per_call_usd=average_cost_per_call_usd,
        model_call_rate=model_call_rate,
    )


def _percentile_nearest_rank(
    values: Sequence[float],
    percentile: float,
) -> float:
    if not values:
        return 0.0

    if not 0 < percentile <= 1:
        raise ValueError("Percentile must be greater than 0 and at most 1.")

    ordered = sorted(values)

    rank = ceil(percentile * len(ordered))

    return ordered[rank - 1]
