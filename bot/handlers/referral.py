from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states import ReferralSettings
from keyboards import admin_referral_menu, admin_referral_sub_keyboard, user_referral_keyboard
from shared_lib.db import (
    get_setting, set_setting,
    get_user, get_user_by_referral_code,
    get_referral_stats,
)

# ─── helpers ─────────────────────────────────

async def _get_referral_cfg() -> dict:
    keys = [
        "referral_enabled", "referral_flat_enabled", "referral_flat_amount",
        "referral_percent_enabled", "referral_percent_value",
        "referral_free_test_enabled",
        "referral_discount_enabled", "referral_discount_value",
    ]
    defaults = {
        "referral_enabled": "0", "referral_flat_enabled": "0", "referral_flat_amount": "50000",
        "referral_percent_enabled": "0", "referral_percent_value": "10",
        "referral_free_test_enabled": "0",
        "referral_discount_enabled": "0", "referral_discount_value": "10",
    }
    cfg = {}
    for k in keys:
        val = await get_setting(k)
        cfg[k] = val if val is not None else defaults[k]
    return cfg

def _bool(cfg, key): return cfg[key] == "1"
def _int(cfg, key): return int(cfg[key] or "0")

async def _show_referral_menu(callback: types.CallbackQuery):
    from handlers.user import _edit_or_replace
    cfg = await _get_referral_cfg()
    await _edit_or_replace(
        callback,
        "🤝 <b>تنظیمات دعوت دوستان</b>",
        admin_referral_menu(
            enabled=_bool(cfg, "referral_enabled"),
            flat_en=_bool(cfg, "referral_flat_enabled"),
            flat_amt=_int(cfg, "referral_flat_amount"),
            pct_en=_bool(cfg, "referral_percent_enabled"),
            pct_val=_int(cfg, "referral_percent_value"),
            free_en=_bool(cfg, "referral_free_test_enabled"),
            disc_en=_bool(cfg, "referral_discount_enabled"),
            disc_val=_int(cfg, "referral_discount_value"),
        )
    )
    await callback.answer()

async def _toggle(key: str):
    cur = await get_setting(key)
    await set_setting(key, "0" if cur == "1" else "1")

# ─── ادمین: منوی اصلی ────────────────────────

def register_referral_handlers(dp):

    @dp.callback_query(F.data == "admin_referral")
    async def admin_referral(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await _show_referral_menu(callback)

    @dp.callback_query(F.data == "referral_toggle_system")
    async def referral_toggle_system(callback: types.CallbackQuery):
        await _toggle("referral_enabled")
        await _show_referral_menu(callback)

    # ── جایزه ثابت ───────────────────────────────

    @dp.callback_query(F.data == "referral_flat")
    async def referral_flat_menu(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        cfg = await _get_referral_cfg()
        status = "✅ فعال" if _bool(cfg, "referral_flat_enabled") else "❌ غیرفعال"
        await _edit_or_replace(
            callback,
            f"💵 <b>جایزه ثابت دعوت‌کننده</b>\n\n"
            f"مبلغ: <b>{_int(cfg, 'referral_flat_amount'):,} تومان</b>\n"
            f"وضعیت: {status}\n\n"
            f"با هر دعوت موفق (اولین خرید) این مبلغ به کیف پول دعوت‌کننده اضافه می‌شه.",
            admin_referral_sub_keyboard("referral_flat_toggle", "referral_flat_edit")
        )
        await callback.answer()

    @dp.callback_query(F.data == "referral_flat_toggle")
    async def referral_flat_toggle(callback: types.CallbackQuery):
        await _toggle("referral_flat_enabled")
        await referral_flat_menu(callback)

    @dp.callback_query(F.data == "referral_flat_edit")
    async def referral_flat_edit_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(ReferralSettings.waiting_for_flat_amount)
        await callback.message.edit_text(
            "💵 مبلغ جایزه ثابت را به تومان وارد کنید:\n<i>مثال: 50000</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data="referral_flat")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(ReferralSettings.waiting_for_flat_amount, F.text)
    async def referral_flat_edit_save(message: types.Message, state: FSMContext):
        text = message.text.strip().replace(",", "")
        if not text.isdigit() or int(text) <= 0:
            await message.answer("❌ عدد صحیح مثبت وارد کنید.")
            return
        await set_setting("referral_flat_amount", text)
        await state.clear()
        await message.answer(f"✅ جایزه ثابت: <b>{int(text):,} تومان</b> ذخیره شد.", parse_mode="HTML",
                             reply_markup=admin_referral_sub_keyboard("referral_flat_toggle", "referral_flat_edit"))

    # ── پورسانت از خرید ──────────────────────────

    @dp.callback_query(F.data == "referral_percent")
    async def referral_percent_menu(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        cfg = await _get_referral_cfg()
        status = "✅ فعال" if _bool(cfg, "referral_percent_enabled") else "❌ غیرفعال"
        await _edit_or_replace(
            callback,
            f"📊 <b>پورسانت از هر خرید</b>\n\n"
            f"درصد: <b>{_int(cfg, 'referral_percent_value')}٪</b>\n"
            f"وضعیت: {status}\n\n"
            f"با هر خریدی که دعوت‌شده انجام بده، این درصد به کیف پول دعوت‌کننده می‌ره.",
            admin_referral_sub_keyboard("referral_percent_toggle", "referral_percent_edit")
        )
        await callback.answer()

    @dp.callback_query(F.data == "referral_percent_toggle")
    async def referral_percent_toggle(callback: types.CallbackQuery):
        await _toggle("referral_percent_enabled")
        await referral_percent_menu(callback)

    @dp.callback_query(F.data == "referral_percent_edit")
    async def referral_percent_edit_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(ReferralSettings.waiting_for_percent_value)
        await callback.message.edit_text(
            "📊 درصد پورسانت را وارد کنید (۱ تا ۱۰۰):\n<i>مثال: 10</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data="referral_percent")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(ReferralSettings.waiting_for_percent_value, F.text)
    async def referral_percent_edit_save(message: types.Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or not (1 <= int(text) <= 100):
            await message.answer("❌ عدد بین ۱ تا ۱۰۰ وارد کنید.")
            return
        await set_setting("referral_percent_value", text)
        await state.clear()
        await message.answer(f"✅ پورسانت: <b>{text}٪</b> ذخیره شد.", parse_mode="HTML",
                             reply_markup=admin_referral_sub_keyboard("referral_percent_toggle", "referral_percent_edit"))

    # ── تست رایگان اضافه ─────────────────────────

    @dp.callback_query(F.data == "referral_free_test")
    async def referral_free_test_menu(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        cfg = await _get_referral_cfg()
        status = "✅ فعال" if _bool(cfg, "referral_free_test_enabled") else "❌ غیرفعال"
        await _edit_or_replace(
            callback,
            f"🎁 <b>تست رایگان اضافه</b>\n\n"
            f"وضعیت: {status}\n\n"
            f"با اولین خرید موفق دعوت‌شده، دعوت‌کننده یه تست رایگان اضافه می‌گیره.",
            admin_referral_sub_keyboard("referral_free_test_toggle", None)
        )
        await callback.answer()

    @dp.callback_query(F.data == "referral_free_test_toggle")
    async def referral_free_test_toggle(callback: types.CallbackQuery):
        await _toggle("referral_free_test_enabled")
        await referral_free_test_menu(callback)

    # ── اعتبار خوش‌آمدگویی ───────────────────────

    @dp.callback_query(F.data == "referral_discount")
    async def referral_discount_menu(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        cfg = await _get_referral_cfg()
        status = "✅ فعال" if _bool(cfg, "referral_discount_enabled") else "❌ غیرفعال"
        await _edit_or_replace(
            callback,
            f"🎫 <b>اعتبار خوش‌آمدگویی کاربر جدید</b>\n\n"
            f"درصد: <b>{_int(cfg, 'referral_discount_value')}٪</b> از اولین خرید\n"
            f"وضعیت: {status}\n\n"
            f"کاربر جدید موقع اولین خریدش این درصد رو به عنوان اعتبار کیف پول می‌گیره.",
            admin_referral_sub_keyboard("referral_discount_toggle", "referral_discount_edit")
        )
        await callback.answer()

    @dp.callback_query(F.data == "referral_discount_toggle")
    async def referral_discount_toggle(callback: types.CallbackQuery):
        await _toggle("referral_discount_enabled")
        await referral_discount_menu(callback)

    @dp.callback_query(F.data == "referral_discount_edit")
    async def referral_discount_edit_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(ReferralSettings.waiting_for_discount_value)
        await callback.message.edit_text(
            "🎫 درصد اعتبار خوش‌آمدگویی را وارد کنید (۱ تا ۱۰۰):\n<i>مثال: 10</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data="referral_discount")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(ReferralSettings.waiting_for_discount_value, F.text)
    async def referral_discount_edit_save(message: types.Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit() or not (1 <= int(text) <= 100):
            await message.answer("❌ عدد بین ۱ تا ۱۰۰ وارد کنید.")
            return
        await set_setting("referral_discount_value", text)
        await state.clear()
        await message.answer(f"✅ اعتبار خوش‌آمدگویی: <b>{text}٪</b> ذخیره شد.", parse_mode="HTML",
                             reply_markup=admin_referral_sub_keyboard("referral_discount_toggle", "referral_discount_edit"))

    # ─── کاربر: صفحه دعوت دوستان ─────────────────

    @dp.callback_query(F.data == "referral")
    async def user_referral_page(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        u = callback.from_user
        user = await get_user(u.id)
        if not user or not user["referral_code"]:
            await callback.answer("خطا در دریافت اطلاعات.", show_alert=True)
            return

        cfg = await _get_referral_cfg()
        if not _bool(cfg, "referral_enabled"):
            await callback.answer("سیستم دعوت دوستان در حال حاضر غیرفعال است.", show_alert=True)
            return

        bot_info = await callback.bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user['referral_code']}"
        stats = await get_referral_stats(u.id)

        rewards_text = ""
        if _bool(cfg, "referral_flat_enabled"):
            rewards_text += f"\n💵 جایزه ثابت: <b>{_int(cfg, 'referral_flat_amount'):,} تومان</b> به ازای هر دعوت"
        if _bool(cfg, "referral_percent_enabled"):
            rewards_text += f"\n📊 پورسانت: <b>{_int(cfg, 'referral_percent_value')}٪</b> از هر خرید دوستت"
        if _bool(cfg, "referral_free_test_enabled"):
            rewards_text += f"\n🎁 <b>یک تست رایگان اضافه</b> برای هر دعوت موفق"
        if _bool(cfg, "referral_discount_enabled"):
            rewards_text += f"\n🎫 دوستت <b>{_int(cfg, 'referral_discount_value')}٪ اعتبار</b> برای اولین خریدش می‌گیره"

        text = (
            f"🤝 <b>دعوت دوستان</b>\n\n"
            f"👥 دعوت‌شدگان: <b>{stats['count']} نفر</b>\n"
            f"💰 جوایز دریافتی: <b>{stats['total']:,} تومان</b>\n\n"
            f"🔗 لینک اختصاصی:\n<code>{ref_link}</code>"
        )
        if rewards_text:
            text += f"\n\n<b>جوایز شما:</b>{rewards_text}"

        await _edit_or_replace(callback, text, user_referral_keyboard(ref_link))
        await callback.answer()
