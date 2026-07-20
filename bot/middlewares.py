from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from shared_lib.db import get_setting, get_text
from keyboards import force_join_keyboard
from force_join_check import get_missing_channels


# ─── دکمه‌ی «یک مرحله عقب» ──────────────────────────────────────────────────────
# تلگرام حافظه‌ی بازگشت نداره؛ خودمون برای هر کاربر تاریخچه‌ی صفحه‌ها رو نگه می‌داریم.
# فقط callback هایی که «صفحه» هستن ثبت می‌شن — اکشن‌ها (خرید، پرداخت، تایید، حذف،
# تاگل، ورودی‌های فرم) هیچ‌وقت ثبت نمی‌شن تا بازگشت هرگز یه اکشن رو دوباره اجرا نکنه.

# صفحه‌های با callback ثابت
NAV_SCREEN_EXACT = {
    # کاربر
    "user_main", "back_to_start", "buy_vpn", "my_services", "my_tickets",
    "profile", "referral", "support", "tutorial", "user_faqs",
    "wallet", "wallet_history", "free_test",
    # منوهای ادمین
    "admin_panel", "admin_servers", "admin_plans", "admin_finance",
    "admin_users", "admin_discount", "admin_free_test", "admin_free_test_global",
    "admin_referral", "admin_support", "admin_tutorials", "admin_tutorial_list",
    "admin_faqs", "admin_stats", "admin_general", "admin_force_join",
    "admin_banner_and_text", "admin_banner_settings", "admin_text_settings",
    "card_settings", "list_channels", "list_plans", "list_servers",
}

# صفحه‌های پارامتردار (جزئیات/لیست) — پیشوندشون ثبت می‌شه
NAV_SCREEN_PREFIXES = (
    "faq_view_", "tutorial_view_",
    "faq_item_", "tutorial_item_", "discount_item_",
    "my_service_", "user_plan_", "user_server_",
    "view_plans_", "view_ticket_",
    "server_settings_", "plan_settings_", "card_settings_", "channel_settings_",
    "admin_ul_", "admin_up_", "admin_ua_services_",
    "admin_free_test_server_", "free_test_server_",
    "extra_time_", "extra_volume_", "sub_link_",
)

_NAV_MAX = 30            # سقف تاریخچه برای هر کاربر
_nav_history: Dict[int, list] = {}


def _is_screen(data: str) -> bool:
    return data in NAV_SCREEN_EXACT or data.startswith(NAV_SCREEN_PREFIXES)


class NavHistoryMiddleware(BaseMiddleware):
    """تاریخچه‌ی ناوبری هر کاربر رو نگه می‌داره و `nav_back` رو به صفحه‌ی قبلی تبدیل می‌کنه."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery) or not event.data:
            return await handler(event, data)

        uid = event.from_user.id
        cb = event.data

        if cb == "nav_back":
            stack = _nav_history.get(uid) or []
            if stack:
                stack.pop()                       # صفحه‌ی فعلی رو برمی‌داریم
            target = stack[-1] if stack else "user_main"
            bot = data.get("bot") or event.bot
            replay = event.model_copy(update={"data": target}).as_(bot)
            return await handler(replay, data)

        if _is_screen(cb):
            stack = _nav_history.setdefault(uid, [])
            if cb in stack:
                # برگشت به صفحه‌ای که قبلاً دیده شده → تاریخچه تا همون‌جا کوتاه می‌شه
                del stack[stack.index(cb) + 1:]
            else:
                stack.append(cb)
                if len(stack) > _NAV_MAX:
                    del stack[0]

        return await handler(event, data)


_DEFAULT_MAINTENANCE_MSG = (
    "🛠 ربات موقتاً در حال بروزرسانی است.\n\n"
    "کمی بعد دوباره امتحان کن. ممنون از صبرت 🙏"
)


class MaintenanceMiddleware(BaseMiddleware):
    """When maintenance mode is on, every non-admin gets the maintenance
    notice and no handler runs. Admins always pass through."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        from bot import is_admin
        if is_admin(user.id):
            return await handler(event, data)

        if await get_setting("maintenance_enabled") != "1":
            return await handler(event, data)

        text = await get_setting("maintenance_message") or _DEFAULT_MAINTENANCE_MSG
        if isinstance(event, CallbackQuery):
            await event.answer()
            try:
                await event.message.edit_text(text, parse_mode="HTML")
            except Exception:
                await event.message.answer(text, parse_mode="HTML")
        elif isinstance(event, Message):
            await event.answer(text, parse_mode="HTML")
        return None


class ForceJoinMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        from bot import is_admin
        if is_admin(user.id):
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "check_force_join":
            return await handler(event, data)

        enabled = await get_setting("force_join_enabled")
        if enabled != "1":
            return await handler(event, data)

        missing = await get_missing_channels(event.bot, user.id)
        if not missing:
            return await handler(event, data)

        text = get_text("force_join_prompt")
        markup = force_join_keyboard(missing)
        if isinstance(event, CallbackQuery):
            await event.answer()
            try:
                await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
            except Exception:
                await event.message.answer(text, reply_markup=markup, parse_mode="HTML")
        elif isinstance(event, Message):
            await event.answer(text, reply_markup=markup, parse_mode="HTML")
        return None
