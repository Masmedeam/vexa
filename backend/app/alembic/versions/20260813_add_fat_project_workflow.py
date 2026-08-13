"""Add FAT projects, documents, sequential qualification steps, and generated cases."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260813_fat_workflow"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.create_table(
        "project",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("owner_id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_owner_id", "project", ["owner_id"])

    op.create_table(
        "projectdocument",
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projectdocument_project_id", "projectdocument", ["project_id"])

    op.create_table(
        "qualificationstep",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("stage", sa.String(length=10), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_qualificationstep_project_id", "qualificationstep", ["project_id"])

    op.create_table(
        "generationrun",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("step_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["qualificationstep.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generationrun_project_id", "generationrun", ["project_id"])
    op.create_index("ix_generationrun_step_id", "generationrun", ["step_id"])

    op.create_table(
        "generatedtestcase",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("step_id", uuid_type, nullable=False),
        sa.Column("test_case_id", sa.String(length=80), nullable=False),
        sa.Column("urs_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["step_id"], ["qualificationstep.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generatedtestcase_step_id", "generatedtestcase", ["step_id"])


def downgrade() -> None:
    op.drop_index("ix_generatedtestcase_step_id", table_name="generatedtestcase")
    op.drop_table("generatedtestcase")
    op.drop_index("ix_generationrun_step_id", table_name="generationrun")
    op.drop_index("ix_generationrun_project_id", table_name="generationrun")
    op.drop_table("generationrun")
    op.drop_index("ix_qualificationstep_project_id", table_name="qualificationstep")
    op.drop_table("qualificationstep")
    op.drop_index("ix_projectdocument_project_id", table_name="projectdocument")
    op.drop_table("projectdocument")
    op.drop_index("ix_project_owner_id", table_name="project")
    op.drop_table("project")
