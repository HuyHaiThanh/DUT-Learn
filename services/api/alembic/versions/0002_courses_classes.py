"""Courses, class membership, audit trail and login throttling."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0002_courses_classes"
down_revision = "0001_init"
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
    op.create_table(
        "courses",
        *common_columns(),
        sa.Column("code", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
    )
    op.create_table(
        "classes",
        *common_columns(),
        sa.Column("course_id", UUID(as_uuid=True), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("code", sa.Text, nullable=False),
        sa.Column("term", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="open"),
        sa.Column("content_version", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("course_id", "code", "term"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_classes_status"),
    )
    op.create_table(
        "class_members",
        *common_columns(),
        sa.Column("class_id", UUID(as_uuid=True), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.UniqueConstraint("class_id", "user_id"),
        sa.CheckConstraint("role IN ('lecturer', 'student')", name="ck_class_members_role"),
    )
    op.create_table(
        "audit_events",
        *common_columns(),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text, nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("detail", JSONB, nullable=False, server_default="{}"),
    )
    op.create_table(
        "login_attempts",
        *common_columns(),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column(
            "attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("succeeded", sa.Boolean, nullable=False),
        sa.CheckConstraint("email = lower(email)", name="ck_login_attempts_email_lower"),
    )
    op.create_index(
        "ix_login_attempts_email_attempted_at", "login_attempts", ["email", "attempted_at"]
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_class_members_user_id", "class_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("login_attempts")
    op.drop_table("audit_events")
    op.drop_table("class_members")
    op.drop_table("classes")
    op.drop_table("courses")
