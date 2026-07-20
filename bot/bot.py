import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from shared_lib.db import (
    init_db, reload_texts_cache, reload_keyboards_cache, set_setting, get_setting,
    reload_admins_cache, is_bot_admin_cached, get_setting_sync, get_restart_request,
)
from handlers.admin import register_admin_handlers
from handlers.servers import register_server_handlers
from handlers.plans import register_plan_handlers
from handlers.user import register_user_handlers
from handlers.finance import register_finance_handlers
from handlers.support import register_support_handlers
from handlers.tutorial import register_tutorial_handlers
from handlers.referral import register_referral_handlers
from handlers.admin_users import register_admin_users_handlers
from handlers.broadcast import register_broadcast_handlers
from handlers.stats import register_stats_handlers
from handlers.discount import register_discount_handlers
from handlers.services import register_services_handlers
from handlers.force_join import register_force_join_handlers
from middlewares import ForceJoinMiddleware, NavHistoryMiddleware, MaintenanceMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()
# token comes from the DB (editable in the panel); .env is the bootstrap fallback
BOT_TOKEN = get_setting_sync("bot_token") or os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]

_START_TIME = time.time()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def is_admin(user_id: int) -> bool:
    """چک می‌کنه آیا کاربر ادمین است یا نه"""
    # bootstrap owners from .env, plus DB-managed bot admins (from cache)
    return user_id in ADMIN_IDS or is_bot_admin_cached(user_id)

# maintenance runs first so it takes precedence over force-join
dp.message.outer_middleware(MaintenanceMiddleware())
dp.callback_query.outer_middleware(MaintenanceMiddleware())
dp.message.outer_middleware(ForceJoinMiddleware())
dp.callback_query.outer_middleware(ForceJoinMiddleware())
# تاریخچه‌ی ناوبری برای دکمه‌ی «یک مرحله عقب» — بعد از جوین اجباری اجرا می‌شه
dp.callback_query.outer_middleware(NavHistoryMiddleware())

# ثبت هندلرها
register_admin_handlers(dp)
register_server_handlers(dp)
register_plan_handlers(dp)
register_support_handlers(dp)
register_tutorial_handlers(dp)
register_referral_handlers(dp)
register_admin_users_handlers(dp)
register_broadcast_handlers(dp)
register_stats_handlers(dp)
register_discount_handlers(dp)
register_services_handlers(dp)
register_user_handlers(dp)
register_finance_handlers(dp)
register_force_join_handlers(dp)

async def _texts_refresh_loop():
    while True:
        await asyncio.sleep(10)
        await reload_texts_cache()
        await reload_keyboards_cache()
        await reload_admins_cache()


async def _heartbeat_loop():
    try:
        me = await bot.get_me()
        await set_setting("bot_username", me.username or "")
    except Exception:
        pass
    while True:
        try:
            await set_setting("bot_heartbeat", datetime.now(timezone.utc).isoformat())
        except Exception:
            pass
        await asyncio.sleep(60)


async def _control_loop():
    # exit when a restart newer than our start time is requested; the container
    # restart policy brings us back with the fresh token/config
    while True:
        await asyncio.sleep(5)
        try:
            if await get_restart_request("bot") > _START_TIME:
                logger.info("restart requested, exiting")
                if os.environ.get("ENABLE_SELF_RESTART") == "1":
                    os._exit(0)
        except Exception:
            pass


async def main():
    logger.info("ربات در حال راه‌اندازی است...")
    await init_db()
    logger.info("دیتابیس آماده شد")
    # seed the token into the DB on first run so the panel can show/edit it
    if not await get_setting("bot_token") and os.getenv("BOT_TOKEN"):
        await set_setting("bot_token", os.getenv("BOT_TOKEN"))
    asyncio.create_task(_texts_refresh_loop())
    asyncio.create_task(_heartbeat_loop())
    asyncio.create_task(_control_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 