from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from database import Base

def gen_id():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="player")  # admin, game_master, player
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class Scenario(Base):
    __tablename__ = "scenarios"
    id = Column(String, primary_key=True, default=gen_id)
    title = Column(String, nullable=False)
    classification = Column(String, default="UNCLASSIFIED")
    scenario_type = Column(String)
    timeframe = Column(String)
    geography = Column(Text)       # JSON
    situation = Column(Text)       # JSON
    factions = Column(Text)        # JSON array
    injects = Column(Text)         # JSON array
    win_conditions = Column(Text)  # JSON
    ai_notes = Column(Text)
    is_template = Column(Boolean, default=False)
    template_name = Column(String, nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UnitTemplate(Base):
    __tablename__ = "unit_templates"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    type = Column(String)
    echelon = Column(String)
    nation_group = Column(String)
    capabilities = Column(Text)   # JSON array
    limitations = Column(Text)    # JSON array
    typical_strength = Column(Integer, default=0)
    is_custom = Column(Boolean, default=False)

class GameSession(Base):
    __tablename__ = "game_sessions"
    id = Column(String, primary_key=True, default=gen_id)
    scenario_id = Column(String, ForeignKey("scenarios.id"))
    title = Column(String)
    status = Column(String, default="Setup")  # Setup, Active, Paused, Complete
    current_turn = Column(Integer, default=0)
    max_turns = Column(Integer)
    time_per_turn_hours = Column(Integer)
    faction_assignments = Column(Text)          # JSON
    current_game_state = Column(Text)           # JSON
    previous_game_state = Column(Text)          # JSON — snapshot before last adjudication
    ai_personality_overrides = Column(Text)     # JSON — faction_id → personality, stored per-session
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scenario = relationship("Scenario")
    turn_logs = relationship("TurnLog", back_populates="session", order_by="TurnLog.turn_number")
    aar_reports = relationship("AARReport", back_populates="session")

class TurnLog(Base):
    __tablename__ = "turn_logs"
    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("game_sessions.id"))
    turn_number = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    player_moves = Column(Text)         # JSON
    ai_moves = Column(Text)             # JSON
    adjudication = Column(Text)         # JSON
    injects_triggered = Column(Text)    # JSON array
    game_master_notes = Column(Text)

    session = relationship("GameSession", back_populates="turn_logs")

class MonteCarloResult(Base):
    __tablename__ = "monte_carlo_results"
    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("game_sessions.id"), nullable=True)
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=True)
    results = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)

class AARReport(Base):
    __tablename__ = "aar_reports"
    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("game_sessions.id"))
    content = Column(Text)  # JSON
    share_token = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("GameSession", back_populates="aar_reports")

class TokenUsage(Base):
    __tablename__ = "token_usage"
    id = Column(String, primary_key=True, default=gen_id)
    function_name = Column(String, nullable=False)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cache_read_tokens = Column(Integer, default=0)
    cache_write_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
