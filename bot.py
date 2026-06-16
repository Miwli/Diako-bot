import asyncio
import logging  # [جدید] ماژول لاگ پایتون
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart

# [جدید] تنظیم لاگ: سطح INFO، فرمت شامل زمان + سطح + پیام
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)  # [جدید] یه logger مخصوص این فایل

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    logger.info(f"کاربر {message.from_user.id} دستور /start فرستاد")  # [جدید]
    await message.answer("سلام! به بات فروش bping خوش آمدید 🚀")

async def main():
    logger.info("ربات در حال راه‌اندازی است...")  # [جدید]
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())