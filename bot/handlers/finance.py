from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import SetCardInfo
from keyboards import admin_finance_menu, card_settings_keyboard, cancel_keyboard
from database import get_setting, set_setting

def register_finance_handlers(dp):

    @dp.callback_query(F.data == "admin_finance")
    async def admin_finance(callback: types.CallbackQuery):
        card_active = await get_setting("card_active")
        is_active = card_active == "1"
        await callback.message.edit_text(
            "💰 <b>مدیریت مالی</b>\n\nروش‌های پرداخت فعال را مدیریت کنید:",
            reply_markup=admin_finance_menu(is_active),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data == "noop")
    async def noop(callback: types.CallbackQuery):
        await callback.answer()

    @dp.callback_query(F.data == "toggle_card")
    async def toggle_card(callback: types.CallbackQuery):
        card_active = await get_setting("card_active")
        new_value = "0" if card_active == "1" else "1"
        await set_setting("card_active", new_value)
        is_active = new_value == "1"
        await callback.message.edit_reply_markup(
            reply_markup=admin_finance_menu(is_active)
        )
        status = "روشن" if is_active else "خاموش"
        await callback.answer(f"کارت به کارت {status} شد.")

    @dp.callback_query(F.data == "card_settings")
    async def card_settings(callback: types.CallbackQuery):
        card_number = await get_setting("card_number") or "تنظیم نشده"
        card_owner = await get_setting("card_owner") or "تنظیم نشده"
        await callback.message.edit_text(
            f"⚙️ <b>تنظیمات کارت به کارت</b>\n"
            f"{'─' * 24}\n"
            f"💳 شماره کارت: <code>{card_number}</code>\n"
            f"👤 نام صاحب کارت: {card_owner}",
            reply_markup=card_settings_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data == "set_card_number")
    async def set_card_number_start(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text(
            "💳 شماره کارت جدید را وارد کنید:\n\nمثال: <code>6219 8610 3452 9876</code>",
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(SetCardInfo.waiting_for_card_number)
        await callback.answer()

    @dp.message(SetCardInfo.waiting_for_card_number)
    async def save_card_number(message: types.Message, state: FSMContext):
        number = message.text.strip().replace(" ", "")
        if not number.isdigit() or len(number) not in (16,):
            await message.answer(
                "❌ شماره کارت باید ۱۶ رقم باشد.\nدوباره وارد کنید:",
                reply_markup=cancel_keyboard()
            )
            return
        formatted = f"{number[:4]} {number[4:8]} {number[8:12]} {number[12:]}"
        await set_setting("card_number", formatted)
        await state.clear()
        await message.answer(
            f"✅ شماره کارت ذخیره شد:\n<code>{formatted}</code>",
            reply_markup=card_settings_keyboard(),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "set_card_owner")
    async def set_card_owner_start(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text(
            "👤 نام صاحب کارت را وارد کنید:",
            reply_markup=cancel_keyboard()
        )
        await state.set_state(SetCardInfo.waiting_for_card_owner)
        await callback.answer()

    @dp.message(SetCardInfo.waiting_for_card_owner)
    async def save_card_owner(message: types.Message, state: FSMContext):
        await set_setting("card_owner", message.text.strip())
        await state.clear()
        await message.answer(
            f"✅ نام صاحب کارت ذخیره شد: {message.text.strip()}",
            reply_markup=card_settings_keyboard()
        )
