"""
Shared pytest fixtures.

Placing conftest.py at the Backend root puts Backend on sys.path (pytest
prepend import mode), so tests can `import main`, `from ml import ...`, etc.
The `client` fixture points the DB at a throwaway temp file so tests never
touch the real poseguide.db, and resets runtime state for isolation.
"""

import pytest
from fastapi.testclient import TestClient

import database
import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_poseguide.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    database._conn = None          # force a fresh connection to the temp DB
    main.reset_state()             # clear runtime state (counts, model, cache)
    with TestClient(main.app) as c:
        yield c
    database._conn = None
