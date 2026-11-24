"""Shared assignments, practice, idempotency and learning events schema."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0006_assignments_practice_events"
down_revision = "0005_reading_positions"
branch_labels = None
depends_on = None


def record_columns(mutable: bool = True) -> list[sa.Column]:
    columns = [
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]
    if mutable:
        columns.append(
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
    return columns


def upgrade() -> None:
    op.create_table(
        "assignments",
        *record_columns(),
        sa.Column("class_id", sa.Uuid(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("criteria", sa.Text(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'closed')", name="ck_assignments_status"
        ),
    )
    op.create_index("ix_assignments_class_id", "assignments", ["class_id"])
    op.create_table(
        "submissions",
        *record_columns(),
        sa.Column("assignment_id", sa.Uuid(), sa.ForeignKey("assignments.id"), nullable=False),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("assignment_id", "student_id"),
    )
    op.create_table(
        "submission_versions",
        *record_columns(mutable=False),
        sa.Column("submission_id", sa.Uuid(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("submission_id", "version_no"),
        sa.CheckConstraint("version_no >= 1", name="ck_submission_versions_version"),
    )
    op.create_table(
        "grade_revisions",
        *record_columns(),
        sa.Column(
            "submission_version_id",
            sa.Uuid(),
            sa.ForeignKey("submission_versions.id"),
            nullable=False,
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("grade", sa.Numeric(4, 2)),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("criteria_snapshot", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("published_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("submission_version_id", "revision_no"),
        sa.CheckConstraint("revision_no >= 1", name="ck_grade_revisions_revision"),
        sa.CheckConstraint("grade BETWEEN 0 AND 10", name="ck_grade_revisions_grade"),
        sa.CheckConstraint("status IN ('draft', 'published')", name="ck_grade_revisions_status"),
    )
    op.create_table(
        "practice_questions",
        *record_columns(),
        sa.Column("class_id", sa.Uuid(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("options", JSONB()),
        sa.Column("answer_key", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("source_chunk_id", sa.Uuid(), sa.ForeignKey("chunks.id")),
        sa.Column("source_version_id", sa.Uuid(), sa.ForeignKey("material_versions.id")),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("supersedes_id", sa.Uuid(), sa.ForeignKey("practice_questions.id")),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("kind IN ('mcq', 'short')", name="ck_practice_questions_kind"),
        sa.CheckConstraint("origin IN ('ai', 'lecturer')", name="ck_practice_questions_origin"),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'published', 'retired')",
            name="ck_practice_questions_status",
        ),
    )
    op.create_index("ix_practice_questions_class_id", "practice_questions", ["class_id"])
    op.create_table(
        "practice_attempts",
        *record_columns(mutable=False),
        sa.Column("question_id", sa.Uuid(), sa.ForeignKey("practice_questions.id"), nullable=False),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_snapshot", JSONB(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean()),
        sa.Column(
            "submitted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_practice_attempts_question_student", "practice_attempts", ["question_id", "student_id"]
    )
    op.create_table(
        "idempotency_keys",
        *record_columns(mutable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("response_ref_type", sa.Text(), nullable=False),
        sa.Column("response_ref_id", sa.Uuid(), nullable=False),
        sa.UniqueConstraint("user_id", "operation", "key"),
        sa.CheckConstraint(
            "operation IN ('submission', 'practice_attempt')", name="ck_idempotency_operation"
        ),
        sa.CheckConstraint("length(key) BETWEEN 8 AND 100", name="ck_idempotency_key_length"),
    )
    op.create_table(
        "learning_events",
        *record_columns(mutable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("class_id", sa.Uuid(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("ref_type", sa.Text()),
        sa.Column("ref_id", sa.Uuid()),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "type IN ('material_opened', 'question_asked', 'citation_opened', "
            "'submission_created', 'practice_attempted', 'feedback_viewed')",
            name="ck_learning_events_type",
        ),
    )
    op.create_index("ix_learning_events_class_user", "learning_events", ["class_id", "user_id"])


def downgrade() -> None:
    for table in (
        "learning_events",
        "idempotency_keys",
        "practice_attempts",
        "practice_questions",
        "grade_revisions",
        "submission_versions",
        "submissions",
        "assignments",
    ):
        op.drop_table(table)
