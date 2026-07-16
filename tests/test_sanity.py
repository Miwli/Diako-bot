from conftest import REAL_DB_PATH


def test_db_path_is_isolated(db_module):
    # sanity check so tests never accidentally hit the real db
    assert db_module.DB_PATH != REAL_DB_PATH
    assert db_module.DB_PATH.endswith("test.db")
