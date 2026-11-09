import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.auth.models import AuditEvent, SessionToken, User
from app.auth.security import token_hash
from app.config import get_settings
from app.courses.models import Class, Lesson
from app.errors import APIError
from app.ingest import queue
from app.main import app
from app.materials.models import Material, MaterialVersion
from app.materials.policy import can_read_version
from app.materials.router import get_storage
from app.materials.service import validate_file
from app.materials.storage import LocalStorage
from app.seed import seed

CSRF = {"X-DUT-CSRF": "1"}
PDF = b"%PDF-1.7\nT08 test"


@pytest.fixture
def material_db(test_engine: Engine, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DUT_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    with Session(test_engine) as db:
        db.execute(text("TRUNCATE users, courses CASCADE"))
        db.commit()
        seed(db)
        yield db
    get_settings.cache_clear()


def account(client, db, name="gv1"):
    client.cookies.clear()
    if name is None:
        return
    user = db.scalars(select(User).where(User.email == f"{name}@dutlearn.local")).one()
    raw = f"materials-test-{name}"
    existing = db.scalar(select(SessionToken).where(SessionToken.token_hash == token_hash(raw)))
    if existing is None:
        db.add(
            SessionToken(
                user_id=user.id,
                token_hash=token_hash(raw),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
        db.commit()
    client.cookies.set("dut_session", raw)


def class_id(db, code="KTLT-01"):
    return db.scalars(select(Class).where(Class.code == code)).one().id


def upload(client, db, filename="lesson.pdf", content=PDF, **fields):
    return client.post(
        f"/api/classes/{class_id(db)}/materials",
        headers=CSRF,
        data={"title": "Bài học", **fields},
        files={"file": (filename, content)},
    )


def create(client, db):
    account(client, db)
    response = upload(client, db)
    assert response.status_code == 201, response.text
    return response.json()


def publish(db, result):
    version = db.get(MaterialVersion, UUID(result["version"]["id"]))
    material = db.get(Material, UUID(result["material"]["id"]))
    version.status = "published"
    version.page_count = 4
    material.active_version_id = version.id
    db.commit()
    return material, version


@pytest.mark.parametrize(
    "filename,content",
    [("lesson.pdf", PDF), ("lesson.txt", "Nội dung".encode()), ("lesson.md", b"# Lesson")],
)
def test_upload_persisted_before_enqueue(
    db_client, material_db, tmp_path, monkeypatch, test_engine, filename, content
):
    calls = []

    def enqueue(version_id):
        # A separate connection can see the version only after upload committed.
        with Session(test_engine) as other:
            version = other.get(MaterialVersion, version_id)
            assert version is not None and version.status == "uploaded"
            assert (
                other.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.target_id == version_id,
                        AuditEvent.action == "material_version.create",
                    )
                )
                == 1
            )
        calls.append(version_id)

    monkeypatch.setattr(queue, "enqueue_ingest", enqueue)
    account(db_client, material_db)
    response = upload(
        db_client, material_db, filename, content, source_note="Nguồn", license_note="CC BY"
    )
    assert response.status_code == 201, response.text
    result = response.json()
    version = material_db.get(MaterialVersion, UUID(result["version"]["id"]))
    assert calls == [version.id]
    assert version.version_no == 1 and version.status == "uploaded"
    assert version.original_filename == filename and version.size_bytes == len(content)
    assert version.checksum_sha256 == hashlib.sha256(content).hexdigest()
    assert version.storage_key == (
        f"materials/{result['material']['id']}/{version.id}.{filename.rsplit('.', 1)[1]}"
    )
    assert (tmp_path / version.storage_key).read_bytes() == content
    assert material_db.get(User, version.created_by).email == "gv1@dutlearn.local"
    assert (
        material_db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "material.create")
        )
        == 1
    )
    listing = db_client.get(f"/api/classes/{class_id(material_db)}/materials").json()
    assert listing[0]["versions"][0]["id"] == str(version.id)
    detail = db_client.get(f"/api/material-versions/{version.id}").json()
    assert detail["status"] == "uploaded" and detail["quality_report"] is None
    downloaded = db_client.get(f"/api/material-versions/{version.id}/file")
    assert downloaded.status_code == 200 and downloaded.content == content
    expected_type = {"pdf": "application/pdf", "txt": "text/plain", "md": "text/markdown"}
    assert downloaded.headers["content-type"].startswith(expected_type[filename.split(".")[-1]])


@pytest.mark.parametrize(
    "filename,content,limit,status,code",
    [
        ("fake.pdf", b"not PDF", 100, 415, "unsupported_media_type"),
        ("bad.txt", b"\xff", 100, 415, "unsupported_media_type"),
        ("bad.md", b"\xfe", 100, 415, "unsupported_media_type"),
        ("big.pdf", PDF, 5, 413, "file_too_large"),
        ("../../x.pdf", PDF, 100, 422, "invalid_filename"),
        ("..\\x.pdf", PDF, 100, 422, "invalid_filename"),
        ("file.exe", b"MZ", 100, 415, "unsupported_media_type"),
    ],
)
def test_invalid_upload_has_no_side_effects(
    db_client, material_db, tmp_path, monkeypatch, filename, content, limit, status, code
):
    monkeypatch.setenv("DUT_MAX_UPLOAD_BYTES", str(limit))
    calls = []
    monkeypatch.setattr(queue, "enqueue_ingest", calls.append)
    account(db_client, material_db)
    response = upload(db_client, material_db, filename, content)
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    for model in (Material, MaterialVersion, AuditEvent):
        assert material_db.scalar(select(func.count()).select_from(model)) == 0
    assert not list(tmp_path.rglob("*")) and not calls


@pytest.mark.parametrize(
    "actor,write_status,read_status,file_status",
    [
        ("gv1", 201, 200, 200),
        ("sv1", 403, 403, 200),
        ("gv2", 404, 404, 404),
        ("sv3", 404, 404, 404),
        ("admin", 404, 404, 404),
        (None, 401, 401, 401),
    ],
)
def test_permission_matrix_all_endpoints(
    db_client, material_db, actor, write_status, read_status, file_status
):
    result = create(db_client, material_db)
    material, version = publish(material_db, result)
    account(db_client, material_db, actor)
    assert upload(db_client, material_db).status_code == write_status
    assert (
        db_client.post(
            f"/api/materials/{material.id}/versions", headers=CSRF, files={"file": ("new.pdf", PDF)}
        ).status_code
        == write_status
    )
    assert db_client.get(f"/api/material-versions/{version.id}").status_code == read_status
    assert db_client.get(f"/api/material-versions/{version.id}/file").status_code == file_status
    list_status = 200 if actor in {"gv1", "sv1"} else (401 if actor is None else 404)
    assert (
        db_client.get(f"/api/classes/{class_id(material_db)}/materials").status_code == list_status
    )


def test_csrf_on_both_uploads(db_client, material_db):
    result = create(db_client, material_db)
    for path in (
        f"/api/classes/{class_id(material_db)}/materials",
        f"/api/materials/{result['material']['id']}/versions",
    ):
        response = db_client.post(path, data={"title": "Lesson"}, files={"file": ("x.pdf", PDF)})
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf_required"
    assert material_db.scalar(select(func.count()).select_from(MaterialVersion)) == 1


@pytest.mark.parametrize(
    "state",
    [
        "uploaded",
        "processing",
        "ready",
        "failed",
        "superseded",
        "revoked",
        "inactive",
        "lecturers",
        "closed",
        "published",
    ],
)
def test_student_visibility_and_policy(db_client, material_db, state):
    result = create(db_client, material_db)
    material, version = publish(material_db, result)
    if state in {"uploaded", "processing", "ready", "failed", "superseded", "revoked"}:
        version.status = state
    elif state == "inactive":
        material.active_version_id = None
    elif state == "lecturers":
        material.visibility = "lecturers"
    elif state == "closed":
        material_db.get(Class, material.class_id).status = "closed"
    version.error = "private processing error"
    version.quality_report = {"sample": "private sample"}
    material_db.commit()
    account(db_client, material_db, "sv1")
    user = material_db.scalars(select(User).where(User.email == "sv1@dutlearn.local")).one()
    assert can_read_version(material_db, user, version) == (state == "published")
    response = db_client.get(f"/api/material-versions/{version.id}/file")
    assert response.status_code == (200 if state == "published" else 404)
    listing = db_client.get(f"/api/classes/{material.class_id}/materials")
    if state == "closed":
        assert listing.status_code == 404
    elif state != "published":
        assert listing.json() == []
    else:
        assert response.content == PDF
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-disposition"] == "inline; filename*=UTF-8''lesson.pdf"
        assert response.headers["content-type"] == "application/pdf"
        assert set(listing.json()[0]) == {
            "id",
            "title",
            "lesson_id",
            "kind",
            "active_version_id",
            "page_count",
            "source_note",
            "license_note",
        }
        assert listing.json()[0]["page_count"] == 4
        assert "private" not in listing.text


def test_sequential_versions_and_kind(db_client, material_db, monkeypatch):
    calls = []
    monkeypatch.setattr(queue, "enqueue_ingest", calls.append)
    result = create(db_client, material_db)
    path = f"/api/materials/{result['material']['id']}/versions"
    for number in (2, 3):
        response = db_client.post(path, headers=CSRF, files={"file": ("new.pdf", PDF)})
        assert response.status_code == 201, response.text
        assert response.json()["version"]["version_no"] == number
    mismatch = db_client.post(path, headers=CSRF, files={"file": ("new.txt", b"text")})
    assert mismatch.status_code == 422 and len(calls) == 3
    assert material_db.scalar(select(func.count()).select_from(MaterialVersion)) == 3


def test_concurrent_versions(db_client, material_db):
    result = create(db_client, material_db)
    cookie = db_client.cookies.get("dut_session")

    def add_version(_):
        with TestClient(app) as client:
            client.cookies.set("dut_session", cookie)
            return client.post(
                f"/api/materials/{result['material']['id']}/versions",
                headers=CSRF,
                files={"file": ("new.pdf", PDF)},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(add_version, range(2)))
    assert [response.status_code for response in responses] == [201, 201]
    assert sorted(response.json()["version"]["version_no"] for response in responses) == [2, 3]


def test_lesson_scope_and_form_validation(db_client, material_db, tmp_path):
    account(db_client, material_db)
    other = Lesson(class_id=class_id(material_db, "KTLT-02"), title="Other")
    own = Lesson(class_id=class_id(material_db), title="Own")
    material_db.add_all([other, own])
    material_db.commit()
    assert upload(db_client, material_db, lesson_id=str(other.id)).status_code == 404
    for title in ("", " " * 3, "x" * 201):
        assert upload(db_client, material_db, title=title).status_code == 422
    assert upload(db_client, material_db, visibility="public").status_code == 422
    assert not list(tmp_path.rglob("*"))
    result = upload(db_client, material_db, lesson_id=str(own.id))
    assert result.status_code == 201 and result.json()["material"]["lesson_id"] == str(own.id)


def test_storage_failure_rolls_back_and_does_not_enqueue(db_client, material_db, monkeypatch):
    class BrokenStorage(LocalStorage):
        def put(self, key, data):
            raise OSError("disk full")

    calls = []
    monkeypatch.setattr(queue, "enqueue_ingest", calls.append)
    app.dependency_overrides[get_storage] = BrokenStorage
    try:
        account(db_client, material_db)
        assert upload(db_client, material_db).status_code == 500
        assert not calls
        assert material_db.scalar(select(func.count()).select_from(Material)) == 0
        assert material_db.scalar(select(func.count()).select_from(MaterialVersion)) == 0
    finally:
        app.dependency_overrides.pop(get_storage, None)


@pytest.mark.parametrize("key", ["../x", "/x", "a/../../x", "C:/x", "a\\x", "", "."])
def test_storage_rejects_escaping_keys(tmp_path, key):
    storage = LocalStorage(tmp_path)
    for operation in (
        lambda: storage.put(key, b"x"),
        lambda: storage.open(key),
        lambda: storage.exists(key),
    ):
        with pytest.raises(ValueError):
            operation()
    assert not list(tmp_path.rglob("*"))


def test_storage_atomic_replace(tmp_path, monkeypatch):
    storage = LocalStorage(tmp_path)
    storage.put("materials/m/v.pdf", PDF)
    import app.materials.storage as module

    def fail_replace(source, destination):
        raise OSError("replace failed")

    monkeypatch.setattr(module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        storage.put("materials/m/v.pdf", b"replacement")
    with storage.open("materials/m/v.pdf") as stream:
        assert stream.read() == PDF
    assert storage.exists("materials/m/v.pdf")
    assert [path.name for path in (tmp_path / "materials/m").iterdir()] == ["v.pdf"]


def test_validation_stops_reading_at_limit(monkeypatch):
    monkeypatch.setenv("DUT_MAX_UPLOAD_BYTES", "5")
    stream = BytesIO(b"%PDF-" + b"x" * 100)
    with pytest.raises(APIError) as error:
        validate_file(UploadFile(filename="test.pdf", file=stream))
    assert error.value.status_code == 413 and stream.tell() == 6


def test_validation_accepts_exact_limit(monkeypatch):
    monkeypatch.setenv("DUT_MAX_UPLOAD_BYTES", "5")
    assert validate_file(UploadFile(filename="test.pdf", file=BytesIO(b"%PDF-"))).data == b"%PDF-"
