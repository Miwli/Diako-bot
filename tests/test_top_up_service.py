import asyncio

from shared_lib.services import wallet
from helpers import make_top_up, make_user, get_balance, get_top_up_status


async def test_approve_credits_balance(db_module):
    await make_user(1, 0)
    rid = await make_top_up(user_id=1, amount=500)
    res = await wallet.approve_top_up(rid, actor="test")
    assert res.status == "ok"
    assert res.amount == 500
    assert await get_balance(1) == 500
    assert await get_top_up_status(rid) == "approved"


async def test_approve_twice_no_double_credit(db_module):
    await make_user(1, 0)
    rid = await make_top_up(user_id=1, amount=500)
    first = await wallet.approve_top_up(rid, actor="test")
    second = await wallet.approve_top_up(rid, actor="test")
    assert first.status == "ok"
    assert second.status == "already_processed"
    assert await get_balance(1) == 500  # credited exactly once


async def test_approve_concurrent_credits_once(db_module):
    await make_user(1, 0)
    rid = await make_top_up(user_id=1, amount=500)
    results = await asyncio.gather(
        wallet.approve_top_up(rid),
        wallet.approve_top_up(rid),
    )
    statuses = [r.status for r in results]
    assert statuses.count("ok") == 1
    assert statuses.count("already_processed") == 1
    assert await get_balance(1) == 500


async def test_approve_nonexistent(db_module):
    res = await wallet.approve_top_up(9999, actor="test")
    assert res.status == "not_found"


async def test_reject_pending(db_module):
    rid = await make_top_up(user_id=1, amount=500)
    res = await wallet.reject_top_up(rid, actor="test")
    assert res.status == "ok"
    assert res.user_id == 1
    assert await get_top_up_status(rid) == "rejected"


async def test_reject_twice(db_module):
    rid = await make_top_up(user_id=1, amount=500)
    first = await wallet.reject_top_up(rid)
    second = await wallet.reject_top_up(rid)
    assert first.status == "ok"
    assert second.status == "already_processed"


async def test_reject_after_approve_is_blocked(db_module):
    await make_user(1, 0)
    rid = await make_top_up(user_id=1, amount=500)
    await wallet.approve_top_up(rid)
    res = await wallet.reject_top_up(rid)
    assert res.status == "already_processed"
    assert await get_balance(1) == 500
