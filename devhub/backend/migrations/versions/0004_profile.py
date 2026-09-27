"""Persistent, bounded profile avatars; existing users require no backfill."""

from alembic import op
import sqlalchemy as sa

revision = "0004_profile"
down_revision = "0003_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("avatar_data", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("avatar_version", sa.String(64), nullable=True))


def downgrade():
    # This removes uploaded pictures only; identity/session data remains intact.
    op.drop_column("users", "avatar_version")
    op.drop_column("users", "avatar_data")
