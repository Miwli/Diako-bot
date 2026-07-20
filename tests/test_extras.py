from unittest.mock import AsyncMock

from shared_lib.services import extras, provisioning
from helpers import (
    make_vpn_order,
    make_volume_request,
    make_time_request,
    get_extra_volume_status,
    get_extra_time_status,
)


async def test_approve_volume_ok(db_module, monkeypatch):
    order_id = await make_vpn_order()
    rid = await make_volume_request(order_id, traffic_gb=10)
    m = AsyncMock()
    monkeypatch.setattr(provisioning, "extend_volume", m)
    res = await extras.approve_volume_request(rid, actor="t")
    assert res.status == "ok"
    assert res.traffic_gb == 10
    assert await get_extra_volume_status(rid) == "approved"
    assert m.call_count == 1


async def test_approve_volume_twice_applies_once(db_module, monkeypatch):
    order_id = await make_vpn_order()
    rid = await make_volume_request(order_id)
    m = AsyncMock()
    monkeypatch.setattr(provisioning, "extend_volume", m)
    await extras.approve_volume_request(rid)
    second = await extras.approve_volume_request(rid)
    assert second.status == "already_processed"
    assert m.call_count == 1


async def test_approve_volume_api_error_keeps_pending(db_module, monkeypatch):
    order_id = await make_vpn_order()
    rid = await make_volume_request(order_id)
    monkeypatch.setattr(provisioning, "extend_volume", AsyncMock(side_effect=Exception("boom")))
    res = await extras.approve_volume_request(rid)
    assert res.status == "api_error"
    assert await get_extra_volume_status(rid) == "pending"


async def test_reject_volume(db_module):
    order_id = await make_vpn_order()
    rid = await make_volume_request(order_id)
    res = await extras.reject_volume_request(rid)
    assert res.status == "ok"
    assert await get_extra_volume_status(rid) == "rejected"


async def test_approve_time_ok(db_module, monkeypatch):
    order_id = await make_vpn_order()
    rid = await make_time_request(order_id, days=15)
    m = AsyncMock()
    monkeypatch.setattr(provisioning, "extend_time", m)
    res = await extras.approve_time_request(rid, actor="t")
    assert res.status == "ok"
    assert res.days == 15
    assert await get_extra_time_status(rid) == "approved"
    assert m.call_count == 1


async def test_approve_time_api_error_keeps_pending(db_module, monkeypatch):
    order_id = await make_vpn_order()
    rid = await make_time_request(order_id)
    monkeypatch.setattr(provisioning, "extend_time", AsyncMock(side_effect=Exception("boom")))
    res = await extras.approve_time_request(rid)
    assert res.status == "api_error"
    assert await get_extra_time_status(rid) == "pending"


async def test_reject_time(db_module):
    order_id = await make_vpn_order()
    rid = await make_time_request(order_id)
    res = await extras.reject_time_request(rid)
    assert res.status == "ok"
    assert await get_extra_time_status(rid) == "rejected"


async def test_approve_nonexistent(db_module):
    assert (await extras.approve_volume_request(999)).status == "not_found"
    assert (await extras.approve_time_request(999)).status == "not_found"
