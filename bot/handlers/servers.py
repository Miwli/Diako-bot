import json
import re
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import AddServer, EditServer
from keyboards import (
    admin_servers_menu, back_to_servers_menu, cancel_keyboard,
    rebecca_services_keyboard, servers_table_keyboard,
    server_settings_keyboard, confirm_delete_server_keyboard
)
from shared_lib.db import (
    add_server, get_servers, get_server,
    delete_server, toggle_server_status, update_server_services,
    update_server_url, update_server_token
)
from rebecca_api import RebeccaAPI

def register_server_handlers(dp):

    @dp.callback_query(F.data == "admin_servers")
    async def admin_servers(callback: types.CallbackQuery):
        await callback.message.edit_text(
            "🖥 مدیریت سرورها",
            reply_markup=admin_servers_menu()
        )
        await callback.answer()

    # ─── اضافه کردن سرور ─────────────────────────

    @dp.callback_query(F.data == "add_server")
    async def add_server_start(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text(
            "🖥 اسم سرور رو بفرست:\n\nمثلاً: سرور آلمان 🇩🇪",
            reply_markup=cancel_keyboard()
        )
        await state.set_state(AddServer.waiting_for_name)
        await callback.answer()

    @dp.message(AddServer.waiting_for_name)
    async def add_server_name(message: types.Message, state: FSMContext):
        await state.update_data(name=message.text)
        await message.answer(
            "🔗 آدرس پنل رو بفرست:\n\nمثلاً: https://rebeccapanel.com:8880",
            reply_markup=cancel_keyboard()
        )
        await state.set_state(AddServer.waiting_for_url)

    @dp.message(AddServer.waiting_for_url)
    async def add_server_url(message: types.Message, state: FSMContext):
        url = message.text.strip()
        if not re.match(r'^https?://[^\s/]+:\d+$', url):
            await message.answer(
                "❌ <b>آدرس معتبر نیست!</b>\n\n"
                "فرمت: <code>https://domain.com:PORT</code>\n\n"
                "⚠️ آدرس نباید به <code>/</code> ختم بشه.",
                parse_mode="HTML",
                reply_markup=cancel_keyboard()
            )
            return
        await state.update_data(panel_url=url)
        await message.answer("🔑 توکن API پنل رو بفرست:", reply_markup=cancel_keyboard())
        await state.set_state(AddServer.waiting_for_token)

    @dp.message(AddServer.waiting_for_token)
    async def add_server_token(message: types.Message, state: FSMContext):
        token = message.text.strip()
        data = await state.get_data()
        await state.update_data(panel_token=token)
        await _fetch_and_show_services(message, state, data["panel_url"], token)

    # ─── ویرایش آدرس و توکن سرور ────────────────

    @dp.callback_query(F.data.startswith("edit_server_url_"))
    async def edit_server_url_start(callback: types.CallbackQuery, state: FSMContext):
        server_id = int(callback.data.replace("edit_server_url_", ""))
        await state.update_data(edit_server_id=server_id)
        await state.set_state(EditServer.waiting_for_url)
        await callback.message.edit_text(
            "🔗 آدرس جدید پنل رو بفرست:\n\nمثلاً: https://rebeccapanel.com:8880",
            reply_markup=cancel_keyboard()
        )
        await callback.answer()

    @dp.message(EditServer.waiting_for_url)
    async def edit_server_url_save(message: types.Message, state: FSMContext):
        url = message.text.strip()
        if not re.match(r'^https?://[^\s/]+:\d+$', url):
            await message.answer(
                "❌ <b>آدرس معتبر نیست!</b>\n\n"
                "فرمت: <code>https://domain.com:PORT</code>\n\n"
                "⚠️ آدرس نباید به <code>/</code> ختم بشه.",
                parse_mode="HTML",
                reply_markup=cancel_keyboard()
            )
            return
        data = await state.get_data()
        server_id = data["edit_server_id"]
        await update_server_url(server_id, url)
        await state.clear()
        server = await get_server(server_id)
        svc_ids = json.loads(server["service_ids"] or "[]")
        status = "✅ فعال" if server["is_active"] else "❌ غیرفعال"
        await message.answer(
            f"✅ آدرس سرور بروزرسانی شد.\n\n"
            f"⚙️ <b>تنظیمات سرور</b>\n"
            f"{'─' * 24}\n"
            f"🖥 <b>{server['name']}</b>\n"
            f"🔗 {server['panel_url']}\n"
            f"📊 وضعیت: {status}\n"
            f"🔧 سرویس‌ها: {len(svc_ids)} سرویس",
            reply_markup=server_settings_keyboard(server_id, server["is_active"]),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data.startswith("edit_server_token_"))
    async def edit_server_token_start(callback: types.CallbackQuery, state: FSMContext):
        server_id = int(callback.data.replace("edit_server_token_", ""))
        await state.update_data(edit_server_id=server_id)
        await state.set_state(EditServer.waiting_for_token)
        await callback.message.edit_text(
            "🔑 توکن جدید API پنل رو بفرست:",
            reply_markup=cancel_keyboard()
        )
        await callback.answer()

    @dp.message(EditServer.waiting_for_token)
    async def edit_server_token_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        server_id = data["edit_server_id"]
        await update_server_token(server_id, message.text.strip())
        await state.clear()
        server = await get_server(server_id)
        svc_ids = json.loads(server["service_ids"] or "[]")
        status = "✅ فعال" if server["is_active"] else "❌ غیرفعال"
        await message.answer(
            f"✅ توکن سرور بروزرسانی شد.\n\n"
            f"⚙️ <b>تنظیمات سرور</b>\n"
            f"{'─' * 24}\n"
            f"🖥 <b>{server['name']}</b>\n"
            f"🔗 {server['panel_url']}\n"
            f"📊 وضعیت: {status}\n"
            f"🔧 سرویس‌ها: {len(svc_ids)} سرویس",
            reply_markup=server_settings_keyboard(server_id, server["is_active"]),
            parse_mode="HTML"
        )

    # ─── ویرایش سرویس‌های سرور ───────────────────

    @dp.callback_query(F.data.startswith("edit_server_services_"))
    async def edit_server_services(callback: types.CallbackQuery, state: FSMContext):
        server_id = int(callback.data.replace("edit_server_services_", ""))
        server = await get_server(server_id)
        await state.update_data(
            panel_url=server["panel_url"],
            panel_token=server["panel_token"],
            edit_server_id=server_id
        )
        await _fetch_and_show_services(
            callback.message, state,
            server["panel_url"], server["panel_token"],
            current_ids=json.loads(server["service_ids"] or "[]"),
            edit_mode=True
        )
        await callback.answer()

    async def _fetch_and_show_services(msg, state, panel_url, token,
                                        current_ids=None, edit_mode=False):
        try:
            api = RebeccaAPI(panel_url, token)
            services = await api.get_services()
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در اتصال به پنل {panel_url}: {e}")
            await msg.answer(
                f"❌ خطا در اتصال به پنل:\n<code>{e}</code>",
                parse_mode="HTML",
                reply_markup=cancel_keyboard()
            )
            return
        if not services:
            await msg.answer(
                "⚠️ هیچ سرویسی در پنل تعریف نشده!",
                reply_markup=cancel_keyboard()
            )
            return
        live_ids = {s["id"] for s in services}
        selected = [sid for sid in (current_ids or []) if sid in live_ids]
        await state.update_data(services=services, selected_service_ids=selected)
        await state.set_state(AddServer.waiting_for_service)
        text = "✏️ سرویس‌های این سرور رو ویرایش کن:" if edit_mode else \
               "🔧 سرویس‌هایی که می‌خوای این سرور داشته باشه رو انتخاب کن:"
        keyboard = rebecca_services_keyboard(services, selected)
        if edit_mode:
            await msg.edit_text(text, reply_markup=keyboard)
        else:
            await msg.answer(text, reply_markup=keyboard)

    @dp.callback_query(AddServer.waiting_for_service, F.data.startswith("toggle_svc_"))
    async def toggle_service(callback: types.CallbackQuery, state: FSMContext):
        svc_id = int(callback.data.replace("toggle_svc_", ""))
        data = await state.get_data()
        selected = list(data.get("selected_service_ids", []))
        if svc_id in selected:
            selected.remove(svc_id)
        else:
            selected.append(svc_id)
        await state.update_data(selected_service_ids=selected)
        await callback.message.edit_reply_markup(
            reply_markup=rebecca_services_keyboard(data["services"], selected)
        )
        await callback.answer()

    @dp.callback_query(AddServer.waiting_for_service, F.data == "confirm_services")
    async def confirm_services(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        selected = data.get("selected_service_ids", [])
        if not selected:
            await callback.answer("حداقل یک سرویس انتخاب کن!", show_alert=True)
            return
        edit_server_id = data.get("edit_server_id")
        if edit_server_id:
            await update_server_services(edit_server_id, selected)
            await state.clear()
            server = await get_server(edit_server_id)
            await callback.message.edit_text(
                f"✅ سرویس‌های سرور <b>{server['name']}</b> بروزرسانی شد.",
                reply_markup=server_settings_keyboard(edit_server_id, server["is_active"]),
                parse_mode="HTML"
            )
        else:
            await add_server(
                name=data["name"],
                panel_url=data["panel_url"],
                panel_token=data["panel_token"],
                service_ids=selected
            )
            await state.clear()
            await callback.message.edit_text(
                f"✅ سرور با موفقیت اضافه شد!\n🔧 {len(selected)} سرویس انتخاب شد.",
                reply_markup=admin_servers_menu()
            )
        await callback.answer()

    # ─── لیست سرورها ─────────────────────────────

    @dp.callback_query(F.data == "list_servers")
    async def list_servers(callback: types.CallbackQuery):
        servers = await get_servers(only_active=False)
        if not servers:
            await callback.message.edit_text(
                "❌ هیچ سروری ثبت نشده!",
                reply_markup=back_to_servers_menu()
            )
            await callback.answer()
            return
        await callback.message.edit_text(
            "🖥 <b>لیست سرورها</b>",
            reply_markup=servers_table_keyboard(servers),
            parse_mode="HTML"
        )
        await callback.answer()

    # ─── تنظیمات سرور ────────────────────────────

    @dp.callback_query(F.data.startswith("server_settings_"))
    async def server_settings(callback: types.CallbackQuery):
        server_id = int(callback.data.replace("server_settings_", ""))
        server = await get_server(server_id)
        svc_ids = json.loads(server["service_ids"] or "[]")
        status = "✅ فعال" if server["is_active"] else "❌ غیرفعال"
        await callback.message.edit_text(
            f"⚙️ <b>تنظیمات سرور</b>\n"
            f"{'─' * 24}\n"
            f"🖥 <b>{server['name']}</b>\n"
            f"🔗 {server['panel_url']}\n"
            f"📊 وضعیت: {status}\n"
            f"🔧 سرویس‌ها: {len(svc_ids)} سرویس",
            reply_markup=server_settings_keyboard(server_id, server["is_active"]),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("toggle_server_"))
    async def toggle_server(callback: types.CallbackQuery):
        """toggle از لیست سرورها — جدول رو رفرش می‌کنه"""
        server_id = int(callback.data.replace("toggle_server_", ""))
        await toggle_server_status(server_id)
        servers = await get_servers(only_active=False)
        await callback.message.edit_reply_markup(
            reply_markup=servers_table_keyboard(servers)
        )
        await callback.answer("وضعیت سرور تغییر کرد.")

    @dp.callback_query(F.data.startswith("toggle_server_settings_"))
    async def toggle_server_from_settings(callback: types.CallbackQuery):
        """toggle از صفحه تنظیمات سرور — صفحه تنظیمات رو رفرش می‌کنه"""
        server_id = int(callback.data.replace("toggle_server_settings_", ""))
        await toggle_server_status(server_id)
        server = await get_server(server_id)
        svc_ids = json.loads(server["service_ids"] or "[]")
        status = "✅ فعال" if server["is_active"] else "❌ غیرفعال"
        await callback.message.edit_text(
            f"⚙️ <b>تنظیمات سرور</b>\n"
            f"{'─' * 24}\n"
            f"🖥 <b>{server['name']}</b>\n"
            f"🔗 {server['panel_url']}\n"
            f"📊 وضعیت: {status}\n"
            f"🔧 سرویس‌ها: {len(svc_ids)} سرویس",
            reply_markup=server_settings_keyboard(server_id, server["is_active"]),
            parse_mode="HTML"
        )
        await callback.answer("وضعیت سرور تغییر کرد.")

    @dp.callback_query(F.data.startswith("delete_server_"))
    async def ask_delete_server(callback: types.CallbackQuery):
        server_id = int(callback.data.replace("delete_server_", ""))
        server = await get_server(server_id)
        await callback.message.edit_text(
            f"⚠️ مطمئنی می‌خوای سرور <b>{server['name']}</b> رو حذف کنی؟\n"
            "این عمل قابل بازگشت نیست.",
            reply_markup=confirm_delete_server_keyboard(server_id),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("confirmed_delete_server_"))
    async def do_delete_server(callback: types.CallbackQuery):
        server_id = int(callback.data.replace("confirmed_delete_server_", ""))
        server = await get_server(server_id)
        await delete_server(server_id)
        servers = await get_servers(only_active=False)
        if servers:
            await callback.message.edit_text(
                f"🗑 سرور <b>{server['name']}</b> حذف شد.\n\n🖥 <b>لیست سرورها</b>",
                reply_markup=servers_table_keyboard(servers),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"🗑 سرور <b>{server['name']}</b> حذف شد.\n\n❌ هیچ سروری باقی نمونده.",
                reply_markup=back_to_servers_menu(),
                parse_mode="HTML"
            )
        await callback.answer("سرور حذف شد.")
