from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import AddPlan, EditPlan
from keyboards import (
    admin_plans_menu, servers_list_keyboard, cancel_keyboard,
    plans_table_keyboard, plan_settings_keyboard,
    confirm_delete_plan_keyboard
)
from database import (
    add_plan, get_servers, get_plans, get_plan,
    delete_plan, toggle_plan_status, get_setting, set_setting, update_plan_field
)

def _fmt_dur(val) -> str:
    return "♾️ بی‌نهایت" if int(val) == 0 else f"{val} روز"

def _fmt_trf(val) -> str:
    return "♾️ بی‌نهایت" if int(val) == 0 else f"{val} گیگابایت"

def register_plan_handlers(dp):

    @dp.callback_query(F.data == "admin_plans")
    async def admin_plans(callback: types.CallbackQuery):
        show_price = (await get_setting("show_plan_price")) == "1"
        await callback.message.edit_text(
            "📦 مدیریت پلن‌ها",
            reply_markup=admin_plans_menu(show_price)
        )
        await callback.answer()

    @dp.callback_query(F.data == "toggle_show_price")
    async def toggle_show_price(callback: types.CallbackQuery):
        current = await get_setting("show_plan_price")
        new_value = "0" if current == "1" else "1"
        await set_setting("show_plan_price", new_value)
        show_price = new_value == "1"
        await callback.message.edit_reply_markup(reply_markup=admin_plans_menu(show_price))
        status = "روشن" if show_price else "خاموش"
        await callback.answer(f"نمایش قیمت {status} شد.")

    # ─── اضافه کردن پلن ──────────────────────────

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
        await callback.message.edit_text(
            "📝 اسم پلن رو بفرست:",
            reply_markup=cancel_keyboard()
        )
        await state.set_state(AddPlan.waiting_for_name)
        await callback.answer()

    @dp.message(AddPlan.waiting_for_name)
    async def add_plan_name(message: types.Message, state: FSMContext):
        await state.update_data(name=message.text)
        await message.answer("💰 قیمت رو بفرست (تومان):", reply_markup=cancel_keyboard())
        await state.set_state(AddPlan.waiting_for_price)

    @dp.message(AddPlan.waiting_for_price)
    async def add_plan_price(message: types.Message, state: FSMContext):
        if not message.text.isdigit():
            await message.answer("❌ قیمت باید عدد باشه! دوباره بفرست:")
            return
        await state.update_data(price=int(message.text))
        await message.answer("📅 مدت رو بفرست (روز):\n<i>برای بی‌نهایت عدد 0 وارد کن</i>", reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(AddPlan.waiting_for_duration)

    @dp.message(AddPlan.waiting_for_duration)
    async def add_plan_duration(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 0:
            await message.answer("❌ عدد صحیح وارد کن. مثال: 30 یا 0 برای بی‌نهایت")
            return
        await state.update_data(duration=int(raw))
        await message.answer("📊 حجم رو بفرست (گیگابایت):\n<i>برای بی‌نهایت عدد 0 وارد کن</i>", reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(AddPlan.waiting_for_traffic)

    @dp.message(AddPlan.waiting_for_traffic)
    async def add_plan_traffic(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 0:
            await message.answer("❌ عدد صحیح وارد کن. مثال: 50 یا 0 برای بی‌نهایت")
            return
        data = await state.get_data()
        await add_plan(
            server_id=data["server_id"],
            name=data["name"],
            price=data["price"],
            duration=data["duration"],
            traffic=int(raw)
        )
        await state.clear()
        await message.answer("✅ پلن با موفقیت اضافه شد!", reply_markup=admin_plans_menu())

    # ─── لیست پلن‌ها ─────────────────────────────

    @dp.callback_query(F.data == "list_plans")
    async def list_plans(callback: types.CallbackQuery):
        servers = await get_servers()
        if not servers:
            await callback.message.edit_text(
                "❌ هیچ سروری ثبت نشده!",
                reply_markup=admin_plans_menu()
            )
            await callback.answer()
            return
        await callback.message.edit_text(
            "🖥 برای دیدن پلن‌ها، سرور رو انتخاب کن:",
            reply_markup=servers_list_keyboard(servers, mode="view_plans")
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("view_plans_"))
    async def view_plans(callback: types.CallbackQuery):
        server_id = int(callback.data.replace("view_plans_", ""))
        plans = await get_plans(server_id, only_active=False)
        if not plans:
            await callback.message.edit_text(
                "❌ هیچ پلنی برای این سرور ثبت نشده!",
                reply_markup=admin_plans_menu()
            )
            await callback.answer()
            return
        await callback.message.edit_text(
            "📦 <b>لیست پلن‌ها</b>\n\n"
            "💡 برای تنظیمات پلن روی اسمش کلیک کن.",
            reply_markup=plans_table_keyboard(plans, server_id),
            parse_mode="HTML"
        )
        await callback.answer()

    # ─── تنظیمات پلن ─────────────────────────────

    @dp.callback_query(F.data.startswith("plan_settings_"))
    async def plan_settings(callback: types.CallbackQuery):
        parts = callback.data.replace("plan_settings_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        plan = await get_plan(plan_id)
        status = "✅ فعال" if plan["is_active"] else "❌ غیرفعال"
        await callback.message.edit_text(
            f"⚙️ <b>تنظیمات پلن</b>\n"
            f"{'─' * 24}\n"
            f"📦 <b>{plan['name']}</b>\n"
            f"📊 حجم: {_fmt_trf(plan['traffic'])}\n"
            f"📅 مدت: {_fmt_dur(plan['duration'])}\n"
            f"💰 قیمت: {plan['price']:,} تومان\n"
            f"📌 وضعیت: {status}",
            reply_markup=plan_settings_keyboard(plan_id, server_id, plan["is_active"]),
            parse_mode="HTML"
        )
        await callback.answer()

    # ─── ویرایش فیلدهای پلن از جدول ──────────────

    @dp.callback_query(F.data.startswith("edit_plan_price_"))
    async def edit_plan_price_start(callback: types.CallbackQuery, state: FSMContext):
        parts = callback.data.replace("edit_plan_price_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        plan = await get_plan(plan_id)
        await state.update_data(plan_id=plan_id, server_id=server_id)
        await state.set_state(EditPlan.waiting_for_price)
        await callback.message.edit_text(
            f"💰 قیمت فعلی پلن <b>{plan['name']}</b>: {plan['price']:,} تومان\n\n"
            "قیمت جدید را به <b>تومان</b> وارد کنید:",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(EditPlan.waiting_for_price)
    async def edit_plan_price_save(message: types.Message, state: FSMContext):
        raw = message.text.strip().replace(",", "").replace("،", "")
        if not raw.isdigit() or int(raw) < 1000:
            await message.answer("❌ قیمت معتبر نیست. حداقل ۱,۰۰۰ تومان وارد کنید.")
            return
        data = await state.get_data()
        await update_plan_field(data["plan_id"], "price", int(raw))
        await state.clear()
        plans = await get_plans(data["server_id"], only_active=False)
        await message.answer(
            "✅ قیمت بروزرسانی شد.\n\n"
            "📦 <b>لیست پلن‌ها</b>\n\n"
            "💡 برای ویرایش روز، حجم یا قیمت روی مقدار مربوطه کلیک کنید.",
            reply_markup=plans_table_keyboard(plans, data["server_id"]),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data.startswith("edit_plan_duration_"))
    async def edit_plan_duration_start(callback: types.CallbackQuery, state: FSMContext):
        parts = callback.data.replace("edit_plan_duration_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        plan = await get_plan(plan_id)
        await state.update_data(plan_id=plan_id, server_id=server_id)
        await state.set_state(EditPlan.waiting_for_duration)
        await callback.message.edit_text(
            f"📅 مدت فعلی پلن <b>{plan['name']}</b>: {_fmt_dur(plan['duration'])}\n\n"
            "مدت جدید را به <b>روز</b> وارد کنید:\n"
            "<i>برای بی‌نهایت عدد 0 وارد کنید</i>",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(EditPlan.waiting_for_duration)
    async def edit_plan_duration_save(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 0:
            await message.answer("❌ عدد صحیح وارد کنید. مثال: 30 یا 0 برای بی‌نهایت")
            return
        data = await state.get_data()
        await update_plan_field(data["plan_id"], "duration", int(raw))
        await state.clear()
        plans = await get_plans(data["server_id"], only_active=False)
        await message.answer(
            "✅ مدت بروزرسانی شد.\n\n"
            "📦 <b>لیست پلن‌ها</b>\n\n"
            "💡 برای ویرایش روز، حجم یا قیمت روی مقدار مربوطه کلیک کنید.",
            reply_markup=plans_table_keyboard(plans, data["server_id"]),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data.startswith("edit_plan_traffic_"))
    async def edit_plan_traffic_start(callback: types.CallbackQuery, state: FSMContext):
        parts = callback.data.replace("edit_plan_traffic_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        plan = await get_plan(plan_id)
        await state.update_data(plan_id=plan_id, server_id=server_id)
        await state.set_state(EditPlan.waiting_for_traffic)
        await callback.message.edit_text(
            f"📊 حجم فعلی پلن <b>{plan['name']}</b>: {_fmt_trf(plan['traffic'])}\n\n"
            "حجم جدید را به <b>گیگابایت</b> وارد کنید:\n"
            "<i>برای بی‌نهایت عدد 0 وارد کنید</i>",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(EditPlan.waiting_for_traffic)
    async def edit_plan_traffic_save(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 0:
            await message.answer("❌ عدد صحیح وارد کنید. مثال: 50 یا 0 برای بی‌نهایت")
            return
        data = await state.get_data()
        await update_plan_field(data["plan_id"], "traffic", int(raw))
        await state.clear()
        plans = await get_plans(data["server_id"], only_active=False)
        await message.answer(
            "✅ حجم بروزرسانی شد.\n\n"
            "📦 <b>لیست پلن‌ها</b>\n\n"
            "💡 برای ویرایش روز، حجم یا قیمت روی مقدار مربوطه کلیک کنید.",
            reply_markup=plans_table_keyboard(plans, data["server_id"]),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data.startswith("toggle_plan_") & ~F.data.startswith("toggle_plan_settings_"))
    async def toggle_plan(callback: types.CallbackQuery):
        """toggle از لیست پلن‌ها — جدول رو رفرش می‌کنه"""
        parts = callback.data.replace("toggle_plan_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        await toggle_plan_status(plan_id)
        plans = await get_plans(server_id, only_active=False)
        await callback.message.edit_reply_markup(
            reply_markup=plans_table_keyboard(plans, server_id)
        )
        await callback.answer("وضعیت پلن تغییر کرد.")

    @dp.callback_query(F.data.startswith("toggle_plan_settings_"))
    async def toggle_plan_from_settings(callback: types.CallbackQuery):
        """toggle از صفحه تنظیمات پلن — صفحه تنظیمات رو رفرش می‌کنه"""
        parts = callback.data.replace("toggle_plan_settings_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        await toggle_plan_status(plan_id)
        plan = await get_plan(plan_id)
        status = "✅ فعال" if plan["is_active"] else "❌ غیرفعال"
        await callback.message.edit_text(
            f"⚙️ <b>تنظیمات پلن</b>\n"
            f"{'─' * 24}\n"
            f"📦 <b>{plan['name']}</b>\n"
            f"📊 حجم: {_fmt_trf(plan['traffic'])}\n"
            f"📅 مدت: {_fmt_dur(plan['duration'])}\n"
            f"💰 قیمت: {plan['price']:,} تومان\n"
            f"📌 وضعیت: {status}",
            reply_markup=plan_settings_keyboard(plan_id, server_id, plan["is_active"]),
            parse_mode="HTML"
        )
        await callback.answer("وضعیت پلن تغییر کرد.")

    @dp.callback_query(F.data.startswith("delete_plan_"))
    async def ask_delete_plan(callback: types.CallbackQuery):
        parts = callback.data.replace("delete_plan_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        plan = await get_plan(plan_id)
        await callback.message.edit_text(
            f"⚠️ مطمئنی می‌خوای پلن <b>{plan['name']}</b> رو حذف کنی؟\n"
            "این عمل قابل بازگشت نیست.",
            reply_markup=confirm_delete_plan_keyboard(plan_id, server_id),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("confirmed_delete_plan_"))
    async def do_delete_plan(callback: types.CallbackQuery):
        parts = callback.data.replace("confirmed_delete_plan_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        plan = await get_plan(plan_id)
        plan_name = plan["name"]
        await delete_plan(plan_id)
        plans = await get_plans(server_id, only_active=False)
        if plans:
            await callback.message.edit_text(
                f"🗑 پلن <b>{plan_name}</b> حذف شد.\n\n📦 <b>لیست پلن‌ها</b>",
                reply_markup=plans_table_keyboard(plans, server_id),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"🗑 پلن <b>{plan_name}</b> حذف شد.\n\n❌ هیچ پلنی باقی نمونده.",
                reply_markup=admin_plans_menu(),
                parse_mode="HTML"
            )
        await callback.answer("پلن حذف شد.")
