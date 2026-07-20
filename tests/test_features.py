import shared_lib.db as db
from shared_lib.services import features


async def test_missing_defaults_false(db_module):
    assert await features.is_enabled("nope") is False


async def test_missing_respects_default_true(db_module):
    assert await features.is_enabled("nope", default=True) is True


async def test_enabled_when_one(db_module):
    await db.set_setting("flag_x", "1")
    assert await features.is_enabled("flag_x") is True


async def test_disabled_when_zero_ignores_default(db_module):
    await db.set_setting("flag_x", "0")
    assert await features.is_enabled("flag_x") is False
    assert await features.is_enabled("flag_x", default=True) is False


async def test_non_one_value_is_false(db_module):
    await db.set_setting("flag_x", "yes")
    assert await features.is_enabled("flag_x") is False
