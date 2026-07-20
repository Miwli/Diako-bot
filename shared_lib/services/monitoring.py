"""Monitoring service — read-only panel health and stats calls.

The seam for server-monitoring panel calls (system stats, nodes, liveness), kept
apart from provisioning so multi-panel can later dispatch these per panel type.
Presentation of the results (geo lookup, status mapping) stays in the panel.
"""

import aiohttp

from shared_lib.rebecca_api import RebeccaAPI


async def get_system_stats(panel_url: str, token: str) -> dict:
    """Overall panel stats — users, bandwidth, CPU and RAM."""
    return await RebeccaAPI(panel_url, token).get_system_stats()


async def get_nodes(panel_url: str, token: str) -> list:
    """Panel nodes with each one's connection status."""
    return await RebeccaAPI(panel_url, token).get_nodes()


async def ping_admin(panel_url: str, token: str, timeout: int = 6):
    """HTTP status of /api/admin (liveness fallback for panels without
    /api/system), or None if unreachable."""
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(
            panel_url.rstrip("/") + "/api/admin",
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as resp:
            await resp.read()
            return resp.status
