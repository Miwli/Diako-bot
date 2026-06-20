import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from database import init_db
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def is_admin(user_id: int) -> bool:
    """چک می‌کنه آیا کاربر ادمین است یا نه"""
    return user_id in ADMIN_IDS

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
register_user_handlers(dp)
register_finance_handlers(dp)

async def main():
    logger.info("ربات در حال راه‌اندازی است...")
    await init_db()
    logger.info("دیتابیس آماده شد")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 