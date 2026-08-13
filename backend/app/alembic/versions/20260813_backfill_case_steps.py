"""Backfill normalized step rows from existing generation snapshots."""
from alembic import op

revision = "20260813_backfill_case_steps"
down_revision = "20260813_step_executions"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        INSERT INTO testcasestep
          (id, generated_test_case_id, step_number, action, expected_result,
           evidence_required, status, observed_result, created_at, updated_at)
        SELECT gen_random_uuid(), g.id,
          (item->>'step_number')::integer,
          item->>'action', item->>'expected_result', item->>'evidence_required',
          'not_started', NULL, NOW(), NOW()
        FROM generatedtestcase AS g
        CROSS JOIN LATERAL jsonb_array_elements(g.payload::jsonb->'test_steps') AS item
        WHERE jsonb_typeof(g.payload::jsonb->'test_steps') = 'array'
          AND NOT EXISTS (
            SELECT 1 FROM testcasestep s
            WHERE s.generated_test_case_id = g.id
          )
    """)

def downgrade() -> None:
    # Normalized rows created by this migration are indistinguishable from later rows;
    # preserve them rather than risk deleting execution data.
    pass
