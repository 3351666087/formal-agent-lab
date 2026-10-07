"""phase 5A: research cases and model–program conformance results

A research case ties a software revision + its tree digests, formal models (by digest), validation artifacts
(by sha256, kept in the artifact store) and conformance results together. Artifacts live in the existing artifact
store; these tables hold the case document (with the stored refs) and a row per conformance result, so a model
version or an imported run can be traced to the cases and correspondence verdicts that reference it.

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "research_cases",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("case_id", sa.String(120), nullable=False),
        sa.Column("case_version", sa.Integer, nullable=False),
        sa.Column("protocol", sa.String(40), nullable=False),
        sa.Column("track", sa.String(40), nullable=False),
        sa.Column("mechanism_family", sa.String(120), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("purpose", sa.Text, nullable=False),
        sa.Column("software_revision", sa.String(40), nullable=False, index=True),
        sa.Column("case_digest", sa.String(64), nullable=False, index=True),
        sa.Column("definition_digest", sa.String(64), nullable=False),
        sa.Column("document", JSON, nullable=False),
        sa.Column("observation_run_id", sa.String(40),
                  sa.ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "case_id", "case_version", name="uq_research_case_version"),
    )
    op.create_table(
        "research_conformance",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("research_case_id", sa.String(40), sa.ForeignKey("research_cases.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("package_id", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("model_digest", sa.String(64), nullable=False, index=True),
        sa.Column("model_version_id", sa.String(40),
                  sa.ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("property_id", sa.String(120), nullable=False),
        sa.Column("property_digest", sa.String(64), nullable=False),
        sa.Column("correspondence", sa.String(24), nullable=False),
        sa.Column("model_verdict", sa.String(32), nullable=False),
        sa.Column("regression_status", sa.String(16), nullable=False),
        sa.Column("document", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("research_conformance")
    op.drop_table("research_cases")
