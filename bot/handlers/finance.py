from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import SetCardInfo
from keyboards import admin_finance_menu, card_settings_keyboard, cancel_keyboard
from shared_lib.db import get_setting, set_setting, get_text

def register_finance_handlers(dp):

    @dp.callback_query(F.data == "admin_finance")
    async def admin_finance(callback: types.CallbackQuery):
        card_active = await get_setting("card_active")
        is_active = card_active == "1"
        await callback.message.edit_text(
            get_text("admin_finance_title"),
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
            get_text("admin_card_settings_text", number=card_number, owner=card_owner),
            reply_markup=card_settings_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data == "set_card_number")
    async def set_card_number_start(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text(
            get_text("admin_card_ask_number"),
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
                get_text("admin_card_invalid"),
                reply_markup=cancel_keyboard()
            )
            return
        formatted = f"{number[:4]} {number[4:8]} {number[8:12]} {number[12:]}"
        await set_setting("card_number", formatted)
        await state.clear()
        await message.answer(
            get_text("admin_card_number_saved", number=formatted),
            reply_markup=card_settings_keyboard(),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "set_card_owner")
    async def set_card_owner_start(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text(
            get_text("admin_card_ask_owner"),
            reply_markup=cancel_keyboard()
        )
        await state.set_state(SetCardInfo.waiting_for_card_owner)
        await callback.answer()

    @dp.message(SetCardInfo.waiting_for_card_owner)
    async def save_card_owner(message: types.Message, state: FSMContext):
        name = message.text.strip()
        await set_setting("card_owner", name)
        await state.clear()
        await message.answer(
            get_text("admin_card_owner_saved", name=name),
            reply_markup=card_settings_keyboard()
        )
