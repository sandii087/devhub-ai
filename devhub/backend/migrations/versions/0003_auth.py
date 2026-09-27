"""Password credentials, single-use email tokens and shared authentication limits."""

from alembic import op
import sqlalchemy as sa

revision = "0003_auth"
down_revision = "0002_ai"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("oidc_flows", sa.Column("link_session_hash", sa.String(64), nullable=True))
    op.create_table(
        "password_credentials",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "email_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])
    op.create_index("ix_email_tokens_expires_at", "email_tokens", ["expires_at"])
    op.create_table(
        "auth_throttles",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_throttles_expires_at", "auth_throttles", ["expires_at"])
    # Existing deployments already have restricted runtime roles; never change their passwords.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'devhub_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON password_credentials, email_tokens, auth_throttles
                TO devhub_app;
        END IF;
    END $$""")


def downgrade():
    raise RuntimeError("Restore or roll forward; do not delete authentication data")
