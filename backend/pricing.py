"""
Anthropic token pricing and cost calculation for THEATER.

Prices are USD per 1,000,000 tokens. `cache_write` is the cache-creation rate
(25% premium over input, i.e. 1.25x — the default 5-minute ephemeral TTL);
`cache_read` is the cache-hit rate (10% of input, i.e. 0.1x).

Anthropic's `usage` reports four disjoint token buckets per request:
  - input_tokens               (uncached input, full price)
  - output_tokens              (generated, output price)
  - cache_creation_input_tokens (written to cache, cache_write price)
  - cache_read_input_tokens     (served from cache, cache_read price)
These do not overlap, so total cost is a straight weighted sum.
"""
from __future__ import annotations

# Per-1M-token USD pricing, keyed by model id.
PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_write": 3.75, "cache_read": 0.30},
    "claude-opus-4-8":   {"input": 5.00, "output": 25.00, "cache_write": 6.25, "cache_read": 0.50},
    "claude-haiku-4-5":  {"input": 1.00, "output": 5.00,  "cache_write": 1.25, "cache_read": 0.10},
}

# Used when the model id isn't in PRICING (matches the project's default model).
_DEFAULT_MODEL = "claude-sonnet-4-6"

_PER_TOKEN = 1_000_000


def get_pricing(model: str | None) -> dict[str, float]:
    """Return the per-1M pricing dict for a model, falling back to the default."""
    if model and model in PRICING:
        return PRICING[model]
    return PRICING[_DEFAULT_MODEL]


def compute_cost(
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    model: str | None = None,
) -> float:
    """Compute the USD cost of a single Claude call from its token buckets.

    Negative token counts are clamped to 0 so a malformed usage object can never
    produce a negative cost. Returns a float rounded to 6 decimal places
    (micro-dollar precision — enough to sum thousands of small calls without drift).
    """
    rates = get_pricing(model)

    def _n(x) -> int:
        try:
            v = int(x)
        except (TypeError, ValueError):
            return 0
        return v if v > 0 else 0

    cost = (
        _n(input_tokens) * rates["input"]
        + _n(output_tokens) * rates["output"]
        + _n(cache_creation_tokens) * rates["cache_write"]
        + _n(cache_read_tokens) * rates["cache_read"]
    ) / _PER_TOKEN
    return round(cost, 6)
