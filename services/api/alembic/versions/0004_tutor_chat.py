"""Tutor sessions, messages and citations."""

import sqlalchemy as sa

from alembic import op

revision = "0004_tutor_chat"
down_revision = "0003_lessons_materials"
branch_labels = None
depends_on = None


def record_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        *record_columns(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("class_id", sa.Uuid(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id")),
        sa.Column("material_id", sa.Uuid(), sa.ForeignKey("materials.id")),
    )
    op.create_index("ix_chat_sessions_user_class", "chat_sessions", ["user_id", "class_id"])
    op.create_table(
        "chat_messages",
        *record_columns(),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("chat_sessions.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("retriever", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_role"),
        sa.CheckConstraint("mode IN ('answer', 'hint')", name="ck_chat_mode"),
        sa.CheckConstraint(
            "status IN ('ok', 'insufficient_evidence', 'error')", name="ck_chat_status"
        ),
    )
    op.create_index(
        "ix_chat_messages_session_created", "chat_messages", ["session_id", "created_at"]
    )
    op.create_table(
        "citations",
        *record_columns(),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("chat_messages.id"), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("chunks.id"), nullable=False),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("material_versions.id"), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("message_id", "ordinal"),
    )
    op.create_index("ix_citations_message_id", "citations", ["message_id"])


def downgrade() -> None:
    op.drop_table("citations")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
