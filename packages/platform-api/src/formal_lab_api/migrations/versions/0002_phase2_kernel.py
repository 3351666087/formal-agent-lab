"""phase 2: v2 contract columns, turn/stage on events, run carry state, operation records, rule sets,
model releases, query bundles, regression cases, environment sessions, matrix cells

Existing rows keep their phase-1 JSON and are marked `formal-lab-contracts/v1`; readers upgrade them on the fly
(formal_lab_contracts.compat), so history is shown with the meaning it was written with.

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
V1 = sa.text("'formal-lab-contracts/v1'")


def upgrade() -> None:
    for table in ("model_versions", "scenarios", "runs"):
        # existing rows were written by phase 1 (v1); new rows set the column explicitly
        op.add_column(table, sa.Column("contract_version", sa.String(40), nullable=False, server_default=V1))
    op.add_column("runs", sa.Column("carry", JSON, nullable=True))
    op.add_column("runs", sa.Column("termination_reason", sa.String(40), nullable=True))
    op.add_column("run_events", sa.Column("turn", JSON, nullable=True))
    op.add_column("run_events", sa.Column("stage", sa.String(24), nullable=True))
    op.create_table(
        "operation_records",
        sa.Column("operation_id", sa.String(160), primary_key=True),
        sa.Column("run_id", sa.String(40), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step", sa.Integer, nullable=False),
        sa.Column("actor_id", sa.String(80)),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("needs_review", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("record", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_operation_records_run_id", "operation_records", ["run_id"])
    op.create_index("ix_operation_records_state", "operation_records", ["state"])
    op.create_index("ix_operation_records_needs_review", "operation_records", ["needs_review"])
    op.create_table(
        "rulesets",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ruleset_id", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("model_version_id", sa.String(40), sa.ForeignKey("model_versions.id"), nullable=False),
        sa.Column("body", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "ruleset_id", "version"),
    )
    op.create_index("ix_rulesets_project_id", "rulesets", ["project_id"])
    op.create_index("ix_rulesets_digest", "rulesets", ["digest"])
    op.create_index("ix_rulesets_model_version_id", "rulesets", ["model_version_id"])
    op.create_table(
        "model_releases",
        sa.Column("release_id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_version_id", sa.String(40), sa.ForeignKey("model_versions.id"), nullable=False),
        sa.Column("ruleset_row_id", sa.String(40), sa.ForeignKey("rulesets.id")),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("record", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_model_releases_project_id", "model_releases", ["project_id"])
    op.create_index("ix_model_releases_model_version_id", "model_releases", ["model_version_id"])
    op.create_table(
        "query_bundles",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_version_id", sa.String(40), sa.ForeignKey("model_versions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("check_id", sa.String(40)),
        sa.Column("bundle", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_query_bundles_project_id", "query_bundles", ["project_id"])
    op.create_index("ix_query_bundles_model_version_id", "query_bundles", ["model_version_id"])
    op.create_index("ix_query_bundles_check_id", "query_bundles", ["check_id"])
    op.create_table(
        "regression_cases",
        sa.Column("case_id", sa.String(60), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_digest", sa.String(64), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("origin_run_id", sa.String(40)),
        sa.Column("case", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_regression_cases_project_id", "regression_cases", ["project_id"])
    op.create_index("ix_regression_cases_model_digest", "regression_cases", ["model_digest"])
    op.create_index("ix_regression_cases_origin_run_id", "regression_cases", ["origin_run_id"])
    op.create_table(
        "environment_sessions",
        sa.Column("session_id", sa.String(60), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id", ondelete="CASCADE")),
        sa.Column("plugin_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("record", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_environment_sessions_project_id", "environment_sessions", ["project_id"])
    op.create_index("ix_environment_sessions_status", "environment_sessions", ["status"])
    op.create_table(
        "matrix_cells",
        sa.Column("matrix_id", sa.String(40), sa.ForeignKey("matrices.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("cell_id", sa.String(40), primary_key=True),
        sa.Column("config_digest", sa.String(64), nullable=False),
        sa.Column("spec", JSON, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("run_id", sa.String(40)),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_matrix_cells_config_digest", "matrix_cells", ["config_digest"])
    op.create_index("ix_matrix_cells_status", "matrix_cells", ["status"])


def downgrade() -> None:
    for table in ("matrix_cells", "environment_sessions", "regression_cases", "query_bundles", "model_releases",
                  "rulesets", "operation_records"):
        op.drop_table(table)
    op.drop_column("run_events", "stage")
    op.drop_column("run_events", "turn")
    op.drop_column("runs", "termination_reason")
    op.drop_column("runs", "carry")
    for table in ("runs", "scenarios", "model_versions"):
        op.drop_column(table, "contract_version")
