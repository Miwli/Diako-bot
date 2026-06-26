from datetime import datetime, timezone, timedelta
import jdatetime
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import BuyVPN, TopUp
from keyboards import (
    user_main_menu, user_servers_keyboard, user_services_keyboard,
    user_plans_keyboard, proforma_keyboard, payment_info_keyboard,
    user_service_detail_keyboard, confirm_delete_service_keyboard,
    wallet_keyboard, admin_topup_keyboard,
    free_test_servers_keyboard, free_test_confirm_keyboard
)
from shared_lib.db import (
    get_servers, get_plans, get_plan, get_plan_with_server, get_setting, set_setting, create_order,
    get_user_services, get_user_service, update_order_status, update_order_vpn_info,
    get_or_create_user, get_user, get_user_wallet_stats, get_transactions,
    add_balance, add_balance_and_transaction, deduct_balance_if_sufficient,
    create_top_up_request, get_top_up_request, update_top_up_status,
    get_free_test_servers, create_free_test_order,
    get_free_test_uses, increment_free_test_uses,
    get_text, get_keyboard_buttons,
)
from rebecca_api import RebeccaAPI

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

TEHRAN = timezone(timedelta(hours=3, minutes=30))


async def _get_main_menu(user_id: int):
    """منوی اصلی رو از DB می‌خونه و برمی‌گردونه"""
    from bot import is_admin
    from keyboards import admin_main_menu
    rows = await get_keyboard_buttons("user_main")
    return admin_main_menu(rows) if is_admin(user_id) else user_main_menu(rows)

async def _edit_or_replace(callback: types.CallbackQuery, text: str, markup, parse_mode="HTML"):
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode=parse_mode)
    except TelegramBadRequest:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=markup, parse_mode=parse_mode)

def _to_jalali(dt_source) -> str:
    try:
        if isinstance(dt_source, str):
            dt = datetime.strptime(dt_source, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        elif isinstance(dt_source, (int, float)) and dt_source > 0:
            dt = datetime.fromtimestamp(dt_source, tz=timezone.utc)
        else:
            return "نامحدود"
        jdt = jdatetime.datetime.fromgregorian(datetime=dt.astimezone(TEHRAN))
        return jdt.strftime("%Y/%m/%d")
    except Exception:
        return "نامشخص"

def _fmt_gb(b: int) -> str:
    return f"{b / (1024 ** 3):.1f} گیگابایت"

def _service_text(order, live=None) -> str:
    STATUS_MAP = {
        "active":   get_text("status_active"),
        "expired":  get_text("status_expired"),
        "limited":  get_text("status_limited"),
        "disabled": get_text("status_disabled"),
    }
    status = STATUS_MAP.get(live.get("status", ""), get_text("status_unknown")) if live else get_text("service_no_live")

    parts = [
        f"📡 وضعیت : {status}",
        "",
        f"🔐 نام سرویس : <code>{order['vpn_username']}</code>",
        f"🖥 سرور : {order['server_name']}",
        f"📦 پلن : {order['plan_name']}",
    ]

    if live:
        data_limit = live.get("data_limit") or 0
        used = live.get("used_traffic") or 0
        parts += ["", "━━━━━━━━━━━━━━━━━━━━━━━━"]
        if data_limit:
            remaining = max(0, data_limit - used)
            pct = int(used / data_limit * 100)
            parts += [
                f"📊 ترافیک : {_fmt_gb(data_limit)}",
                f"📉 مصرف شده : {_fmt_gb(used)} ({pct}٪)",
                f"📈 باقی‌مانده : {_fmt_gb(remaining)}",
            ]
        else:
            parts.append(get_text("service_traffic_unlimited"))
        parts.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        expire = live.get("expire")
        parts.append(f"📅 انقضا : {_to_jalali(expire) if expire else get_text('service_expire_unlimited')}")

    parts.append(f"🗓 خرید : {_to_jalali(order['created_at'])}")
    return "\n".join(parts)

async def _send_main_menu(target, user: types.User):
    from bot import logger
    menu = await _get_main_menu(user.id)
    name = user.first_name or "کاربر"
    caption = get_text("start_welcome_default", name=name)
    banner = await get_setting("banner_file_id")

    async def _send(msg, is_cb=False):
        try:
            if banner:
                await msg.answer_photo(photo=banner, caption=caption, reply_markup=menu, parse_mode="HTML", protect_content=True)
            else:
                await msg.answer(caption, reply_markup=menu, parse_mode="HTML")
        except TelegramBadRequest as e:
            logger.error(f"خطا در ارسال منوی اصلی (HTML): {e} — متن: {caption[:80]!r}")
            import re as _re
            plain = _re.sub(r'<[^>]+>', '', caption)
            await msg.answer(plain, reply_markup=menu)

    try:
        if isinstance(target, types.CallbackQuery):
            try:
                await target.message.delete()
            except Exception:
                pass
            await _send(target.message)
            await target.answer()
        else:
            await _send(target)
    except TelegramForbiddenError:
        logger.warning(f"کاربر {user.id} بات را بلاک کرده — ارسال منو لغو شد")

def register_user_handlers(dp):

    @dp.callback_query(F.data.in_({"language"}))
    async def coming_soon(callback: types.CallbackQuery):
        await callback.answer("🔜 به زودی...", show_alert=True)

    # ─── تست رایگان ──────────────────────────────

    def _fmt_dur(val) -> str:
        return "♾️ بی‌نهایت" if float(val or 0) == 0 else f"{val} ساعت"

    def _fmt_trf(val) -> str:
        return "♾️ بی‌نهایت" if float(val or 0) == 0 else f"{val} گیگابایت"

    async def _check_free_test_eligibility(user_id: int):
        """بررسی واجد شرایط بودن — (ok, reason)"""
        max_uses = int(await get_setting("free_test_max_uses") or "1")
        uses = await get_free_test_uses(user_id)
        if max_uses != 0 and uses >= max_uses:
            return False, get_text("free_test_max_uses")
        return True, None

    @dp.callback_query(F.data == "free_test")
    async def free_test_start(callback: types.CallbackQuery):
        u = callback.from_user
        ok, reason = await _check_free_test_eligibility(u.id)
        if not ok:
            await callback.answer(f"❌ {reason}", show_alert=True)
            return

        servers = await get_free_test_servers()
        if not servers:
            await callback.answer(get_text("free_test_unavailable"), show_alert=True)
            return

        if len(servers) == 1:
            await _show_free_test_confirm(callback, servers[0])
        else:
            await _edit_or_replace(
                callback,
                "🎁 <b>تست رایگان</b>\n\nسرور مورد نظر را انتخاب کنید:",
                free_test_servers_keyboard(servers)
            )
        await callback.answer()

    @dp.callback_query(F.data.startswith("free_test_server_"))
    async def free_test_select_server(callback: types.CallbackQuery):
        server_id = int(callback.data.replace("free_test_server_", ""))
        ok, reason = await _check_free_test_eligibility(callback.from_user.id)
        if not ok:
            await callback.answer(f"❌ {reason}", show_alert=True)
            return
        from shared_lib.db import get_server
        server = await get_server(server_id)
        if not server or not server["free_test_enabled"]:
            await callback.answer(get_text("free_test_server_unavailable"), show_alert=True)
            return
        await _show_free_test_confirm(callback, server)
        await callback.answer()

    async def _show_free_test_confirm(callback, server):
        dur = _fmt_dur(server["free_test_duration"])
        trf = _fmt_trf(server["free_test_traffic"])
        text = (
            f"🎁 <b>تست رایگان</b>\n"
            f"{'─' * 24}\n"
            f"🖥 سرور: <b>{server['name']}</b>\n"
            f"⏱ مدت: <b>{dur}</b>\n"
            f"📊 حجم: <b>{trf}</b>\n"
            f"{'─' * 24}\n\n"
            "با زدن دکمه زیر سرویس تست برات ساخته می‌شه:"
        )
        await _edit_or_replace(callback, text, free_test_confirm_keyboard(server["id"]))

    @dp.callback_query(F.data.startswith("free_test_confirm_"))
    async def free_test_confirm(callback: types.CallbackQuery):
        from handlers.admin import _make_qr
        from keyboards import subscription_approved_keyboard
        import json

        server_id = int(callback.data.replace("free_test_confirm_", ""))
        u = callback.from_user

        ok, reason = await _check_free_test_eligibility(u.id)
        if not ok:
            await callback.answer(f"❌ {reason}", show_alert=True)
            return

        from shared_lib.db import get_server
        server = await get_server(server_id)
        if not server or not server["free_test_enabled"] or not server["is_active"]:
            await callback.answer(get_text("free_test_server_unavailable"), show_alert=True)
            return

        service_ids = json.loads(server["service_ids"] or "[]")
        if not service_ids:
            await callback.answer(get_text("free_test_no_service_config"), show_alert=True)
            return

        await callback.answer()
        await callback.message.edit_text(get_text("free_test_creating"))

        try:
            api = RebeccaAPI(server["panel_url"], server["panel_token"])

            live_services = await api.get_services()
            live_ids = {s["id"] for s in live_services}
            service_id = next((sid for sid in service_ids if sid in live_ids), None)
            if service_id is None:
                await callback.message.edit_text(
                    get_text("free_test_error_no_service"),
                    reply_markup=free_test_confirm_keyboard(server_id)
                )
                return

            user_data = await api.create_user(
                service_id=service_id,
                data_limit_gb=float(server["free_test_traffic"] or 0),
                duration_hours=float(server["free_test_duration"] or 0),
            )
            sub_path = user_data.get("subscription_url", "")
            subscription_url = await api.get_subscription_url(sub_path)
            username = user_data.get("username", "")
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در ساخت تست رایگان برای سرور #{server_id}: {e}")
            await callback.message.edit_text(
                get_text("free_test_error_api", error=str(e)),
                reply_markup=free_test_confirm_keyboard(server_id),
                parse_mode="HTML"
            )
            return

        await get_or_create_user(u.id, u.first_name, u.username)
        order_id = await create_free_test_order(u.id, u.username or u.first_name, server_id)
        await update_order_status(order_id, "approved")
        await update_order_vpn_info(order_id, username, subscription_url)
        await increment_free_test_uses(u.id)

        qr_file = _make_qr(subscription_url)
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=qr_file,
            caption=get_text("free_test_success", server=server['name'], url=subscription_url),
            reply_markup=subscription_approved_keyboard(subscription_url),
            parse_mode="HTML"
        )

    # ─── پروفایل ──────────────────────────────────

    @dp.callback_query(F.data == "profile")
    async def profile_page(callback: types.CallbackQuery):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        u = callback.from_user
        user = await get_or_create_user(u.id, u.first_name, u.username)
        stats = await get_user_wallet_stats(u.id)
        username_line = f"📱 یوزرنیم : @{u.username}" if u.username else "📱 یوزرنیم : —"
        text = (
            f"👤 {u.first_name}\n\n"
            f"{'━' * 24}\n"
            f"🆔 آیدی تلگرام : <code>{u.id}</code>\n"
            f"{username_line}\n"
            f"📅 تاریخ عضویت : {_to_jalali(user['created_at'])}\n"
            f"💰 موجودی : <b>{stats['balance']:,} تومان</b>\n"
            f"🎫 کد معرف : <code>{user['referral_code']}</code>\n"
            f"{'━' * 24}"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="user_main")],
        ])
        await _edit_or_replace(callback, text, kb)
        await callback.answer()

    # ─── شارژ حساب ────────────────────────────────

    @dp.callback_query(F.data == "top_up")
    async def top_up_start(callback: types.CallbackQuery, state: FSMContext):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="wallet")],
        ])
        await _edit_or_replace(callback, get_text("topup_prompt"), kb)
        await state.set_state(TopUp.waiting_for_amount)
        await callback.answer()

    @dp.message(TopUp.waiting_for_amount, F.text)
    async def top_up_amount(message: types.Message, state: FSMContext):
        raw = message.text.strip().replace(",", "").replace("،", "")
        if not raw.isdigit() or int(raw) < 10000:
            await message.answer(get_text("topup_invalid_amount"), parse_mode="HTML")
            return
        amount = int(raw)
        await state.update_data(amount=amount)
        card_number = await get_setting("card_number")
        card_owner  = await get_setting("card_owner")
        await message.answer(
            f"💳 <b>اطلاعات پرداخت</b>\n\n"
            f"مبلغ: <b>{amount:,} تومان</b>\n\n"
            f"شماره کارت:\n<code>{card_number or '—'}</code>\n"
            f"به نام: <b>{card_owner or '—'}</b>\n\n"
            "بعد از واریز، تصویر رسید را ارسال کنید.",
            parse_mode="HTML"
        )
        await state.set_state(TopUp.waiting_for_receipt)

    @dp.message(TopUp.waiting_for_receipt)
    async def top_up_receipt(message: types.Message, state: FSMContext):
        if not message.photo:
            await message.answer(get_text("topup_not_photo"))
            return
        data = await state.get_data()
        amount = data["amount"]
        u = message.from_user
        await get_or_create_user(u.id, u.first_name, u.username)
        file_id = message.photo[-1].file_id
        request_id = await create_top_up_request(u.id, u.username, amount, file_id)
        await state.clear()

        from bot import ADMIN_IDS
        caption = (
            f"💳 <b>درخواست شارژ حساب</b>\n\n"
            f"👤 کاربر: {u.full_name}"
            + (f" (@{u.username})" if u.username else "") +
            f"\n🆔 آیدی: <code>{u.id}</code>\n"
            f"💰 مبلغ: <b>{amount:,} تومان</b>\n"
            f"🔖 شماره درخواست: #{request_id}"
        )
        for admin_id in ADMIN_IDS:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=caption,
                reply_markup=admin_topup_keyboard(request_id),
                parse_mode="HTML"
            )
        await message.answer(get_text("topup_submitted"), reply_markup=wallet_keyboard())

    # ─── کیف پول ──────────────────────────────────

    @dp.callback_query(F.data == "wallet")
    async def wallet_page(callback: types.CallbackQuery):
        u = callback.from_user
        await get_or_create_user(u.id, u.first_name, u.username)
        stats = await get_user_wallet_stats(u.id)
        name = u.first_name or "کاربر"
        text = (
            f"👤 {name} عزیز\n\n"
            f"{'━' * 24}\n"
            f"💰 موجودی\n"
            f"<b>{stats['balance']:,} تومان</b>\n"
            f"{'━' * 24}\n\n"
            f"🛒 سرویس‌های خریداری‌شده    <b>{stats['services']}</b> عدد\n"
            f"📑 فاکتورهای پرداخت‌شده     <b>{stats['invoices']}</b> عدد"
        )
        await _edit_or_replace(callback, text, wallet_keyboard())
        await callback.answer()

    @dp.callback_query(F.data == "wallet_history")
    async def wallet_history(callback: types.CallbackQuery):
        txs = await get_transactions(callback.from_user.id)
        if not txs:
            await callback.answer(get_text("wallet_no_transactions"), show_alert=True)
            return
        lines = ["📜 <b>تاریخچه تراکنش‌ها</b>\n" + "━" * 24]
        for tx in txs:
            icon = "➕" if tx["amount"] > 0 else "➖"
            lines.append(
                f"{icon} {abs(tx['amount']):,} تومان\n"
                f"   {tx['description'] or ''}\n"
                f"   📅 {_to_jalali(tx['created_at'])}"
            )
        text = "\n" + "━" * 24 + "\n"
        text = lines[0] + ("\n" + "─" * 24 + "\n").join([""] + lines[1:])
        await _edit_or_replace(callback, text, wallet_keyboard())
        await callback.answer()

    @dp.callback_query(F.data == "buy_vpn")
    async def buy_vpn(callback: types.CallbackQuery):
        servers = await get_servers(only_active=True)
        if not servers:
            await callback.message.edit_text(get_text("buy_no_servers"), reply_markup=await _get_main_menu(callback.from_user.id))
            await callback.answer()
            return

        if len(servers) == 1:
            await show_plans(callback, servers[0]["id"], multiple_servers=False)
        else:
            await callback.message.edit_text(
                get_text("buy_select_server"),
                reply_markup=user_servers_keyboard(servers)
            )
        await callback.answer()

    @dp.callback_query(F.data.startswith("user_server_"))
    async def user_select_server(callback: types.CallbackQuery):
        server_id = int(callback.data.replace("user_server_", ""))
        await show_plans(callback, server_id, multiple_servers=True)
        await callback.answer()

    @dp.callback_query(F.data == "user_main")
    async def user_main(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await _send_main_menu(callback, callback.from_user)

    @dp.callback_query(F.data == "my_services")
    async def my_services(callback: types.CallbackQuery):
        orders = await get_user_services(callback.from_user.id)
        if not orders:
            await _edit_or_replace(callback, get_text("services_empty"), user_services_keyboard([]))
        else:
            await _edit_or_replace(callback, get_text("services_header"), user_services_keyboard(orders))
        await callback.answer()

    @dp.callback_query(F.data.startswith("my_service_"))
    async def my_service_detail(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("my_service_", ""))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer(get_text("service_not_found"), show_alert=True)
            return

        await callback.answer()
        live = None
        try:
            api = RebeccaAPI(order["panel_url"], order["panel_token"])
            live = await api.get_user(order["vpn_username"])
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در دریافت اطلاعات سرویس {order['vpn_username']}: {e}")

        await _edit_or_replace(
            callback,
            _service_text(order, live),
            user_service_detail_keyboard(order_id, order["subscription_url"])
        )

    @dp.callback_query(F.data.startswith("renew_service_"))
    async def renew_service(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("renew_service_", ""))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer(get_text("service_not_found"), show_alert=True)
            return
        if order["order_type"] == "free_test":
            await callback.answer(get_text("renew_free_test_error"), show_alert=True)
            return
        plan = await get_plan(order["plan_id"])
        if not plan:
            await callback.answer(get_text("renew_no_server"), show_alert=True)
            return
        plans = await get_plans(plan["server_id"], only_active=True)
        if not plans:
            await callback.answer(get_text("renew_no_plans"), show_alert=True)
            return
        show_price = (await get_setting("show_plan_price")) == "1"
        await _edit_or_replace(
            callback,
            get_text("renew_prompt"),
            user_plans_keyboard(plans, plan["server_id"], multiple_servers=False, show_price=show_price)
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("delete_service_"))
    async def ask_delete_service(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("delete_service_", ""))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer(get_text("service_not_found"), show_alert=True)
            return
        await _edit_or_replace(
            callback,
            get_text("delete_confirm", name=order['vpn_username']),
            confirm_delete_service_keyboard(order_id)
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("confirmed_delete_service_"))
    async def do_delete_service(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("confirmed_delete_service_", ""))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer(get_text("service_not_found"), show_alert=True)
            return
        await callback.answer()
        try:
            api = RebeccaAPI(order["panel_url"], order["panel_token"])
            await api.delete_user(order["vpn_username"])
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در حذف سرویس {order['vpn_username']}: {e}")
            await callback.message.answer(get_text("delete_error", error=str(e)))
            return
        await update_order_status(order_id, "deleted")
        orders = await get_user_services(callback.from_user.id)
        if orders:
            await _edit_or_replace(callback, get_text("delete_done_has_more"), user_services_keyboard(orders))
        else:
            await _edit_or_replace(callback, get_text("delete_done_empty"), user_services_keyboard([]))

    @dp.callback_query(F.data.startswith("sub_link_"))
    async def send_sub_link(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("sub_link_", ""))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order or not order["subscription_url"]:
            await callback.answer(get_text("sublink_unavailable"), show_alert=True)
            return
        await callback.message.answer(
            get_text("sublink_sent", url=order['subscription_url']),
            parse_mode="HTML"
        )
        await callback.answer()

    async def show_plans(callback: types.CallbackQuery, server_id: int, multiple_servers: bool = False):
        plans = await get_plans(server_id, only_active=True)
        if not plans:
            await callback.message.edit_text(get_text("buy_no_plans"), reply_markup=await _get_main_menu(callback.from_user.id))
            return
        show_price = (await get_setting("show_plan_price")) == "1"
        await callback.message.edit_text(
            get_text("buy_select_plan"),
            reply_markup=user_plans_keyboard(plans, server_id, multiple_servers, show_price)
        )

    @dp.callback_query(F.data.startswith("user_plan_"))
    async def user_select_plan(callback: types.CallbackQuery):
        plan_id = int(callback.data.replace("user_plan_", ""))
        plan = await get_plan(plan_id)
        if not plan:
            await callback.answer("پلن مورد نظر یافت نشد.", show_alert=True)
            return

        stats = await get_user_wallet_stats(callback.from_user.id)
        has_balance = stats["balance"] >= plan["price"]

        text = (
            f"🧾 <b>پیش‌فاکتور</b>\n"
            f"{'─' * 24}\n"
            f"📦 <b>پلن:</b> {plan['name']}\n"
            f"📊 <b>حجم:</b> {plan['traffic']} گیگابایت\n"
            f"📅 <b>مدت:</b> {plan['duration']} روز\n"
            f"{'─' * 24}\n"
            f"💰 <b>مبلغ قابل پرداخت:</b> {plan['price']:,} تومان"
        )
        if has_balance:
            text += f"\n💎 <b>موجودی کیف پول:</b> {stats['balance']:,} تومان"

        await callback.message.edit_text(
            text,
            reply_markup=proforma_keyboard(plan_id, has_balance=has_balance),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("pay_") & ~F.data.startswith("pay_wallet_"))
    async def pay_plan(callback: types.CallbackQuery, state: FSMContext):
        plan_id = int(callback.data.replace("pay_", ""))

        card_active = await get_setting("card_active")
        card_number = await get_setting("card_number")
        card_owner = await get_setting("card_owner")

        if card_active != "1" or not card_number:
            await callback.answer(get_text("payment_card_unavailable"), show_alert=True)
            return

        plan     = await get_plan_with_server(plan_id)
        fsm_data = await state.get_data()
        discount_amount  = fsm_data.get("discount_amount", 0)
        discount_code    = fsm_data.get("discount_code")
        discount_code_id = fsm_data.get("discount_code_id")
        final_price      = plan["price"] - discount_amount

        if final_price <= 0:
            # رایگان شد — مستقیم سرویس بساز
            await state.clear()
            import json as _json
            service_ids = _json.loads(plan["service_ids"] or "[]")
            if not service_ids:
                await callback.answer(get_text("free_test_no_service_config"), show_alert=True)
                return
            u = callback.from_user
            await get_or_create_user(u.id, u.first_name, u.username)
            try:
                api = RebeccaAPI(plan["panel_url"], plan["panel_token"])
                live = await api.get_services()
                live_ids = {s["id"] for s in live}
                sid = next((s for s in service_ids if s in live_ids), None)
                if not sid:
                    await callback.answer("سرویس پنل یافت نشد.", show_alert=True)
                    return
                user_data = await api.create_user(sid, plan["traffic"], plan["duration"])
                sub_path = user_data.get("subscription_url", "")
                subscription_url = await api.get_subscription_url(sub_path)
                vpn_username = user_data.get("username", "")
            except Exception as e:
                from bot import logger
                logger.error(f"خطا در ساخت رایگان plan #{plan_id}: {e}")
                await callback.answer(get_text("wallet_error_api", error=str(e)), show_alert=True)
                return
            order_id = await create_order(u.id, u.username or u.first_name, plan_id, "discount_free")
            await update_order_status(order_id, "approved")
            await update_order_vpn_info(order_id, vpn_username, subscription_url)
            if discount_code:
                from shared_lib.db import update_order_discount, use_discount_code
                await update_order_discount(order_id, discount_code, discount_amount)
                if discount_code_id:
                    await use_discount_code(discount_code_id, u.id)
            from handlers.admin import _make_qr
            from keyboards import subscription_approved_keyboard
            qr = _make_qr(subscription_url)
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=qr,
                caption=get_text("discount_free_success", url=subscription_url),
                reply_markup=subscription_approved_keyboard(subscription_url),
                parse_mode="HTML"
            )
            await callback.answer()
            return

        await state.update_data(plan_id=plan_id)
        await state.set_state(BuyVPN.waiting_for_receipt)

        owner_line    = f"👤 <b>به نام:</b> {card_owner}\n" if card_owner else ""
        discount_line = f"🎟 <b>تخفیف:</b> {discount_amount:,} تومان\n" if discount_amount else ""
        await callback.message.edit_text(
            f"💳 <b>اطلاعات پرداخت</b>\n"
            f"{'─' * 24}\n"
            f"💳 <b>شماره کارت:</b>\n<code>{card_number}</code>\n"
            f"{owner_line}"
            f"{discount_line}"
            f"💰 <b>مبلغ:</b> {final_price:,} تومان\n"
            f"{'─' * 24}\n\n"
            f"📸 پس از واریز، تصویر رسید را ارسال کنید.",
            reply_markup=payment_info_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("pay_wallet_"))
    async def pay_with_wallet(callback: types.CallbackQuery, state: FSMContext):
        from keyboards import subscription_approved_keyboard
        plan_id = int(callback.data.replace("pay_wallet_", ""))
        plan = await get_plan_with_server(plan_id)
        if not plan:
            await callback.answer("پلن یافت نشد.", show_alert=True)
            return

        fsm_data         = await state.get_data()
        discount_amount  = fsm_data.get("discount_amount", 0)
        discount_code    = fsm_data.get("discount_code")
        discount_code_id = fsm_data.get("discount_code_id")
        final_price      = max(0, plan["price"] - discount_amount)

        u = callback.from_user
        await get_or_create_user(u.id, u.first_name, u.username)

        import json
        service_ids = json.loads(plan["service_ids"] or "[]")
        if not service_ids:
            await callback.answer(get_text("free_test_no_service_config"), show_alert=True)
            return

        if final_price > 0:
            deducted = await deduct_balance_if_sufficient(u.id, final_price)
            if not deducted:
                await callback.answer(get_text("wallet_no_balance"), show_alert=True)
                return

        try:
            api = RebeccaAPI(plan["panel_url"], plan["panel_token"])
            user_data = await api.create_user(
                service_id=service_ids[0],
                data_limit_gb=plan["traffic"],
                duration_days=plan["duration"]
            )
            sub_path = user_data.get("subscription_url", "")
            subscription_url = await api.get_subscription_url(sub_path)
            username = user_data.get("username", "")
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در ساخت یوزر (wallet) برای plan #{plan_id}: {e}")
            if final_price > 0:
                await add_balance(u.id, final_price)
            await callback.answer(get_text("wallet_error_api", error=str(e)), show_alert=True)
            return

        try:
            order_id = await create_order(u.id, u.username or u.first_name, plan_id, "wallet")
            await update_order_status(order_id, "approved")
            await update_order_vpn_info(order_id, username, subscription_url)
            if final_price > 0:
                await add_balance_and_transaction(u.id, -final_price, "purchase", f"خرید پلن {plan['name']}")
            if discount_code:
                from shared_lib.db import update_order_discount, use_discount_code
                await update_order_discount(order_id, discount_code, discount_amount)
                if discount_code_id:
                    await use_discount_code(discount_code_id, u.id)
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در ثبت سفارش wallet plan #{plan_id} — حذف یوزر {username}: {e}")
            try:
                await api.delete_user(username)
            except Exception:
                pass
            if final_price > 0:
                await add_balance(u.id, final_price)
            await callback.answer(get_text("wallet_error_order"), show_alert=True)
            return

        await state.clear()
        from handlers.admin import _make_qr
        qr_file = _make_qr(subscription_url)
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=qr_file,
            caption=get_text("wallet_purchase_success", url=subscription_url),
            reply_markup=subscription_approved_keyboard(subscription_url),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data == "cancel_payment")
    async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.edit_text(get_text("payment_cancelled"), reply_markup=await _get_main_menu(callback.from_user.id))
        await callback.answer()

    @dp.message(BuyVPN.waiting_for_receipt, F.photo)
    async def receive_receipt(message: types.Message, state: FSMContext):
        from bot import ADMIN_IDS
        from keyboards import admin_order_keyboard

        data = await state.get_data()
        plan_id = data["plan_id"]
        plan = await get_plan(plan_id)

        receipt_file_id = message.photo[-1].file_id
        username = message.from_user.username or message.from_user.first_name

        order_id = await create_order(
            user_id=message.from_user.id,
            username=username,
            plan_id=plan_id,
            receipt_file_id=receipt_file_id
        )

        discount_code   = data.get("discount_code")
        discount_amount = data.get("discount_amount", 0)
        discount_code_id= data.get("discount_code_id")
        if discount_code and discount_amount:
            from shared_lib.db import update_order_discount, use_discount_code
            await update_order_discount(order_id, discount_code, discount_amount)
            if discount_code_id:
                await use_discount_code(discount_code_id, message.from_user.id)

        await state.clear()

        await message.answer(get_text("payment_submitted"))

        final_price   = plan["price"] - discount_amount
        discount_line = f"🎟 کد تخفیف: <code>{discount_code}</code> ({discount_amount:,} تومان)\n" if discount_code else ""
        admin_text = (
            f"🛎 <b>سفارش جدید — شماره #{order_id}</b>\n"
            f"{'─' * 24}\n"
            f"یک کاربر پلن زیر را خریداری کرده و رسید پرداخت ارسال کرده است:\n\n"
            f"👤 کاربر: @{username} (<code>{message.from_user.id}</code>)\n"
            f"📦 پلن: <b>{plan['name']}</b>\n"
            f"📊 حجم: {plan['traffic']} گیگابایت\n"
            f"📅 مدت: {plan['duration']} روز\n"
            f"{discount_line}"
            f"💰 مبلغ: <b>{final_price:,} تومان</b>\n"
            f"{'─' * 24}\n"
            f"پس از بررسی رسید، وضعیت سفارش را تعیین کنید:"
        )
        for admin_id in ADMIN_IDS:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=receipt_file_id,
                caption=admin_text,
                reply_markup=admin_order_keyboard(order_id),
                parse_mode="HTML"
            )

    @dp.message(BuyVPN.waiting_for_receipt)
    async def receipt_not_photo(message: types.Message):
        await message.answer(get_text("payment_not_photo"))
