"""Measure prompt-cache effectiveness against the live Anthropic API.

This exercises the exact same cached system+schema blocks the gameplay
endpoints use (here: the scenario generator's blocks, which are the largest),
sending N identical requests and reporting cache-read vs. uncached input tokens
on each. The first call writes the cache (cache_creation > 0); subsequent calls
read it (cache_read > 0), which is the "before/after" the task asks for.

Requires a real ANTHROPIC_API_KEY in the environment / .env. Run from backend/:

    cd backend && python -m scripts.measure_cache --runs 5

Note: this makes real (small, max_tokens=16) API calls and costs a few cents.
"""
from __future__ import annotations

import argparse
import asyncio

import ai_client
from database import settings


def _cache_blocks() -> list[dict]:
    # Same two cached blocks as generate_scenario() — well over the cache minimum.
    return [
        {"type": "text", "text": ai_client.SCENARIO_SYSTEM, "cache_control": {"type": "ephemeral"}},
        {
            "type": "text",
            "text": f"\nOUTPUT SCHEMA (return exactly this structure):\n{ai_client.SCENARIO_SCHEMA}",
            "cache_control": {"type": "ephemeral"},
        },
    ]


async def _one_call(client, system) -> dict:
    resp = await client.messages.create(
        model=settings.claude_model,
        max_tokens=16,
        system=system,
        messages=[{"role": "user", "content": "Reply with the single word: OK"}],
    )
    u = resp.usage
    return {
        "input": getattr(u, "input_tokens", 0) or 0,
        "cache_creation": getattr(u, "cache_creation_input_tokens", 0) or 0,
        "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
        "output": getattr(u, "output_tokens", 0) or 0,
    }


async def main(runs: int) -> None:
    if not settings.anthropic_api_key or settings.anthropic_api_key == "test-key-not-real":
        raise SystemExit("ANTHROPIC_API_KEY is not set — populate it in backend/.env first.")

    client = ai_client.get_client()
    system = _cache_blocks()

    print(f"Model: {settings.claude_model}")
    print(f"Sending {runs} identical requests with cached system+schema blocks.\n")
    print(f"{'run':>3}  {'uncached_in':>11}  {'cache_create':>12}  {'cache_read':>10}  {'output':>6}")

    first_static = None
    last = None
    for i in range(1, runs + 1):
        last = await _one_call(client, system)
        # The cached prefix size is (cache_creation on run 1) ~= (cache_read on later runs)
        if first_static is None:
            first_static = last["cache_creation"] + last["input"]
        print(
            f"{i:>3}  {last['input']:>11}  {last['cache_creation']:>12}  "
            f"{last['cache_read']:>10}  {last['output']:>6}"
        )

    if runs >= 2 and last and first_static:
        cached = last["cache_read"]
        pct = (cached / first_static * 100) if first_static else 0
        print(
            f"\nOn the final run, {cached} of ~{first_static} prefix tokens were served "
            f"from cache ({pct:.0f}% of the static prefix)."
        )
        print(
            "Cache reads bill at ~10% of input price, so that static prefix costs "
            "~90% less on every repeat call."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Measure prompt-cache hit rate against the live API.")
    parser.add_argument("--runs", type=int, default=5, help="Number of identical requests to send (default 5).")
    asyncio.run(main(parser.parse_args().runs))
