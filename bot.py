import asyncio
import logging  # ماژول لاگ 
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types , F
from aiogram.filters import CommandStart
from database import init_db
from keyboards import admin_main_menu
from keyboards import admin_panel_menu

#  تنظیم لاگ: سطح اینفو ، فرمت شامل زمان + سطح + پیام
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)  #  یه logger مخصوص این فایل

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = [int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip()]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def is_admin(user_id: int) -> bool:
    """چک می‌کنه آیا کاربر ادمین است یا نه"""
    return user_id in ADMIN_IDS

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    logger.info(f"کاربر {message.from_user.id} دستور /start فرستاد")

    if is_admin(message.from_user.id):
        await message.answer(
            "سلام ادمین! 👋",
            reply_markup=admin_main_menu()
        )
    else:
        await message.answer("سلام! به بات فروش bping خوش آمدید 🚀")

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "⚙️ پنل ادمین",
        reply_markup=admin_panel_menu()        
    )
    await callback.answer

async def main():
    logger.info("ربات در حال راه‌اندازی است...")  # LOG START
    await init_db() # ساخت جدول های دیتابیس
    logger.info("دیتابیس اماده شد")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())