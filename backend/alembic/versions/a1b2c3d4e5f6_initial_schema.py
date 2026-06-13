"""initial_schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-13 00:00:00.000000

Creates all 10 tables that make up the THEATER schema.  Tables are created
in FK-dependency order (dependees before dependants); dropped in reverse.

This migration is the authoritative source of the initial schema.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. users ──────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )

    # ── 2. unit_templates ─────────────────────────────────────────────────────
    op.create_table(
        "unit_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("echelon", sa.String(), nullable=True),
        sa.Column("nation_group", sa.String(), nullable=True),
        sa.Column("capabilities", sa.Text(), nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("typical_strength", sa.Integer(), nullable=True),
        sa.Column("is_custom", sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 3. scenarios (references users) ───────────────────────────────────────
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("classification", sa.String(), nullable=True),
        sa.Column("scenario_type", sa.String(), nullable=True),
        sa.Column("timeframe", sa.String(), nullable=True),
        sa.Column("geography", sa.Text(), nullable=True),
        sa.Column("situation", sa.Text(), nullable=True),
        sa.Column("factions", sa.Text(), nullable=True),
        sa.Column("injects", sa.Text(), nullable=True),
        sa.Column("win_conditions", sa.Text(), nullable=True),
        sa.Column("ai_notes", sa.Text(), nullable=True),
        sa.Column("is_template", sa.Boolean(), nullable=True),
        sa.Column("template_name", sa.String(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=True),
        sa.Column("published_by_user_id", sa.String(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=True),
        sa.Column("is_official", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 4. game_sessions (references scenarios, users) ────────────────────────
    op.create_table(
        "game_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("scenario_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("current_turn", sa.Integer(), nullable=True),
        sa.Column("max_turns", sa.Integer(), nullable=True),
        sa.Column("time_per_turn_hours", sa.Integer(), nullable=True),
        sa.Column("faction_assignments", sa.Text(), nullable=True),
        sa.Column("current_game_state", sa.Text(), nullable=True),
        sa.Column("previous_game_state", sa.Text(), nullable=True),
        sa.Column("ai_personality_overrides", sa.Text(), nullable=True),
        sa.Column("forecasting_enabled", sa.Boolean(), nullable=True),
        sa.Column("total_brier_score", sa.Float(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 5. turn_logs (references game_sessions) ───────────────────────────────
    op.create_table(
        "turn_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("turn_number", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("player_moves", sa.Text(), nullable=True),
        sa.Column("ai_moves", sa.Text(), nullable=True),
        sa.Column("adjudication", sa.Text(), nullable=True),
        sa.Column("injects_triggered", sa.Text(), nullable=True),
        sa.Column("game_master_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 6. turn_forecasts (references turn_logs, game_sessions, users) ────────
    op.create_table(
        "turn_forecasts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("turn_id", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("turn_number", sa.Integer(), nullable=True),
        sa.Column("p_blue_wins", sa.Float(), nullable=True),
        sa.Column("p_red_wins", sa.Float(), nullable=True),
        sa.Column("p_escalation", sa.Float(), nullable=True),
        sa.Column("p_key_objective_captured", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("blue_achieved", sa.Boolean(), nullable=True),
        sa.Column("red_achieved", sa.Boolean(), nullable=True),
        sa.Column("escalation_occurred", sa.Boolean(), nullable=True),
        sa.Column("key_objective_captured", sa.Boolean(), nullable=True),
        sa.Column("brier_score", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"]),
        sa.ForeignKeyConstraint(["turn_id"], ["turn_logs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 7. monte_carlo_results (references game_sessions, scenarios) ──────────
    op.create_table(
        "monte_carlo_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("scenario_id", sa.String(), nullable=True),
        sa.Column("results", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["scenario_id"], ["scenarios.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 8. aar_reports (references game_sessions) ─────────────────────────────
    op.create_table(
        "aar_reports",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("share_token", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("share_token"),
    )

    # ── 9. adjudication_logs (references turn_logs, game_sessions, users) ─────
    op.create_table(
        "adjudication_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("turn_id", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("function_name", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("ai_inputs", sa.Text(), nullable=True),
        sa.Column("ai_system_prompt", sa.Text(), nullable=True),
        sa.Column("ai_user_message", sa.Text(), nullable=True),
        sa.Column("ai_response_full", sa.Text(), nullable=True),
        sa.Column("ai_reasoning", sa.Text(), nullable=True),
        sa.Column("turn_outcome", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"]),
        sa.ForeignKeyConstraint(["turn_id"], ["turn_logs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── 10. token_usage (references users, game_sessions) ─────────────────────
    op.create_table(
        "token_usage",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("function_name", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
        sa.Column("claude_model", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # Drop in reverse FK-dependency order so referencing tables are removed first.
    op.drop_table("token_usage")
    op.drop_table("adjudication_logs")
    op.drop_table("aar_reports")
    op.drop_table("monte_carlo_results")
    op.drop_table("turn_forecasts")
    op.drop_table("turn_logs")
    op.drop_table("game_sessions")
    op.drop_table("scenarios")
    op.drop_table("unit_templates")
    op.drop_table("users")
