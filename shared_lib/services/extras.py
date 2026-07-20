"""Extra volume / time request service — approve and reject.

Both the bot handler and the panel view drive the same request approval flow
(resolve the target service, apply the change on the panel, flip the request
status). This is the single source of truth so the two can't drift apart. No
aiogram dependency: the caller sends the user notification from the result.
"""

from dataclasses import dataclass

from shared_lib.services import provisioning
from shared_lib.db import (
    get_extra_volume_request,
    update_extra_volume_request,
    get_extra_time_request,
    update_extra_time_request,
    get_plan_with_server,
)


@dataclass
class ExtraResult:
    status: str  # ok | not_found | already_processed | plan_not_found | api_error
    user_id: int = 0  # who to notify
    traffic_gb: float = 0
    days: int = 0
    error: str = ""


async def approve_volume_request(req_id: int, actor: str = "system") -> ExtraResult:
    req = await get_extra_volume_request(req_id)
    if not req:
        return ExtraResult(status="not_found")
    if req["status"] == "approved":
        return ExtraResult(status="already_processed")
    plan = await get_plan_with_server(req["vpn_plan_id"])
    if not plan:
        return ExtraResult(status="plan_not_found")
    try:
        await provisioning.extend_volume(
            plan["panel_url"], plan["panel_token"], req["vpn_username"], req["traffic_gb"]
        )
    except Exception as e:
        return ExtraResult(status="api_error", error=str(e))
    await update_extra_volume_request(req_id, "approved")
    return ExtraResult(status="ok", user_id=req["user_id"], traffic_gb=req["traffic_gb"])


async def reject_volume_request(req_id: int, actor: str = "system") -> ExtraResult:
    req = await get_extra_volume_request(req_id)
    if not req:
        return ExtraResult(status="not_found")
    if req["status"] != "pending":
        return ExtraResult(status="already_processed")
    await update_extra_volume_request(req_id, "rejected")
    return ExtraResult(status="ok", user_id=req["user_id"])


async def approve_time_request(req_id: int, actor: str = "system") -> ExtraResult:
    req = await get_extra_time_request(req_id)
    if not req:
        return ExtraResult(status="not_found")
    if req["status"] == "approved":
        return ExtraResult(status="already_processed")
    plan = await get_plan_with_server(req["vpn_plan_id"])
    if not plan:
        return ExtraResult(status="plan_not_found")
    try:
        await provisioning.extend_time(
            plan["panel_url"], plan["panel_token"], req["vpn_username"], req["days"]
        )
    except Exception as e:
        return ExtraResult(status="api_error", error=str(e))
    await update_extra_time_request(req_id, "approved")
    return ExtraResult(status="ok", user_id=req["service_user_id"], days=req["days"])


async def reject_time_request(req_id: int, actor: str = "system") -> ExtraResult:
    req = await get_extra_time_request(req_id)
    if not req:
        return ExtraResult(status="not_found")
    if req["status"] != "pending":
        return ExtraResult(status="already_processed")
    await update_extra_time_request(req_id, "rejected")
    return ExtraResult(status="ok", user_id=req["service_user_id"])
