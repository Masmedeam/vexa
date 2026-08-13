"""Add review, execution, evidence, and generation feedback records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260813_output_lifecycle"
down_revision = "20260813_fat_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)
    common = [
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]
    op.create_table(
        "testcasereview", *common,
        sa.Column("generated_test_case_id", uuid_type, nullable=False),
        sa.Column("reviewer_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("comment", sa.String(4000), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["generated_test_case_id"], ["generatedtestcase.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_testcasereview_generated_test_case_id", "testcasereview", ["generated_test_case_id"])
    op.create_index("ix_testcasereview_reviewer_id", "testcasereview", ["reviewer_id"])

    op.create_table(
        "testexecution", *common,
        sa.Column("generated_test_case_id", uuid_type, nullable=False),
        sa.Column("executor_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("observed_result", sa.String(10000), nullable=True),
        sa.Column("deviation_reference", sa.String(255), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["generated_test_case_id"], ["generatedtestcase.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["executor_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_testexecution_generated_test_case_id", "testexecution", ["generated_test_case_id"])
    op.create_index("ix_testexecution_executor_id", "testexecution", ["executor_id"])

    op.create_table(
        "testevidence", *common,
        sa.Column("execution_id", uuid_type, nullable=False),
        sa.Column("evidence_type", sa.String(50), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["testexecution.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_testevidence_execution_id", "testevidence", ["execution_id"])

    op.create_table(
        "generationfeedback", *common,
        sa.Column("project_id", uuid_type, nullable=False),
        sa.Column("author_id", uuid_type, nullable=False),
        sa.Column("step_id", uuid_type, nullable=True),
        sa.Column("generation_run_id", uuid_type, nullable=True),
        sa.Column("feedback_type", sa.String(40), nullable=False),
        sa.Column("content", sa.String(10000), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["qualificationstep.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["generation_run_id"], ["generationrun.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("project_id", "author_id", "step_id", "generation_run_id"):
        op.create_index(f"ix_generationfeedback_{column}", "generationfeedback", [column])


def downgrade() -> None:
    for column in ("project_id", "author_id", "step_id", "generation_run_id"):
        op.drop_index(f"ix_generationfeedback_{column}", table_name="generationfeedback")
    op.drop_table("generationfeedback")
    op.drop_index("ix_testevidence_execution_id", table_name="testevidence")
    op.drop_table("testevidence")
    op.drop_index("ix_testexecution_executor_id", table_name="testexecution")
    op.drop_index("ix_testexecution_generated_test_case_id", table_name="testexecution")
    op.drop_table("testexecution")
    op.drop_index("ix_testcasereview_reviewer_id", table_name="testcasereview")
    op.drop_index("ix_testcasereview_generated_test_case_id", table_name="testcasereview")
    op.drop_table("testcasereview")
