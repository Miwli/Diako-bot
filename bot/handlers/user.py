from datetime import datetime, timezone, timedelta
import jdatetime
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import BuyVPN, TopUp, ChangeNote
from shared_lib.formatters import fmt_traffic_bytes, fmt_traffic_gb
from keyboards import (
    user_main_menu, user_servers_keyboard, user_services_keyboard,
    user_plans_keyboard, proforma_keyboard, payment_info_keyboard,
    user_service_detail_keyboard, confirm_delete_service_keyboard,
    confirm_changestatus_keyboard, cancel_changenote_keyboard,
    changeloc_servers_keyboard, confirm_changeloc_keyboard, admin_changeloc_keyboard,
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
    get_text, get_keyboard_buttons, set_service_note,
    get_selected_payment_card,
    create_location_change_request, get_location_change_request,
    get_pending_location_change, update_location_change_request,
    perform_location_change,
)
from shared_lib.rebecca_api import RebeccaAPI

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

TEHRAN = timezone(timedelta(hours=3, minutes=30))


async def _get_main_menu(user_id: int):
    """منوی اصلی رو از DB می‌خونه و برمی‌گردونه"""
    from bot import is_admin
    rows = await get_keyboard_buttons("user_main", admin=is_admin(user_id))
    return user_main_menu(rows)

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
    return fmt_traffic_bytes(b)

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

async def _banner_caption_entities():
    """entities ذخیره‌شده‌ی کپشن بنر رو به آبجکت MessageEntity برمی‌گردونه"""
    import json as _json
    raw = await get_setting("banner_caption_entities")
    if not raw:
        return None
    try:
        from aiogram.types import MessageEntity
        return [MessageEntity.model_validate(d) for d in _json.loads(raw)]
    except Exception:
        return None

async def _send_main_menu(target, user: types.User):
    from bot import logger
    menu = await _get_main_menu(user.id)
    name = user.first_name or "کاربر"

    # کپشن دلخواه ادمین اولویت داره؛ وگرنه متن پیش‌فرض خوش‌آمد
    custom_caption = await get_setting("banner_caption")
    if custom_caption:
        caption = custom_caption
        entities = await _banner_caption_entities()
        parse_mode = None  # entities با parse_mode ترکیب نمی‌شه؛ متن ادمین literal است
    else:
        caption = get_text("start_welcome_default", name=name)
        entities = None
        parse_mode = "HTML"
    banner = await get_setting("banner_file_id")

    async def _send(msg, is_cb=False):
        try:
            if banner:
                await msg.answer_photo(photo=banner, caption=caption, caption_entities=entities, reply_markup=menu, parse_mode=parse_mode, protect_content=True)
            else:
                await msg.answer(caption, entities=entities, reply_markup=menu, parse_mode=parse_mode)
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
        await callback.answer(get_text("coming_soon"), show_alert=True)

    # ─── تست رایگان ──────────────────────────────

    def _fmt_dur(val) -> str:
        return "♾️ بی‌نهایت" if float(val or 0) == 0 else f"{val} ساعت"

    def _fmt_trf(val) -> str:
        return "♾️ بی‌نهایت" if float(val or 0) == 0 else fmt_traffic_gb(val)

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
                get_text("free_test_select_server"),
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
        text = get_text("free_test_confirm_text", server=server["name"], duration=dur, traffic=trf)
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
        from keyboards import profile_keyboard
        u = callback.from_user
        user = await get_or_create_user(u.id, u.first_name, u.username)
        stats = await get_user_wallet_stats(u.id)
        username_line = f"📱 یوزرنیم : @{u.username}" if u.username else "📱 یوزرنیم : —"
        text = get_text(
            "profile_text",
            name=u.first_name,
            user_id=u.id,
            username_line=username_line,
            join_date=_to_jalali(user["created_at"]),
            balance=f"{stats['balance']:,}",
            referral_code=user["referral_code"],
        )
        await _edit_or_replace(callback, text, profile_keyboard())
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
        card = await get_selected_payment_card()
        await message.answer(
            get_text("payment_card_info",
                     amount=f"{amount:,}",
                     card_number=card["number"] if card else "—",
                     card_owner=(card["owner"] if card else None) or "—"),
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

        from bot import ADMIN_IDS, logger
        caption = get_text(
            "admin_topup_notify",
            full_name=u.full_name,
            username_part=f" (@{u.username})" if u.username else "",
            user_id=u.id,
            amount=f"{amount:,}",
            request_id=request_id,
        )
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=caption,
                    reply_markup=admin_topup_keyboard(request_id),
                    parse_mode="HTML"
                )
            except Exception as exc:
                logger.error(f"خطا در اطلاع‌رسانی شارژ به ادمین {admin_id}: {exc}")
        await message.answer(get_text("topup_submitted"), reply_markup=wallet_keyboard())

    # ─── کیف پول ──────────────────────────────────

    @dp.callback_query(F.data == "wallet")
    async def wallet_page(callback: types.CallbackQuery):
        u = callback.from_user
        await get_or_create_user(u.id, u.first_name, u.username)
        stats = await get_user_wallet_stats(u.id)
        name = u.first_name or "کاربر"
        text = get_text(
            "wallet_balance_text",
            name=name,
            balance=f"{stats['balance']:,}",
            services=stats["services"],
            invoices=stats["invoices"],
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
        server_id = order["server_id"]
        if not server_id:
            await callback.answer(get_text("renew_no_server"), show_alert=True)
            return
        plans = await get_plans(server_id, only_active=True)
        if not plans:
            await callback.answer(get_text("renew_no_plans"), show_alert=True)
            return
        show_price = (await get_setting("show_plan_price")) == "1"
        await _edit_or_replace(
            callback,
            get_text("renew_prompt"),
            user_plans_keyboard(plans, server_id, multiple_servers=False, show_price=show_price)
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

    @dp.callback_query(F.data.startswith("changestatus_"))
    async def ask_toggle_status(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("changestatus_", ""))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer(get_text("service_not_found"), show_alert=True)
            return
        try:
            api = RebeccaAPI(order["panel_url"], order["panel_token"])
            live = await api.get_user(order["vpn_username"])
        except Exception as e:
            await callback.answer(get_text("changestatus_error", error=str(e)), show_alert=True)
            return
        target_active = live.get("status") != "active"
        text = get_text(
            "changestatus_confirm_enable" if target_active else "changestatus_confirm_disable",
            name=order["vpn_username"]
        )
        await _edit_or_replace(callback, text, confirm_changestatus_keyboard(order_id, target_active))
        await callback.answer()

    @dp.callback_query(F.data.startswith("confirmed_changestatus_"))
    async def do_toggle_status(callback: types.CallbackQuery):
        order_id_s, target_s = callback.data.replace("confirmed_changestatus_", "").rsplit("_", 1)
        order_id, target_active = int(order_id_s), bool(int(target_s))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer(get_text("service_not_found"), show_alert=True)
            return
        try:
            api = RebeccaAPI(order["panel_url"], order["panel_token"])
            await api.toggle_status(order["vpn_username"], target_active)
        except Exception as e:
            await callback.answer(get_text("changestatus_error", error=str(e)), show_alert=True)
            return
        await callback.answer(get_text("changestatus_active" if target_active else "changestatus_disabled"))
        live = None
        try:
            live = await api.get_user(order["vpn_username"])
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در دریافت اطلاعات سرویس {order['vpn_username']}: {e}")
        await _edit_or_replace(
            callback,
            _service_text(order, live),
            user_service_detail_keyboard(order_id, order["subscription_url"])
        )

    @dp.callback_query(F.data.startswith("changenote_"))
    async def ask_note(callback: types.CallbackQuery, state: FSMContext):
        order_id = int(callback.data.replace("changenote_", ""))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer(get_text("service_not_found"), show_alert=True)
            return
        await state.set_state(ChangeNote.waiting_for_note)
        await state.update_data(order_id=order_id)
        await _edit_or_replace(callback, get_text("changenote_prompt"), cancel_changenote_keyboard(order_id))
        await callback.answer()

    @dp.message(ChangeNote.waiting_for_note, F.text)
    async def save_note(message: types.Message, state: FSMContext):
        data = await state.get_data()
        order_id = data["order_id"]
        note = message.text.strip()
        if len(note) > 500:
            await message.answer(get_text("changenote_too_long"))
            return
        await set_service_note(order_id, note)
        await state.clear()
        await message.answer(get_text("changenote_success"))

    # ─── تغییر لوکیشن ─────────────────────────────

    @dp.callback_query(F.data.startswith("chgloc_srv_"))
    async def changeloc_pick_server(callback: types.CallbackQuery):
        order_id_s, server_id_s = callback.data.replace("chgloc_srv_", "").rsplit("_", 1)
        order_id, server_id = int(order_id_s), int(server_id_s)
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer(get_text("service_not_found"), show_alert=True)
            return
        from shared_lib.db import get_server
        target = await get_server(server_id)
        if not target or not target["is_active"]:
            await callback.answer(get_text("changeloc_no_servers"), show_alert=True)
            return
        text = get_text("changeloc_confirm",
                        from_server=order["server_name"], to_server=target["name"])
        await _edit_or_replace(callback, text, confirm_changeloc_keyboard(order_id, server_id))
        await callback.answer()

    @dp.callback_query(F.data.startswith("chgloc_go_"))
    async def changeloc_go(callback: types.CallbackQuery):
        order_id_s, server_id_s = callback.data.replace("chgloc_go_", "").rsplit("_", 1)
        order_id, server_id = int(order_id_s), int(server_id_s)
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer(get_text("service_not_found"), show_alert=True)
            return
        if await get_pending_location_change(order_id):
            await callback.answer(get_text("changeloc_already_pending"), show_alert=True)
            return

        need_admin = (await get_setting("changeloc_need_admin") or "1") == "1"
        if not need_admin:
            await callback.answer()
            await callback.message.edit_text(get_text("changeloc_processing"))
            try:
                result = await perform_location_change(order_id, server_id)
            except Exception as e:
                from bot import logger
                logger.error(f"خطا در تغییر لوکیشن سفارش #{order_id}: {e}")
                await callback.message.edit_text(
                    get_text("changeloc_error", error=str(e)),
                    reply_markup=user_service_detail_keyboard(order_id, order["subscription_url"]),
                    parse_mode="HTML"
                )
                return
            from shared_lib.db import get_server
            target = await get_server(server_id)
            await callback.message.edit_text(
                get_text("changeloc_success", server=target["name"], url=result["subscription_url"]),
                reply_markup=user_service_detail_keyboard(order_id, result["subscription_url"]),
                parse_mode="HTML"
            )
            return

        req_id = await create_location_change_request(
            callback.from_user.id, order_id, order["server_id"], server_id
        )
        from bot import bot, ADMIN_IDS, logger
        from shared_lib.db import get_server
        target = await get_server(server_id)
        admin_text = get_text(
            "changeloc_admin_request",
            user_id=callback.from_user.id, order_id=order_id,
            from_server=order["server_name"], to_server=target["name"],
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text, reply_markup=admin_changeloc_keyboard(req_id))
            except Exception as exc:
                logger.error(f"خطا در اطلاع‌رسانی تغییر لوکیشن به ادمین {admin_id}: {exc}")
        await callback.answer()
        await _edit_or_replace(
            callback,
            get_text("changeloc_pending"),
            user_service_detail_keyboard(order_id, order["subscription_url"])
        )

    @dp.callback_query(F.data.startswith("chgloc_approve_"))
    async def changeloc_approve(callback: types.CallbackQuery):
        from bot import is_admin, bot, logger
        if not is_admin(callback.from_user.id):
            await callback.answer()
            return
        req_id = int(callback.data.replace("chgloc_approve_", ""))
        req = await get_location_change_request(req_id)
        if not req or req["status"] != "pending":
            await callback.answer(get_text("changeloc_already_processed"), show_alert=True)
            return
        await callback.answer()
        try:
            result = await perform_location_change(req["order_id"], req["to_server_id"])
        except Exception as e:
            logger.error(f"خطا در اعمال تغییر لوکیشن درخواست #{req_id}: {e}")
            await callback.message.edit_text(
                callback.message.text + "\n\n" + get_text("changeloc_error", error=str(e))
            )
            return
        await update_location_change_request(req_id, "approved")
        await callback.message.edit_text(
            callback.message.text + "\n\n" + get_text("changeloc_admin_approved")
        )
        try:
            await bot.send_message(
                req["user_id"],
                get_text("changeloc_user_approved",
                         server=req["to_server_name"], url=result["subscription_url"]),
                parse_mode="HTML"
            )
        except Exception as exc:
            logger.error(f"خطا در اطلاع‌رسانی تایید تغییر لوکیشن به کاربر {req['user_id']}: {exc}")

    @dp.callback_query(F.data.startswith("chgloc_reject_"))
    async def changeloc_reject(callback: types.CallbackQuery):
        from bot import is_admin, bot, logger
        if not is_admin(callback.from_user.id):
            await callback.answer()
            return
        req_id = int(callback.data.replace("chgloc_reject_", ""))
        req = await get_location_change_request(req_id)
        if not req or req["status"] != "pending":
            await callback.answer(get_text("changeloc_already_processed"), show_alert=True)
            return
        await update_location_change_request(req_id, "rejected")
        await callback.answer()
        await callback.message.edit_text(
            callback.message.text + "\n\n" + get_text("changeloc_admin_rejected")
        )
        try:
            await bot.send_message(req["user_id"], get_text("changeloc_user_rejected"))
        except Exception as exc:
            logger.error(f"خطا در اطلاع‌رسانی رد تغییر لوکیشن به کاربر {req['user_id']}: {exc}")

    @dp.callback_query(F.data.startswith("changeloc_"))
    async def changeloc_start(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("changeloc_", ""))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer(get_text("service_not_found"), show_alert=True)
            return
        if await get_pending_location_change(order_id):
            await callback.answer(get_text("changeloc_already_pending"), show_alert=True)
            return
        servers = [s for s in await get_servers(only_active=True) if s["id"] != order["server_id"]]
        if not servers:
            await callback.answer(get_text("changeloc_no_servers"), show_alert=True)
            return
        await _edit_or_replace(
            callback,
            get_text("changeloc_select", name=order["vpn_username"]),
            changeloc_servers_keyboard(order_id, servers)
        )
        await callback.answer()

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
            await callback.answer(get_text("plan_not_found"), show_alert=True)
            return

        stats = await get_user_wallet_stats(callback.from_user.id)
        has_balance = stats["balance"] >= plan["price"]

        balance_line = f"\n💎 <b>موجودی کیف پول:</b> {stats['balance']:,} تومان" if has_balance else ""
        text = get_text(
            "proforma_text",
            plan_name=plan["name"],
            traffic=plan["traffic"],
            duration=plan["duration"],
            price=f"{plan['price']:,}",
            balance_line=balance_line,
        )

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
        card = await get_selected_payment_card()

        if card_active != "1" or not card:
            await callback.answer(get_text("payment_card_unavailable"), show_alert=True)
            return
        card_number = card["number"]
        card_owner = card["owner"]

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
                    await callback.answer(get_text("plan_service_not_found"), show_alert=True)
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

        owner_line    = f"\n👤 <b>به نام:</b> {card_owner}" if card_owner else ""
        discount_line = f"\n🎟 <b>تخفیف:</b> {discount_amount:,} تومان" if discount_amount else ""
        await callback.message.edit_text(
            get_text(
                "payment_buy_card_info",
                card_number=card_number,
                owner_line=owner_line,
                discount_line=discount_line,
                amount=f"{final_price:,}",
            ),
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
            await callback.answer(get_text("plan_not_found"), show_alert=True)
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
        from bot import ADMIN_IDS, logger
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
        admin_text = get_text(
            "admin_order_notify",
            order_id=order_id,
            username=username,
            user_id=message.from_user.id,
            plan_name=plan["name"],
            traffic=plan["traffic"],
            duration=plan["duration"],
            discount_line=discount_line,
            amount=f"{final_price:,}",
        )
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=receipt_file_id,
                    caption=admin_text,
                    reply_markup=admin_order_keyboard(order_id),
                    parse_mode="HTML"
                )
            except Exception as exc:
                logger.error(f"خطا در اطلاع‌رسانی سفارش به ادمین {admin_id}: {exc}")

    @dp.message(BuyVPN.waiting_for_receipt)
    async def receipt_not_photo(message: types.Message):
        await message.answer(get_text("payment_not_photo"))
