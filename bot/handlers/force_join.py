from aiogram import types, F
from aiogram.fsm.context import FSMContext
from states import AddChannel, EditChannel
from keyboards import (
    admin_force_join_menu, channels_table_keyboard, channel_item_keyboard,
    confirm_delete_channel_keyboard, cancel_keyboard,
)
from shared_lib.db import (
    get_setting, set_setting, get_text,
    get_required_channels, get_required_channel, add_required_channel,
    update_required_channel, toggle_required_channel, delete_required_channel,
)
from force_join_check import get_missing_channels


def _valid_chat_id(raw: str) -> bool:
    if raw.startswith("@") and len(raw) > 1:
        return True
    if raw.startswith("-100") and raw[1:].isdigit():
        return True
    return False


def register_force_join_handlers(dp):

    @dp.callback_query(F.data == "admin_force_join")
    async def admin_force_join(callback: types.CallbackQuery):
        enabled = await get_setting("force_join_enabled")
        await callback.message.edit_text(
            get_text("admin_force_join_title"),
            reply_markup=admin_force_join_menu(enabled == "1"),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data == "toggle_force_join")
    async def toggle_force_join(callback: types.CallbackQuery):
        enabled = await get_setting("force_join_enabled")
        new_value = "0" if enabled == "1" else "1"
        await set_setting("force_join_enabled", new_value)
        await callback.message.edit_reply_markup(reply_markup=admin_force_join_menu(new_value == "1"))
        status = "روشن" if new_value == "1" else "خاموش"
        await callback.answer(f"جوین اجباری {status} شد.")

    async def _show_channels_list(callback: types.CallbackQuery):
        channels = await get_required_channels()
        text = get_text("admin_channels_list_text")
        if not channels:
            text += "\n\n" + get_text("admin_channels_empty")
        await callback.message.edit_text(
            text,
            reply_markup=channels_table_keyboard(channels),
            parse_mode="HTML"
        )

    @dp.callback_query(F.data == "list_channels")
    async def list_channels(callback: types.CallbackQuery):
        await _show_channels_list(callback)
        await callback.answer()

    @dp.callback_query(F.data == "add_channel")
    async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.edit_text(
            get_text("admin_channel_ask_id"),
            reply_markup=cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.set_state(AddChannel.waiting_for_chat_id)
        await callback.answer()

    @dp.message(AddChannel.waiting_for_chat_id)
    async def add_channel_id(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not _valid_chat_id(raw):
            await message.answer(get_text("admin_channel_id_invalid"), reply_markup=cancel_keyboard(), parse_mode="HTML")
            return
        await state.update_data(chat_id=raw)
        await message.answer(get_text("admin_channel_ask_title"), reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(AddChannel.waiting_for_title)

    @dp.message(AddChannel.waiting_for_title)
    async def add_channel_title(message: types.Message, state: FSMContext):
        await state.update_data(title=message.text.strip())
        await message.answer(get_text("admin_channel_ask_link"), reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(AddChannel.waiting_for_link)

    @dp.message(AddChannel.waiting_for_link)
    async def add_channel_link(message: types.Message, state: FSMContext):
        link = message.text.strip()
        link = None if link == "-" else link
        data = await state.get_data()
        await add_required_channel(data["chat_id"], data["title"], link)
        await state.clear()
        channels = await get_required_channels()
        await message.answer(
            get_text("admin_channel_added"),
            reply_markup=channels_table_keyboard(channels),
            parse_mode="HTML"
        )

    async def _channel_settings_text_and_kb(channel_id: int):
        channel = await get_required_channel(channel_id)
        status = "✅ فعال" if channel["is_active"] else "❌ غیرفعال"
        text = get_text(
            "admin_channel_settings_text",
            chat_id=channel["chat_id"],
            title=channel["title"] or "—",
            link=channel["invite_link"] or "—",
            status=status,
        )
        return text, channel_item_keyboard(channel_id, bool(channel["is_active"]))

    @dp.callback_query(F.data.startswith("channel_settings_"))
    async def channel_item_settings(callback: types.CallbackQuery):
        channel_id = int(callback.data.replace("channel_settings_", ""))
        channel = await get_required_channel(channel_id)
        if not channel:
            await callback.answer()
            return
        text, kb = await _channel_settings_text_and_kb(channel_id)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()

    @dp.callback_query(F.data.startswith("toggle_channel_"))
    async def toggle_channel_item(callback: types.CallbackQuery):
        channel_id = int(callback.data.replace("toggle_channel_", ""))
        await toggle_required_channel(channel_id)
        channels = await get_required_channels()
        await callback.message.edit_reply_markup(reply_markup=channels_table_keyboard(channels))
        await callback.answer()

    @dp.callback_query(F.data.startswith("edit_channel_id_"))
    async def edit_channel_id_start(callback: types.CallbackQuery, state: FSMContext):
        channel_id = int(callback.data.replace("edit_channel_id_", ""))
        await state.update_data(channel_id=channel_id)
        await callback.message.edit_text(get_text("admin_channel_ask_edit_id"), reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(EditChannel.waiting_for_chat_id)
        await callback.answer()

    @dp.message(EditChannel.waiting_for_chat_id)
    async def edit_channel_id_save(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not _valid_chat_id(raw):
            await message.answer(get_text("admin_channel_id_invalid"), reply_markup=cancel_keyboard(), parse_mode="HTML")
            return
        data = await state.get_data()
        channel_id = data["channel_id"]
        await update_required_channel(channel_id, chat_id=raw)
        await state.clear()
        text, kb = await _channel_settings_text_and_kb(channel_id)
        await message.answer(get_text("admin_channel_id_saved") + "\n\n" + text, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data.startswith("edit_channel_title_"))
    async def edit_channel_title_start(callback: types.CallbackQuery, state: FSMContext):
        channel_id = int(callback.data.replace("edit_channel_title_", ""))
        await state.update_data(channel_id=channel_id)
        await callback.message.edit_text(get_text("admin_channel_ask_edit_title"), reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(EditChannel.waiting_for_title)
        await callback.answer()

    @dp.message(EditChannel.waiting_for_title)
    async def edit_channel_title_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        channel_id = data["channel_id"]
        await update_required_channel(channel_id, title=message.text.strip())
        await state.clear()
        text, kb = await _channel_settings_text_and_kb(channel_id)
        await message.answer(get_text("admin_channel_title_saved") + "\n\n" + text, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data.startswith("edit_channel_link_"))
    async def edit_channel_link_start(callback: types.CallbackQuery, state: FSMContext):
        channel_id = int(callback.data.replace("edit_channel_link_", ""))
        await state.update_data(channel_id=channel_id)
        await callback.message.edit_text(get_text("admin_channel_ask_edit_link"), reply_markup=cancel_keyboard(), parse_mode="HTML")
        await state.set_state(EditChannel.waiting_for_link)
        await callback.answer()

    @dp.message(EditChannel.waiting_for_link)
    async def edit_channel_link_save(message: types.Message, state: FSMContext):
        link = message.text.strip()
        link = "" if link == "-" else link
        data = await state.get_data()
        channel_id = data["channel_id"]
        await update_required_channel(channel_id, invite_link=link)
        await state.clear()
        text, kb = await _channel_settings_text_and_kb(channel_id)
        await message.answer(get_text("admin_channel_link_saved") + "\n\n" + text, reply_markup=kb, parse_mode="HTML")

    @dp.callback_query(F.data.startswith("delete_channel_"))
    async def delete_channel_confirm(callback: types.CallbackQuery):
        channel_id = int(callback.data.replace("delete_channel_", ""))
        await callback.message.edit_text(
            get_text("admin_channel_delete_confirm"),
            reply_markup=confirm_delete_channel_keyboard(channel_id),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("confirmed_delete_channel_"))
    async def delete_channel_confirmed(callback: types.CallbackQuery):
        channel_id = int(callback.data.replace("confirmed_delete_channel_", ""))
        await delete_required_channel(channel_id)
        await callback.answer(get_text("admin_channel_deleted"))
        await _show_channels_list(callback)

    @dp.callback_query(F.data == "check_force_join")
    async def check_force_join(callback: types.CallbackQuery):
        missing = await get_missing_channels(callback.bot, callback.from_user.id)
        if missing:
            await callback.answer(get_text("force_join_still_missing"), show_alert=True)
            return

        from shared_lib.db import get_or_create_user, get_user as _get_user
        from bot import is_admin
        u = callback.from_user
        await get_or_create_user(u.id, u.first_name, u.username)
        _u = await _get_user(u.id)
        if _u and _u["is_banned"] and not is_admin(u.id):
            await callback.answer()
            await callback.message.edit_text(get_text("start_banned"))
            return

        from handlers.user import _send_main_menu
        await _send_main_menu(callback, u)
