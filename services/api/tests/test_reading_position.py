from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.courses.models import Class, ClassMember, Course
from app.deps import require_user
from app.main import app
from app.materials.models import Chunk, Material, MaterialVersion
from app.progress.models import ReadingPosition


@pytest.fixture
def reading(db_client, test_engine):
    with Session(test_engine) as db:
        users = [
            User(
                email=f"{uuid4()}@test.invalid",
                full_name="Synthetic",
                password_hash="unused",
                system_role="admin" if i == 3 else "user",
            )
            for i in range(4)
        ]
        course = Course(code=str(uuid4()), name="Synthetic course")
        db.add_all([*users, course])
        db.flush()
        classroom = Class(course_id=course.id, code=str(uuid4()), term="test", status="open")
        db.add(classroom)
        other_class = Class(course_id=course.id, code=str(uuid4()), term="test", status="open")
        db.add(other_class)
        db.flush()
        db.add(ClassMember(class_id=other_class.id, user_id=users[2].id, role="student"))
        db.add_all(
            [
                ClassMember(class_id=classroom.id, user_id=users[i].id, role=role)
                for i, role in [(0, "student"), (1, "lecturer")]
            ]
        )
        materials, versions = [], []
        for i in range(2):
            material = Material(
                class_id=classroom.id, title=f"Synthetic {i}", kind="text", visibility="students"
            )
            db.add(material)
            db.flush()
            version = MaterialVersion(
                material_id=material.id,
                version_no=1,
                status="published",
                storage_key="unused",
                checksum_sha256="0" * 64,
                created_by=users[1].id,
                page_count=3,
            )
            db.add(version)
            db.flush()
            material.active_version_id = version.id
            db.add(
                Chunk(
                    version_id=version.id,
                    ordinal=0,
                    kind="text",
                    page_index=1,
                    page_index_end=1,
                    page_label="ii",
                    char_start=0,
                    char_end=4,
                    text="test",
                    token_count=1,
                    embedding=[0.0] * 384,
                )
            )
            materials.append(material)
            versions.append(version)
        db.commit()
        actor = [0]
        app.dependency_overrides[require_user] = lambda: users[actor[0]]

        def put(index=0, page=1, **changes):
            return db_client.put(
                "/api/reading-position",
                headers={"X-DUT-CSRF": "1"},
                json={
                    "material_id": str(materials[index].id),
                    "version_id": str(versions[index].id),
                    "page_index": page,
                    **changes,
                },
            )

        yield SimpleNamespace(
            db=db,
            client=db_client,
            users=users,
            actor=actor,
            put=put,
            materials=materials,
            versions=versions,
            classroom=classroom,
            get=lambda: db_client.get("/api/me/continue"),
        )


def test_upsert_latest_label_and_isolation(reading):
    r = reading
    assert r.get().json() is None
    assert r.put().status_code == 204
    first = r.get().json()
    assert first["page_label"] == "ii"
    assert first["material_title"] == "Synthetic 0"
    assert first["course_name"] == "Synthetic course"
    assert first["class_id"] == str(r.classroom.id)
    assert r.put(1).status_code == 204
    assert r.get().json()["material_id"] == str(r.materials[1].id)
    assert r.put(page=2).status_code == 204
    assert r.get().json()["page_index"] == 2
    assert r.get().json()["page_label"] == "3"
    assert (
        r.db.scalar(
            select(func.count())
            .select_from(ReadingPosition)
            .where(ReadingPosition.user_id == r.users[0].id)
        )
        == 2
    )
    r.actor[0] = 1
    assert r.get().json() is None


@pytest.mark.parametrize("change", ["revoked", "superseded", "visibility", "closed", "membership"])
def test_invalid_latest_skipped_without_deletion(reading, change):
    r = reading
    assert r.put(0).status_code == 204
    assert r.put(1).status_code == 204
    if change in {"revoked", "superseded"}:
        r.versions[1].status = change
        if change == "revoked":
            r.materials[1].active_version_id = None
        else:
            replacement = MaterialVersion(
                material_id=r.materials[1].id,
                version_no=2,
                status="published",
                storage_key="unused",
                checksum_sha256="1" * 64,
                created_by=r.users[1].id,
                page_count=3,
            )
            r.db.add(replacement)
            r.db.flush()
            r.materials[1].active_version_id = replacement.id
    elif change == "visibility":
        r.materials[1].visibility = "lecturers"
    elif change == "closed":
        r.classroom.status = "closed"
    else:
        member = r.db.scalar(select(ClassMember).where(ClassMember.user_id == r.users[0].id))
        r.db.delete(member)
    r.db.commit()
    data = r.get().json()
    assert (
        data is None
        if change in {"closed", "membership"}
        else data["material_id"] == str(r.materials[0].id)
    )
    assert (
        r.db.scalar(
            select(func.count())
            .select_from(ReadingPosition)
            .where(ReadingPosition.user_id == r.users[0].id)
        )
        == 2
    )
    assert r.put(1).status_code == 404


@pytest.mark.parametrize("actor", [2, 3])
def test_outsider_and_admin_have_no_implicit_rights(reading, actor):
    reading.actor[0] = actor
    assert reading.put().status_code == 404
    assert reading.get().json() is None


def test_visibility_and_active_version_required_even_for_lecturer(reading):
    r = reading
    r.materials[0].visibility = "lecturers"
    r.db.commit()
    assert r.put().status_code == 404
    r.actor[0] = 1
    assert r.put().status_code == 204
    r.materials[0].active_version_id = None
    r.db.commit()
    assert r.put().status_code == 404
    assert r.get().json() is None


@pytest.mark.parametrize("page", [-1, 3, 100, 1.5, True])
def test_page_range(reading, page):
    assert reading.put(page=page).status_code == 422


def test_mismatch_csrf_and_auth(reading):
    r = reading
    assert r.put(version_id=str(r.versions[1].id)).status_code == 404
    assert r.put(version_id=str(uuid4())).status_code == 404
    assert r.client.put("/api/reading-position", json={}).status_code == 403
    del app.dependency_overrides[require_user]
    assert r.put().status_code == 401
    assert r.get().status_code == 401


def test_migration_downgrade_upgrade(test_engine):
    from alembic.config import Config
    from sqlalchemy import inspect, text

    from alembic import command

    with test_engine.begin() as connection:
        schema = "reading_migration_" + uuid4().hex
        original = connection.scalar(text("SHOW search_path"))
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}", public'))
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert "reading_positions" in inspect(connection).get_table_names(schema=schema)
        command.downgrade(config, "0004_tutor_chat")
        assert "reading_positions" not in inspect(connection).get_table_names(schema=schema)
        command.upgrade(config, "head")
        assert "reading_positions" in inspect(connection).get_table_names(schema=schema)
        connection.execute(text(f"SET LOCAL search_path TO {original}"))
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
