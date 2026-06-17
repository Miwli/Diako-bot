from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import AddPlan
from keyboards import admin_plans_menu, servers_list_keyboard
from database import add_plan, get_servers

def register_plan_handlers(dp):

    @dp.callback_query(F.data == "admin_plans")
    async def admin_plans(callback: types.CallbackQuery):
        await callback.message.edit_text(
            "📦 مدیریت پلن‌ها",
            reply_markup=admin_plans_menu()
        )
        await callback.answer()

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
            traffic=int(message.text)
        )
        await state.clear()
        await message.answer(
            "✅ پلن با موفقیت اضافه شد!",
            reply_markup=admin_plans_menu()
        )