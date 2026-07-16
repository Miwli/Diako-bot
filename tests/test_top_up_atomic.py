import asyncio

from helpers import get_top_up_status, make_top_up


async def test_approve_pending(db_module):
    rid = await make_top_up()
    ok = await db_module.approve_top_up_atomic(rid)
    assert ok is True
    assert await get_top_up_status(rid) == "approved"


async def test_approve_twice_no_double_credit(db_module):
    rid = await make_top_up()
    first = await db_module.approve_top_up_atomic(rid)
    second = await db_module.approve_top_up_atomic(rid)
    assert first is True
    assert second is False


async def test_approve_nonexistent(db_module):
    ok = await db_module.approve_top_up_atomic(9999)
    assert ok is False


async def test_approve_concurrent_only_one_wins(db_module):
    # two concurrent approvals on the same request, only one should return True
    rid = await make_top_up()
    results = await asyncio.gather(
        db_module.approve_top_up_atomic(rid),
        db_module.approve_top_up_atomic(rid),
    )
    assert results.count(True) == 1
    assert await get_top_up_status(rid) == "approved"
