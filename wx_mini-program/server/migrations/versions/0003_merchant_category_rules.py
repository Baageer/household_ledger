"""Add learned merchant to category rules."""
from alembic import op
import sqlalchemy as sa

revision = "0003_merchant_category_rules"
down_revision = "0002_import_transfer_account"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("merchant_category_rules"):
        op.create_table(
            "merchant_category_rules",
            sa.Column("family_id", sa.String(length=64), nullable=False),
            sa.Column("normalized_merchant", sa.String(length=200), nullable=False),
            sa.Column("category_id", sa.String(length=64), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["family_id"], ["families.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
            sa.PrimaryKeyConstraint("family_id", "normalized_merchant"),
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("merchant_category_rules"):
        op.drop_table("merchant_category_rules")
