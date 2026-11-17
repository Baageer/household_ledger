"""Add transfer target to imported transactions."""
from alembic import op
import sqlalchemy as sa

revision = "0002_import_transfer_account"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("import_transactions")}
    if "transfer_to_account_id" not in columns:
        op.add_column("import_transactions", sa.Column("transfer_to_account_id", sa.String(length=64), nullable=True))
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("import_transactions")
    has_transfer_account_fk = any(key.get("constrained_columns") == ["transfer_to_account_id"] for key in foreign_keys)
    if not has_transfer_account_fk:
        op.create_foreign_key(
            "fk_import_transactions_transfer_to_account_id_accounts",
            "import_transactions", "accounts", ["transfer_to_account_id"], ["id"],
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    transfer_account_fk = next((key for key in inspector.get_foreign_keys("import_transactions") if key.get("constrained_columns") == ["transfer_to_account_id"]), None)
    if transfer_account_fk and transfer_account_fk.get("name"):
        op.drop_constraint(transfer_account_fk["name"], "import_transactions", type_="foreignkey")
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("import_transactions")}
    if "transfer_to_account_id" in columns:
        op.drop_column("import_transactions", "transfer_to_account_id")
