from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import AddPlan, EditPlan
from keyboards import (
    admin_plans_menu, servers_list_keyboard, cancel_keyboard,
    plans_table_keyboard, plan_settings_keyboard,
    confirm_delete_plan_keyboard
)
from shared_lib.db import (
    add_plan, get_servers, get_plans, get_plan,
    delete_plan, toggle_plan_status, get_setting, set_setting, update_plan_field,
    get_text,
)
from shared_lib.services import features

def _fmt_dur(val) -> str:
    return "♾️ بی‌نهایت" if int(val) == 0 else f"{val} روز"

def _fmt_trf(val) -> str:
    return "♾️ بی‌نهایت" if int(val) == 0 else f"{val} گیگابایت"

def _fmt_ip(val) -> str:
    return "♾️ نامحدود" if int(val or 0) == 0 else f"{val} کاربر"

def _plan_settings_text(plan) -> str:
    status = "✅ فعال" if plan["is_active"] else "❌ غیرفعال"
    return get_text("admin_plan_settings_text",
                    name=plan["name"],
                    traffic=_fmt_trf(plan["traffic"]),
                    duration=_fmt_dur(plan["duration"]),
                    ip_limit=_fmt_ip(plan["ip_limit"]),
                    price=f"{plan['price']:,}",
                    status=status)

def register_plan_handlers(dp):

    @dp.callback_query(F.data == "admin_plans")
    async def admin_plans(callback: types.CallbackQuery):
        show_price = await features.is_enabled("show_plan_price")
        await callback.message.edit_text(
            get_text("admin_plans_title"),
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
                get_text("admin_plans_no_servers"),
                reply_markup=admin_plans_menu()
            )
            await callback.answer()
            return
        await callback.message.edit_text(
            get_text("admin_plans_select_server"),
            reply_markup=servers_list_keyboard(servers)
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("select_server_"))
    async def select_server(callback: types.CallbackQuery, state: FSMContext):
        server_id = int(callback.data.replace("select_server_", ""))
        await state.update_data(server_id=server_id)
        await callback.message.edit_text(
            get_text("admin_plan_ask_name"),
            reply_markup=cancel_keyboard()
        )
        await state.set_state(AddPlan.waiting_for_name)
        await callback.answer()

    @dp.message(AddPlan.waiting_for_name)
    async def add_plan_name(message: types.Message, state: FSMContext):
        await state.update_data(name=message.text)
        await message.answer(get_text("admin_plan_ask_price"), reply_markup=cancel_keyboard())
        await state.set_state(AddPlan.waiting_for_price)

    @dp.message(AddPlan.waiting_for_price)
    async def add_plan_price(message: types.Message, state: FSMContext):
        if not message.text.isdigit():
            await message.answer(get_text("admin_plan_price_ask_int"))
            return
        await state.update_data(price=int(message.text))
        await message.answer(get_text("admin_plan_ask_duration"), reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(AddPlan.waiting_for_duration)

    @dp.message(AddPlan.waiting_for_duration)
    async def add_plan_duration(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 0:
            await message.answer(get_text("admin_plan_duration_invalid"))
            return
        await state.update_data(duration=int(raw))
        await message.answer(get_text("admin_plan_ask_traffic"), reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(AddPlan.waiting_for_traffic)

    @dp.message(AddPlan.waiting_for_traffic)
    async def add_plan_traffic(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 0:
            await message.answer(get_text("admin_plan_traffic_invalid"))
            return
        await state.update_data(traffic=int(raw))
        await message.answer(get_text("admin_plan_ask_ip_limit"), reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(AddPlan.waiting_for_ip_limit)

    @dp.message(AddPlan.waiting_for_ip_limit)
    async def add_plan_ip_limit(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 0:
            await message.answer(get_text("admin_plan_ip_limit_invalid"))
            return
        data = await state.get_data()
        await add_plan(
            server_id=data["server_id"],
            name=data["name"],
            price=data["price"],
            duration=data["duration"],
            traffic=data["traffic"],
            ip_limit=int(raw)
        )
        await state.clear()
        await message.answer(get_text("admin_plan_added"), reply_markup=admin_plans_menu())

    # ─── لیست پلن‌ها ─────────────────────────────

    @dp.callback_query(F.data == "list_plans")
    async def list_plans(callback: types.CallbackQuery):
        servers = await get_servers()
        if not servers:
            await callback.message.edit_text(
                get_text("admin_servers_empty"),
                reply_markup=admin_plans_menu()
            )
            await callback.answer()
            return
        await callback.message.edit_text(
            get_text("admin_plans_select_server_view"),
            reply_markup=servers_list_keyboard(servers, mode="view_plans")
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("view_plans_"))
    async def view_plans(callback: types.CallbackQuery):
        server_id = int(callback.data.replace("view_plans_", ""))
        plans = await get_plans(server_id, only_active=False)
        if not plans:
            await callback.message.edit_text(
                get_text("admin_plans_empty_for_server"),
                reply_markup=admin_plans_menu()
            )
            await callback.answer()
            return
        await callback.message.edit_text(
            get_text("admin_plans_list_text"),
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
        await callback.message.edit_text(
            _plan_settings_text(plan),
            reply_markup=plan_settings_keyboard(plan_id, server_id, plan["is_active"]),
            parse_mode="HTML"
        )
        await callback.answer()

    # ─── ویرایش فیلدهای پلن ──────────────────────

    @dp.callback_query(F.data.startswith("edit_plan_price_"))
    async def edit_plan_price_start(callback: types.CallbackQuery, state: FSMContext):
        parts = callback.data.replace("edit_plan_price_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        plan = await get_plan(plan_id)
        await state.update_data(plan_id=plan_id, server_id=server_id)
        await state.set_state(EditPlan.waiting_for_price)
        await callback.message.edit_text(
            get_text("admin_plan_ask_edit_price", name=plan["name"], price=f"{plan['price']:,}"),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(EditPlan.waiting_for_price)
    async def edit_plan_price_save(message: types.Message, state: FSMContext):
        raw = message.text.strip().replace(",", "").replace("،", "")
        if not raw.isdigit() or int(raw) < 1000:
            await message.answer(get_text("admin_plan_price_invalid"))
            return
        data = await state.get_data()
        await update_plan_field(data["plan_id"], "price", int(raw))
        await state.clear()
        plans = await get_plans(data["server_id"], only_active=False)
        await message.answer(
            get_text("admin_plan_updated_list", field="قیمت"),
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
            get_text("admin_plan_ask_edit_duration", name=plan["name"], duration=_fmt_dur(plan["duration"])),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(EditPlan.waiting_for_duration)
    async def edit_plan_duration_save(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 0:
            await message.answer(get_text("admin_plan_duration_invalid"))
            return
        data = await state.get_data()
        await update_plan_field(data["plan_id"], "duration", int(raw))
        await state.clear()
        plans = await get_plans(data["server_id"], only_active=False)
        await message.answer(
            get_text("admin_plan_updated_list", field="مدت"),
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
            get_text("admin_plan_ask_edit_traffic", name=plan["name"], traffic=_fmt_trf(plan["traffic"])),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(EditPlan.waiting_for_traffic)
    async def edit_plan_traffic_save(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 0:
            await message.answer(get_text("admin_plan_traffic_invalid"))
            return
        data = await state.get_data()
        await update_plan_field(data["plan_id"], "traffic", int(raw))
        await state.clear()
        plans = await get_plans(data["server_id"], only_active=False)
        await message.answer(
            get_text("admin_plan_updated_list", field="حجم"),
            reply_markup=plans_table_keyboard(plans, data["server_id"]),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data.startswith("edit_plan_ip_limit_"))
    async def edit_plan_ip_limit_start(callback: types.CallbackQuery, state: FSMContext):
        parts = callback.data.replace("edit_plan_ip_limit_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        plan = await get_plan(plan_id)
        await state.update_data(plan_id=plan_id, server_id=server_id)
        await state.set_state(EditPlan.waiting_for_ip_limit)
        await callback.message.edit_text(
            get_text("admin_plan_ask_edit_ip_limit", name=plan["name"], ip_limit=_fmt_ip(plan["ip_limit"])),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(EditPlan.waiting_for_ip_limit)
    async def edit_plan_ip_limit_save(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.isdigit() or int(raw) < 0:
            await message.answer(get_text("admin_plan_ip_limit_invalid"))
            return
        data = await state.get_data()
        await update_plan_field(data["plan_id"], "ip_limit", int(raw))
        await state.clear()
        plans = await get_plans(data["server_id"], only_active=False)
        await message.answer(
            get_text("admin_plan_updated_list", field="کاربر هم‌زمان"),
            reply_markup=plans_table_keyboard(plans, data["server_id"]),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data.startswith("toggle_plan_") & ~F.data.startswith("toggle_plan_settings_"))
    async def toggle_plan(callback: types.CallbackQuery):
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
        parts = callback.data.replace("toggle_plan_settings_", "").split("_")
        plan_id, server_id = int(parts[0]), int(parts[1])
        await toggle_plan_status(plan_id)
        plan = await get_plan(plan_id)
        await callback.message.edit_text(
            _plan_settings_text(plan),
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
            get_text("admin_plan_delete_confirm", name=plan["name"]),
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
                get_text("admin_plan_deleted_list", name=plan_name),
                reply_markup=plans_table_keyboard(plans, server_id),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                get_text("admin_plan_deleted_empty", name=plan_name),
                reply_markup=admin_plans_menu(),
                parse_mode="HTML"
            )
        await callback.answer("پلن حذف شد.")
