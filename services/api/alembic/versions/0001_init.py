"""Initialize pgvector and authentication storage."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def common_columns() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "users",
        *common_columns(),
        sa.Column("email", sa.Text, nullable=False, unique=True),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("system_role", sa.Text, nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lower"),
        sa.CheckConstraint("system_role IN ('admin', 'user')", name="ck_users_system_role"),
    )
    op.create_table(
        "sessions",
        *common_columns(),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("users")
    # Keep vector: other schemas may still depend on the extension.
