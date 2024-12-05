from typing import Generator

import pytest
from starlette.testclient import TestClient

from src.deps import get_db

pytest_plugins = [
    "tests.fixtures.db",
    "tests.fixtures.menu",
    "tests.fixtures.client",
]


@pytest.fixture
def app(redis_client) -> Generator["FastAPI", None, None]:
    from src.app import create_app

    app = create_app()
    yield app


@pytest.fixture
def client(app, db_session) -> Generator["TestClient", None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client

    del app.dependency_overrides[get_db]
