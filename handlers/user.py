from datetime import datetime, timezone, timedelta
import jdatetime
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import BuyVPN
from keyboards import (
    user_main_menu, user_servers_keyboard, user_services_keyboard,
    user_plans_keyboard, proforma_keyboard, payment_info_keyboard,
    user_service_detail_keyboard
)
from database import (
    get_servers, get_plans, get_plan, get_setting, create_order,
    get_user_services, get_user_service
)
from rebecca_api import RebeccaAPI

from aiogram.exceptions import TelegramBadRequest

TEHRAN = timezone(timedelta(hours=3, minutes=30))

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
        "active":   "✅ فعال",
        "expired":  "❌ منقضی شده",
        "limited":  "❌ ترافیک تمام شده",
        "disabled": "⚠️ غیرفعال",
    }
    status = STATUS_MAP.get(live.get("status", ""), "❓ نامشخص") if live else "⚠️ اطلاعات زنده در دسترس نیست"

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
            parts.append("📊 ترافیک : نامحدود")
        parts.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        expire = live.get("expire")
        parts.append(f"📅 انقضا : {_to_jalali(expire) if expire else 'نامحدود'}")

    parts.append(f"🗓 خرید : {_to_jalali(order['created_at'])}")
    return "\n".join(parts)

def register_user_handlers(dp):

    @dp.callback_query(F.data == "buy_vpn")
    async def buy_vpn(callback: types.CallbackQuery):
        servers = await get_servers(only_active=True)
        if not servers:
            await callback.message.edit_text(
                "⚠️ در حال حاضر سرویسی برای فروش وجود ندارد.\nلطفاً بعداً مراجعه کنید.",
                reply_markup=user_main_menu()
            )
            await callback.answer()
            return

        if len(servers) == 1:
            await show_plans(callback, servers[0]["id"], multiple_servers=False)
        else:
            await callback.message.edit_text(
                "🖥 لطفاً یک سرور انتخاب کنید:",
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
        from bot import is_admin
        from keyboards import admin_main_menu
        await state.clear()
        menu = admin_main_menu() if is_admin(callback.from_user.id) else user_main_menu()
        await _edit_or_replace(callback, "🏠 منوی اصلی", menu)
        await callback.answer()

    @dp.callback_query(F.data == "my_services")
    async def my_services(callback: types.CallbackQuery):
        orders = await get_user_services(callback.from_user.id)
        if not orders:
            await _edit_or_replace(
                callback,
                "📋 <b>سرویس‌های من</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "هنوز هیچ سرویسی نداری.",
                user_services_keyboard([])
            )
        else:
            await _edit_or_replace(
                callback,
                "📋 <b>سرویس‌های من</b>",
                user_services_keyboard(orders)
            )
        await callback.answer()

    @dp.callback_query(F.data.startswith("my_service_"))
    async def my_service_detail(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("my_service_", ""))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order:
            await callback.answer("سرویس یافت نشد.", show_alert=True)
            return

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
        await callback.answer()

    @dp.callback_query(F.data.startswith("sub_link_"))
    async def send_sub_link(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("sub_link_", ""))
        order = await get_user_service(order_id, callback.from_user.id)
        if not order or not order["subscription_url"]:
            await callback.answer("لینک در دسترس نیست.", show_alert=True)
            return
        await callback.message.answer(
            f"🔗 لینک اشتراک:\n\n<code>{order['subscription_url']}</code>",
            parse_mode="HTML"
        )
        await callback.answer()

    async def show_plans(callback: types.CallbackQuery, server_id: int, multiple_servers: bool = False):
        plans = await get_plans(server_id, only_active=True)
        if not plans:
            await callback.message.edit_text(
                "⚠️ این سرور در حال حاضر پلن فعالی ندارد.\nلطفاً بعداً مراجعه کنید.",
                reply_markup=user_main_menu()
            )
            return
        show_price = (await get_setting("show_plan_price")) == "1"
        await callback.message.edit_text(
            "📦 یک پلن انتخاب کنید:",
            reply_markup=user_plans_keyboard(plans, server_id, multiple_servers, show_price)
        )

    @dp.callback_query(F.data.startswith("user_plan_"))
    async def user_select_plan(callback: types.CallbackQuery):
        plan_id = int(callback.data.replace("user_plan_", ""))
        plan = await get_plan(plan_id)
        if not plan:
            await callback.answer("پلن مورد نظر یافت نشد.", show_alert=True)
            return

        text = (
            f"🧾 <b>پیش‌فاکتور</b>\n"
            f"{'─' * 24}\n"
            f"📦 <b>پلن:</b> {plan['name']}\n"
            f"📊 <b>حجم:</b> {plan['traffic']} گیگابایت\n"
            f"📅 <b>مدت:</b> {plan['duration']} روز\n"
            f"{'─' * 24}\n"
            f"💰 <b>مبلغ قابل پرداخت:</b> {plan['price']:,} تومان"
        )
        await callback.message.edit_text(
            text,
            reply_markup=proforma_keyboard(plan_id),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("pay_"))
    async def pay_plan(callback: types.CallbackQuery, state: FSMContext):
        plan_id = int(callback.data.replace("pay_", ""))

        card_active = await get_setting("card_active")
        card_number = await get_setting("card_number")
        card_owner = await get_setting("card_owner")

        if card_active != "1" or not card_number:
            await callback.answer(
                "در حال حاضر امکان پرداخت وجود ندارد. لطفاً بعداً مراجعه کنید.",
                show_alert=True
            )
            return

        plan = await get_plan(plan_id)
        await state.update_data(plan_id=plan_id)
        await state.set_state(BuyVPN.waiting_for_receipt)

        owner_line = f"👤 <b>به نام:</b> {card_owner}\n" if card_owner else ""
        await callback.message.edit_text(
            f"💳 <b>اطلاعات پرداخت</b>\n"
            f"{'─' * 24}\n"
            f"💳 <b>شماره کارت:</b>\n<code>{card_number}</code>\n"
            f"{owner_line}"
            f"💰 <b>مبلغ:</b> {plan['price']:,} تومان\n"
            f"{'─' * 24}\n\n"
            f"📸 پس از واریز، تصویر رسید را ارسال کنید.",
            reply_markup=payment_info_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data == "cancel_payment")
    async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await callback.message.edit_text(
            "❌ پرداخت لغو شد.",
            reply_markup=user_main_menu()
        )
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
        await state.clear()

        await message.answer(
            "✅ رسید شما دریافت شد.\n"
            "⏳ پس از بررسی توسط پشتیبانی، نتیجه به شما اعلام خواهد شد."
        )

        admin_text = (
            f"🛎 <b>سفارش جدید — شماره #{order_id}</b>\n"
            f"{'─' * 24}\n"
            f"یک کاربر پلن زیر را خریداری کرده و رسید پرداخت ارسال کرده است:\n\n"
            f"👤 کاربر: @{username} (<code>{message.from_user.id}</code>)\n"
            f"📦 پلن: <b>{plan['name']}</b>\n"
            f"📊 حجم: {plan['traffic']} گیگابایت\n"
            f"📅 مدت: {plan['duration']} روز\n"
            f"💰 مبلغ: <b>{plan['price']:,} تومان</b>\n"
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
        await message.answer("📸 لطفاً تصویر رسید را ارسال کنید.")
