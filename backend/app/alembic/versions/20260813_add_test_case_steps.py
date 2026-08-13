"""Store generated protocol steps as independently updateable records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260813_test_case_steps"
down_revision = "20260813_document_versions"
branch_labels = None
depends_on = None

def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table(
        "testcasestep",
        sa.Column("id", u, nullable=False), sa.Column("generated_test_case_id", u, nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False), sa.Column("action", sa.String(10000), nullable=False),
        sa.Column("expected_result", sa.String(10000), nullable=False), sa.Column("evidence_required", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("observed_result", sa.String(10000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["generated_test_case_id"], ["generatedtestcase.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_testcasestep_generated_test_case_id", "testcasestep", ["generated_test_case_id"])

def downgrade() -> None:
    op.drop_index("ix_testcasestep_generated_test_case_id", table_name="testcasestep")
    op.drop_table("testcasestep")
