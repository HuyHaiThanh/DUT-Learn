from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from threading import Barrier
from uuid import UUID, uuid4

import pymupdf
import pytest
import test_materials
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_materials import CSRF, account, class_id, upload

from app.auth.models import AuditEvent, User
from app.courses.models import Class, Lesson
from app.errors import APIError
from app.ingest.chunk import chunk_document
from app.ingest.extract import extract_pdf, extract_text
from app.materials import publication
from app.materials.models import Chunk, Material, MaterialVersion
from app.materials.publication import change_publication
from app.rag.embedder import FakeEmbedder

material_db = test_materials.material_db


def ready(client, db, *, filename="lesson.md", content=None):
    account(client, db)
    response = upload(
        client, db, filename, content or "Đoạn mở đầu.\r\n\r\nNội dung 😀 tiếng Việt.".encode()
    )
    assert response.status_code == 201, response.text
    item = response.json()
    version = db.get(MaterialVersion, UUID(item["version"]["id"]))
    version.status = "ready"
    version.page_count = 1
    version.quality_report = {
        "page_count": 1,
        "chunk_count": {"text": 1, "code": 0},
        "empty_pages": [0],
        "glued_tokens_before": 2,
        "glued_tokens_after": 0,
        "sample": ["private sample"],
    }
    db.commit()
    return db.get(Material, version.material_id), version


def post(client, version, action):
    return client.post(f"/api/material-versions/{version.id}/{action}", headers=CSRF)


def epoch(db, material):
    db.expire_all()
    return db.get(Class, material.class_id).content_version


@pytest.mark.parametrize(
    "state", ["uploaded", "processing", "failed", "published", "superseded", "revoked"]
)
def test_publish_only_ready(db_client, material_db, state):
    material, version = ready(db_client, material_db)
    version.status = state
    material_db.commit()
    response = post(db_client, version, "publish")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"
    assert epoch(material_db, material) == 0
    assert material_db.get(MaterialVersion, version.id).status == state


def test_replace_then_revoke_active(db_client, material_db):
    db = material_db
    material, first = ready(db_client, db)
    assert post(db_client, first, "publish").status_code == 200
    assert epoch(db, material) == 1
    result = db_client.post(
        f"/api/materials/{material.id}/versions",
        headers=CSRF,
        files={"file": ("new.md", b"New page")},
    )
    second = db.get(MaterialVersion, UUID(result.json()["version"]["id"]))
    second.status = "ready"
    db.commit()
    assert post(db_client, second, "publish").status_code == 200
    assert epoch(db, material) == 2
    assert first.status == "superseded" and material.active_version_id == second.id
    assert second.published_at is not None and second.published_by == first.created_by
    account(db_client, db, "sv1")
    for suffix in ("file", "pages/0/text"):
        assert db_client.get(f"/api/material-versions/{first.id}/{suffix}").status_code == 404
        assert db_client.get(f"/api/material-versions/{second.id}/{suffix}").status_code == 200
    account(db_client, db)
    assert post(db_client, second, "revoke").status_code == 200
    assert epoch(db, material) == 3
    assert material.active_version_id is None
    assert second.revoked_at is not None and second.revoked_by == first.created_by
    account(db_client, db, "sv1")
    for suffix in ("file", "pages/0/text"):
        assert db_client.get(f"/api/material-versions/{second.id}/{suffix}").status_code == 404
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action.in_(["material_version.publish", "material_version.revoke"]))
        )
        == 3
    )


@pytest.mark.parametrize(
    "state,expected",
    [
        ("ready", 200),
        ("superseded", 200),
        ("uploaded", 409),
        ("processing", 409),
        ("failed", 409),
        ("revoked", 409),
    ],
)
def test_revoke_inactive_does_not_bump_epoch(db_client, material_db, state, expected):
    material, version = ready(db_client, material_db)
    version.status = state
    material_db.commit()
    assert post(db_client, version, "revoke").status_code == expected
    assert epoch(material_db, material) == 0


@pytest.mark.parametrize(
    "actor,write_status,read_status",
    [
        ("gv1", 200, 200),
        ("sv1", 403, 200),
        ("gv2", 404, 404),
        ("sv3", 404, 404),
        ("admin", 404, 404),
        (None, 401, 401),
    ],
)
def test_new_endpoints_permission_matrix(db_client, material_db, actor, write_status, read_status):
    material, version = ready(db_client, material_db)
    assert post(db_client, version, "publish").status_code == 200
    # Separate ready version exercises authorization before the publication state check.
    result = db_client.post(
        f"/api/materials/{material.id}/versions",
        headers=CSRF,
        files={"file": ("new.md", b"New page")},
    )
    pending = material_db.get(MaterialVersion, UUID(result.json()["version"]["id"]))
    pending.status = "ready"
    material_db.commit()
    account(db_client, material_db, actor)
    assert (
        db_client.get(f"/api/material-versions/{version.id}/pages/0/text").status_code
        == read_status
    )
    assert db_client.get(f"/api/classes/{material.class_id}/materials").status_code == read_status
    assert (
        db_client.patch(
            f"/api/materials/{material.id}", headers=CSRF, json={"title": "New"}
        ).status_code
        == write_status
    )
    assert post(db_client, pending, "publish").status_code == write_status
    assert post(db_client, version, "revoke").status_code == write_status


def test_csrf_and_missing_resources(db_client, material_db):
    material, version = ready(db_client, material_db)
    for action in ("publish", "revoke"):
        assert db_client.post(f"/api/material-versions/{version.id}/{action}").status_code == 403
        assert (
            db_client.post(f"/api/material-versions/{uuid4()}/{action}", headers=CSRF).status_code
            == 404
        )
    assert (
        db_client.patch(f"/api/materials/{material.id}", json={"title": "New"}).status_code == 403
    )
    assert (
        db_client.patch(
            f"/api/materials/{uuid4()}", headers=CSRF, json={"title": "New"}
        ).status_code
        == 404
    )
    assert db_client.get(f"/api/material-versions/{uuid4()}/pages/0/text").status_code == 404
    assert epoch(material_db, material) == 0


def test_patch_visibility_lesson_validation_and_summary(db_client, material_db):
    db = material_db
    material, version = ready(db_client, db)
    assert post(db_client, version, "publish").status_code == 200
    own = Lesson(class_id=material.class_id, title="Own")
    other = Lesson(class_id=class_id(db, "KTLT-02"), title="Other")
    db.add_all([own, other])
    db.commit()
    path = f"/api/materials/{material.id}"
    assert (
        db_client.patch(
            path, headers=CSRF, json={"lesson_id": str(other.id), "visibility": "lecturers"}
        ).status_code
        == 404
    )
    assert epoch(db, material) == 1 and material.visibility == "students"
    for invalid in (
        {"title": None},
        {"title": "  "},
        {"visibility": None},
        {"title": "x" * 201},
        {"kind": "pdf"},
    ):
        assert db_client.patch(path, headers=CSRF, json=invalid).status_code == 422
    assert (
        db_client.patch(
            path, headers=CSRF, json={"title": " New ", "lesson_id": str(own.id)}
        ).status_code
        == 200
    )
    assert epoch(db, material) == 1 and material.title == "New"
    assert (
        db_client.patch(
            path, headers=CSRF, json={"visibility": "lecturers", "lesson_id": None}
        ).status_code
        == 200
    )
    assert epoch(db, material) == 2 and material.lesson_id is None
    assert db_client.patch(path, headers=CSRF, json={"visibility": "lecturers"}).status_code == 200
    assert epoch(db, material) == 2
    report = db_client.get(f"/api/classes/{material.class_id}/materials").json()[0][
        "quality_report"
    ]
    assert report == {
        "page_count": 1,
        "chunk_count": {"text": 1, "code": 0},
        "empty_pages": 1,
        "glued_tokens_before": 2,
        "glued_tokens_after": 0,
    }
    account(db_client, db, "sv1")
    for suffix in ("file", "pages/0/text"):
        assert db_client.get(f"/api/material-versions/{version.id}/{suffix}").status_code == 404
    assert db_client.get(f"/api/classes/{material.class_id}/materials").json() == []


@pytest.mark.parametrize("pdf", [False, True])
def test_pages_canonical_offsets_and_bounds(db_client, material_db, pdf):
    if pdf:
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((40, 40), "First text")
            page.insert_text((120, 40), "separated")
            page.insert_text((40, 100), "1/1")
            content = document.tobytes()
        extracted = extract_pdf(content)
    else:
        content = ("Mo\u031b\u0309 đầu 😀.\r\n\r\n" + "Nội dung. " * 700).encode()
        extracted = extract_text(content)
    material, version = ready(
        db_client, material_db, filename="lesson.pdf" if pdf else "lesson.md", content=content
    )
    drafts = chunk_document(extracted, FakeEmbedder())
    for ordinal, draft in enumerate(drafts):
        material_db.add(
            Chunk(
                version_id=version.id,
                ordinal=ordinal,
                **asdict(draft),
                embedding=[0.0] * 384,
            )
        )
    material_db.commit()
    assert post(db_client, version, "publish").status_code == 200
    account(db_client, material_db, "sv1")
    for page in extracted.pages:
        response = db_client.get(f"/api/material-versions/{version.id}/pages/{page.index}/text")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert int(response.headers["x-page-count"]) == len(extracted.pages)
        body = response.json()
        assert body["text"] == page.text and body["page_label"] == page.label
        assert len(body["chunks"]) == sum(d.page_index == page.index for d in drafts)
        for chunk in body["chunks"]:
            stored = material_db.get(Chunk, UUID(chunk["id"]))
            assert body["text"][chunk["char_start"] : chunk["char_end"]] == stored.text
    for page in (-1, len(extracted.pages), 999):
        assert (
            db_client.get(f"/api/material-versions/{version.id}/pages/{page}/text").status_code
            == 404
        )
    classroom = material_db.get(Class, material.class_id)
    classroom.status = "closed"
    material_db.commit()
    assert db_client.get(f"/api/material-versions/{version.id}/pages/0/text").status_code == 404


@pytest.mark.parametrize("same_version", [False, True])
def test_concurrent_publish_serializes(db_client, material_db, test_engine, same_version):
    material, first = ready(db_client, material_db)
    second = MaterialVersion(
        material_id=material.id,
        version_no=2,
        status="ready",
        storage_key="second.md",
        checksum_sha256="a" * 64,
        created_by=first.created_by,
    )
    material_db.add(second)
    material_db.commit()
    ids = [first.id, first.id if same_version else second.id]
    actor_id = first.created_by
    barrier = Barrier(2)

    def publish(version_id):
        with Session(test_engine) as db:
            user = db.get(User, actor_id)
            version = db.get(MaterialVersion, version_id)
            barrier.wait(timeout=10)
            try:
                change_publication(db, user, version, publish=True)
                return 200
            except APIError as error:
                db.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(publish, ids))
    assert sorted(statuses) == ([200, 409] if same_version else [200, 200])
    assert epoch(material_db, material) == (1 if same_version else 2)
    published = material_db.scalars(
        select(MaterialVersion).where(
            MaterialVersion.material_id == material.id, MaterialVersion.status == "published"
        )
    ).all()
    assert len(published) == 1 and published[0].id == material.active_version_id


def test_audit_failure_rolls_back_all_publication_changes(db_client, material_db, monkeypatch):
    material, version = ready(db_client, material_db)

    def fail(*args):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(publication, "audit", fail)
    user = material_db.get(User, version.created_by)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        change_publication(material_db, user, version, publish=True)
    material_db.rollback()
    assert epoch(material_db, material) == 0
    assert version.status == "ready" and material.active_version_id is None
