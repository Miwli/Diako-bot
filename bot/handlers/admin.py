import json
import html as html_lib
import qrcode
from io import BytesIO
from aiogram import types, F
from aiogram.types import BufferedInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from keyboards import admin_main_menu, admin_panel_menu, user_main_menu, after_order_keyboard, subscription_approved_keyboard, admin_topup_keyboard, admin_general_menu, admin_banner_settings_menu, admin_banner_and_text_menu, admin_text_settings_menu, admin_free_test_menu, admin_free_test_global_menu, admin_free_test_server_menu
from states import AdminAction, GeneralSettings, FreeTestSettings
from aiogram.filters import Command
from shared_lib.db import (
    get_order, get_plan_with_server, update_order_status, update_order_vpn_info,
    get_top_up_request, update_top_up_status, approve_top_up_atomic,
    add_balance, add_balance_and_transaction, get_or_create_user,
    get_setting, set_setting,
    get_servers, get_server, update_server_free_test, apply_free_test_to_all,
    reset_free_test_uses,
    get_referral_by_referred, mark_first_purchase_rewarded,
    add_referral_commission, get_user,
    get_text,
)
from shared_lib.rebecca_api import RebeccaAPI

async def _apply_referral_rewards(bot, buyer_id: int, price: int):
    from bot import logger
    referral = await get_referral_by_referred(buyer_id)
    if not referral:
        return
    referrer_id = referral["referrer_id"]
    is_first = not referral["first_purchase_rewarded"]

    cfg_keys = [
        "referral_enabled", "referral_flat_enabled", "referral_flat_amount",
        "referral_percent_enabled", "referral_percent_value",
        "referral_free_test_enabled",
        "referral_discount_enabled", "referral_discount_value",
    ]
    cfg = {k: (await get_setting(k) or "0") for k in cfg_keys}
    if cfg["referral_enabled"] != "1":
        return

    total_reward = 0

    if is_first:
        if cfg["referral_flat_enabled"] == "1":
            flat = int(cfg["referral_flat_amount"] or "0")
            if flat > 0:
                await add_balance_and_transaction(referrer_id, flat, f"جایزه دعوت کاربر {buyer_id}")
                total_reward += flat

        if cfg["referral_free_test_enabled"] == "1":
            try:
                from shared_lib.db import decrement_free_test_uses
                await decrement_free_test_uses(referrer_id)
            except Exception as e:
                logger.error(f"خطا در اعطای تست رایگان به {referrer_id}: {e}")

        if cfg["referral_discount_enabled"] == "1":
            pct = int(cfg["referral_discount_value"] or "0")
            if pct > 0:
                credit = price * pct // 100
                await add_balance_and_transaction(buyer_id, credit, f"اعتبار خوش‌آمدگویی {pct}٪ اولین خرید")

        await mark_first_purchase_rewarded(buyer_id, total_reward)

    if cfg["referral_percent_enabled"] == "1":
        pct = int(cfg["referral_percent_value"] or "0")
        if pct > 0:
            commission = price * pct // 100
            if commission > 0:
                await add_balance_and_transaction(referrer_id, commission, f"پورسانت {pct}٪ خرید کاربر {buyer_id}")
                await add_referral_commission(buyer_id, commission)
                try:
                    await bot.send_message(
                        referrer_id,
                        get_text("referral_commission_notify", amount=f"{commission:,}"),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

def _make_qr(data: str) -> BufferedInputFile:
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return BufferedInputFile(buf.read(), filename="qr.png")

def register_admin_handlers(dp):

    @dp.message(CommandStart())
    async def cmd_start(message: types.Message):
        from bot import is_admin, logger
        from handlers.user import _send_main_menu
        u = message.from_user
        logger.info(f"کاربر {u.id} دستور /start فرستاد")

        await get_or_create_user(u.id, u.first_name, u.username)

        from shared_lib.db import get_user as _get_user
        _u = await _get_user(u.id)
        if _u and _u["is_banned"] and not is_admin(u.id):
            await message.answer(get_text("start_banned"))
            return

        args = message.text.split(maxsplit=1)
        if len(args) > 1 and args[1].startswith("ref_"):
            ref_code = args[1][4:]
            from shared_lib.db import (
                get_user_by_referral_code, set_referral_by,
                create_referral, get_user, get_setting
            )
            referral_enabled = await get_setting("referral_enabled")
            if referral_enabled == "1":
                referrer = await get_user_by_referral_code(ref_code)
                if referrer and referrer["user_id"] != u.id:
                    cur_user = await get_user(u.id)
                    if cur_user and not cur_user["referral_by"]:
                        await set_referral_by(u.id, ref_code)
                        await create_referral(referrer["user_id"], u.id)
                        logger.info(f"کاربر {u.id} با لینک دعوت {ref_code} ثبت شد")

        await _send_main_menu(message, u)

    async def _edit_or_replace(callback: types.CallbackQuery, text: str, markup, parse_mode="HTML"):
        try:
            await callback.message.edit_text(text, reply_markup=markup, parse_mode=parse_mode)
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=markup, parse_mode=parse_mode)

    @dp.callback_query(F.data == "admin_panel")
    async def admin_panel(callback: types.CallbackQuery):
        from bot import is_admin
        if not is_admin(callback.from_user.id):
            await callback.answer("⛔️ شما به این بخش دسترسی ندارید.", show_alert=True)
            return
        await _edit_or_replace(callback, get_text("admin_panel_title"), admin_panel_menu())
        await callback.answer()

    @dp.callback_query(F.data.in_(set()))
    async def admin_coming_soon(callback: types.CallbackQuery):
        await callback.answer(get_text("coming_soon"), show_alert=True)

    def _parse_positive_number(text: str):
        try:
            val = float(text.replace(",", "."))
            return val if val >= 0 else None
        except ValueError:
            return None

    def _format_duration(val) -> str:
        return "♾️ بی‌نهایت" if float(val) == 0 else f"{val} ساعت"

    def _format_max_uses(val: str) -> str:
        return "♾️ بی‌نهایت" if str(val) == "0" else f"{val} بار"

    # ─── تنظیمات تست رایگان ───────────────────────
    async def _free_test_page(callback: types.CallbackQuery):
        servers = await get_servers(only_active=False)
        await _edit_or_replace(callback, get_text("admin_free_test_title"), admin_free_test_menu(servers))
        await callback.answer()

    @dp.callback_query(F.data == "admin_free_test")
    async def admin_free_test(callback: types.CallbackQuery):
        await _free_test_page(callback)

    def _free_test_global_text(duration, traffic, max_uses) -> str:
        return get_text("admin_free_test_global_text",
                        duration=_format_duration(duration),
                        traffic=traffic,
                        max_uses=_format_max_uses(str(max_uses)))

    @dp.callback_query(F.data == "admin_free_test_global")
    async def admin_free_test_global(callback: types.CallbackQuery):
        duration  = await get_setting("free_test_duration")  or "1"
        traffic   = await get_setting("free_test_traffic")   or "1"
        max_uses  = await get_setting("free_test_max_uses")  or "1"
        await _edit_or_replace(callback, _free_test_global_text(duration, traffic, max_uses), admin_free_test_global_menu())
        await callback.answer()

    @dp.callback_query(F.data == "admin_free_test_global_duration")
    async def admin_free_test_global_duration_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(FreeTestSettings.waiting_for_global_duration)
        await callback.message.edit_text(get_text("admin_free_test_ask_duration"), parse_mode="HTML")
        await callback.answer()

    @dp.message(FreeTestSettings.waiting_for_global_duration, F.text)
    async def admin_free_test_global_duration_save(message: types.Message, state: FSMContext):
        val = _parse_positive_number(message.text)
        if val is None:
            await message.answer(get_text("admin_invalid_number"))
            return
        await set_setting("free_test_duration", str(val))
        await state.clear()
        traffic  = await get_setting("free_test_traffic") or "1"
        max_uses = await get_setting("free_test_max_uses") or "1"
        await message.answer(_free_test_global_text(str(val), traffic, max_uses),
                             reply_markup=admin_free_test_global_menu(), parse_mode="HTML")

    @dp.callback_query(F.data == "admin_free_test_global_traffic")
    async def admin_free_test_global_traffic_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(FreeTestSettings.waiting_for_global_traffic)
        await callback.message.edit_text(get_text("admin_free_test_ask_traffic"), parse_mode="HTML")
        await callback.answer()

    @dp.message(FreeTestSettings.waiting_for_global_traffic, F.text)
    async def admin_free_test_global_traffic_save(message: types.Message, state: FSMContext):
        val = _parse_positive_number(message.text)
        if val is None:
            await message.answer(get_text("admin_invalid_pos_number"))
            return
        await set_setting("free_test_traffic", str(val))
        await state.clear()
        duration = await get_setting("free_test_duration") or "1"
        max_uses = await get_setting("free_test_max_uses") or "1"
        await message.answer(_free_test_global_text(duration, str(val), max_uses),
                             reply_markup=admin_free_test_global_menu(), parse_mode="HTML")

    @dp.callback_query(F.data == "admin_free_test_apply_all")
    async def admin_free_test_apply_all(callback: types.CallbackQuery):
        duration = float(await get_setting("free_test_duration") or "1")
        traffic  = float(await get_setting("free_test_traffic")  or "1")
        await apply_free_test_to_all(duration, traffic)
        await callback.answer(f"✅ اعمال شد: {_format_duration(duration)} / {traffic} گیگ", show_alert=True)

    @dp.callback_query(F.data == "admin_free_test_max_uses")
    async def admin_free_test_max_uses_start(callback: types.CallbackQuery, state: FSMContext):
        current = await get_setting("free_test_max_uses") or "1"
        await state.set_state(FreeTestSettings.waiting_for_max_uses)
        await callback.message.edit_text(
            get_text("admin_free_test_ask_max_uses", current=_format_max_uses(current)),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(FreeTestSettings.waiting_for_max_uses, F.text)
    async def admin_free_test_max_uses_save(message: types.Message, state: FSMContext):
        text_in = message.text.strip()
        if not text_in.isdigit() or int(text_in) < 0:
            await message.answer(get_text("admin_invalid_int"))
            return
        val = text_in
        await set_setting("free_test_max_uses", val)
        await state.clear()
        duration = await get_setting("free_test_duration") or "1"
        traffic  = await get_setting("free_test_traffic")  or "1"
        await message.answer(_free_test_global_text(duration, traffic, val),
                             reply_markup=admin_free_test_global_menu(), parse_mode="HTML")

    @dp.callback_query(F.data == "admin_free_test_reset_all")
    async def admin_free_test_reset_all(callback: types.CallbackQuery):
        await reset_free_test_uses()
        await callback.answer("✅ تعداد استفاده همه کاربران ریست شد.", show_alert=True)

    def _free_test_server_text(server) -> str:
        trf = server['free_test_traffic'] or 0
        trf_display = "♾️ بی‌نهایت" if float(trf) == 0 else f"{trf} گیگابایت"
        return get_text("admin_free_test_server_text",
                        name=server['name'],
                        status="✅ فعال" if server['free_test_enabled'] else "❌ غیرفعال",
                        duration=_format_duration(server['free_test_duration'] or 0),
                        traffic=trf_display)

    @dp.callback_query(F.data.startswith("admin_free_test_server_"))
    async def admin_free_test_server(callback: types.CallbackQuery):
        server_id = int(callback.data.replace("admin_free_test_server_", ""))
        server = await get_server(server_id)
        await _edit_or_replace(callback, _free_test_server_text(server), admin_free_test_server_menu(server_id, bool(server["free_test_enabled"])))
        await callback.answer()

    @dp.callback_query(F.data.startswith("admin_free_test_toggle_"))
    async def admin_free_test_toggle(callback: types.CallbackQuery):
        server_id = int(callback.data.replace("admin_free_test_toggle_", ""))
        server = await get_server(server_id)
        new_val = 0 if server["free_test_enabled"] else 1
        await update_server_free_test(server_id, enabled=new_val)
        server = await get_server(server_id)
        await _edit_or_replace(callback, _free_test_server_text(server), admin_free_test_server_menu(server_id, bool(new_val)))
        await callback.answer()

    @dp.callback_query(F.data.startswith("admin_free_test_duration_"))
    async def admin_free_test_server_duration_start(callback: types.CallbackQuery, state: FSMContext):
        server_id = int(callback.data.replace("admin_free_test_duration_", ""))
        await state.update_data(server_id=server_id)
        await state.set_state(FreeTestSettings.waiting_for_server_duration)
        await callback.message.edit_text(get_text("admin_free_test_ask_server_dur"), parse_mode="HTML")
        await callback.answer()

    @dp.message(FreeTestSettings.waiting_for_server_duration, F.text)
    async def admin_free_test_server_duration_save(message: types.Message, state: FSMContext):
        val = _parse_positive_number(message.text)
        if val is None:
            await message.answer(get_text("admin_invalid_number"))
            return
        data = await state.get_data()
        server_id = data["server_id"]
        await update_server_free_test(server_id, duration=val)
        await state.clear()
        server = await get_server(server_id)
        await message.answer(_free_test_server_text(server), reply_markup=admin_free_test_server_menu(server_id, bool(server["free_test_enabled"])), parse_mode="HTML")

    @dp.callback_query(F.data.startswith("admin_free_test_traffic_"))
    async def admin_free_test_server_traffic_start(callback: types.CallbackQuery, state: FSMContext):
        server_id = int(callback.data.replace("admin_free_test_traffic_", ""))
        await state.update_data(server_id=server_id)
        await state.set_state(FreeTestSettings.waiting_for_server_traffic)
        await callback.message.edit_text(get_text("admin_free_test_ask_server_trf"), parse_mode="HTML")
        await callback.answer()

    @dp.message(FreeTestSettings.waiting_for_server_traffic, F.text)
    async def admin_free_test_server_traffic_save(message: types.Message, state: FSMContext):
        val = _parse_positive_number(message.text)
        if val is None:
            await message.answer(get_text("admin_invalid_pos_number"))
            return
        data = await state.get_data()
        server_id = data["server_id"]
        await update_server_free_test(server_id, traffic=val)
        await state.clear()
        server = await get_server(server_id)
        await message.answer(_free_test_server_text(server), reply_markup=admin_free_test_server_menu(server_id, bool(server["free_test_enabled"])), parse_mode="HTML")

    # ─── تنظیمات عمومی ────────────────────────────
    @dp.callback_query(F.data == "admin_general")
    async def admin_general(callback: types.CallbackQuery):
        await _edit_or_replace(callback, get_text("admin_general_title"), admin_general_menu())
        await callback.answer()

    @dp.callback_query(F.data == "admin_banner_and_text")
    async def admin_banner_and_text(callback: types.CallbackQuery):
        await _edit_or_replace(callback, get_text("admin_banner_and_text_title"), admin_banner_and_text_menu())
        await callback.answer()

    @dp.callback_query(F.data == "admin_banner_settings")
    async def admin_banner_settings(callback: types.CallbackQuery):
        banner = await get_setting("banner_file_id")
        status = get_text("admin_banner_status_active") if banner else get_text("admin_banner_status_none")
        await _edit_or_replace(callback, f"🖼 تنظیمات بنر\n\n{status}", admin_banner_settings_menu(has_banner=bool(banner)))
        await callback.answer()

    @dp.callback_query(F.data == "admin_banner_upload")
    async def admin_banner_upload(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(GeneralSettings.waiting_for_banner)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await callback.message.edit_text(
            get_text("admin_banner_upload_prompt"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_banner_settings")]
            ])
        )
        await callback.answer()

    @dp.message(GeneralSettings.waiting_for_banner, F.photo)
    async def admin_banner_save(message: types.Message, state: FSMContext):
        file_id = message.photo[-1].file_id
        await set_setting("banner_file_id", file_id)
        await state.clear()
        await message.answer(get_text("admin_banner_saved"), reply_markup=admin_banner_settings_menu(has_banner=True))

    @dp.callback_query(F.data == "admin_banner_settings", GeneralSettings.waiting_for_banner)
    async def admin_banner_upload_cancel(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        banner = await get_setting("banner_file_id")
        status = get_text("admin_banner_status_active") if banner else get_text("admin_banner_status_none")
        await _edit_or_replace(callback, f"🖼 تنظیمات بنر\n\n{status}", admin_banner_settings_menu(has_banner=bool(banner)))
        await callback.answer()

    @dp.callback_query(F.data == "admin_banner_delete")
    async def admin_banner_delete(callback: types.CallbackQuery):
        await set_setting("banner_file_id", "")
        status = get_text("admin_banner_status_none")
        await _edit_or_replace(callback, f"🖼 تنظیمات بنر\n\n{status}", admin_banner_settings_menu(has_banner=False))
        await callback.answer("🗑 بنر حذف شد.")

    @dp.callback_query(F.data == "admin_text_settings")
    async def admin_text_settings(callback: types.CallbackQuery):
        await _edit_or_replace(callback, get_text("admin_text_settings_title"), admin_text_settings_menu())
        await callback.answer()

    @dp.callback_query(F.data == "admin_banner_caption")
    async def admin_banner_caption_start(callback: types.CallbackQuery, state: FSMContext):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        current = await get_setting("banner_caption") or ""
        text = get_text("admin_caption_edit_prompt", current=current or "(پیش‌فرض)")
        await state.set_state(GeneralSettings.waiting_for_caption)
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_text_settings")]
            ])
        )
        await callback.answer()

    @dp.message(GeneralSettings.waiting_for_caption, F.text)
    async def admin_banner_caption_save(message: types.Message, state: FSMContext):
        import json as _json
        text = message.text
        entities = message.entities or []
        has_premium = any(e.type == "custom_emoji" for e in entities)
        await set_setting("banner_caption", text)
        if entities:
            await set_setting("banner_caption_entities", _json.dumps([e.model_dump() for e in entities]))
        else:
            await set_setting("banner_caption_entities", "")
        await state.clear()
        note = " (با ایموجی پرمیوم)" if has_premium else ""
        await message.answer(get_text("admin_caption_saved", note=note), reply_markup=admin_text_settings_menu())

    @dp.callback_query(F.data == "admin_text_settings", GeneralSettings.waiting_for_caption)
    async def admin_banner_caption_cancel(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await _edit_or_replace(callback, get_text("admin_text_settings_title"), admin_text_settings_menu())
        await callback.answer()

    @dp.callback_query(F.data == "admin_build_text")
    async def admin_build_text_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(GeneralSettings.waiting_for_emoji_text)
        await callback.message.edit_text(get_text("admin_build_text_prompt"))
        await callback.answer()

    @dp.message(GeneralSettings.waiting_for_emoji_text)
    async def admin_build_text_process(message: types.Message, state: FSMContext):
        await state.clear()
        text = message.text or message.caption or ""
        entities = message.entities or message.caption_entities or []
        custom_emojis = [e for e in entities if getattr(e, "custom_emoji_id", None)]

        if not text:
            await message.answer("❌ پیام خالی است.", reply_markup=admin_text_settings_menu())
            return

        if not custom_emojis:
            await message.answer(
                "❌ استیکر پرمیوم‌ای پیدا نشد. مطمئن شو اشتراک پرمیوم داری و استیکر custom emoji فرستادی.",
                reply_markup=admin_text_settings_menu()
            )
            return

        raw = text.encode("utf-16-le")
        parts = []
        cursor = 0
        for e in sorted(custom_emojis, key=lambda x: x.offset):
            e_start = e.offset * 2
            e_end = (e.offset + e.length) * 2
            parts.append(raw[cursor:e_start].decode("utf-16-le"))
            fallback = raw[e_start:e_end].decode("utf-16-le")
            parts.append(f'<tg-emoji emoji-id="{e.custom_emoji_id}">{fallback}</tg-emoji>')
            cursor = e_end
        parts.append(raw[cursor:].decode("utf-16-le"))
        result = "".join(parts)

        await message.answer(f"✅ پیش‌نمایش:\n\n{result}", parse_mode="HTML")
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
        code_msg = f"<code>{html_lib.escape(result)}</code>"
        if len(result) <= 256:
            copy_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 کپی متن", copy_text=CopyTextButton(text=result))],
            ])
            await message.answer(code_msg, parse_mode="HTML", reply_markup=copy_kb)
        else:
            await message.answer(code_msg, parse_mode="HTML")
        await message.answer("⬆️", reply_markup=admin_text_settings_menu())

    @dp.callback_query(F.data == "back_to_start")
    async def back_to_start(callback: types.CallbackQuery):
        from handlers.user import _send_main_menu
        await _send_main_menu(callback, callback.from_user)

    @dp.callback_query(F.data == "cancel")
    async def cancel_operation(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await _edit_or_replace(callback, get_text("admin_cancel_op"), admin_panel_menu())
        await callback.answer()

    @dp.callback_query(F.data.startswith("order_approve_"))
    async def order_approve(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("order_approve_", ""))
        order = await get_order(order_id)
        if not order:
            await callback.answer("سفارش یافت نشد.", show_alert=True)
            return
        if order["status"] != "pending":
            await callback.answer("این سفارش قبلاً پردازش شده.", show_alert=True)
            return

        plan = await get_plan_with_server(order["plan_id"])

        try:
            stored_ids = json.loads(plan["service_ids"] or "[]")
            if not stored_ids:
                await callback.answer("سرویسی برای این سرور تنظیم نشده!", show_alert=True)
                return
            api = RebeccaAPI(plan["panel_url"], plan["panel_token"])

            live_services = await api.get_services()
            live_ids = {s["id"] for s in live_services}
            service_id = next((sid for sid in stored_ids if sid in live_ids), None)
            if service_id is None:
                await callback.answer(
                    "❌ سرویس‌های انتخاب‌شده برای این سرور دیگه توی پنل Rebecca وجود ندارن.\n"
                    "از پنل ادمین → مدیریت سرورها → سرویس‌ها رو آپدیت کن.",
                    show_alert=True
                )
                return

            user_data = await api.create_user(
                service_id=service_id,
                data_limit_gb=plan["traffic"],
                duration_days=plan["duration"]
            )
            sub_path = user_data.get("subscription_url", "")
            subscription_url = await api.get_subscription_url(sub_path)
            username = user_data.get("username", "")
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در ساخت یوزر برای سفارش #{order_id}: {e}")
            await callback.answer(f"خطا در ساخت یوزر: {e}", show_alert=True)
            return

        try:
            await update_order_status(order_id, "approved")
            await update_order_vpn_info(order_id, username, subscription_url)
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در ذخیره سفارش #{order_id} — حذف یوزر {username}: {e}")
            try:
                await api.delete_user(username)
            except Exception:
                pass
            await callback.answer(f"خطا در ثبت اطلاعات: {e}", show_alert=True)
            return

        await _apply_referral_rewards(callback.bot, order["user_id"], plan["price"])

        await callback.message.edit_caption(
            callback.message.caption + f"\n\n✅ <b>تایید شد</b> — یوزر: <code>{username}</code>",
            parse_mode="HTML",
            reply_markup=after_order_keyboard()
        )
        qr_file = _make_qr(subscription_url)
        try:
            await callback.bot.send_photo(
                chat_id=order["user_id"],
                photo=qr_file,
                caption=get_text("order_approved", url=subscription_url),
                reply_markup=subscription_approved_keyboard(subscription_url),
                parse_mode="HTML"
            )
        except TelegramForbiddenError:
            from bot import logger
            logger.warning(f"کاربر {order['user_id']} بات را بلاک کرده — اطلاعیه سفارش ارسال نشد")
        await callback.answer("سفارش تایید شد.")

    @dp.callback_query(F.data.startswith("order_reject_") & ~F.data.startswith("order_reject_reason_"))
    async def order_reject(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("order_reject_", ""))
        order = await get_order(order_id)
        if not order:
            await callback.answer("سفارش یافت نشد.", show_alert=True)
            return
        if order["status"] != "pending":
            await callback.answer("این سفارش قبلاً پردازش شده.", show_alert=True)
            return

        await update_order_status(order_id, "rejected")
        await callback.message.edit_caption(
            callback.message.caption + "\n\n❌ <b>رد شد</b>",
            parse_mode="HTML",
            reply_markup=after_order_keyboard()
        )
        try:
            await callback.bot.send_message(
                chat_id=order["user_id"],
                text=get_text("order_rejected"),
            )
        except TelegramForbiddenError:
            from bot import logger
            logger.warning(f"کاربر {order['user_id']} بات را بلاک کرده — اطلاعیه رد سفارش ارسال نشد")
        await callback.answer("سفارش رد شد.")

    @dp.callback_query(F.data.startswith("order_reject_reason_"))
    async def order_reject_reason_start(callback: types.CallbackQuery, state: FSMContext):
        order_id = int(callback.data.replace("order_reject_reason_", ""))
        order = await get_order(order_id)
        if not order or order["status"] != "pending":
            await callback.answer("این سفارش قبلاً پردازش شده.", show_alert=True)
            return
        await state.update_data(order_id=order_id)
        await state.set_state(AdminAction.waiting_for_rejection_reason)
        await callback.message.reply(
            "✏️ دلیل رد را بنویسید (یا /skip برای رد بدون دلیل):"
        )
        await callback.answer()

    # ─── شارژ حساب ────────────────────────────────

    @dp.callback_query(F.data.startswith("topup_approve_"))
    async def topup_approve(callback: types.CallbackQuery):
        request_id = int(callback.data.replace("topup_approve_", ""))
        req = await get_top_up_request(request_id)
        if not req:
            await callback.answer("درخواست یافت نشد.", show_alert=True)
            return
        approved = await approve_top_up_atomic(request_id)
        if not approved:
            await callback.answer("این درخواست قبلاً پردازش شده.", show_alert=True)
            return
        await get_or_create_user(req["user_id"], "", req["username"])
        await add_balance_and_transaction(req["user_id"], req["amount"], "charge", f"شارژ حساب #{request_id}")
        await callback.message.edit_caption(
            callback.message.caption + f"\n\n✅ <b>تایید شد</b>",
            parse_mode="HTML"
        )
        try:
            await callback.bot.send_message(
                chat_id=req["user_id"],
                text=get_text("topup_approved", amount=f"{req['amount']:,}"),
                parse_mode="HTML"
            )
        except TelegramForbiddenError:
            from bot import logger
            logger.warning(f"کاربر {req['user_id']} بات را بلاک کرده — اطلاعیه شارژ ارسال نشد")
        await callback.answer("شارژ تایید شد.")

    @dp.callback_query(F.data.startswith("topup_reject_"))
    async def topup_reject(callback: types.CallbackQuery):
        request_id = int(callback.data.replace("topup_reject_", ""))
        req = await get_top_up_request(request_id)
        if not req:
            await callback.answer("درخواست یافت نشد.", show_alert=True)
            return
        if req["status"] != "pending":
            await callback.answer("این درخواست قبلاً پردازش شده.", show_alert=True)
            return
        await update_top_up_status(request_id, "rejected")
        await callback.message.edit_caption(
            callback.message.caption + "\n\n❌ <b>رد شد</b>",
            parse_mode="HTML"
        )
        try:
            await callback.bot.send_message(
                chat_id=req["user_id"],
                text=get_text("topup_rejected"),
            )
        except TelegramForbiddenError:
            from bot import logger
            logger.warning(f"کاربر {req['user_id']} بات را بلاک کرده — اطلاعیه رد شارژ ارسال نشد")
        await callback.answer("درخواست رد شد.")

    @dp.message(AdminAction.waiting_for_rejection_reason)
    async def order_reject_with_reason(message: types.Message, state: FSMContext):
        data = await state.get_data()
        order_id = data["order_id"]
        order = await get_order(order_id)

        if not order or order["status"] != "pending":
            await state.clear()
            await message.answer("این سفارش قبلاً پردازش شده.", reply_markup=after_order_keyboard())
            return

        reason = message.text if message.text and message.text != "/skip" else None
        await update_order_status(order_id, "rejected", rejection_reason=reason)
        await state.clear()

        try:
            await message.bot.send_message(
                chat_id=order["user_id"],
                text=get_text("order_rejected_with_reason"),
            )
            if message.text != "/skip":
                await message.copy_to(chat_id=order["user_id"])
        except TelegramForbiddenError:
            from bot import logger
            logger.warning(f"کاربر {order['user_id']} بات را بلاک کرده — اطلاعیه رد سفارش ارسال نشد")

        await message.answer("✅ سفارش رد شد و کاربر مطلع شد.", reply_markup=after_order_keyboard())
