import asyncio

import pytest

import shared_lib.db as db

# real db path, grabbed before any patching, used by the sanity test
REAL_DB_PATH = db.DB_PATH


@pytest.fixture
def db_module(tmp_path, monkeypatch):
    """Fresh isolated SQLite file per test.

    Patches the module attribute directly instead of just the env var,
    since db functions read DB_PATH from this global at connect time.
    """
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", str(test_db))
    asyncio.run(db.init_db())
    return db
