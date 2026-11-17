"""Reading positions, one per user and material."""

import sqlalchemy as sa

from alembic import op

revision = "0005_reading_positions"
down_revision = "0004_tutor_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reading_positions",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("material_id", sa.Uuid(), sa.ForeignKey("materials.id"), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("material_versions.id"), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "material_id"),
        sa.CheckConstraint("page_index >= 0", name="ck_reading_positions_page"),
    )


def downgrade() -> None:
    op.drop_table("reading_positions")
