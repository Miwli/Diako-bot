import json
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, MessageEntity
from states import Support, AdminSupportSettings
from keyboards import (
    support_menu_keyboard, ticket_keyboard,
    my_tickets_keyboard, admin_support_settings_keyboard
)
from shared_lib.db import (
    get_setting, set_setting,
    create_ticket, get_ticket, get_ticket_by_topic,
    get_user_open_ticket, get_user_tickets,
    set_ticket_topic, close_ticket as db_close_ticket,
    get_text,
)


def _alert(key: str, **fmt) -> str:
    # show_alert در تلگرام فقط تا ~۲۰۰ کاراکتر نشون می‌ده
    return get_text(key, **fmt)[:200]


def register_support_handlers(dp):

    # ─── منوی پشتیبانی ───────────────────────────

    @dp.callback_query(F.data == "support")
    async def support_menu(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        from handlers.user import _edit_or_replace
        await _edit_or_replace(callback, get_text("support_menu"), support_menu_keyboard())
        await callback.answer()

    @dp.callback_query(F.data == "new_ticket")
    async def new_ticket_start(callback: types.CallbackQuery, state: FSMContext):
        support_group_id = await get_setting("support_group_id")
        if not support_group_id:
            await callback.answer(_alert("support_unavailable"), show_alert=True)
            return

        open_ticket = await get_user_open_ticket(callback.from_user.id)
        if open_ticket:
            await callback.answer(_alert("support_has_open_ticket", id=open_ticket['id']), show_alert=True)
            return

        await state.set_state(Support.waiting_for_first_message)
        await callback.message.edit_text(
            get_text("support_new_ticket_prompt"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 لغو", callback_data="support")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(Support.waiting_for_first_message)
    async def create_ticket_handler(message: types.Message, state: FSMContext):
        support_group_id = await get_setting("support_group_id")
        if not support_group_id:
            await message.answer(get_text("support_unavailable"))
            await state.clear()
            return

        u = message.from_user
        ticket_id = await create_ticket(u.id)

        try:
            group_id = int(support_group_id)
            topic = await message.bot.create_forum_topic(
                chat_id=group_id,
                name=f"تیکت #{ticket_id} — {u.full_name}"
            )
            topic_id = topic.message_thread_id
            await set_ticket_topic(ticket_id, topic_id, group_id)

            user_line = f"👤 {u.full_name}" + (f" (@{u.username})" if u.username else "")
            await message.bot.send_message(
                chat_id=group_id,
                message_thread_id=topic_id,
                text=(
                    f"🎫 <b>تیکت #{ticket_id}</b>\n"
                    f"{'─' * 20}\n"
                    f"{user_line}\n"
                    f"🆔 <code>{u.id}</code>\n"
                    f"{'─' * 20}\n"
                    f"برای بستن: /close"
                ),
                parse_mode="HTML"
            )
            await message.copy_to(chat_id=group_id, message_thread_id=topic_id)

        except Exception as e:
            from bot import logger
            logger.error(f"خطا در ساخت تیکت #{ticket_id}: {e}")
            await db_close_ticket(ticket_id)
            await message.answer(
                get_text("support_error_creating", error=str(e)),
                parse_mode="HTML"
            )
            await state.clear()
            return

        await state.set_state(Support.in_conversation)
        await state.update_data(ticket_id=ticket_id)
        msg_text, msg_entities = await _get_ticket_msg()
        if msg_entities:
            await message.answer(msg_text, reply_markup=ticket_keyboard(ticket_id), entities=msg_entities)
        else:
            await message.answer(msg_text, reply_markup=ticket_keyboard(ticket_id), parse_mode="HTML")

    @dp.message(Support.in_conversation)
    async def forward_user_message(message: types.Message, state: FSMContext):
        data = await state.get_data()
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            await state.clear()
            return

        ticket = await get_ticket(ticket_id)
        if not ticket or ticket["status"] != "open":
            await state.clear()
            await message.answer(get_text("support_ticket_closed"), reply_markup=support_menu_keyboard())
            return

        try:
            await message.copy_to(
                chat_id=ticket["group_id"],
                message_thread_id=ticket["topic_id"]
            )
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در ارسال پیام به تیکت #{ticket_id}: {e}")
            await message.answer(get_text("support_error_send"))

    # ─── تیکت‌های من ──────────────────────────────

    @dp.callback_query(F.data == "my_tickets")
    async def my_tickets(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        tickets = await get_user_tickets(callback.from_user.id)
        if not tickets:
            await _edit_or_replace(callback, get_text("support_tickets_empty"), support_menu_keyboard())
        else:
            await _edit_or_replace(callback, get_text("support_tickets_list"), my_tickets_keyboard(tickets))
        await callback.answer()

    @dp.callback_query(F.data.startswith("view_ticket_"))
    async def view_ticket(callback: types.CallbackQuery, state: FSMContext):
        from handlers.user import _edit_or_replace
        ticket_id = int(callback.data.replace("view_ticket_", ""))
        ticket = await get_ticket(ticket_id)
        if not ticket or ticket["user_id"] != callback.from_user.id:
            await callback.answer(_alert("ticket_not_found"), show_alert=True)
            return

        if ticket["status"] == "open":
            await state.set_state(Support.in_conversation)
            await state.update_data(ticket_id=ticket_id)
            await _edit_or_replace(callback, get_text("support_view_open", id=ticket_id), ticket_keyboard(ticket_id))
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 بازگشت", callback_data="my_tickets")]
            ])
            await _edit_or_replace(callback, get_text("support_view_closed", id=ticket_id), kb)
        await callback.answer()

    @dp.callback_query(F.data.startswith("close_ticket_"))
    async def close_ticket_user(callback: types.CallbackQuery, state: FSMContext):
        from handlers.user import _edit_or_replace
        ticket_id = int(callback.data.replace("close_ticket_", ""))
        ticket = await get_ticket(ticket_id)
        if not ticket or ticket["user_id"] != callback.from_user.id:
            await callback.answer(_alert("ticket_not_found"), show_alert=True)
            return
        if ticket["status"] != "open":
            await callback.answer(_alert("ticket_already_closed"), show_alert=True)
            return

        await _do_close_ticket(ticket, callback.bot)
        await state.clear()

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 بازگشت", callback_data="support")]
        ])
        await _edit_or_replace(callback, get_text("support_close_self", id=ticket_id), kb)
        await callback.answer()

    # ─── گروه: دستورات و پیام‌های ادمین ──────────────

    @dp.message(Command("close"), F.chat.type.in_({"group", "supergroup"}))
    async def close_ticket_command(message: types.Message):
        support_group_id = await get_setting("support_group_id")
        if not support_group_id or str(message.chat.id) != support_group_id:
            return
        if not message.message_thread_id:
            await message.reply("این دستور باید داخل یک تاپیک تیکت اجرا شود.")
            return

        ticket = await get_ticket_by_topic(message.message_thread_id)
        if not ticket:
            await message.reply("تیکتی برای این تاپیک یافت نشد.")
            return
        if ticket["status"] != "open":
            await message.reply("این تیکت قبلاً بسته شده است.")
            return

        await _do_close_ticket(ticket, message.bot)
        try:
            await message.bot.send_message(
                ticket["user_id"],
                get_text("support_closed_by_support", id=ticket['id']),
                parse_mode="HTML",
                reply_markup=support_menu_keyboard()
            )
        except Exception:
            pass
        await message.reply(f"✅ تیکت #{ticket['id']} بسته شد.")

    # ─── متن پیش‌فرض پیام تیکت ──────────────────────

    _DEFAULT_TICKET_MSG = (
        "✅ پیامت دریافت شد.\n\n"
        "تیم پشتیبانی در اسرع وقت جواب می‌ده. "
        "وقتی پاسخ آماده شد همینجا بهت می‌رسه.\n\n"
        "اگه چیز دیگه‌ای هست که بخوای اضافه کنی، همین الان بنویس."
    )

    async def _get_ticket_msg():
        text = await get_setting("support_ticket_msg") or _DEFAULT_TICKET_MSG
        entities_raw = await get_setting("support_ticket_msg_entities") or ""
        entities = None
        if entities_raw:
            try:
                entities = [MessageEntity(**e) for e in json.loads(entities_raw)]
            except Exception:
                entities = None
        return text, entities

    @dp.message(F.chat.type.in_({"group", "supergroup"}), F.from_user.is_bot == False, ~F.text.startswith("/"))
    async def handle_group_message(message: types.Message):
        support_group_id = await get_setting("support_group_id")
        if not support_group_id or str(message.chat.id) != support_group_id:
            return
        if not message.message_thread_id:
            return

        ticket = await get_ticket_by_topic(message.message_thread_id)
        if not ticket or ticket["status"] != "open":
            return

        try:
            await message.copy_to(ticket["user_id"])
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در ارسال پاسخ به کاربر (تیکت #{ticket['id']}): {e}")

    async def _do_close_ticket(ticket, bot):
        await db_close_ticket(ticket["id"])
        try:
            await bot.close_forum_topic(
                chat_id=ticket["group_id"],
                message_thread_id=ticket["topic_id"]
            )
        except Exception as e:
            from bot import logger
            logger.error(f"خطا در بستن تاپیک تیکت #{ticket['id']}: {e}")

    # ─── تنظیمات پشتیبانی (ادمین) ─────────────────

    @dp.callback_query(F.data == "admin_support")
    async def admin_support_settings(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        group_id = await get_setting("support_group_id") or "تنظیم نشده"
        await _edit_or_replace(
            callback,
            get_text("admin_support_settings_text", group_id=group_id),
            admin_support_settings_keyboard()
        )
        await callback.answer()

    @dp.callback_query(F.data == "admin_support_set_group")
    async def admin_support_set_group_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(AdminSupportSettings.waiting_for_group_id)
        await callback.message.edit_text(
            get_text("admin_support_ask_group_id"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 لغو", callback_data="admin_support")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(AdminSupportSettings.waiting_for_group_id, F.text)
    async def admin_support_set_group_save(message: types.Message, state: FSMContext):
        raw = message.text.strip()
        if not raw.lstrip("-").isdigit():
            await message.answer(get_text("admin_support_group_id_invalid"), parse_mode="HTML")
            return
        await set_setting("support_group_id", raw)
        await state.clear()
        await message.answer(
            get_text("admin_support_group_id_saved", group_id=raw),
            parse_mode="HTML",
            reply_markup=admin_support_settings_keyboard()
        )

    @dp.callback_query(F.data == "admin_support_edit_msg")
    async def admin_support_edit_msg_start(callback: types.CallbackQuery, state: FSMContext):
        current_text, _ = await _get_ticket_msg()
        await state.set_state(AdminSupportSettings.waiting_for_ticket_msg)
        await callback.message.edit_text(
            get_text("admin_support_ask_ticket_msg", current=current_text),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 لغو", callback_data="admin_support")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(AdminSupportSettings.waiting_for_ticket_msg, F.text)
    async def admin_support_edit_msg_save(message: types.Message, state: FSMContext):
        text = message.text
        entities = message.entities or []
        has_premium = any(e.type == "custom_emoji" for e in entities)

        await set_setting("support_ticket_msg", text)
        if entities:
            await set_setting("support_ticket_msg_entities", json.dumps([e.model_dump() for e in entities]))
        else:
            await set_setting("support_ticket_msg_entities", "")

        await state.clear()
        note = " (با ایموجی پرمیوم)" if has_premium else ""
        await message.answer(
            get_text("admin_support_ticket_msg_saved", note=note),
            reply_markup=admin_support_settings_keyboard()
        )
