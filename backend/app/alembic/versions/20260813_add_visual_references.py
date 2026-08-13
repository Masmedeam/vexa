"""add visual references

Revision ID: 20260813_add_visual_references
Revises: 20260813_backfill_traceability
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_add_visual_references"
down_revision: str | None = "20260813_backfill_traceability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "visualreference",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("generated_test_case_id", sa.Uuid(), nullable=True),
        sa.Column("test_case_step_id", sa.Uuid(), nullable=True),
        sa.Column("query", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_url", sa.String(length=2000), nullable=False),
        sa.Column("image_url", sa.String(length=2000), nullable=True),
        sa.Column("snippet", sa.String(length=4000), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["generated_test_case_id"], ["generatedtestcase.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_case_step_id"], ["testcasestep.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_visualreference_project_id", "visualreference", ["project_id"])
    op.create_index("ix_visualreference_generated_test_case_id", "visualreference", ["generated_test_case_id"])
    op.create_index("ix_visualreference_test_case_step_id", "visualreference", ["test_case_step_id"])


def downgrade() -> None:
    op.drop_index("ix_visualreference_test_case_step_id", table_name="visualreference")
    op.drop_index("ix_visualreference_generated_test_case_id", table_name="visualreference")
    op.drop_index("ix_visualreference_project_id", table_name="visualreference")
    op.drop_table("visualreference")
