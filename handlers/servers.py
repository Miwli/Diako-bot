from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import AddServer
from keyboards import admin_servers_menu, back_to_servers_menu
from database import add_server, get_servers
import re

def register_server_handlers(dp):

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
    
    @dp.callback_query(F.data == "list_servers")
    async def list_servers(callback: types.CallbackQuery):
        servers = await get_servers(only_active=False)
        if not servers:
            await callback.message.edit_text(
                "❌ هیچ سروری ثبت نشده!",
                reply_markup=back_to_servers_menu(),
            )
            await callback.answer()
            return
        text = "🖥 <b>لیست سرورها:</b>\n\n"
        for server in servers:
            status = "✅" if server["is_active"] else "❌"
            text += (
                f"{status} <b>{server['name']}</b>\n"
                f"🔗 {server['panel_url']}\n\n"
            )
        await callback.message.edit_text(
            text,
            reply_markup=admin_servers_menu(),
            parse_mode="HTML"
        )
        await callback.answer()