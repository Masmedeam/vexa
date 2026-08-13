"""Add executable records for each generated protocol step."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260813_step_executions"
down_revision = "20260813_test_case_steps"
branch_labels = None
depends_on = None

def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table(
        "teststepexecution",
        sa.Column("id", u, nullable=False), sa.Column("test_case_step_id", u, nullable=False), sa.Column("executor_id", u, nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("observed_result", sa.String(10000), nullable=True),
        sa.Column("deviation_reference", sa.String(255), nullable=True), sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["test_case_step_id"], ["testcasestep.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["executor_id"], ["user.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_teststepexecution_test_case_step_id", "teststepexecution", ["test_case_step_id"])
    op.create_index("ix_teststepexecution_executor_id", "teststepexecution", ["executor_id"])
    op.alter_column("testevidence", "execution_id", nullable=True)
    op.add_column("testevidence", sa.Column("step_execution_id", u, nullable=True))
    op.create_foreign_key("fk_testevidence_step_execution", "testevidence", "teststepexecution", ["step_execution_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_testevidence_step_execution_id", "testevidence", ["step_execution_id"])

def downgrade() -> None:
    op.alter_column("testevidence", "execution_id", nullable=False)
    op.drop_index("ix_testevidence_step_execution_id", table_name="testevidence")
    op.drop_constraint("fk_testevidence_step_execution", "testevidence", type_="foreignkey")
    op.drop_column("testevidence", "step_execution_id")
    op.drop_index("ix_teststepexecution_executor_id", table_name="teststepexecution")
    op.drop_index("ix_teststepexecution_test_case_step_id", table_name="teststepexecution")
    op.drop_table("teststepexecution")
