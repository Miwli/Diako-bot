import asyncio
import logging  # ماژول لاگ 
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types , F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from states import AddPlan, AddServer
from database import add_plan, add_server, get_plan_by_name, get_servers, init_db
from keyboards import admin_main_menu, admin_panel_menu, admin_plans_menu, admin_servers_menu, servers_list_keyboard


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
        await message.answer("سلام! 👋 به bping خوش اومدی 🚀")

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "⚙️ پنل ادمین",
        reply_markup=admin_panel_menu()        
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🏠 دوباره اومدی صفحه اصلی!",
        reply_markup=admin_main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_plans")
async def admin_plans(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📦 مدیریت پلن‌ها",
        reply_markup=admin_plans_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_servers")
async def admin_servers(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🖥 مدیریت سرورها",
        reply_markup=admin_servers_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "add_server")
async def add_server_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🖥 اسم سرور رو بفرست:\n\nمثلاً: سرور آلمان 🇩🇪")
    await state.set_state(AddServer.waiting_for_name)
    await callback.answer()

@dp.message(AddServer.waiting_for_name)
async def add_server_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("🔗 آدرس پنل رو بفرست:\n\nمثلاً: https://rebeccapanel.com:8880")
    await state.set_state(AddServer.waiting_for_url)

@dp.message(AddServer.waiting_for_url)
async def add_server_url(message: types.Message, state: FSMContext):
    import re
    url = message.text.strip()
    pattern = r'^https?://[^\s/]+:\d+$'
    if not re.match(pattern, url):
        await message.answer(
            "❌ <b>آدرس وارد شده معتبر نیست!</b>\n\n"
            "لطفاً دوباره با فرمت زیر وارد کن:\n\n"
            "فرمت: <code>https://domain.com:PORT</code>\n"
            "مثال: <code>https://rebeccapanel.com:8880</code>",
            parse_mode="HTML"
        )
        return
    await state.update_data(panel_url=url)
    await message.answer("🔑 توکن API پنل رو بفرست:")
    await state.set_state(AddServer.waiting_for_token)

@dp.message(AddServer.waiting_for_token)
async def add_server_token(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await add_server(
        name=data["name"],
        panel_url=data["panel_url"],
        panel_token=message.text
    )
    await state.clear()
    await message.answer(
        "✅ سرور با موفقیت اضافه شد!",
        reply_markup=admin_servers_menu()
    )

@dp.callback_query(F.data == "add_plan")
async def add_plan_start(callback: types.CallbackQuery, state: FSMContext):
    servers = await get_servers()
    if not servers:
        await callback.message.edit_text(
            "❌ هیچ سروری ثبت نشده!\nاول از بخش مدیریت سرورها یه سرور اضافه کن.",
            reply_markup=admin_plans_menu()
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        "🖥 سرور مورد نظر رو انتخاب کن:",
        reply_markup=servers_list_keyboard(servers)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("select_server_"))
async def select_server(callback: types.CallbackQuery, state: FSMContext):
    server_id = int(callback.data.replace("select_server_", ""))
    await state.update_data(server_id=server_id)
    await callback.message.edit_text("📝 اسم پلن رو بفرست:")
    await state.set_state(AddPlan.waiting_for_name)
    await callback.answer()

@dp.message(AddPlan.waiting_for_name)
async def add_plan_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("💰 قیمت رو بفرست (تومان):")
    await state.set_state(AddPlan.waiting_for_price)

@dp.message(AddPlan.waiting_for_price)
async def add_plan_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ قیمت باید عدد باشه! دوباره بفرست:")
        return
    await state.update_data(price=int(message.text))
    await message.answer("📅 مدت رو بفرست (روز):")
    await state.set_state(AddPlan.waiting_for_duration)

@dp.message(AddPlan.waiting_for_duration)
async def add_plan_duration(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ مدت باید عدد باشه! دوباره بفرست:")
        return
    await state.update_data(duration=int(message.text))
    await message.answer("📊 حجم رو بفرست (گیگابایت):")
    await state.set_state(AddPlan.waiting_for_traffic)

@dp.message(AddPlan.waiting_for_traffic)
async def add_plan_traffic(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ حجم باید عدد باشه! دوباره بفرست:")
        return
    data = await state.get_data()
    await add_plan(
        server_id=data["server_id"],
        name=data["name"],
        price=data["price"],
        duration=data["duration"],
        traffic=int(message.text),
        
    )
    await state.clear()
    await message.answer(
        "✅ پلن با موفقیت اضافه شد!",
        reply_markup=admin_plans_menu()
    )
    

async def main():
    logger.info("ربات در حال راه‌اندازی است...")  # LOG START
    await init_db() # ساخت جدول های دیتابیس
    logger.info("دیتابیس اماده شد")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())