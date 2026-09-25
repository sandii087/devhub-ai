"""Project AI consent and bounded, idempotent requests."""

from alembic import op
import sqlalchemy as sa

revision = "0002_ai"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_settings",
        sa.Column("org_id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"]),
    )
    op.create_table(
        "ai_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("output", sa.Text()),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id", "project_id"], ["projects.org_id", "projects.id"]),
        sa.ForeignKeyConstraint(["org_id", "user_id"], ["memberships.org_id", "memberships.user_id"]),
    )
    op.create_index("ix_ai_requests_org_id", "ai_requests", ["org_id"])
    op.create_index("ix_ai_requests_created_at", "ai_requests", ["created_at"])
    for name in ("ai_settings", "ai_requests"):
        predicate = "org_id = NULLIF(current_setting('devhub.org_id', true), '')::uuid"
        op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {name} USING ({predicate}) WITH CHECK ({predicate})")


def downgrade():
    raise RuntimeError("Restore or roll forward; do not automatically delete AI audit data")
