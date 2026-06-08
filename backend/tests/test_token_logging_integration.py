"""Integration test: running a turn through a stubbed AsyncAnthropic client
writes a TokenUsage row with the right cost and attribution.

The Claude HTTP call is replaced with a fake so the test is offline and
deterministic; everything downstream (_log_tokens -> pricing -> DB write) is
exercised for real against the test SQLite DB configured in conftest.
"""
import asyncio
import json
from types import SimpleNamespace

import ai_client
import database
import models
import pricing


class _FakeMessages:
    def __init__(self, response):
        self._response = response

    async def create(self, **kwargs):
        # Record the kwargs so we can assert on the cached prompt structure
        _FakeMessages.last_kwargs = kwargs
        return self._response


class _FakeClient:
    def __init__(self, response):
        self.messages = _FakeMessages(response)


def _fake_response(usage):
    block = SimpleNamespace(
        type="text",
        text=json.dumps({
            "turn_number": 1,
            "narrative": "Test narrative.",
            "key_events": [],
            "casualties": [],
            "position_updates": [],
        }),
    )
    return SimpleNamespace(content=[block], usage=usage, stop_reason="end_turn")


def _run_adjudication(monkeypatch, usage):
    monkeypatch.setattr(ai_client, "get_client", lambda: _FakeClient(_fake_response(usage)))
    return asyncio.run(
        ai_client.adjudicate_turn(
            scenario={"title": "Test", "scenario_type": "Tactical", "situation": {}},
            blue_moves=[],
            red_moves=[],
            current_game_state={"unit_status": [], "faction_scores": []},
            turn_number=1,
            user_id="user-123",
            session_id="session-abc",
        )
    )


def test_turn_writes_token_usage_row(monkeypatch):
    usage = SimpleNamespace(
        input_tokens=1200,
        output_tokens=800,
        cache_read_input_tokens=4000,
        cache_creation_input_tokens=600,
    )

    result = _run_adjudication(monkeypatch, usage)
    assert result["turn_number"] == 1  # the parsed AI output came back

    db = database.SessionLocal()
    try:
        rows = db.query(models.TokenUsage).all()
        assert len(rows) == 1
        row = rows[0]

        # Token buckets persisted correctly
        assert row.function_name == "adjudicate_turn"
        assert row.input_tokens == 1200
        assert row.output_tokens == 800
        assert row.cache_read_tokens == 4000
        assert row.cache_write_tokens == 600

        # Attribution threaded through from the router-level context
        assert row.user_id == "user-123"
        assert row.session_id == "session-abc"
        assert row.claude_model == database.settings.claude_model

        # Cost matches the pricing helper exactly
        expected_cost = pricing.compute_cost(
            input_tokens=1200,
            output_tokens=800,
            cache_creation_tokens=600,
            cache_read_tokens=4000,
            model=database.settings.claude_model,
        )
        assert row.total_cost_usd == expected_cost
    finally:
        db.close()


def test_missing_cache_fields_default_to_zero(monkeypatch):
    # A usage object without cache_* attributes (cache miss) must not crash
    usage = SimpleNamespace(input_tokens=500, output_tokens=100)

    _run_adjudication(monkeypatch, usage)

    db = database.SessionLocal()
    try:
        row = db.query(models.TokenUsage).one()
        assert row.cache_read_tokens == 0
        assert row.cache_write_tokens == 0
        assert row.total_cost_usd == pricing.compute_cost(
            input_tokens=500, output_tokens=100, model=database.settings.claude_model
        )
    finally:
        db.close()


def test_red_team_system_prompt_is_static(monkeypatch):
    """The cached red-team system block must not contain per-faction text,
    otherwise the prompt cache fragments per faction."""
    usage = SimpleNamespace(input_tokens=100, output_tokens=50)
    monkeypatch.setattr(ai_client, "get_client", lambda: _FakeClient(_fake_response(usage)))

    asyncio.run(
        ai_client.generate_red_team_moves(
            scenario={"title": "T", "timeframe": "now", "geography": {}, "situation": {}},
            faction={"faction_id": "RED-01", "name": "Northern Front", "ai_personality": "Aggressive"},
            game_state={"unit_status": [], "faction_scores": []},
            player_moves=[],
            turn_history=[],
            current_turn=1,
            injects=[],
            user_id="u1",
            session_id="s1",
        )
    )

    system_blocks = _FakeMessages.last_kwargs["system"]
    cached_system_text = system_blocks[0]["text"]
    # Faction identity should live in the dynamic user turn, not the cached system block
    assert "Northern Front" not in cached_system_text
    assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}
    user_content = _FakeMessages.last_kwargs["messages"][0]["content"]
    assert "Northern Front" in user_content
