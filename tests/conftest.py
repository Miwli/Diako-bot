import asyncio
import os
import sys

import pytest

# bot/ modules (keyboards, middlewares) use top-level imports relative to bot/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot"))

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
