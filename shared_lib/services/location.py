"""Location change service — move a service between two Rebecca panels.

Recreates the user on the destination panel preserving remaining volume and
time, deletes the old user, and records the new sub link on the order. Both the
bot handler and the panel view call this same function. Returns
{"vpn_username", "subscription_url"}.
"""

import time
import json

from shared_lib.services import provisioning
from shared_lib.db import get_service_by_order, get_server, update_order_location


async def change_location(order_id: int, to_server_id: int) -> dict:
    service = await get_service_by_order(order_id)
    if not service or not service["vpn_username"]:
        raise ValueError("سرویس یا یوزرنیم VPN پیدا نشد")

    target = await get_server(to_server_id)
    if not target or not target["is_active"]:
        raise ValueError("سرور مقصد در دسترس نیست")

    service_ids = json.loads(target["service_ids"] or "[]")
    if not service_ids:
        raise ValueError("سرور مقصد سرویس پیکربندی‌شده ندارد")

    # live state from the current server — basis for remaining volume and time
    live = await provisioning.get_live_user(
        service["panel_url"], service["panel_token"], service["vpn_username"]
    )
    data_limit = live.get("data_limit") or 0
    used = live.get("used_traffic") or 0
    expire_ts = live.get("expire") or 0

    remaining_gb = 0 if data_limit == 0 else max(data_limit - used, 0) / (1024 ** 3)
    now = int(time.time())
    remaining_hours = 0 if expire_ts == 0 else max(expire_ts - now, 0) / 3600
    if expire_ts and remaining_hours == 0:
        raise ValueError("سرویس منقضی شده — قابل انتقال نیست")

    # equivalent user on the destination server — first valid panel service
    try:
        result = await provisioning.provision_service(
            target["panel_url"], target["panel_token"],
            service_ids, remaining_gb,
            duration_hours=remaining_hours,
        )
    except provisioning.NoLiveServiceError:
        raise ValueError("سرویس‌های تنظیم‌شده روی سرور مقصد در پنل موجود نیستند")
    new_username = result["username"]
    new_sub_url = result["subscription_url"]

    # remove the old user — a failure here doesn't abort the move
    try:
        await provisioning.remove_service(
            service["panel_url"], service["panel_token"], service["vpn_username"]
        )
    except Exception:
        pass

    await update_order_location(order_id, to_server_id, new_username, new_sub_url)
    return {"vpn_username": new_username, "subscription_url": new_sub_url}
