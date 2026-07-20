from unittest.mock import AsyncMock

import shared_lib.db as db
from shared_lib.services import orders, provisioning
from helpers import make_user, make_plan_row, get_balance


def _fake_provision(username="bp_u", url="https://sub/u"):
    return AsyncMock(return_value={"username": username, "subscription_url": url, "raw": {}})


async def test_wallet_purchase_success(db_module, monkeypatch):
    await make_user(1, 20000)
    plan = await make_plan_row(price=10000)
    monkeypatch.setattr(provisioning, "provision_service", _fake_provision())
    res = await orders.fulfill(
        plan, 1, "u", order_type="wallet", final_price=10000,
        charge_wallet=True, verify_live=False,
    )
    assert res.status == "ok"
    assert res.username == "bp_u"
    assert await get_balance(1) == 10000  # 20000 - 10000
    order = await db.get_order(res.order_id)
    assert order["status"] == "approved"
    assert order["vpn_username"] == "bp_u"


async def test_wallet_insufficient_balance_no_provision(db_module, monkeypatch):
    await make_user(1, 5000)
    plan = await make_plan_row(price=10000)
    m = _fake_provision()
    monkeypatch.setattr(provisioning, "provision_service", m)
    res = await orders.fulfill(
        plan, 1, "u", order_type="wallet", final_price=10000,
        charge_wallet=True, verify_live=False,
    )
    assert res.status == "no_balance"
    assert await get_balance(1) == 5000  # untouched
    assert m.call_count == 0


async def test_wallet_api_error_refunds(db_module, monkeypatch):
    await make_user(1, 20000)
    plan = await make_plan_row(price=10000)
    monkeypatch.setattr(provisioning, "provision_service", AsyncMock(side_effect=Exception("down")))
    res = await orders.fulfill(
        plan, 1, "u", order_type="wallet", final_price=10000,
        charge_wallet=True, verify_live=False,
    )
    assert res.status == "api_error"
    assert await get_balance(1) == 20000  # charge rolled back


async def test_wallet_save_error_refunds_and_removes(db_module, monkeypatch):
    await make_user(1, 20000)
    plan = await make_plan_row(price=10000)
    monkeypatch.setattr(provisioning, "provision_service", _fake_provision())
    remove = AsyncMock()
    monkeypatch.setattr(provisioning, "remove_service", remove)
    monkeypatch.setattr(orders, "create_order", AsyncMock(side_effect=Exception("db fail")))
    res = await orders.fulfill(
        plan, 1, "u", order_type="wallet", final_price=10000,
        charge_wallet=True, verify_live=False,
    )
    assert res.status == "save_error"
    assert await get_balance(1) == 20000  # refunded
    assert remove.call_count == 1  # orphan panel user removed


async def test_discount_free_no_charge(db_module, monkeypatch):
    await make_user(1, 0)
    plan = await make_plan_row(price=10000)
    monkeypatch.setattr(provisioning, "provision_service", _fake_provision())
    res = await orders.fulfill(
        plan, 1, "u", order_type="discount_free", final_price=0,
        charge_wallet=False, verify_live=True,
    )
    assert res.status == "ok"
    assert await get_balance(1) == 0  # nothing charged
    order = await db.get_order(res.order_id)
    assert order["status"] == "approved"


async def test_no_service_config_no_charge(db_module, monkeypatch):
    await make_user(1, 20000)
    plan = await make_plan_row(price=10000, service_ids=[])
    m = _fake_provision()
    monkeypatch.setattr(provisioning, "provision_service", m)
    res = await orders.fulfill(
        plan, 1, "u", order_type="wallet", final_price=10000,
        charge_wallet=True, verify_live=False,
    )
    assert res.status == "no_service_config"
    assert await get_balance(1) == 20000  # not charged
    assert m.call_count == 0
