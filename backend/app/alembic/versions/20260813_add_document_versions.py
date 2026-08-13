"""Keep immutable snapshots when source documents are replaced."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260813_document_versions"
down_revision = "20260813_output_lifecycle"
branch_labels = None
depends_on = None

def upgrade() -> None:
    u = postgresql.UUID(as_uuid=True)
    op.create_table(
        "documentversion",
        sa.Column("id", u, nullable=False), sa.Column("document_id", u, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False), sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(255), nullable=True), sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["projectdocument.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documentversion_document_id", "documentversion", ["document_id"])

def downgrade() -> None:
    op.drop_index("ix_documentversion_document_id", table_name="documentversion")
    op.drop_table("documentversion")
