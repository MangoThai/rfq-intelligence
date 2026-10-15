from decimal import Decimal

import pytest

from rfq_intelligence.observability import (
    GPT_6_LUNA_STANDARD_PRICING,
    ModelCallMetrics,
    ModelUsage,
    estimate_model_cost_usd,
    summarize_model_metrics,
)


def make_metrics(
    *,
    response_id: str,
    latency_ms: float,
    input_tokens: int,
    output_tokens: int,
    cost: str,
) -> ModelCallMetrics:
    usage = ModelUsage(
        input_tokens=input_tokens,
        cached_input_tokens=0,
        cache_write_tokens=0,
        output_tokens=output_tokens,
        reasoning_tokens=0,
        total_tokens=input_tokens + output_tokens,
    )

    return ModelCallMetrics(
        model="test-model",
        response_id=response_id,
        latency_ms=latency_ms,
        usage=usage,
        estimated_cost_usd=Decimal(cost),
    )


def test_estimate_model_cost_without_cache() -> None:
    usage = ModelUsage(
        input_tokens=1000,
        cached_input_tokens=0,
        cache_write_tokens=0,
        output_tokens=200,
        reasoning_tokens=0,
        total_tokens=1200,
    )

    cost = estimate_model_cost_usd(
        usage=usage,
        pricing=GPT_6_LUNA_STANDARD_PRICING,
    )

    assert cost == Decimal("0.00020")


def test_estimate_model_cost_with_cached_input() -> None:
    usage = ModelUsage(
        input_tokens=1000,
        cached_input_tokens=600,
        cache_write_tokens=0,
        output_tokens=200,
        reasoning_tokens=0,
        total_tokens=1200,
    )

    cost = estimate_model_cost_usd(
        usage=usage,
        pricing=GPT_6_LUNA_STANDARD_PRICING,
    )

    assert cost == Decimal("0.000146")


def test_estimate_model_cost_rejects_invalid_usage() -> None:
    usage = ModelUsage(
        input_tokens=100,
        cached_input_tokens=80,
        cache_write_tokens=30,
        output_tokens=10,
        reasoning_tokens=0,
        total_tokens=110,
    )

    with pytest.raises(
        ValueError,
        match="cannot exceed input tokens",
    ):
        estimate_model_cost_usd(
            usage=usage,
            pricing=GPT_6_LUNA_STANDARD_PRICING,
        )


def test_summarize_model_metrics() -> None:
    metrics = [
        make_metrics(
            response_id="resp_1",
            latency_ms=1000.0,
            input_tokens=500,
            output_tokens=100,
            cost="0.00010",
        ),
        make_metrics(
            response_id="resp_2",
            latency_ms=2000.0,
            input_tokens=600,
            output_tokens=120,
            cost="0.00012",
        ),
        make_metrics(
            response_id="resp_3",
            latency_ms=5000.0,
            input_tokens=700,
            output_tokens=130,
            cost="0.00014",
        ),
        None,
    ]

    summary = summarize_model_metrics(metrics)

    assert summary.total_requests == 4
    assert summary.model_calls == 3
    assert summary.skipped_model_calls == 1

    assert summary.total_input_tokens == 1800
    assert summary.total_output_tokens == 350
    assert summary.total_tokens == 2150

    assert summary.total_cost_usd == Decimal("0.00036")
    assert summary.average_cost_per_call_usd == Decimal("0.00012")

    assert summary.average_latency_ms == pytest.approx(2666.6666666666665)
    assert summary.p95_latency_ms == 5000.0

    assert summary.average_tokens_per_call == pytest.approx(716.6666666666666)

    assert summary.model_call_rate == pytest.approx(0.75)


def test_summarize_model_metrics_without_model_calls() -> None:
    summary = summarize_model_metrics([None, None])

    assert summary.total_requests == 2
    assert summary.model_calls == 0
    assert summary.skipped_model_calls == 2

    assert summary.total_tokens == 0
    assert summary.total_cost_usd == Decimal("0")

    assert summary.average_latency_ms == 0.0
    assert summary.p95_latency_ms == 0.0
    assert summary.average_tokens_per_call == 0.0
    assert summary.average_cost_per_call_usd == Decimal("0")

    assert summary.model_call_rate == 0.0
