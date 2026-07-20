"""Provisioning service — the single seam between the app and the VPN panel.

All panel (Rebecca) calls go through here so handlers and panel views never
talk to RebeccaAPI directly. This is the place a multi-panel factory will later
swap RebeccaAPI for another panel client (phase F).

Functions do not swallow errors: the panel client raises on API failure and
callers keep their own error handling. The one shaped exception is
NoLiveServiceError, so callers can tell "no matching live service" apart from a
generic API error and show their existing message.
"""

from shared_lib.rebecca_api import RebeccaAPI


class NoLiveServiceError(Exception):
    """None of the candidate service ids exist in the panel right now."""


def _api(panel_url: str, token: str) -> RebeccaAPI:
    return RebeccaAPI(panel_url, token)


async def provision_service(
    panel_url: str,
    token: str,
    service_ids: list,
    traffic_gb: float,
    *,
    duration_days: float = 0,
    duration_hours: float = 0,
    ip_limit: int = 0,
    verify_live: bool = True,
) -> dict:
    """Create a panel user and return {username, subscription_url, raw}.

    verify_live=True fetches the panel's live services and picks the first
    candidate id that still exists (raising NoLiveServiceError if none do).
    verify_live=False uses service_ids[0] directly (wallet purchase path).
    """
    api = _api(panel_url, token)

    if verify_live:
        live = await api.get_services()
        live_ids = {s["id"] for s in live}
        service_id = next((sid for sid in service_ids if sid in live_ids), None)
        if service_id is None:
            raise NoLiveServiceError()
    else:
        service_id = service_ids[0]

    raw = await api.create_user(
        service_id=service_id,
        data_limit_gb=traffic_gb,
        duration_days=duration_days,
        duration_hours=duration_hours,
        ip_limit=ip_limit,
    )
    sub_path = raw.get("subscription_url", "")
    subscription_url = await api.get_subscription_url(sub_path)
    return {
        "username": raw.get("username", ""),
        "subscription_url": subscription_url,
        "raw": raw,
    }


async def list_services(panel_url: str, token: str) -> list:
    """Services defined in the panel (used when configuring a server)."""
    return await _api(panel_url, token).get_services()


async def get_live_user(panel_url: str, token: str, username: str) -> dict:
    """Live user info from the panel (status, traffic, expiry)."""
    return await _api(panel_url, token).get_user(username)


async def remove_service(panel_url: str, token: str, username: str) -> None:
    """Delete a user from the panel."""
    await _api(panel_url, token).delete_user(username)


async def extend_volume(panel_url: str, token: str, username: str, extra_gb: float) -> dict:
    """Add data volume to an existing user."""
    return await _api(panel_url, token).add_volume(username, extra_gb)


async def extend_time(panel_url: str, token: str, username: str, extra_days: int) -> dict:
    """Add time to an existing user."""
    return await _api(panel_url, token).add_time(username, extra_days)


async def set_status(panel_url: str, token: str, username: str, active: bool) -> dict:
    """Enable or disable a user."""
    return await _api(panel_url, token).toggle_status(username, active)
