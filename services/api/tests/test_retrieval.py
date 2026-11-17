import math
import os
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.config import Settings
from app.courses.models import Class, ClassMember, Course
from app.materials.models import Chunk, Material, MaterialVersion
from app.rag.embedder import E5Embedder, FakeEmbedder
from app.rag.retriever import DenseRetriever, get_retriever
from app.rag.scope import scoped_chunks, versions_still_valid


@pytest.fixture
def world(test_engine):
    with test_engine.connect() as connection:
        transaction = connection.begin()
        with Session(connection) as db:
            users = [
                User(
                    email=f"{uuid4()}@example.test",
                    full_name="Test",
                    password_hash="unused",
                    system_role="admin" if i == 3 else "user",
                    is_active=True,
                )
                for i in range(4)
            ]
            db.add_all(users)
            course = Course(code=str(uuid4()), name="Synthetic course")
            db.add(course)
            db.flush()
            classes = [
                Class(course_id=course.id, code=str(i), term="test", status="open")
                for i in range(2)
            ]
            db.add_all(classes)
            db.flush()
            for classroom in classes:
                for user, role in zip(users[:2], ["student", "lecturer"], strict=True):
                    db.add(ClassMember(class_id=classroom.id, user_id=user.id, role=role))
            db.flush()

            def material(*, classroom=None, visibility="students", status="published", score=0.8):
                mat = Material(
                    class_id=(classroom or classes[0]).id,
                    title="Synthetic material",
                    kind="text",
                    visibility=visibility,
                )
                db.add(mat)
                db.flush()
                ver = MaterialVersion(
                    material_id=mat.id,
                    version_no=1,
                    status=status,
                    storage_key="synthetic.txt",
                    checksum_sha256="0" * 64,
                    created_by=users[1].id,
                )
                db.add(ver)
                db.flush()
                mat.active_version_id = ver.id
                query = FakeEmbedder().embed_query("needle")
                axis = next(i for i, value in enumerate(query) if value == 0)
                vector = [score * value for value in query]
                vector[axis] = math.sqrt(1 - score * score)
                chunk = Chunk(
                    version_id=ver.id,
                    ordinal=0,
                    kind="text",
                    page_index=0,
                    page_index_end=0,
                    page_label="1",
                    char_start=0,
                    char_end=14,
                    text="synthetic text",
                    token_count=2,
                    embedding=vector,
                )
                db.add(chunk)
                db.flush()
                return mat, ver, chunk

            yield db, users, classes, material
        transaction.rollback()


@pytest.mark.parametrize(
    ("scenario", "visible"),
    [
        ("published", True),
        ("superseded", False),
        ("revoked", False),
        ("ready", False),
        ("inactive", False),
        ("lecturers", False),
        ("lecturer", True),
        ("other_class", False),
        ("closed", False),
        ("closed_lecturer", False),
        ("outsider", False),
        ("admin", False),
    ],
)
def test_i2_matrix(world, scenario, visible):
    db, users, classes, material = world
    mat, ver, chunk = material()
    user = users[0]
    if scenario in {"superseded", "revoked", "ready"}:
        ver.status = scenario
    if scenario == "inactive":
        mat.active_version_id = None
    if scenario in {"lecturers", "lecturer"}:
        mat.visibility = "lecturers"
    if scenario == "other_class":
        mat.class_id = classes[1].id
    if scenario in {"closed", "closed_lecturer"}:
        classes[0].status = "closed"
    if scenario in {"lecturer", "closed_lecturer"}:
        user = users[1]
    if scenario in {"outsider", "admin"}:
        user = users[2 if scenario == "outsider" else 3]
    result = DenseRetriever(FakeEmbedder()).retrieve(
        db,
        user=user,
        class_id=classes[0].id,
        query="needle",
        k=10,
    )
    assert {hit.chunk_id for hit in result.hits} == ({chunk.id} if visible else set())


def test_active_switch_and_revalidation(world):
    db, users, classes, material = world
    mat, old, old_chunk = material()
    _, hidden, _ = material(visibility="lecturers")
    _, foreign, _ = material(classroom=classes[1])
    ids = {old.id, hidden.id, foreign.id, uuid4()}
    assert versions_still_valid(db, user=users[0], class_id=classes[0].id, version_ids=ids) == {
        old.id
    }
    old.status = "superseded"
    db.flush()
    new = MaterialVersion(
        material_id=mat.id,
        version_no=2,
        status="published",
        storage_key="new.txt",
        checksum_sha256="1" * 64,
        created_by=users[1].id,
    )
    db.add(new)
    db.flush()
    mat.active_version_id = new.id
    chunk = Chunk(
        version_id=new.id,
        ordinal=0,
        kind="text",
        page_index=0,
        page_index_end=0,
        char_start=0,
        char_end=3,
        text="new",
        token_count=1,
        embedding=FakeEmbedder().embed_query("needle"),
    )
    db.add(chunk)
    db.flush()
    assert set(db.scalars(scoped_chunks(db, user=users[0], class_id=classes[0].id))) == {chunk}
    assert versions_still_valid(
        db, user=users[0], class_id=classes[0].id, version_ids=ids | {new.id}
    ) == {new.id}
    new.status = "revoked"
    db.flush()
    assert (
        versions_still_valid(
            db, user=users[0], class_id=classes[0].id, version_ids={old.id, new.id}
        )
        == set()
    )


def test_ranking_and_exact_cosine(world):
    db, users, classes, material = world
    chunks = [material(score=score)[2] for score in [0.3, 0.9, 0.9, 0.7]]
    tied = chunks[1]
    duplicate = Chunk(
        version_id=tied.version_id,
        ordinal=1,
        kind="code",
        page_index=1,
        page_index_end=2,
        char_start=0,
        char_end=1,
        text="x",
        token_count=1,
        embedding=tied.embedding,
    )
    db.add(duplicate)
    db.flush()
    retriever = DenseRetriever(FakeEmbedder())
    result = retriever.retrieve(db, user=users[0], class_id=classes[0].id, query="needle", k=4)
    expected = sorted([chunks[1], chunks[2], duplicate], key=lambda c: (c.version_id, c.ordinal))
    assert [hit.chunk_id for hit in result.hits] == [c.id for c in expected] + [chunks[3].id]
    assert [hit.rank for hit in result.hits] == [1, 2, 3, 4]
    distance = Chunk.embedding.cosine_distance(FakeEmbedder().embed_query("needle"))
    for hit in result.hits:
        actual = db.scalar(select(distance).where(Chunk.id == hit.chunk_id))
        assert hit.cosine == pytest.approx(1 - actual, abs=1e-6)
    assert result.top_cosine == max(h.cosine for h in result.hits)
    assert set(result.timings_ms) == {"embed", "search"}
    assert all(value >= 0 for value in result.timings_ms.values())


def test_preferences_raw_score_and_final_gate_score(world):
    db, users, classes, material = world
    high = material(score=0.95)[2]
    middle = material(score=0.81)[2]
    preferred, _, low = material(score=0.8)
    low.page_index, low.page_index_end = 2, 4
    retriever = DenseRetriever(FakeEmbedder())
    kwargs = dict(db=db, user=users[0], class_id=classes[0].id, query="needle", k=3)
    baseline = retriever.retrieve(**kwargs)
    result = retriever.retrieve(**kwargs, prefer_material_id=preferred.id, prefer_page_index=3)
    assert [h.chunk_id for h in result.hits] == [high.id, low.id, middle.id]
    assert {h.chunk_id: h.cosine for h in result.hits} == {
        h.chunk_id: h.cosine for h in baseline.hits
    }
    for invalid in [
        uuid4(),
        material(visibility="lecturers")[0].id,
        material(classroom=classes[1])[0].id,
    ]:
        ignored = retriever.retrieve(**kwargs, prefer_material_id=invalid, prefer_page_index=3)
        assert ignored.hits == baseline.hits
    # A large bonus can exclude the original top cosine; the gate uses only final hits.
    boosted = DenseRetriever(FakeEmbedder(), Settings(prefer_material_bonus=0.3)).retrieve(
        db,
        user=users[0],
        class_id=classes[0].id,
        query="needle",
        k=1,
        prefer_material_id=preferred.id,
    )
    assert boosted.hits[0].chunk_id == low.id
    assert boosted.top_cosine == pytest.approx(0.8, abs=1e-6)


def test_page_bonus_and_candidate_pool(world):
    db, users, classes, material = world
    _, _, first = material(score=0.825)
    preferred, _, cross_page = material(score=0.8)
    cross_page.page_index, cross_page.page_index_end = 2, 4
    retriever = DenseRetriever(FakeEmbedder())
    kwargs = dict(
        db=db,
        user=users[0],
        class_id=classes[0].id,
        query="needle",
        k=1,
        prefer_material_id=preferred.id,
    )
    assert retriever.retrieve(**kwargs).hits[0].chunk_id == first.id
    for page in [2, 3, 4]:
        assert (
            retriever.retrieve(**kwargs, prefer_page_index=page).hits[0].chunk_id == cross_page.id
        )
    assert retriever.retrieve(**kwargs, prefer_page_index=5).hits[0].chunk_id == first.id
    for _ in range(20):
        material(score=0.84)
    # Even a large bonus does not bring a chunk outside the top-20 candidate pool in.
    large = DenseRetriever(FakeEmbedder(), Settings(prefer_material_bonus=1))
    assert large.retrieve(**kwargs).hits[0].chunk_id != cross_page.id


def test_invalid_query_k_empty_scope_factory(world):
    db, users, classes, _ = world
    retriever = DenseRetriever(FakeEmbedder())
    kwargs = dict(db=db, user=users[0], class_id=classes[0].id, query="needle", k=10)
    result = retriever.retrieve(**kwargs)
    assert result.hits == [] and result.top_cosine is None
    with pytest.raises(ValueError):
        retriever.retrieve(**{**kwargs, "query": " \n "})
    with pytest.raises(ValueError):
        retriever.retrieve(**{**kwargs, "k": 0})
    assert isinstance(get_retriever(Settings()), DenseRetriever)
    with pytest.raises(NotImplementedError, match="T16"):
        get_retriever(Settings(retriever="hybrid"))


@pytest.mark.model
@pytest.mark.skipif(os.getenv("DUT_RUN_MODEL_TESTS") != "1", reason="Opt-in real E5 model")
def test_real_e5_scoped_retrieval(world):
    db, users, classes, material = world
    _, _, chunk = material()
    embedder = E5Embedder()
    chunk.text = "Vòng lặp for thực hiện một khối lệnh nhiều lần."
    chunk.embedding = embedder.embed_passages([chunk.text])[0]
    result = DenseRetriever(embedder).retrieve(
        db,
        user=users[0],
        class_id=classes[0].id,
        query="Vòng lặp for là gì?",
        k=5,
    )
    assert [h.chunk_id for h in result.hits] == [chunk.id]
    assert result.top_cosine is not None and 0 < result.top_cosine <= 1
