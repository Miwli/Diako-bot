"""Feature flags — boolean settings read from the settings table.

Gate a feature behind a flag so it can be toggled from the panel without a code
change. A flag is on when its setting value is exactly "1"; a missing setting
falls back to the given default.
"""

from shared_lib.db import get_setting


async def is_enabled(key: str, *, default: bool = False) -> bool:
    """True when the setting `key` is turned on ("1"). Missing -> default."""
    val = await get_setting(key)
    if val is None:
        return default
    return val == "1"
