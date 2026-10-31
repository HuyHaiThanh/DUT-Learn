import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from alembic import command
from app.db import get_db
from app.main import app


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    url = os.environ.get("DUT_TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set DUT_TEST_DATABASE_URL to a dedicated PostgreSQL test database")
    parsed = make_url(url)
    if not parsed.database or not parsed.database.endswith("_test"):
        pytest.fail("DUT_TEST_DATABASE_URL must target a database ending in _test")
    schema = "test_" + uuid4().hex
    admin = create_engine(url, connect_args={"connect_timeout": 2})
    with admin.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema},public"})
    try:
        with engine.begin() as connection:
            config = Config("alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def db_client(test_engine: Engine) -> Iterator[TestClient]:
    def override_db() -> Iterator[Session]:
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client
