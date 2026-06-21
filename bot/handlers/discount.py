import re
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states import AddDiscountCode, ApplyDiscount
from keyboards import (
    admin_discount_menu, admin_discount_item_keyboard,
    discount_type_keyboard, discount_expiry_keyboard,
    proforma_keyboard,
)
from shared_lib.db import (
    get_discount_codes, get_discount_code_by_id,
    create_discount_code, toggle_discount_code, delete_discount_code,
    validate_discount_code, get_plan, get_user_wallet_stats,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def _code_detail(c) -> str:
    type_label = f"{c['value']}٪ تخفیف" if c["type"] == "percent" else f"{c['value']:,} تومان تخفیف"
    uses       = f"{c['used_count']}" + (f" از {c['max_uses']}" if c["max_uses"] else " (نامحدود)")
    status     = "✅ فعال" if c["is_active"] else "❌ غیرفعال"
    expiry     = c["expires_at"] or "ندارد"
    return (
        f"🎟 <b>کد تخفیف: <code>{c['code']}</code></b>\n\n"
        f"🏷 نوع: {type_label}\n"
        f"📊 استفاده‌شده: {uses}\n"
        f"📅 انقضا: {expiry}\n"
        f"🚦 وضعیت: {status}"
    )

async def _show_list(target):
    codes = await get_discount_codes()
    text  = "🎟 <b>کدهای تخفیف</b>"
    kb    = admin_discount_menu(codes)
    if isinstance(target, types.CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except TelegramBadRequest:
            await target.message.delete()
            await target.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")

def register_discount_handlers(dp):

    # ─── ادمین: لیست ──────────────────────────────

    @dp.callback_query(F.data == "admin_discount")
    async def admin_discount(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        await _show_list(callback)

    # ─── ادمین: نمایش آیتم ────────────────────────

    @dp.callback_query(F.data.startswith("discount_item_"))
    async def discount_item(callback: types.CallbackQuery):
        code_id = int(callback.data.replace("discount_item_", ""))
        c = await get_discount_code_by_id(code_id)
        if not c:
            await callback.answer("کد یافت نشد.", show_alert=True)
            return
        try:
            await callback.message.edit_text(
                _code_detail(c),
                reply_markup=admin_discount_item_keyboard(code_id, bool(c["is_active"])),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(
                _code_detail(c),
                reply_markup=admin_discount_item_keyboard(code_id, bool(c["is_active"])),
                parse_mode="HTML"
            )
        await callback.answer()

    @dp.callback_query(F.data.startswith("discount_toggle_"))
    async def discount_toggle(callback: types.CallbackQuery):
        code_id = int(callback.data.replace("discount_toggle_", ""))
        await toggle_discount_code(code_id)
        await discount_item(callback)

    @dp.callback_query(F.data.startswith("discount_delete_"))
    async def discount_delete(callback: types.CallbackQuery):
        code_id = int(callback.data.replace("discount_delete_", ""))
        await delete_discount_code(code_id)
        await callback.answer("✅ کد حذف شد.")
        await _show_list(callback)

    # ─── ادمین: افزودن کد ─────────────────────────

    @dp.callback_query(F.data == "discount_add")
    async def discount_add_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(AddDiscountCode.waiting_for_code)
        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_discount")]
        ])
        await callback.message.edit_text(
            "🎟 <b>افزودن کد تخفیف</b>\n\n"
            "کد تخفیف را وارد کنید:\n"
            "<i>(فقط حروف انگلیسی و اعداد — مثال: SUMMER30)</i>",
            reply_markup=cancel_kb, parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(AddDiscountCode.waiting_for_code, F.text)
    async def discount_add_code(message: types.Message, state: FSMContext):
        code = message.text.strip().upper()
        if not re.match(r"^[A-Z0-9_-]{2,20}$", code):
            await message.answer("❌ کد باید ۲ تا ۲۰ کاراکتر انگلیسی یا عدد باشد.")
            return
        existing = await validate_discount_code(code)
        if existing:
            await message.answer("❌ این کد قبلاً ثبت شده.")
            return
        await state.update_data(code=code)
        await state.set_state(AddDiscountCode.waiting_for_type)
        await message.answer(
            f"✅ کد: <code>{code}</code>\n\nنوع تخفیف را انتخاب کنید:",
            reply_markup=discount_type_keyboard(), parse_mode="HTML"
        )

    @dp.callback_query(AddDiscountCode.waiting_for_type, F.data.in_({"discount_type_percent", "discount_type_fixed"}))
    async def discount_add_type(callback: types.CallbackQuery, state: FSMContext):
        type_ = "percent" if callback.data == "discount_type_percent" else "fixed"
        await state.update_data(type_=type_)
        await state.set_state(AddDiscountCode.waiting_for_value)
        hint = "درصد (۱ تا ۱۰۰)" if type_ == "percent" else "مبلغ به تومان (مثال: 50000)"
        await callback.message.edit_text(
            f"مقدار تخفیف را وارد کنید ({hint}):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_discount")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(AddDiscountCode.waiting_for_value, F.text)
    async def discount_add_value(message: types.Message, state: FSMContext):
        text = message.text.strip().replace(",", "")
        data = await state.get_data()
        if not text.isdigit() or int(text) <= 0:
            await message.answer("❌ عدد مثبت وارد کنید.")
            return
        value = int(text)
        if data["type_"] == "percent" and value > 100:
            await message.answer("❌ درصد باید بین ۱ تا ۱۰۰ باشد.")
            return
        await state.update_data(value=value)
        await state.set_state(AddDiscountCode.waiting_for_max_uses)
        await message.answer(
            "حداکثر تعداد استفاده را وارد کنید:\n<i>(۰ = نامحدود)</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_discount")]
            ]),
            parse_mode="HTML"
        )

    @dp.message(AddDiscountCode.waiting_for_max_uses, F.text)
    async def discount_add_max_uses(message: types.Message, state: FSMContext):
        text = message.text.strip()
        if not text.isdigit():
            await message.answer("❌ عدد صحیح وارد کنید.")
            return
        await state.update_data(max_uses=int(text))
        await state.set_state(AddDiscountCode.waiting_for_expiry)
        await message.answer(
            "تاریخ انقضا را وارد کنید:\n<i>(فرمت: YYYY-MM-DD  مثال: 2025-12-31)</i>",
            reply_markup=discount_expiry_keyboard(), parse_mode="HTML"
        )

    @dp.callback_query(AddDiscountCode.waiting_for_expiry, F.data == "discount_expiry_none")
    async def discount_add_no_expiry(callback: types.CallbackQuery, state: FSMContext):
        await _finish_add(callback.message, state, expires_at=None)
        await callback.answer()

    @dp.message(AddDiscountCode.waiting_for_expiry, F.text)
    async def discount_add_expiry(message: types.Message, state: FSMContext):
        date = message.text.strip()
        if not _DATE_RE.match(date):
            await message.answer("❌ فرمت اشتباه. مثال: 2025-12-31")
            return
        await _finish_add(message, state, expires_at=date)

    async def _finish_add(target, state: FSMContext, expires_at):
        data = await state.get_data()
        await state.clear()
        await create_discount_code(data["code"], data["type_"], data["value"], data["max_uses"], expires_at)
        type_label = f"{data['value']}٪" if data["type_"] == "percent" else f"{data['value']:,} تومان"
        text = (
            f"✅ <b>کد تخفیف ساخته شد!</b>\n\n"
            f"🎟 کد: <code>{data['code']}</code>\n"
            f"🏷 تخفیف: {type_label}\n"
            f"📊 محدودیت: {'نامحدود' if not data['max_uses'] else data['max_uses']}\n"
            f"📅 انقضا: {expires_at or 'ندارد'}"
        )
        if hasattr(target, "edit_text"):
            await target.edit_text(text, parse_mode="HTML")
        else:
            await target.answer(text, parse_mode="HTML")
        await _show_list(target)

    # ─── کاربر: اعمال کد تخفیف ───────────────────

    @dp.callback_query(F.data.startswith("apply_discount_"))
    async def apply_discount_start(callback: types.CallbackQuery, state: FSMContext):
        plan_id = int(callback.data.replace("apply_discount_", ""))
        await state.set_state(ApplyDiscount.waiting_for_code)
        await state.update_data(plan_id=plan_id)
        await callback.message.edit_text(
            "🎟 کد تخفیف خود را وارد کنید:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"user_plan_{plan_id}")]
            ])
        )
        await callback.answer()

    @dp.message(ApplyDiscount.waiting_for_code, F.text)
    async def apply_discount_code(message: types.Message, state: FSMContext):
        code_text = message.text.strip()
        data      = await state.get_data()
        plan_id   = data["plan_id"]
        await state.clear()

        code = await validate_discount_code(code_text, user_id=message.from_user.id)
        if not code:
            await message.answer(
                "❌ این کد تخفیف معتبر نیست، منقضی شده یا قبلاً استفاده کرده‌اید.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"user_plan_{plan_id}")]
                ])
            )
            return

        plan = await get_plan(plan_id)
        if not plan:
            await message.answer("❌ پلن یافت نشد.")
            return

        original  = plan["price"]
        if code["type"] == "percent":
            discount = original * code["value"] // 100
        else:
            discount = min(code["value"], original)
        final = original - discount

        stats       = await get_user_wallet_stats(message.from_user.id)
        has_balance = stats["balance"] >= final

        text = (
            f"🧾 <b>پیش‌فاکتور</b>\n"
            f"{'─' * 24}\n"
            f"📦 <b>پلن:</b> {plan['name']}\n"
            f"📊 <b>حجم:</b> {plan['traffic']} گیگابایت\n"
            f"📅 <b>مدت:</b> {plan['duration']} روز\n"
            f"{'─' * 24}\n"
            f"💰 قیمت اصلی: <s>{original:,}</s> تومان\n"
            f"🎟 تخفیف کد <code>{code['code']}</code>: {discount:,} تومان\n"
            f"✅ <b>مبلغ نهایی: {final:,} تومان</b>"
        )
        if has_balance:
            text += f"\n💎 موجودی کیف پول: {stats['balance']:,} تومان"

        await message.answer(
            text,
            reply_markup=proforma_keyboard(plan_id, has_balance=has_balance, has_discount=True),
            parse_mode="HTML"
        )

        await state.update_data(
            plan_id=plan_id,
            discount_code=code["code"],
            discount_code_id=code["id"],
            discount_amount=discount,
            final_price=final,
        )