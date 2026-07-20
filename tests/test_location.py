from unittest.mock import AsyncMock

import pytest

import shared_lib.db as db
from shared_lib.services import provisioning
from shared_lib.services.location import change_location
from helpers import make_vpn_order


async def _approved_service(vpn_username="old_user"):
    order_id = await make_vpn_order()
    await db.update_order_status(order_id, "approved")
    await db.update_order_vpn_info(order_id, vpn_username, "https://old/sub")
    return order_id


async def _make_target_server():
    await db.add_server("dest", "https://dest.test", "dtok", [1])
    return (await db.get_servers(only_active=False))[-1]["id"]


async def test_change_location_moves_service(db_module, monkeypatch):
    order_id = await _approved_service()
    dest_id = await _make_target_server()

    monkeypatch.setattr(provisioning, "get_live_user",
                        AsyncMock(return_value={"data_limit": 0, "used_traffic": 0, "expire": 0}))
    monkeypatch.setattr(provisioning, "provision_service",
                        AsyncMock(return_value={"username": "new_user", "subscription_url": "https://new/sub", "raw": {}}))
    remove = AsyncMock()
    monkeypatch.setattr(provisioning, "remove_service", remove)

    result = await change_location(order_id, dest_id)
    assert result["vpn_username"] == "new_user"
    assert result["subscription_url"] == "https://new/sub"

    order = await db.get_order(order_id)
    assert order["vpn_username"] == "new_user"
    assert order["subscription_url"] == "https://new/sub"
    assert order["location_server_id"] == dest_id
    assert remove.call_count == 1  # old user removed


async def test_change_location_expired_service_blocked(db_module, monkeypatch):
    order_id = await _approved_service()
    dest_id = await _make_target_server()

    # expire in the past -> remaining time is 0 -> not transferable
    monkeypatch.setattr(provisioning, "get_live_user",
                        AsyncMock(return_value={"data_limit": 100, "used_traffic": 0, "expire": 1}))
    prov = AsyncMock()
    monkeypatch.setattr(provisioning, "provision_service", prov)

    with pytest.raises(ValueError):
        await change_location(order_id, dest_id)
    assert prov.call_count == 0  # never provisioned on the destination
