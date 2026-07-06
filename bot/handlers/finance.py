from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import AddCard, EditCard
from keyboards import (
    admin_finance_menu, cards_table_keyboard, card_item_keyboard,
    confirm_delete_card_keyboard, cancel_keyboard,
)
from shared_lib.db import (
    get_setting, set_setting, get_text,
    get_payment_cards, get_payment_card, add_payment_card,
    update_payment_card, toggle_payment_card, delete_payment_card,
)

_MODE_TEXT_KEYS = {
    "round_robin": "admin_card_mode_round_robin",
    "random":      "admin_card_mode_random",
    "fixed":       "admin_card_mode_fixed",
}

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

    async def _show_cards_list(callback: types.CallbackQuery):
        cards = await get_payment_cards()
        mode = await get_setting("card_select_mode") or "round_robin"
        text = get_text("admin_cards_list_text", mode=get_text(_MODE_TEXT_KEYS[mode]))
        if not cards:
            text += "\n\n" + get_text("admin_cards_empty")
        await callback.message.edit_text(
            text,
            reply_markup=cards_table_keyboard(cards, mode),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "card_settings")
    async def card_settings_list(callback: types.CallbackQuery):
        await _show_cards_list(callback)
        await callback.answer()

    @dp.callback_query(F.data.startswith("set_card_mode_"))
    async def set_card_mode(callback: types.CallbackQuery):
        mode = callback.data.replace("set_card_mode_", "")
        await set_setting("card_select_mode", mode)
        await _show_cards_list(callback)
        await callback.answer(get_text("admin_card_mode_changed", mode=get_text(_MODE_TEXT_KEYS[mode])))

    @dp.callback_query(F.data == "add_card")
    async def add_card_start(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text(
            get_text("admin_card_ask_number"),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(AddCard.waiting_for_number)
        await callback.answer()

    @dp.message(AddCard.waiting_for_number)
    async def add_card_number(message: types.Message, state: FSMContext):
        number = message.text.strip().replace(" ", "")
        if not number.isdigit() or len(number) != 16:
            await message.answer(get_text("admin_card_invalid"), reply_markup=cancel_keyboard())
            return
        formatted = f"{number[:4]} {number[4:8]} {number[8:12]} {number[12:]}"
        await state.update_data(number=formatted)
        await message.answer(get_text("admin_card_ask_owner"), reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(AddCard.waiting_for_owner)

    @dp.message(AddCard.waiting_for_owner)
    async def add_card_owner(message: types.Message, state: FSMContext):
        owner = message.text.strip()
        owner = None if owner == "-" else owner
        data = await state.get_data()
        await add_payment_card(data["number"], owner)
        await state.clear()
        cards = await get_payment_cards()
        mode = await get_setting("card_select_mode") or "round_robin"
        await message.answer(
            get_text("admin_card_added"),
            reply_markup=cards_table_keyboard(cards, mode),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data.startswith("card_settings_"))
    async def card_item_settings(callback: types.CallbackQuery):
        card_id = int(callback.data.replace("card_settings_", ""))
        card = await get_payment_card(card_id)
        if not card:
            await callback.answer()
            return
        mode = await get_setting("card_select_mode") or "round_robin"
        fixed_id = await get_setting("card_fixed_id")
        is_fixed = str(fixed_id) == str(card_id)
        status = "✅ فعال" if card["is_active"] else "❌ غیرفعال"
        await callback.message.edit_text(
            get_text("admin_card_settings_text", number=card["number"], owner=card["owner"] or "—", status=status),
            reply_markup=card_item_keyboard(card_id, bool(card["is_active"]), is_fixed, mode),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("toggle_card_item_"))
    async def toggle_card_item(callback: types.CallbackQuery):
        card_id = int(callback.data.replace("toggle_card_item_", ""))
        await toggle_payment_card(card_id)
        cards = await get_payment_cards()
        mode = await get_setting("card_select_mode") or "round_robin"
        await callback.message.edit_reply_markup(reply_markup=cards_table_keyboard(cards, mode))
        await callback.answer()

    @dp.callback_query(F.data.startswith("set_fixed_card_"))
    async def set_fixed_card(callback: types.CallbackQuery):
        card_id = int(callback.data.replace("set_fixed_card_", ""))
        await set_setting("card_fixed_id", str(card_id))
        card = await get_payment_card(card_id)
        mode = await get_setting("card_select_mode") or "round_robin"
        status = "✅ فعال" if card["is_active"] else "❌ غیرفعال"
        await callback.message.edit_text(
            get_text("admin_card_settings_text", number=card["number"], owner=card["owner"] or "—", status=status),
            reply_markup=card_item_keyboard(card_id, bool(card["is_active"]), True, mode),
            parse_mode="HTML"
        )
        await callback.answer(get_text("admin_card_set_fixed"))

    @dp.callback_query(F.data.startswith("edit_card_number_"))
    async def edit_card_number_start(callback: types.CallbackQuery, state: FSMContext):
        card_id = int(callback.data.replace("edit_card_number_", ""))
        await state.update_data(card_id=card_id)
        await callback.message.edit_text(
            get_text("admin_card_ask_edit_number"),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(EditCard.waiting_for_number)
        await callback.answer()

    @dp.message(EditCard.waiting_for_number)
    async def edit_card_number_save(message: types.Message, state: FSMContext):
        number = message.text.strip().replace(" ", "")
        if not number.isdigit() or len(number) != 16:
            await message.answer(get_text("admin_card_invalid"), reply_markup=cancel_keyboard())
            return
        formatted = f"{number[:4]} {number[4:8]} {number[8:12]} {number[12:]}"
        data = await state.get_data()
        card_id = data["card_id"]
        await update_payment_card(card_id, number=formatted)
        await state.clear()
        card = await get_payment_card(card_id)
        mode = await get_setting("card_select_mode") or "round_robin"
        fixed_id = await get_setting("card_fixed_id")
        is_fixed = str(fixed_id) == str(card_id)
        status = "✅ فعال" if card["is_active"] else "❌ غیرفعال"
        await message.answer(
            get_text("admin_card_number_saved") + "\n\n" +
            get_text("admin_card_settings_text", number=card["number"], owner=card["owner"] or "—", status=status),
            reply_markup=card_item_keyboard(card_id, bool(card["is_active"]), is_fixed, mode),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data.startswith("edit_card_owner_"))
    async def edit_card_owner_start(callback: types.CallbackQuery, state: FSMContext):
        card_id = int(callback.data.replace("edit_card_owner_", ""))
        await state.update_data(card_id=card_id)
        await callback.message.edit_text(
            get_text("admin_card_ask_edit_owner"),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(EditCard.waiting_for_owner)
        await callback.answer()

    @dp.message(EditCard.waiting_for_owner)
    async def edit_card_owner_save(message: types.Message, state: FSMContext):
        owner = message.text.strip()
        owner = "" if owner == "-" else owner
        data = await state.get_data()
        card_id = data["card_id"]
        await update_payment_card(card_id, owner=owner)
        await state.clear()
        card = await get_payment_card(card_id)
        mode = await get_setting("card_select_mode") or "round_robin"
        fixed_id = await get_setting("card_fixed_id")
        is_fixed = str(fixed_id) == str(card_id)
        status = "✅ فعال" if card["is_active"] else "❌ غیرفعال"
        await message.answer(
            get_text("admin_card_owner_saved") + "\n\n" +
            get_text("admin_card_settings_text", number=card["number"], owner=card["owner"] or "—", status=status),
            reply_markup=card_item_keyboard(card_id, bool(card["is_active"]), is_fixed, mode),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data.startswith("delete_card_"))
    async def delete_card_confirm(callback: types.CallbackQuery):
        card_id = int(callback.data.replace("delete_card_", ""))
        await callback.message.edit_text(
            get_text("admin_card_delete_confirm"),
            reply_markup=confirm_delete_card_keyboard(card_id),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("confirmed_delete_card_"))
    async def delete_card_confirmed(callback: types.CallbackQuery):
        card_id = int(callback.data.replace("confirmed_delete_card_", ""))
        await delete_payment_card(card_id)
        await callback.answer(get_text("admin_card_deleted"))
        await _show_cards_list(callback)
