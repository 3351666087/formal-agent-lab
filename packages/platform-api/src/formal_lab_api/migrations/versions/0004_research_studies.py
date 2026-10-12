"""phase 6A: imported research study results (fal-research-study/v1 + responses + evaluations)

A study's results are produced locally (formal_lab_eval.research) and imported read-only: the study definition, the
report, and one row per planned unit holding its latest raw response record and evaluation, so the Web UI can show
the two result axes and the raw answer of every unit. Re-importing a study replaces its previous import.

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "research_studies",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("project_id", sa.String(40), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
                  index=True),
        sa.Column("study_id", sa.String(120), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("study_digest", sa.String(64), nullable=False),
        sa.Column("study", JSON, nullable=False),
        sa.Column("report", JSON, nullable=False),
        sa.Column("units", JSON, nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "study_id", name="uq_research_study"),
    )
    op.create_table(
        "research_study_units",
        sa.Column("study_row_id", sa.String(40), sa.ForeignKey("research_studies.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("unit_id", sa.String(255), primary_key=True),
        sa.Column("track", sa.String(40), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("behavior", sa.String(32), nullable=True),
        sa.Column("response", JSON, nullable=False),
        sa.Column("evaluation", JSON, nullable=True),
        sa.Column("history", JSON, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("research_study_units")
    op.drop_table("research_studies")
