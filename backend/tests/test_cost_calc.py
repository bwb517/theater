"""Unit tests for pricing.compute_cost — edge cases the brief called out:
zero tokens, cache misses, cache hits, unknown model fallback, overflow, and
malformed inputs."""
import pricing


def test_zero_tokens_is_zero_cost():
    assert pricing.compute_cost(0, 0, 0, 0, "claude-sonnet-4-6") == 0.0


def test_cache_miss_input_output_only():
    # 1M input @ $3 + 1M output @ $15, no cache activity
    cost = pricing.compute_cost(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_creation_tokens=0,
        cache_read_tokens=0,
        model="claude-sonnet-4-6",
    )
    assert cost == round(3.0 + 15.0, 6)


def test_cache_hit_uses_cheaper_read_rate():
    # 1M cache-read tokens @ $0.30 (0.1x input) is far cheaper than full input
    read_cost = pricing.compute_cost(cache_read_tokens=1_000_000, model="claude-sonnet-4-6")
    full_input_cost = pricing.compute_cost(input_tokens=1_000_000, model="claude-sonnet-4-6")
    assert read_cost == 0.30
    assert read_cost < full_input_cost


def test_cache_creation_premium():
    # cache-creation is 1.25x input ($3.75 per 1M on sonnet)
    assert pricing.compute_cost(cache_creation_tokens=1_000_000, model="claude-sonnet-4-6") == 3.75


def test_all_four_buckets_sum():
    cost = pricing.compute_cost(
        input_tokens=1000,
        output_tokens=500,
        cache_creation_tokens=300,
        cache_read_tokens=2000,
        model="claude-sonnet-4-6",
    )
    expected = (1000 * 3.0 + 500 * 15.0 + 300 * 3.75 + 2000 * 0.30) / 1_000_000
    assert cost == round(expected, 6)


def test_unknown_model_falls_back_to_default():
    unknown = pricing.compute_cost(input_tokens=1_000_000, model="some-future-model")
    default = pricing.compute_cost(input_tokens=1_000_000, model="claude-sonnet-4-6")
    assert unknown == default


def test_none_model_uses_default():
    assert pricing.compute_cost(input_tokens=1_000_000, model=None) == 3.0


def test_negative_tokens_clamped_to_zero():
    # A malformed usage object must never produce a negative cost
    assert pricing.compute_cost(input_tokens=-5000, output_tokens=-1, model="claude-sonnet-4-6") == 0.0


def test_non_numeric_tokens_treated_as_zero():
    assert pricing.compute_cost(input_tokens=None, output_tokens="oops", model="claude-sonnet-4-6") == 0.0


def test_large_token_counts_no_overflow():
    # 1B input + 1B output should compute cleanly as a float
    cost = pricing.compute_cost(
        input_tokens=1_000_000_000,
        output_tokens=1_000_000_000,
        model="claude-sonnet-4-6",
    )
    assert cost == round(1000 * 3.0 + 1000 * 15.0, 6)
    assert cost == 18000.0


def test_opus_pricing_distinct_from_sonnet():
    opus = pricing.compute_cost(input_tokens=1_000_000, model="claude-opus-4-8")
    sonnet = pricing.compute_cost(input_tokens=1_000_000, model="claude-sonnet-4-6")
    assert opus == 5.0
    assert opus > sonnet
