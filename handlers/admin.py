import json
import html as html_lib
import qrcode
from io import BytesIO
from aiogram import types, F
from aiogram.types import BufferedInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from keyboards import admin_main_menu, admin_panel_menu, user_main_menu, after_order_keyboard, subscription_approved_keyboard, admin_topup_keyboard, admin_general_menu, admin_banner_settings_menu, admin_banner_and_text_menu, admin_text_settings_menu
from states import AdminAction, GeneralSettings
from aiogram.filters import Command
from database import (
    get_order, get_plan_with_server, update_order_status, update_order_vpn_info,
    get_top_up_request, update_top_up_status, approve_top_up_atomic,
    add_balance, add_balance_and_transaction, get_or_create_user,
    get_setting, set_setting
)
from rebecca_api import RebeccaAPI

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
        logger.info(f"کاربر {message.from_user.id} دستور /start فرستاد")
        await _send_main_menu(message, message.from_user)

    async def _edit_or_replace(callback: types.CallbackQuery, text: str, markup, parse_mode="HTML"):
        """اگه پیام عکسه، حذف کن و متن جدید بفرست — وگرنه ویرایش کن"""
        try:
            await callback.message.edit_text(text, reply_markup=markup, parse_mode=parse_mode)
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=markup, parse_mode=parse_mode)

    @dp.callback_query(F.data == "admin_panel")
    async def admin_panel(callback: types.CallbackQuery):
        await _edit_or_replace(callback, "⚙️ پنل ادمین", admin_panel_menu())
        await callback.answer()

    @dp.callback_query(F.data.in_({
        "admin_users", "admin_discount", "admin_free_test",
        "admin_referral", "admin_support", "admin_broadcast", "admin_stats"
    }))
    async def admin_coming_soon(callback: types.CallbackQuery):
        await callback.answer("🔜 به زودی...", show_alert=True)

    # ─── تنظیمات عمومی ────────────────────────────
    @dp.callback_query(F.data == "admin_general")
    async def admin_general(callback: types.CallbackQuery):
        await _edit_or_replace(callback, "⚙️ تنظیمات عمومی", admin_general_menu())
        await callback.answer()

    @dp.callback_query(F.data == "admin_banner_and_text")
    async def admin_banner_and_text(callback: types.CallbackQuery):
        await _edit_or_replace(callback, "🎨 ظاهر ربات", admin_banner_and_text_menu())
        await callback.answer()

    @dp.callback_query(F.data == "admin_banner_settings")
    async def admin_banner_settings(callback: types.CallbackQuery):
        banner = await get_setting("banner_file_id")
        status = "✅ بنر فعال است." if banner else "❌ بنر تنظیم نشده."
        await _edit_or_replace(callback, f"🖼 تنظیمات بنر\n\n{status}", admin_banner_settings_menu(has_banner=bool(banner)))
        await callback.answer()

    @dp.callback_query(F.data == "admin_banner_upload")
    async def admin_banner_upload(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(GeneralSettings.waiting_for_banner)
        await callback.message.edit_text("🖼 عکس بنر را ارسال کنید:")
        await callback.answer()

    @dp.message(GeneralSettings.waiting_for_banner, F.photo)
    async def admin_banner_save(message: types.Message, state: FSMContext):
        file_id = message.photo[-1].file_id
        await set_setting("banner_file_id", file_id)
        await state.clear()
        await message.answer("✅ بنر ذخیره شد.", reply_markup=admin_banner_settings_menu(has_banner=True))

    @dp.callback_query(F.data == "admin_banner_delete")
    async def admin_banner_delete(callback: types.CallbackQuery):
        await set_setting("banner_file_id", "")
        await _edit_or_replace(callback, "🖼 تنظیمات بنر\n\n❌ بنر تنظیم نشده.", admin_banner_settings_menu(has_banner=False))
        await callback.answer("🗑 بنر حذف شد.")

    @dp.callback_query(F.data == "admin_text_settings")
    async def admin_text_settings(callback: types.CallbackQuery):
        await _edit_or_replace(callback, "✏️ تنظیمات متن", admin_text_settings_menu())
        await callback.answer()

    @dp.callback_query(F.data == "admin_banner_caption")
    async def admin_banner_caption_start(callback: types.CallbackQuery, state: FSMContext):
        current = await get_setting("banner_caption") or ""
        text = (
            "✏️ متن فعلی بنر:\n"
            f"<code>{current or '(پیش‌فرض)'}</code>\n\n"
            "متن جدید را ارسال کنید.\n"
            "می‌توانید از <code>{name}</code> برای نام کاربر استفاده کنید."
        )
        await state.set_state(GeneralSettings.waiting_for_caption)
        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()

    @dp.message(GeneralSettings.waiting_for_caption, F.text)
    async def admin_banner_caption_save(message: types.Message, state: FSMContext):
        await set_setting("banner_caption", message.text.strip())
        await state.clear()
        await message.answer("✅ متن بنر ذخیره شد.", reply_markup=admin_text_settings_menu())

    @dp.callback_query(F.data == "admin_build_text")
    async def admin_build_text_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(GeneralSettings.waiting_for_emoji_text)
        await callback.message.edit_text(
            "🛠 پیام خود را همراه با استیکر پرمیوم ارسال کنید.\n"
            "ربات اموجی‌ها را با تگ HTML جایگزین می‌کند."
        )
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

        # پیام اول: پیش‌نمایش واقعی با اموجی پرمیوم
        await message.answer(f"✅ پیش‌نمایش:\n\n{result}", parse_mode="HTML")
        # پیام دوم: متن خام برای کپی (escape می‌کنیم تا تگ‌ها به صورت متن نمایش داده شن)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
        copy_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 کپی متن", copy_text=CopyTextButton(text=result))],
        ])
        await message.answer(f"<code>{html_lib.escape(result)}</code>", parse_mode="HTML", reply_markup=copy_kb)
        await message.answer("⬆️", reply_markup=admin_text_settings_menu())

    @dp.callback_query(F.data == "back_to_start")
    async def back_to_start(callback: types.CallbackQuery):
        from handlers.user import _send_main_menu
        await _send_main_menu(callback, callback.from_user)

    @dp.callback_query(F.data == "cancel")
    async def cancel_operation(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await _edit_or_replace(callback, "❌ عملیات لغو شد.", admin_panel_menu())
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

            # سرویس‌های زنده رو از پنل می‌گیریم و اولین ID معتبر رو انتخاب می‌کنیم
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

        await callback.message.edit_caption(
            callback.message.caption + f"\n\n✅ <b>تایید شد</b> — یوزر: <code>{username}</code>",
            parse_mode="HTML",
            reply_markup=after_order_keyboard()
        )
        qr_file = _make_qr(subscription_url)
        await callback.bot.send_photo(
            chat_id=order["user_id"],
            photo=qr_file,
            caption=(
                f"✅ <b>سفارش شما تایید شد!</b>\n\n"
                f"🔗 لینک اشتراک:\n<code>{subscription_url}</code>\n\n"
                f"لینک را در اپلیکیشن VPN وارد کنید یا QR Code را اسکن کنید."
            ),
            reply_markup=subscription_approved_keyboard(subscription_url),
            parse_mode="HTML"
        )
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
        await callback.bot.send_message(
            chat_id=order["user_id"],
            text="❌ متأسفانه سفارش شما تایید نشد.\nدر صورت نیاز با پشتیبانی تماس بگیرید."
        )
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
        await callback.bot.send_message(
            chat_id=req["user_id"],
            text=f"✅ <b>شارژ حساب تایید شد!</b>\n\n💰 مبلغ <b>{req['amount']:,} تومان</b> به کیف پول شما اضافه شد.",
            parse_mode="HTML"
        )
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
        await callback.bot.send_message(
            chat_id=req["user_id"],
            text="❌ متأسفانه درخواست شارژ حساب شما تایید نشد.\nدر صورت نیاز با پشتیبانی تماس بگیرید."
        )
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

        await message.bot.send_message(
            chat_id=order["user_id"],
            text="❌ متأسفانه سفارش شما تایید نشد."
        )
        if message.text != "/skip":
            await message.copy_to(chat_id=order["user_id"])

        await message.answer("✅ سفارش رد شد و کاربر مطلع شد.", reply_markup=after_order_keyboard())
