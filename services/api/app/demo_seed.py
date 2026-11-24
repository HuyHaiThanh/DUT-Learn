"""Synthetic, repeatable demo data; run with python -m app.demo_seed."""

import argparse
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.admin.service import save_created
from app.assignments import service as assignments
from app.assignments.models import Assignment, GradeRevision, Submission, SubmissionVersion
from app.assignments.schemas import (
    AssignmentCreate,
    AssignmentUpdate,
    GradeCreate,
    SubmissionCreate,
)
from app.auth.models import User
from app.auth.security import hash_password
from app.courses.models import Class, ClassMember, Course, Lesson
from app.courses.schemas import LessonCreate, LessonUpdate
from app.courses.service import create_lesson, update_lesson
from app.db import SessionLocal
from app.deps import require_class_lecturer, require_class_member
from app.ingest.worker import IngestWorker
from app.materials.models import Material, MaterialVersion
from app.materials.publication import change_publication
from app.materials.service import lecturer_material, save_upload, validate_file
from app.materials.storage import LocalStorage
from app.practice import service as practice
from app.practice.models import PracticeAttempt, PracticeQuestion
from app.practice.schemas import AttemptCreate, QuestionCreate

ACCOUNTS = [
    ("quantri", "Quản trị viên (demo)", "admin"),
    ("gv.chau", "Lê Minh Châu", "user"),
    ("sv.thao", "Nguyễn Thị Phương Thảo", "user"),
    ("sv.duc", "Trần Văn Đức", "user"),
    ("sv.bao", "Phạm Gia Bảo", "user"),
    ("sv.anh", "Võ Ngọc Anh", "user"),
]
LESSONS = ["Chương 6. Hàm và đệ quy", "Chương 7. Con trỏ", "Chương 8. Kiểu cấu trúc"]
TITLES = [
    "Bài 0: Làm quen với hàm",
    "Bài 1: Hàm đệ quy tính giai thừa",
    "Bài 2: Con trỏ và mảng",
]
CRITERIA = "Đúng phần dừng (4đ); đúng phần đệ quy (4đ); giải thích rõ (2đ)."
SIMPLE_C = "```c\nint binhphuong(int n) { return n * n; }\n```"
FACTORIAL_C = (
    "```c\nlong long giaithua(int n) {\n"
    "    if (n <= 1) return 1;\n"
    "    return n * giaithua(n - 1);\n}\n```\n"
    "Với n không âm, n <= 1 là phần dừng; mỗi bước giảm n đi 1."
)
FACTORIAL_FIRST_C = (
    "```c\nlong long giaithua(int n) {\n"
    "    if (n == 0) return 1;\n"
    "    return n * giaithua(n - 1);\n}\n```"
)
QUESTIONS = [
    QuestionCreate(
        kind="mcq",
        stem="Phần dừng của hàm đệ quy tính giai thừa có tác dụng gì?",
        options=["Kết thúc chuỗi lời gọi đệ quy", "Tăng số lần gọi hàm", "Cấp phát con trỏ"],
        answer_key="0",
        explanation="Phần dừng trả kết quả trực tiếp, không gọi đệ quy tiếp.",
    ),
    QuestionCreate(
        kind="mcq",
        stem="Khai báo nào tạo con trỏ tới int?",
        options=["int p;", "int *p;", "int &p;"],
        answer_key="1",
        explanation="int *p khai báo p là con trỏ tới int.",
    ),
    QuestionCreate(
        kind="mcq",
        stem="Với int x = 3; int *p = &x;, *p và &x lần lượt là gì?",
        options=["Địa chỉ và giá trị", "Giá trị của x và địa chỉ của x", "Hai số nguyên"],
        answer_key="1",
        explanation="* giải tham chiếu con trỏ hợp lệ; & lấy địa chỉ đối tượng.",
    ),
    QuestionCreate(
        kind="mcq",
        stem="Có nên giải tham chiếu con trỏ NULL không?",
        options=["Có, kết quả luôn là 0", "Không, đó là hành vi không xác định"],
        answer_key="1",
        explanation="NULL không trỏ tới đối tượng hợp lệ để giải tham chiếu.",
    ),
    QuestionCreate(
        kind="short",
        stem="Giải thích vì sao hàm đệ quy cần tiến về phần dừng.",
        answer_key="Mỗi lời gọi phải thu nhỏ bài toán để cuối cùng đạt phần dừng.",
        explanation="Nếu không tiến về phần dừng, lời gọi có thể tiếp diễn và làm tràn ngăn xếp.",
    ),
    QuestionCreate(
        kind="mcq",
        stem="Với int a[3];, chỉ số phần tử hợp lệ là gì?",
        options=["0, 1, 2", "1, 2, 3"],
        answer_key="0",
        explanation="Mảng C đánh chỉ số từ 0 đến số phần tử trừ 1.",
    ),
]


def demo_password() -> str:
    password = os.environ.get("DUT_DEMO_PASSWORD", "")
    if len(password) < 10:
        raise ValueError("DUT_DEMO_PASSWORD bắt buộc có và dài ít nhất 10 ký tự.")
    return password


def seed(db: Session, pdf: Path | None = None) -> UUID:
    password = demo_password()  # Validate before opening a connection or writing anything.
    engine = db.get_bind()
    if not isinstance(engine, Engine):
        raise ValueError("Demo seed requires an engine-bound session.")
    # Business services commit independently. A dedicated session-level lock survives them.
    with engine.connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(54015)"))
        lock.commit()
        try:
            return seed_locked(db, password, pdf)
        finally:
            db.rollback()
            lock.execute(text("SELECT pg_advisory_unlock(54015)"))
            lock.commit()


def seed_locked(db: Session, password: str, pdf: Path | None) -> UUID:
    users: dict[str, User] = {}
    for account, name, role in ACCOUNTS:
        email = f"{account}@demo.dutlearn.local"
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                full_name=name,
                system_role=role,
                password_hash=hash_password(password),
            )
            # The first synthetic administrator bootstraps its own audit entry.
            save_created(db, users.get("quantri", user), user, "user")
        users[account] = user
    admin, lecturer = users["quantri"], users["gv.chau"]
    course = db.scalar(select(Course).where(Course.code == "KTLT"))
    if course is None:
        course = Course(code="KTLT", name="Kỹ thuật lập trình")
        save_created(db, admin, course, "course")
    classroom = db.scalar(
        select(Class).where(
            Class.course_id == course.id,
            Class.code == "KTLT-DEMO",
            Class.term == "2026-2027.1",
        )
    )
    if classroom is None:
        classroom = Class(course_id=course.id, code="KTLT-DEMO", term="2026-2027.1", status="open")
        save_created(db, admin, classroom, "class")
    for account, user in users.items():
        if account == "quantri":
            continue
        member = db.scalar(
            select(ClassMember).where(
                ClassMember.class_id == classroom.id,
                ClassMember.user_id == user.id,
            )
        )
        if member is None:
            member = ClassMember(
                class_id=classroom.id,
                user_id=user.id,
                role="lecturer" if account == "gv.chau" else "student",
            )
            save_created(db, admin, member, "class_member")
    require_class_lecturer(require_class_member(classroom.id, db, lecturer), db, lecturer)
    lessons = []
    for index, title in enumerate(LESSONS):
        lesson = db.scalar(
            select(Lesson).where(
                Lesson.class_id == classroom.id,
                Lesson.title == title,
            )
        )
        if lesson is None:
            lesson = create_lesson(
                db, lecturer, classroom, LessonCreate(title=title, position=index)
            )
            if index < 2:
                update_lesson(db, lecturer, lesson, LessonUpdate(is_published=True))
        lessons.append(lesson)
    seed_assignments(db, lecturer, classroom, lessons, users)
    seed_practice(db, lecturer, classroom, lessons, users)
    if pdf is None:
        print("Cảnh báo: không có --pdf; không tạo học liệu.")
    else:
        seed_material(db, lecturer, classroom, lessons[0], pdf)
    print_summary(db, classroom, users)
    return classroom.id


def seed_assignments(
    db: Session,
    lecturer: User,
    classroom: Class,
    lessons: list[Lesson],
    users: dict[str, User],
) -> None:
    for index, title in enumerate(TITLES):
        item = db.scalar(
            select(Assignment).where(
                Assignment.class_id == classroom.id,
                Assignment.title == title,
            )
        )
        if item is None:
            created = assignments.create_assignment(
                db,
                lecturer,
                classroom.id,
                AssignmentCreate(
                    title=title,
                    instructions=[
                        "Dữ liệu minh họa. Viết hàm C tính bình phương một số nguyên nhỏ.",
                        "Dữ liệu minh họa. Viết hàm đệ quy tính n! với 0 <= n <= 20 "
                        "và giải thích phần dừng.",
                        "Dữ liệu minh họa. Dùng con trỏ duyệt mảng số nguyên.",
                    ][index],
                    criteria=CRITERIA if index == 1 else "Đúng kết quả; giải thích rõ.",
                    due_at=datetime(
                        2026,
                        11,
                        20 if index == 0 else 30,
                        23,
                        59,
                        tzinfo=timezone(timedelta(hours=7)),
                    )
                    if index < 2
                    else None,
                    lesson_id=lessons[0 if index < 2 else 1].id,
                ),
            )
            item = db.get(Assignment, created.id)
            assert item is not None
        if index == 2:
            continue
        if item.status == "draft":
            assignments.update_assignment(
                db, lecturer, item.id, AssignmentUpdate(status="published")
            )
        for account, score in [
            ("sv.thao", "8.0" if index == 0 else "9.0"),
            ("sv.duc", "7.5" if index == 0 else "7.0"),
        ]:
            student = users[account]
            contents = (
                [SIMPLE_C]
                if index == 0
                else (
                    [FACTORIAL_FIRST_C, FACTORIAL_C]
                    if account == "sv.thao"
                    else [FACTORIAL_FIRST_C]
                )
            )
            version_id = None
            for number, content in enumerate(contents, 1):
                checked = assignments.assignment(db, student, item.id, "student")
                result = assignments.submit(
                    db,
                    student,
                    checked,
                    SubmissionCreate(
                        content=content,
                        idempotency_key=f"demo-assignment-{index}-{account}-{number}",
                    ),
                )
                version_id = result["version_id"]
                if index == 0:
                    # Bài 0 is a past assignment: date its submissions before the
                    # deadline, otherwise the demo shows them all as late.
                    stored = db.get(SubmissionVersion, version_id)
                    if stored is not None:
                        stored.submitted_at = datetime(
                            2026, 11, 19, 20, number, tzinfo=timezone(timedelta(hours=7))
                        )
                        db.commit()
            assert version_id is not None
            if not assignments.revisions(db, version_id):
                grade = assignments.save_grade(
                    db,
                    lecturer,
                    version_id,
                    GradeCreate(
                        grade=Decimal(score),
                        comment="Bài làm rõ ràng, cần chú ý điều kiện đầu vào.",
                    ),
                )
                if index == 0 or account == "sv.thao":
                    assignments.publish_grade(db, lecturer, grade["revision_id"])
            else:
                history = assignments.revisions(db, version_id)
                if (index == 0 or account == "sv.thao") and history[-1].status == "draft":
                    assignments.publish_grade(db, lecturer, history[-1].id)
        if index == 0 and item.status == "published":
            assignments.update_assignment(db, lecturer, item.id, AssignmentUpdate(status="closed"))


def seed_practice(
    db: Session,
    lecturer: User,
    classroom: Class,
    lessons: list[Lesson],
    users: dict[str, User],
) -> None:
    for index, template in enumerate(QUESTIONS):
        question = db.scalar(
            select(PracticeQuestion).where(
                PracticeQuestion.class_id == classroom.id,
                PracticeQuestion.stem == template.stem,
            )
        )
        if question is None:
            question = practice.create_question(
                db,
                lecturer,
                classroom.id,
                template.model_copy(
                    update={"lesson_id": lessons[0 if index in {0, 4} else 1].id},
                ),
            )
        if index < 5 and question.status == "draft":
            practice.transition(
                db, lecturer, practice.lecturer_question(db, lecturer, question.id), "publish"
            )
        for account, limit in [("sv.thao", 4), ("sv.duc", 2)]:
            if index >= limit:
                continue
            student = users[account]
            checked = practice.question_for_member(db, student, question.id)
            practice.submit_attempt(
                db,
                student,
                checked,
                AttemptCreate(
                    response="0" if account == "sv.thao" and index == 3 else template.answer_key,
                    idempotency_key=f"demo-practice-{index}-{account}",
                ),
            )


def seed_material(db: Session, lecturer: User, classroom: Class, lesson: Lesson, pdf: Path) -> None:
    material = db.scalar(
        select(Material).where(
            Material.class_id == classroom.id,
            Material.title == "Giáo trình Lập trình căn bản",
        )
    )
    version = None
    if material is not None:
        lecturer_material(db, lecturer, material.id)
        if (
            db.scalar(
                select(MaterialVersion.id).where(
                    MaterialVersion.material_id == material.id,
                    MaterialVersion.status == "published",
                )
            )
            is not None
        ):
            return
        version = db.scalar(
            select(MaterialVersion)
            .where(
                MaterialVersion.material_id == material.id,
            )
            .order_by(MaterialVersion.version_no.desc())
            .limit(1)
        )
    if version is None:
        with pdf.open("rb") as stream:
            validated = validate_file(UploadFile(stream, filename=pdf.name))
        if validated.kind != "pdf":
            raise ValueError("--pdf phải là tệp PDF có lớp văn bản.")
        new_material = material is None
        if material is None:
            material = Material(
                class_id=classroom.id,
                lesson_id=lesson.id,
                title="Giáo trình Lập trình căn bản",
                kind="pdf",
                visibility="students",
                source_note="VOER — Giáo trình Lập trình căn bản",
                license_note="CC BY 3.0",
            )
        uploaded = save_upload(
            db, lecturer, material, validated, LocalStorage(), new_material=new_material
        )
        version = db.get(MaterialVersion, uploaded.version.id)
        assert version is not None
    version_id = version.id
    db.commit()  # Release the reader snapshot before the synchronous worker uses its own sessions.
    if version.status in {"uploaded", "failed"}:
        IngestWorker().process(version_id)
    db.refresh(version)
    if version.status != "ready":
        raise RuntimeError("Học liệu chưa sẵn sàng để công bố; kiểm tra xử lý và chạy lại seed.")
    change_publication(db, lecturer, version, publish=True)


def print_summary(db: Session, classroom: Class, users: dict[str, User]) -> None:
    print("Dữ liệu minh họa — Kỹ thuật lập trình")
    for user in users.values():
        print(user.email)
    print(f"{classroom.code} ({classroom.term}) — /lop/{classroom.id}")
    assignment_ids = select(Assignment.id).where(Assignment.class_id == classroom.id)
    submission_ids = select(Submission.id).where(Submission.assignment_id.in_(assignment_ids))
    version_ids = select(SubmissionVersion.id).where(
        SubmissionVersion.submission_id.in_(submission_ids)
    )
    question_ids = select(PracticeQuestion.id).where(PracticeQuestion.class_id == classroom.id)
    material_ids = select(Material.id).where(Material.class_id == classroom.id)
    counts = {
        "Tài khoản": len(users),
        "Bài học": db.scalar(
            select(func.count()).select_from(Lesson).where(Lesson.class_id == classroom.id)
        ),
        "Học liệu": db.scalar(
            select(func.count()).select_from(Material).where(Material.id.in_(material_ids))
        ),
        "Phiên bản học liệu": db.scalar(
            select(func.count())
            .select_from(MaterialVersion)
            .where(MaterialVersion.material_id.in_(material_ids))
        ),
        "Bài tập": db.scalar(
            select(func.count()).select_from(Assignment).where(Assignment.id.in_(assignment_ids))
        ),
        "Bài nộp": db.scalar(
            select(func.count()).select_from(Submission).where(Submission.id.in_(submission_ids))
        ),
        "Lần nộp": db.scalar(
            select(func.count())
            .select_from(SubmissionVersion)
            .where(SubmissionVersion.id.in_(version_ids))
        ),
        "Bản chấm": db.scalar(
            select(func.count())
            .select_from(GradeRevision)
            .where(GradeRevision.submission_version_id.in_(version_ids))
        ),
        "Câu luyện tập": db.scalar(
            select(func.count())
            .select_from(PracticeQuestion)
            .where(PracticeQuestion.id.in_(question_ids))
        ),
        "Lượt làm": db.scalar(
            select(func.count())
            .select_from(PracticeAttempt)
            .where(PracticeAttempt.question_id.in_(question_ids))
        ),
    }
    for label, count in counts.items():
        print(f"{label}: {count} (đã tạo hoặc đã có sẵn)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tạo dữ liệu minh họa DUTLearn, chạy lại được.")
    parser.add_argument("--pdf", type=Path, help="Giáo trình PDF có lớp văn bản")
    args = parser.parse_args()
    try:
        demo_password()
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    with SessionLocal() as db:
        seed(db, args.pdf)


if __name__ == "__main__":
    main()
