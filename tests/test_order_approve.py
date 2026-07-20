from unittest.mock import AsyncMock

import shared_lib.db as db
from shared_lib.services import orders, provisioning
from helpers import make_vpn_order, get_order_status


def _fake_provision(username="bp_test", url="https://sub/x"):
    return AsyncMock(return_value={"username": username, "subscription_url": url, "raw": {}})


async def test_approve_success(db_module, monkeypatch):
    order_id = await make_vpn_order()
    monkeypatch.setattr(provisioning, "provision_service", _fake_provision())
    res = await orders.approve(order_id, actor="test")
    assert res.status == "ok"
    assert res.username == "bp_test"
    assert res.subscription_url == "https://sub/x"
    assert await get_order_status(order_id) == "approved"
    order = await db.get_order(order_id)
    assert order["vpn_username"] == "bp_test"
    assert order["subscription_url"] == "https://sub/x"


async def test_approve_twice_no_double_provision(db_module, monkeypatch):
    order_id = await make_vpn_order()
    mock = _fake_provision()
    monkeypatch.setattr(provisioning, "provision_service", mock)
    first = await orders.approve(order_id, actor="test")
    second = await orders.approve(order_id, actor="test")
    assert first.status == "ok"
    assert second.status == "already_processed"
    assert mock.call_count == 1  # the already-approved order is not re-provisioned


async def test_approve_api_error_leaves_order_pending(db_module, monkeypatch):
    order_id = await make_vpn_order()
    monkeypatch.setattr(
        provisioning, "provision_service", AsyncMock(side_effect=Exception("panel down"))
    )
    res = await orders.approve(order_id, actor="test")
    assert res.status == "api_error"
    assert "panel down" in res.error
    assert await get_order_status(order_id) == "pending"


async def test_approve_no_live_service_leaves_order_pending(db_module, monkeypatch):
    order_id = await make_vpn_order()
    monkeypatch.setattr(
        provisioning, "provision_service",
        AsyncMock(side_effect=provisioning.NoLiveServiceError()),
    )
    res = await orders.approve(order_id, actor="test")
    assert res.status == "no_live_service"
    assert await get_order_status(order_id) == "pending"


async def test_approve_nonexistent(db_module):
    res = await orders.approve(9999, actor="test")
    assert res.status == "not_found"


async def test_reject_pending(db_module):
    order_id = await make_vpn_order()
    res = await orders.reject(order_id, actor="test", reason="bad receipt")
    assert res.status == "ok"
    assert res.user_id == 1
    assert await get_order_status(order_id) == "rejected"


async def test_reject_twice(db_module):
    order_id = await make_vpn_order()
    first = await orders.reject(order_id, actor="test")
    second = await orders.reject(order_id, actor="test")
    assert first.status == "ok"
    assert second.status == "already_processed"
