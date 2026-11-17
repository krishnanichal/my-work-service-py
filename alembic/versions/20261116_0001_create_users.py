import sqlalchemy as sa
from alembic import op

revision = "20261116_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("handle", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("handle", name="uq_users_handle"),
        sa.CheckConstraint("handle = lower(handle)", name="ck_users_handle_lowercase"),
    )
    op.create_index("ix_users_created_at_id", "users", ["created_at", "id"])


def downgrade() -> None:
    op.drop_table("users")
