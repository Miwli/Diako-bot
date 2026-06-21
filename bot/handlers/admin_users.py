import math
from datetime import datetime
import jdatetime
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from states import AdminUserManagement
from keyboards import admin_users_menu, admin_user_list_keyboard, admin_user_profile_keyboard
from shared_lib.db import (
    get_user, get_users_paginated, get_users_count, search_users,
    ban_user, unban_user, admin_adjust_balance,
    get_user_wallet_stats, get_transactions, get_free_test_uses,
    get_user_ticket_counts, get_user_order_counts, get_referral_stats,
    get_referral_by_referred, get_user_by_referral_code,
    get_user_services, decrement_free_test_uses,
)

_FILTER_LABELS = {
    "newest":    "🕐 جدیدترین‌ها",
    "topbuyers": "🏆 بیشترین خرید",
    "banned":    "🚫 بن‌شده‌ها",
}

def _jalali(dt_str: str) -> str:
    if not dt_str:
        return "نامشخص"
    try:
        dt = datetime.fromisoformat(dt_str)
        return jdatetime.datetime.fromgregorian(datetime=dt).strftime("%-d %B %Y")
    except Exception:
        return dt_str

def _cancel_kb(back_cb: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 انصراف", callback_data=back_cb)]
    ])

async def _build_profile_text(user) -> str:
    uid = user["user_id"]
    name = user["first_name"] or "—"
    uname = f"@{user['username']}" if user["username"] else "ندارد"
    joined = _jalali(user["created_at"])
    status = "🚫 بن‌شده" if user["is_banned"] else "✅ فعال"
    balance = user["balance"] or 0

    order_counts = await get_user_order_counts(uid)
    approved = order_counts.get("approved", 0)
    pending  = order_counts.get("pending", 0)
    rejected = order_counts.get("rejected", 0)

    tickets_open, tickets_closed = await get_user_ticket_counts(uid)

    free_uses = await get_free_test_uses(uid)

    ref_stats = await get_referral_stats(uid)
    referral = await get_referral_by_referred(uid)
    referrer_text = "ندارد"
    if referral:
        referrer = await get_user(referral["referrer_id"])
        if referrer:
            rname = referrer["first_name"] or str(referral["referrer_id"])
            runame = f" (@{referrer['username']})" if referrer["username"] else ""
            referrer_text = f"{rname}{runame}"

    tx_count = len(await get_transactions(uid, limit=100))

    lines = [
        f"👤 <b>پروفایل کاربر</b>",
        f"",
        f"🆔 آیدی: <code>{uid}</code>",
        f"👤 نام: {name}",
        f"📱 یوزرنیم: {uname}",
        f"📅 عضویت: {joined}",
        f"🚦 وضعیت: {status}",
        f"",
        f"💰 موجودی: <b>{balance:,} تومان</b>",
        f"📜 تراکنش‌ها: {tx_count} مورد",
        f"",
        f"📦 سفارش‌ها: {approved} تایید | {pending} در انتظار | {rejected} رد",
        f"🎧 تیکت‌ها: {tickets_open} باز | {tickets_closed} بسته",
        f"🎁 تست رایگان: {free_uses} بار استفاده",
        f"",
        f"🤝 رفرال:",
        f"  └ معرف: {referrer_text}",
        f"  └ دعوت‌شدگان: {ref_stats['count']} نفر | درآمد: {ref_stats['total']:,} تومان",
    ]
    return "\n".join(lines)

async def _show_profile(target, user_id: int, bot=None):
    """نمایش پروفایل کاربر — target می‌تونه callback یا message باشه"""
    user = await get_user(user_id)
    if not user:
        if hasattr(target, "answer"):
            await target.answer("کاربر پیدا نشد.", show_alert=True)
        return

    text = await _build_profile_text(user)
    kb   = admin_user_profile_keyboard(user_id, bool(user["is_banned"]))

    if isinstance(target, types.CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            await target.message.delete()
            await target.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")

def register_admin_users_handlers(dp):

    # ─── منوی اصلی ────────────────────────────────

    @dp.callback_query(F.data == "admin_users")
    async def admin_users_main(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        try:
            await callback.message.edit_text("👥 <b>مدیریت کاربران</b>", reply_markup=admin_users_menu(), parse_mode="HTML")
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer("👥 <b>مدیریت کاربران</b>", reply_markup=admin_users_menu(), parse_mode="HTML")
        await callback.answer()

    @dp.callback_query(F.data == "noop")
    async def noop(callback: types.CallbackQuery):
        await callback.answer()

    # ─── لیست با فیلتر و صفحه‌بندی ────────────────

    @dp.callback_query(F.data.startswith("admin_ul_"))
    async def admin_user_list(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        parts = callback.data.split("_")
        # admin_ul_{filter}_{page}
        page        = int(parts[-1])
        filter_type = parts[-2]

        users = await get_users_paginated(page, filter_type)
        total = await get_users_count(filter_type)
        label = _FILTER_LABELS.get(filter_type, "کاربران")

        if not users:
            await callback.answer("کاربری یافت نشد.", show_alert=True)
            return

        text = f"👥 <b>{label}</b>\n\nتعداد کل: {total} کاربر"
        kb   = admin_user_list_keyboard(users, page, filter_type, total)
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

    # ─── جستجو ────────────────────────────────────

    @dp.callback_query(F.data == "admin_users_search")
    async def admin_users_search_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(AdminUserManagement.waiting_for_search_query)
        try:
            await callback.message.edit_text(
                "🔍 <b>جستجوی کاربر</b>\n\nآیدی عددی یا یوزرنیم (@username) وارد کنید:",
                reply_markup=_cancel_kb("admin_users"),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(
                "🔍 <b>جستجوی کاربر</b>\n\nآیدی عددی یا یوزرنیم (@username) وارد کنید:",
                reply_markup=_cancel_kb("admin_users"),
                parse_mode="HTML"
            )
        await callback.answer()

    @dp.message(AdminUserManagement.waiting_for_search_query, F.text)
    async def admin_users_search_execute(message: types.Message, state: FSMContext):
        query = message.text.strip()
        results = await search_users(query)
        await state.clear()

        if not results:
            await message.answer(
                f"❌ کاربری با «{query}» پیدا نشد.",
                reply_markup=_cancel_kb("admin_users")
            )
            return

        if len(results) == 1:
            await _show_profile(message, results[0]["user_id"])
            return

        rows = []
        for u in results[:20]:
            mark  = "🚫 " if u["is_banned"] else ""
            name  = u["first_name"] or ""
            uname = f" (@{u['username']})" if u["username"] else ""
            rows.append([InlineKeyboardButton(
                text=f"{mark}{name}{uname}",
                callback_data=f"admin_up_{u['user_id']}"
            )])
        rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_users")])
        await message.answer(
            f"🔍 {len(results)} نتیجه برای «{query}»:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            parse_mode="HTML"
        )

    # ─── پروفایل کاربر ────────────────────────────

    @dp.callback_query(F.data.startswith("admin_up_"))
    async def admin_user_profile(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        user_id = int(callback.data.replace("admin_up_", ""))
        await _show_profile(callback, user_id)

    # ─── افزودن موجودی ────────────────────────────

    @dp.callback_query(F.data.startswith("admin_ua_addbal_"))
    async def admin_add_balance_start(callback: types.CallbackQuery, state: FSMContext):
        user_id = int(callback.data.replace("admin_ua_addbal_", ""))
        await state.set_state(AdminUserManagement.waiting_for_add_amount)
        await state.update_data(uid=user_id)
        user = await get_user(user_id)
        name = user["first_name"] if user else str(user_id)
        await callback.message.edit_text(
            f"➕ مبلغ افزودن به موجودی <b>{name}</b> را به تومان وارد کنید:",
            reply_markup=_cancel_kb(f"admin_up_{user_id}"),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(AdminUserManagement.waiting_for_add_amount, F.text)
    async def admin_add_balance_save(message: types.Message, state: FSMContext):
        text = message.text.strip().replace(",", "")
        if not text.isdigit() or int(text) <= 0:
            await message.answer("❌ عدد صحیح مثبت وارد کنید.")
            return
        data = await state.get_data()
        uid  = data["uid"]
        await admin_adjust_balance(uid, int(text), "افزودن دستی توسط ادمین")
        await state.clear()
        await message.answer(f"✅ <b>{int(text):,} تومان</b> به حساب کاربر اضافه شد.", parse_mode="HTML")
        await _show_profile(message, uid)

    # ─── کسر موجودی ───────────────────────────────

    @dp.callback_query(F.data.startswith("admin_ua_dedbal_"))
    async def admin_deduct_balance_start(callback: types.CallbackQuery, state: FSMContext):
        user_id = int(callback.data.replace("admin_ua_dedbal_", ""))
        await state.set_state(AdminUserManagement.waiting_for_deduct_amount)
        await state.update_data(uid=user_id)
        user = await get_user(user_id)
        name = user["first_name"] if user else str(user_id)
        await callback.message.edit_text(
            f"➖ مبلغ کسر از موجودی <b>{name}</b> را به تومان وارد کنید:",
            reply_markup=_cancel_kb(f"admin_up_{user_id}"),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(AdminUserManagement.waiting_for_deduct_amount, F.text)
    async def admin_deduct_balance_save(message: types.Message, state: FSMContext):
        text = message.text.strip().replace(",", "")
        if not text.isdigit() or int(text) <= 0:
            await message.answer("❌ عدد صحیح مثبت وارد کنید.")
            return
        data = await state.get_data()
        uid  = data["uid"]
        await admin_adjust_balance(uid, -int(text), "کسر دستی توسط ادمین")
        await state.clear()
        await message.answer(f"✅ <b>{int(text):,} تومان</b> از حساب کاربر کسر شد.", parse_mode="HTML")
        await _show_profile(message, uid)

    # ─── بن کردن ──────────────────────────────────

    @dp.callback_query(F.data.startswith("admin_ua_ban_"))
    async def admin_ban_start(callback: types.CallbackQuery, state: FSMContext):
        user_id = int(callback.data.replace("admin_ua_ban_", ""))
        await state.set_state(AdminUserManagement.waiting_for_ban_reason)
        await state.update_data(uid=user_id)
        user = await get_user(user_id)
        name = user["first_name"] if user else str(user_id)
        await callback.message.edit_text(
            f"🚫 دلیل بن کردن <b>{name}</b> را بنویسید:\n<i>(برای رد کردن، «—» بفرستید)</i>",
            reply_markup=_cancel_kb(f"admin_up_{user_id}"),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(AdminUserManagement.waiting_for_ban_reason, F.text)
    async def admin_ban_save(message: types.Message, state: FSMContext):
        reason = "" if message.text.strip() == "—" else message.text.strip()
        data   = await state.get_data()
        uid    = data["uid"]
        await ban_user(uid)
        await state.clear()
        await message.answer(f"✅ کاربر بن شد." + (f"\nدلیل: {reason}" if reason else ""), parse_mode="HTML")
        try:
            await message.bot.send_message(uid, "⛔️ دسترسی شما به ربات محدود شده است.")
        except (TelegramForbiddenError, TelegramBadRequest):
            pass
        await _show_profile(message, uid)

    # ─── آنبن کردن ────────────────────────────────

    @dp.callback_query(F.data.startswith("admin_ua_unban_"))
    async def admin_unban(callback: types.CallbackQuery):
        user_id = int(callback.data.replace("admin_ua_unban_", ""))
        await unban_user(user_id)
        try:
            await callback.bot.send_message(user_id, "✅ دسترسی شما به ربات بازگردانده شد.")
        except (TelegramForbiddenError, TelegramBadRequest):
            pass
        await _show_profile(callback, user_id)

    # ─── ارسال پیام مستقیم ────────────────────────

    @dp.callback_query(F.data.startswith("admin_ua_msg_"))
    async def admin_direct_msg_start(callback: types.CallbackQuery, state: FSMContext):
        user_id = int(callback.data.replace("admin_ua_msg_", ""))
        await state.set_state(AdminUserManagement.waiting_for_direct_msg)
        await state.update_data(uid=user_id)
        user = await get_user(user_id)
        name = user["first_name"] if user else str(user_id)
        await callback.message.edit_text(
            f"📨 پیام خود را برای <b>{name}</b> بنویسید:",
            reply_markup=_cancel_kb(f"admin_up_{user_id}"),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(AdminUserManagement.waiting_for_direct_msg, F.text)
    async def admin_direct_msg_send(message: types.Message, state: FSMContext):
        data = await state.get_data()
        uid  = data["uid"]
        await state.clear()
        try:
            await message.bot.send_message(
                uid,
                f"📨 <b>پیام از پشتیبانی:</b>\n\n{message.text}",
                parse_mode="HTML"
            )
            await message.answer("✅ پیام ارسال شد.")
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            await message.answer(f"❌ ارسال ناموفق: {e}")
        await _show_profile(message, uid)

    # ─── اعطای تست رایگان ─────────────────────────

    @dp.callback_query(F.data.startswith("admin_ua_freetest_"))
    async def admin_grant_free_test(callback: types.CallbackQuery):
        user_id = int(callback.data.replace("admin_ua_freetest_", ""))
        await decrement_free_test_uses(user_id)
        await callback.answer("✅ یک تست رایگان اضافه شد.", show_alert=True)
        await _show_profile(callback, user_id)

    # ─── لیست سرویس‌های کاربر ─────────────────────

    @dp.callback_query(F.data.startswith("admin_ua_services_"))
    async def admin_user_services(callback: types.CallbackQuery):
        user_id = int(callback.data.replace("admin_ua_services_", ""))
        services = await get_user_services(user_id)
        if not services:
            await callback.answer("این کاربر سرویسی ندارد.", show_alert=True)
            return

        lines = [f"📋 <b>سرویس‌های کاربر {user_id}</b>\n"]
        for s in services:
            st = s.get("status", "")
            emoji = "✅" if st == "approved" else "❌"
            uname = s.get("vpn_username") or "—"
            plan  = s.get("plan_name") or "—"
            lines.append(f"{emoji} {plan} — <code>{uname}</code>")

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"admin_up_{user_id}")]
        ])
        try:
            await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer("\n".join(lines), reply_markup=kb, parse_mode="HTML")
        await callback.answer()
