"""
SQLAlchemy ORM models for the DFS Handicap Engine.

Schema follows the v9.0 specification:
  - slate_runs
  - stage1_forecasts
  - handoff_snapshots
  - stage2_blind_reviews
  - stage2_reconciliation
  - product_snapshots
  - stage2_reviews
  - entry_candidates
  - final_entries
  - clv_settlements
  - channel_economics

All tables are append-only (no UPDATE/DELETE in normal operation).
Alembic manages migrations.
"""

import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///dfs_engine.db")


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Append-only guard: block UPDATE and DELETE at the ORM level
# ---------------------------------------------------------------------------

def _block_update(mapper, connection, target):  # noqa: ARG001
    raise RuntimeError(
        f"Append-only ledger violation: attempted UPDATE on {type(target).__name__}. "
        "Use a new row with corrected values."
    )


def _block_delete(mapper, connection, target):  # noqa: ARG001
    raise RuntimeError(
        f"Append-only ledger violation: attempted DELETE on {type(target).__name__}."
    )


def _register_append_only(cls):
    """Register after_update / after_delete guards on an ORM class."""
    event.listen(cls, "after_update", _block_update)
    event.listen(cls, "after_delete", _block_delete)
    return cls


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

@_register_append_only
class SlateRun(Base):
    __tablename__ = "slate_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), unique=True, nullable=False)
    slate_date = Column(String(10), nullable=False)
    sports = Column(String(64), nullable=False)
    platforms = Column(String(256), nullable=False)
    mode = Column(String(16), nullable=False, default="DEEP")
    bankroll = Column(Float, nullable=False)
    information_state_hash = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)

    forecasts = relationship("Stage1Forecast", back_populates="run")


@_register_append_only
class Stage1Forecast(Base):
    __tablename__ = "stage1_forecasts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("slate_runs.run_id"), nullable=False)
    forecast_id = Column(String(64), unique=True, nullable=False)
    event_id = Column(String(64))
    player_id = Column(String(64))
    market = Column(String(64))
    threshold = Column(Float)
    p_over = Column(Float)
    p_under = Column(Float)
    p_push = Column(Float)
    mean = Column(Float)
    median = Column(Float)
    q10 = Column(Float)
    q90 = Column(Float)
    model_origin = Column(String(64))
    market_reference = Column(Float)
    participation_json = Column(JSON)
    sim_tier = Column(String(32))
    stress_class = Column(String(32))
    data_grade = Column(String(4))
    created_at = Column(DateTime, default=datetime.utcnow)
    frozen_at = Column(DateTime)

    run = relationship("SlateRun", back_populates="forecasts")


@_register_append_only
class HandoffSnapshot(Base):
    __tablename__ = "handoff_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    handoff_id = Column(String(64), unique=True, nullable=False)
    forecast_id = Column(String(64), ForeignKey("stage1_forecasts.forecast_id"))
    snapshot_json = Column(JSON, nullable=False)
    frozen_at = Column(DateTime, default=datetime.utcnow)


@_register_append_only
class Stage2BlindReview(Base):
    __tablename__ = "stage2_blind_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String(64), unique=True, nullable=False)
    forecast_id = Column(String(64), ForeignKey("stage1_forecasts.forecast_id"))
    p_over_blind = Column(Float)
    p_under_blind = Column(Float)
    p_push_blind = Column(Float)
    participation_json = Column(JSON)
    adversarial_cases = Column(JSON)
    frozen_at = Column(DateTime, default=datetime.utcnow)


@_register_append_only
class Stage2Reconciliation(Base):
    __tablename__ = "stage2_reconciliation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    forecast_id = Column(String(64), ForeignKey("stage1_forecasts.forecast_id"))
    p_core_a = Column(Float)
    p_core_b = Column(Float)
    p_fused = Column(Float)
    p_market = Column(Float)
    cov_ab = Column(Float)
    model_agreement = Column(String(16))
    created_at = Column(DateTime, default=datetime.utcnow)


@_register_append_only
class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    forecast_id = Column(String(64), ForeignKey("stage1_forecasts.forecast_id"))
    platform = Column(String(32))
    product_info = Column(JSON)
    fetched_at = Column(DateTime, default=datetime.utcnow)


@_register_append_only
class Stage2Review(Base):
    __tablename__ = "stage2_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    validation_id = Column(String(128), unique=True, nullable=False)
    forecast_id = Column(String(64), ForeignKey("stage1_forecasts.forecast_id"))
    platform = Column(String(32))
    final_tier = Column(String(32))
    verdict = Column(String(32))
    ev_median = Column(Float)
    ev_q20 = Column(Float)
    p_ev_positive = Column(Float)
    downgrade_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


@_register_append_only
class EntryCandidate(Base):
    __tablename__ = "entry_candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(String(64), unique=True, nullable=False)
    run_id = Column(String(64), ForeignKey("slate_runs.run_id"))
    platform = Column(String(32))
    legs = Column(JSON)
    p_joint = Column(Float)
    multiplier = Column(Float)
    ev = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


@_register_append_only
class FinalEntry(Base):
    __tablename__ = "final_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(String(64), ForeignKey("entry_candidates.entry_id"))
    run_id = Column(String(64), ForeignKey("slate_runs.run_id"))
    stake_recommended = Column(Float)
    stake_requested = Column(Float)
    stake_accepted = Column(Float)
    submitted_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


@_register_append_only
class CLVSettlement(Base):
    __tablename__ = "clv_settlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(String(64), ForeignKey("entry_candidates.entry_id"))
    forecast_id = Column(String(64))
    p_forecast = Column(Float)
    p_closing = Column(Float)
    clv = Column(Float)
    outcome = Column(String(16))
    stat_value = Column(Float)
    threshold = Column(Float)
    settled_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


@_register_append_only
class ChannelEconomics(Base):
    __tablename__ = "channel_economics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("slate_runs.run_id"))
    platform = Column(String(32))
    sport = Column(String(16))
    n_entries = Column(Integer)
    total_stake = Column(Float)
    total_winnings = Column(Float)
    roi = Column(Float)
    edph = Column(Float)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Engine / Session factory
# ---------------------------------------------------------------------------

def get_engine(url: str = _DATABASE_URL):
    """Create SQLAlchemy engine with WAL mode for SQLite."""
    engine = create_engine(url, echo=False, future=True)
    if url.startswith("sqlite"):
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("PRAGMA journal_mode=WAL"))
    return engine


def create_all_tables(engine=None):
    """Create all tables if they do not exist."""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)


SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def get_session(engine=None):
    """Return a new SQLAlchemy session."""
    if engine is None:
        engine = get_engine()
    SessionLocal.configure(bind=engine)
    return SessionLocal()
