"""Add normalized URS requirements and requirement-to-test traceability."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260813_traceability"
down_revision = "20260813_backfill_case_steps"
branch_labels = None
depends_on = None

def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table(
        "ursrequirement",
        sa.Column("id", u, nullable=False), sa.Column("project_id", u, nullable=False), sa.Column("document_id", u, nullable=True),
        sa.Column("requirement_id", sa.String(255), nullable=False), sa.Column("requirement_text", sa.String(10000), nullable=False),
        sa.Column("source_location", sa.String(255), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["document_id"], ["projectdocument.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ursrequirement_project_id", "ursrequirement", ["project_id"])
    op.create_index("ix_ursrequirement_document_id", "ursrequirement", ["document_id"])
    op.create_table(
        "testcaserequirement",
        sa.Column("id", u, nullable=False), sa.Column("generated_test_case_id", u, nullable=False), sa.Column("requirement_id", u, nullable=False),
        sa.Column("relationship_type", sa.String(40), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["generated_test_case_id"], ["generatedtestcase.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["requirement_id"], ["ursrequirement.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_testcaserequirement_generated_test_case_id", "testcaserequirement", ["generated_test_case_id"])
    op.create_index("ix_testcaserequirement_requirement_id", "testcaserequirement", ["requirement_id"])

def downgrade() -> None:
    op.drop_index("ix_testcaserequirement_requirement_id", table_name="testcaserequirement")
    op.drop_index("ix_testcaserequirement_generated_test_case_id", table_name="testcaserequirement")
    op.drop_table("testcaserequirement")
    op.drop_index("ix_ursrequirement_document_id", table_name="ursrequirement")
    op.drop_index("ix_ursrequirement_project_id", table_name="ursrequirement")
    op.drop_table("ursrequirement")
