"""Initial, frozen schema. Future model edits do not change this migration."""

from pathlib import Path
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    schema = Path(__file__).with_name("0001_schema.sql").read_text()
    op.execute(schema)


def downgrade():
    raise RuntimeError("Destructive baseline downgrade is disabled; restore a backup or roll forward")
