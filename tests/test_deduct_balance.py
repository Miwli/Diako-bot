import asyncio

from helpers import get_balance, make_user


async def test_deduct_success(db_module):
    await make_user(1, 1000)
    ok = await db_module.deduct_balance_if_sufficient(1, 300)
    assert ok is True
    assert await get_balance(1) == 700


async def test_deduct_exact_balance(db_module):
    await make_user(1, 500)
    ok = await db_module.deduct_balance_if_sufficient(1, 500)
    assert ok is True
    assert await get_balance(1) == 0


async def test_deduct_insufficient_leaves_balance(db_module):
    await make_user(1, 100)
    ok = await db_module.deduct_balance_if_sufficient(1, 500)
    assert ok is False
    assert await get_balance(1) == 100


async def test_deduct_sequential(db_module):
    await make_user(1, 1000)
    first = await db_module.deduct_balance_if_sufficient(1, 600)
    second = await db_module.deduct_balance_if_sufficient(1, 600)
    assert first is True
    assert second is False
    assert await get_balance(1) == 400


async def test_deduct_concurrent_no_double_spend(db_module):
    # two concurrent deducts that together exceed the balance, only one should win
    await make_user(1, 1000)
    results = await asyncio.gather(
        db_module.deduct_balance_if_sufficient(1, 600),
        db_module.deduct_balance_if_sufficient(1, 600),
    )
    assert results.count(True) == 1
    assert await get_balance(1) == 400
