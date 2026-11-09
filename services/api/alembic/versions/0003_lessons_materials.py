"""Lessons, materials, material versions and chunks (Tech Lead, wave W-C shared schema)."""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0003_lessons_materials"
down_revision = "0002_courses_classes"
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


VERSION_STATUSES = "'uploaded','processing','ready','failed','published','superseded','revoked'"


def upgrade() -> None:
    op.create_table(
        "lessons",
        *common_columns(),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_lessons_class_id", "lessons", ["class_id", "position"])

    op.create_table(
        "materials",
        *common_columns(),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("lesson_id", UUID(as_uuid=True), sa.ForeignKey("lessons.id")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("visibility", sa.Text, nullable=False, server_default="students"),
        sa.Column("source_note", sa.Text),
        sa.Column("license_note", sa.Text),
        sa.Column("active_version_id", UUID(as_uuid=True)),
        sa.CheckConstraint("kind IN ('pdf', 'text')", name="ck_materials_kind"),
        sa.CheckConstraint(
            "visibility IN ('students', 'lecturers')", name="ck_materials_visibility"
        ),
    )
    op.create_index("ix_materials_class_id", "materials", ["class_id"])

    op.create_table(
        "material_versions",
        *common_columns(),
        sa.Column("material_id", UUID(as_uuid=True), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="uploaded"),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.Text),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("page_count", sa.Integer),
        sa.Column("quality_report", JSONB),
        sa.Column("error", sa.Text),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("published_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("material_id", "version_no"),
        sa.CheckConstraint(f"status IN ({VERSION_STATUSES})", name="ck_material_versions_status"),
    )
    # At most one published version per material (I2/I4 rely on a single active version).
    op.create_index(
        "ux_material_versions_one_published",
        "material_versions",
        ["material_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_foreign_key(
        "fk_materials_active_version",
        "materials",
        "material_versions",
        ["active_version_id"],
        ["id"],
    )

    op.create_table(
        "chunks",
        *common_columns(),
        sa.Column(
            "version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("material_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("kind", sa.Text, nullable=False, server_default="text"),
        sa.Column("page_index", sa.Integer, nullable=False),
        sa.Column("page_index_end", sa.Integer, nullable=False),
        sa.Column("page_label", sa.Text),
        sa.Column("char_start", sa.Integer, nullable=False),
        sa.Column("char_end", sa.Integer, nullable=False),
        sa.Column("code_block_id", sa.Text),
        sa.Column("part_no", sa.Integer),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.UniqueConstraint("version_id", "ordinal"),
        sa.CheckConstraint("kind IN ('text', 'code')", name="ck_chunks_kind"),
        sa.CheckConstraint("page_index_end >= page_index", name="ck_chunks_page_range"),
    )
    op.create_index("ix_chunks_version_id", "chunks", ["version_id"])


def downgrade() -> None:
    op.drop_table("chunks")
    op.drop_constraint("fk_materials_active_version", "materials", type_="foreignkey")
    op.drop_table("material_versions")
    op.drop_table("materials")
    op.drop_table("lessons")
