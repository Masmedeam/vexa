"""Backfill requirement and test-case links from generation snapshots."""
from alembic import op

revision = "20260813_backfill_traceability"
down_revision = "20260813_traceability"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
      INSERT INTO ursrequirement (id, project_id, document_id, requirement_id, requirement_text, source_location, created_at, updated_at)
      SELECT gen_random_uuid(), s.project_id,
             (SELECT d.id FROM projectdocument d WHERE d.project_id = s.project_id AND d.document_type = 'URS' ORDER BY d.created_at DESC LIMIT 1),
             g.urs_id, COALESCE(g.payload::jsonb->>'urs_text', 'Requirement text not provided in generation output'), NULL, NOW(), NOW()
      FROM generatedtestcase g JOIN qualificationstep s ON s.id = g.step_id
      WHERE NOT EXISTS (SELECT 1 FROM ursrequirement r WHERE r.project_id = s.project_id AND r.requirement_id = g.urs_id)
    """)
    op.execute("""
      INSERT INTO testcaserequirement (id, generated_test_case_id, requirement_id, relationship_type, created_at, updated_at)
      SELECT gen_random_uuid(), g.id, r.id, 'tests', NOW(), NOW()
      FROM generatedtestcase g JOIN qualificationstep s ON s.id = g.step_id
      JOIN ursrequirement r ON r.project_id = s.project_id AND r.requirement_id = g.urs_id
      WHERE NOT EXISTS (SELECT 1 FROM testcaserequirement x WHERE x.generated_test_case_id = g.id AND x.requirement_id = r.id)
    """)

def downgrade() -> None:
    pass
