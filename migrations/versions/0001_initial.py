"""Initial users schema.

Matches the schema existing deployments already have (created by
postgres-init-users/admin.sql or Base.metadata.create_all), so existing
databases are stamped at this revision instead of running it.

Revision ID: 0001
Revises:
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("permissions", sa.String(), nullable=False),
        sa.Column("password", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("users")
