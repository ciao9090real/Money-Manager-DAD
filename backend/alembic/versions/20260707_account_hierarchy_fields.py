"""add account hierarchy fields

Revision ID: 20260707_account_hierarchy_fields
Revises:
Create Date: 2026-07-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260707_account_hierarchy_fields"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("parent_account_id", sa.Integer(), nullable=True))
    op.add_column("accounts", sa.Column("account_type", sa.String(length=40), nullable=True))
    op.add_column("accounts", sa.Column("account_level", sa.Integer(), nullable=True))
    op.add_column("accounts", sa.Column("display_order", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_accounts_parent_account_id"), "accounts", ["parent_account_id"], unique=False)
    op.create_foreign_key("fk_accounts_parent_account_id", "accounts", "accounts", ["parent_account_id"], ["id"])
    op.execute("UPDATE accounts SET account_type = type WHERE account_type IS NULL")
    op.execute("UPDATE accounts SET account_level = 1 WHERE account_level IS NULL")
    op.execute("UPDATE accounts SET display_order = 0 WHERE display_order IS NULL")
    op.alter_column("accounts", "account_type", nullable=False)
    op.alter_column("accounts", "account_level", nullable=False)
    op.alter_column("accounts", "display_order", nullable=False)


def downgrade() -> None:
    op.drop_column("accounts", "display_order")
    op.drop_column("accounts", "account_level")
    op.drop_column("accounts", "account_type")
    op.drop_constraint("fk_accounts_parent_account_id", "accounts", type_="foreignkey")
    op.drop_index(op.f("ix_accounts_parent_account_id"), table_name="accounts")
    op.drop_column("accounts", "parent_account_id")
