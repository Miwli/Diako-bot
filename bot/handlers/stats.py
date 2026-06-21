from datetime import datetime, timezone, timedelta
import jdatetime
from aiogram import types, F
from aiogram.exceptions import TelegramBadRequest
from keyboards import admin_stats_keyboard
from shared_lib.db import get_admin_stats

_TZ_IR = timezone(timedelta(hours=3, minutes=30))

def _now_ir() -> str:
    dt = datetime.now(_TZ_IR)
    jdt = jdatetime.datetime.fromgregorian(datetime=dt)
    return jdt.strftime("%-d %B %Y — %H:%M")

def _fmt(n: int) -> str:
    return f"{n:,}"

def _build_stats_text(s: dict) -> str:
    plans_text = ""
    for i, (name, cnt) in enumerate(s["top_plans"]):
        mark = "├" if i < len(s["top_plans"]) - 1 else "└"
        plans_text += f"\n  {mark} {name} — {_fmt(cnt)} بار"

    return (
        f"📊 <b>آمار و گزارش</b>\n"
        f"\n"
        f"👥 <b>کاربران</b>\n"
        f"  ├ کل: <b>{_fmt(s['total_users'])}</b> نفر\n"
        f"  ├ امروز: +{s['users_today']}\n"
        f"  ├ این هفته: +{s['users_week']}\n"
        f"  ├ این ماه: +{s['users_month']}\n"
        f"  └ بن‌شده: {s['banned_users']}\n"
        f"\n"
        f"💰 <b>مالی</b>\n"
        f"  ├ درآمد کل: <b>{_fmt(s['rev_total'])} تومان</b>\n"
        f"  ├ این ماه: {_fmt(s['rev_month'])} تومان\n"
        f"  ├ امروز: {_fmt(s['rev_today'])} تومان\n"
        f"  └ موجودی کیف پول‌ها: {_fmt(s['total_wallet'])} تومان\n"
        f"\n"
        f"📦 <b>سرویس‌ها</b>\n"
        f"  ├ کل تایید‌شده: {_fmt(s['total_orders'])}\n"
        f"  ├ در انتظار تایید: {s['pending_orders']}\n"
        f"  └ تست رایگان: {s['free_tests']}\n"
        + (f"\n🏆 <b>پرفروش‌ترین پلن‌ها</b>{plans_text}\n" if s["top_plans"] else "")
        + f"\n"
        f"🤝 <b>رفرال:</b> {_fmt(s['total_referrals'])} دعوت موفق\n"
        f"\n"
        f"🎧 <b>پشتیبانی</b>\n"
        f"  ├ تیکت‌های باز: {s['open_tickets']}\n"
        f"  └ کل تیکت‌ها: {_fmt(s['total_tickets'])}\n"
        f"\n"
        f"🕐 <i>{_now_ir()}</i>"
    )

def register_stats_handlers(dp):

    @dp.callback_query(F.data == "admin_stats")
    async def admin_stats(callback: types.CallbackQuery):
        s    = await get_admin_stats()
        text = _build_stats_text(s)
        try:
            await callback.message.edit_text(text, reply_markup=admin_stats_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=admin_stats_keyboard(), parse_mode="HTML")
        await callback.answer()
