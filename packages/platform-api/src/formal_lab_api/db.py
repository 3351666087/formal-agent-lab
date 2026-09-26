"""Database engine, sessions and ORM tables (PostgreSQL)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .settings import get_settings

JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JsonType, list[Any]: JsonType}


def _now() -> datetime:
    from formal_lab_contracts import utcnow

    return utcnow()


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    group: Mapped[str | None] = mapped_column(String(120), doc="organisational grouping label")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Model(Base):
    __tablename__ = "models"
    __table_args__ = (UniqueConstraint("project_id", "package_id"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    package_id: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    latest_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class ModelVersion(Base):
    """Immutable: editing a model always inserts a new version."""

    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("model_id", "version"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    digest: Mapped[str] = mapped_column(String(64), index=True)
    semantic_profile: Mapped[str] = mapped_column(String(80))
    package: Mapped[dict[str, Any]] = mapped_column(JsonType, doc="ModelPackage contract object")
    parent_version: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Scenario(Base):
    __tablename__ = "scenarios"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    manifest: Mapped[dict[str, Any]] = mapped_column(JsonType, doc="ScenarioManifest contract object")
    copied_from: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class StrategyConfig(Base):
    __tablename__ = "strategy_configs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    plugin_id: Mapped[str] = mapped_column(String(200))
    plugin_version: Mapped[str] = mapped_column(String(40))
    config: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Matrix(Base):
    __tablename__ = "matrices"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    spec: Mapped[dict[str, Any]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (UniqueConstraint("project_id", "client_request_id"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[str | None] = mapped_column(ForeignKey("scenarios.id", ondelete="SET NULL"), index=True)
    strategy_config_id: Mapped[str | None] = mapped_column(ForeignKey("strategy_configs.id", ondelete="SET NULL"))
    matrix_id: Mapped[str | None] = mapped_column(ForeignKey("matrices.id", ondelete="SET NULL"), index=True)
    source_run_id: Mapped[str | None] = mapped_column(String(40), index=True)
    client_request_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), index=True)
    status_reason: Mapped[str | None] = mapped_column(Text)
    manifest: Mapped[dict[str, Any]] = mapped_column(JsonType, doc="RunManifest contract object")
    workflow_id: Mapped[str | None] = mapped_column(String(80))
    event_seq: Mapped[int] = mapped_column(BigInteger, default=0)
    last_step: Mapped[int] = mapped_column(Integer, default=0)
    usage: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    paused_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    final_state: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    imported: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "idempotency_key"), Index("ix_run_events_run_step", "run_id",
                                                                          "logical_step"))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(40), unique=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    logical_step: Mapped[int | None] = mapped_column(Integer)
    wall_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[str | None] = mapped_column(String(80))
    causal_parents: Mapped[list[Any]] = mapped_column(JsonType, default=list)
    payload_schema: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType)
    idempotency_key: Mapped[str] = mapped_column(String(200))


class Operation(Base):
    """Idempotency ledger: one row per (run, step, kind); retries read it before acting."""

    __tablename__ = "operations"
    operation_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    step: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(16))  # STARTED | COMPLETED | FAILED
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    result: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Snapshot(Base):
    __tablename__ = "env_snapshots"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True)
    step: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_revision: Mapped[int] = mapped_column(Integer)
    digest: Mapped[str] = mapped_column(String(64))
    artifact: Mapped[dict[str, Any]] = mapped_column(JsonType, doc="ArtifactRef of the snapshot JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("run_id", "digest", "kind"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # snapshot | model_call | export | inspect_log | log
    digest: Mapped[str] = mapped_column(String(64), index=True)
    ref: Mapped[dict[str, Any]] = mapped_column(JsonType, doc="ArtifactRef")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MetricRow(Base):
    __tablename__ = "metrics"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True)
    metric_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    result: Mapped[dict[str, Any]] = mapped_column(JsonType, doc="MetricResult")
    value: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))


class CheckRow(Base):
    __tablename__ = "checks"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id", ondelete="CASCADE"), index=True)
    query: Mapped[dict[str, Any]] = mapped_column(JsonType)
    result: Mapped[dict[str, Any]] = mapped_column(JsonType, doc="BoundedCheckResult")
    verdict: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PluginRow(Base):
    __tablename__ = "plugin_catalog"
    plugin_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    version: Mapped[str] = mapped_column(String(40), primary_key=True)
    interface: Mapped[str] = mapped_column(String(40))
    descriptor: Mapped[dict[str, Any]] = mapped_column(JsonType)
    descriptor_digest: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(Text)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


@lru_cache(maxsize=4)
def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_settings().database_url, pool_pre_ping=True, pool_size=10, max_overflow=10,
                         future=True)


@lru_cache(maxsize=4)
def _factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), expire_on_commit=False, future=True)


@contextmanager
def session_scope(url: str | None = None) -> Iterator[Session]:
    session = _factory(url)()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
