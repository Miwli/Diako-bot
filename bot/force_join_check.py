from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from shared_lib.db import get_required_channels


async def get_missing_channels(bot, user_id: int) -> list:
    """کانال‌هایی که کاربر هنوز عضوشون نیست رو برمی‌گردونه"""
    channels = await get_required_channels(active_only=True)
    missing = []
    for ch in channels:
        chat_id = ch["chat_id"]
        if not ch["invite_link"] and not chat_id.startswith("@"):
            # لینکی برای جوین نیست، پس نمی‌تونیم ازش بخوایم
            continue
        try:
            member = await bot.get_chat_member(ch["chat_id"], user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except (TelegramBadRequest, TelegramForbiddenError):
            # ربات به این کانال دسترسی نداره
            continue
    return missing
