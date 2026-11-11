"""Durable, tenant-scoped activity results for retries after a lost response."""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE research_activity_results (
            operation_id TEXT PRIMARY KEY,
            firm_id VARCHAR(64) NOT NULL,
            assessment_id UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
            result JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_research_results_firm ON research_activity_results(firm_id)")
    op.execute("ALTER TABLE research_activity_results ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE research_activity_results FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY research_activity_tenant ON research_activity_results
        USING (firm_id = current_setting('app.firm_id', true))
        WITH CHECK (
            firm_id = current_setting('app.firm_id', true)
            AND EXISTS (
                SELECT 1 FROM assessments
                WHERE assessments.id = research_activity_results.assessment_id
                  AND assessments.firm_id = research_activity_results.firm_id
            )
        )
    """)
    op.execute("GRANT SELECT, INSERT, DELETE ON research_activity_results TO thesis_app")


def downgrade():
    op.execute("DROP TABLE research_activity_results")
