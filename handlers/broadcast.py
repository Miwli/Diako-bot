import asyncio
import json
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, MessageEntity
from states import Broadcast
from keyboards import admin_broadcast_menu, admin_broadcast_confirm_keyboard
from database import get_all_user_ids, get_active_service_user_ids

_TARGET_LABELS = {
    "all":    "همه کاربران",
    "active": "کاربران با سرویس فعال",
}

def _parse_content(message: types.Message):
    if message.photo:
        ents = json.dumps([e.model_dump() for e in message.caption_entities]) if message.caption_entities else None
        return "photo", message.photo[-1].file_id, message.caption or "", ents
    if message.video:
        ents = json.dumps([e.model_dump() for e in message.caption_entities]) if message.caption_entities else None
        return "video", message.video.file_id, message.caption or "", ents
    if message.text:
        ents = json.dumps([e.model_dump() for e in message.entities]) if message.entities else None
        return "text", None, message.text, ents
    return None, None, None, None

def _load_entities(ents_json):
    if not ents_json:
        return None
    try:
        return [MessageEntity(**e) for e in json.loads(ents_json)]
    except Exception:
        return None

async def _send_one(bot, uid: int, content_type: str, file_id, caption: str, entities):
    if content_type == "text":
        if entities:
            await bot.send_message(uid, caption, entities=entities)
        else:
            await bot.send_message(uid, caption)
    elif content_type == "photo":
        if entities:
            await bot.send_photo(uid, file_id, caption=caption, caption_entities=entities)
        else:
            await bot.send_photo(uid, file_id, caption=caption)
    elif content_type == "video":
        if entities:
            await bot.send_video(uid, file_id, caption=caption, caption_entities=entities)
        else:
            await bot.send_video(uid, file_id, caption=caption)

async def _do_broadcast(bot, status_chat_id: int, status_msg_id: int,
                        user_ids: list, content_type: str,
                        file_id, caption: str, ents_json: str):
    from bot import logger
    entities = _load_entities(ents_json)
    total = len(user_ids)
    sent = failed = 0

    for i, uid in enumerate(user_ids):
        try:
            await _send_one(bot, uid, content_type, file_id, caption, entities)
            sent += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception as e:
            logger.error(f"broadcast error uid={uid}: {e}")
            failed += 1

        if (i + 1) % 20 == 0 or (i + 1) == total:
            try:
                await bot.edit_message_text(
                    f"📢 در حال ارسال...\n\n"
                    f"✅ موفق: {sent}\n"
                    f"❌ ناموفق: {failed}\n"
                    f"📊 {i+1}/{total}",
                    chat_id=status_chat_id,
                    message_id=status_msg_id
                )
            except Exception:
                pass

        await asyncio.sleep(0.05)

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 پیام همگانی جدید", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔙 پنل ادمین",         callback_data="admin_panel")],
    ])
    try:
        await bot.edit_message_text(
            f"✅ پیام همگانی ارسال شد!\n\n"
            f"📨 موفق: {sent}\n"
            f"❌ ناموفق (بلاک یا ارور): {failed}\n"
            f"👥 کل: {total}",
            chat_id=status_chat_id,
            message_id=status_msg_id,
            reply_markup=back_kb
        )
    except Exception:
        pass
    logger.info(f"broadcast done: {sent}/{total} ok, {failed} failed")

def register_broadcast_handlers(dp):

    @dp.callback_query(F.data == "admin_broadcast")
    async def admin_broadcast_main(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        try:
            await callback.message.edit_text(
                "📢 <b>پیام همگانی</b>\n\nمخاطبان را انتخاب کنید:",
                reply_markup=admin_broadcast_menu(),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(
                "📢 <b>پیام همگانی</b>\n\nمخاطبان را انتخاب کنید:",
                reply_markup=admin_broadcast_menu(),
                parse_mode="HTML"
            )
        await callback.answer()

    @dp.callback_query(F.data.in_({"broadcast_target_all", "broadcast_target_active"}))
    async def broadcast_pick_target(callback: types.CallbackQuery, state: FSMContext):
        target = "all" if callback.data == "broadcast_target_all" else "active"
        await state.set_state(Broadcast.waiting_for_content)
        await state.update_data(target=target)
        label = _TARGET_LABELS[target]
        cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_broadcast")]
        ])
        try:
            await callback.message.edit_text(
                f"📢 <b>ارسال به {label}</b>\n\n"
                f"پیام خود را ارسال کنید:\n"
                f"<i>(متن، عکس یا ویدیو با کپشن)</i>",
                reply_markup=cancel_kb,
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(
                f"📢 <b>ارسال به {label}</b>\n\nپیام خود را ارسال کنید:",
                reply_markup=cancel_kb,
                parse_mode="HTML"
            )
        await callback.answer()

    @dp.message(Broadcast.waiting_for_content)
    async def broadcast_receive_content(message: types.Message, state: FSMContext):
        content_type, file_id, caption, ents_json = _parse_content(message)
        if not content_type:
            await message.answer("❌ فقط متن، عکس یا ویدیو ارسال کنید.")
            return

        data = await state.get_data()
        target = data.get("target", "all")

        user_ids = await (get_all_user_ids() if target == "all" else get_active_service_user_ids())
        count = len(user_ids)

        await state.set_state(Broadcast.waiting_for_confirm)
        await state.update_data(
            content_type=content_type,
            file_id=file_id,
            caption=caption,
            ents_json=ents_json,
            user_ids=user_ids,
        )

        await message.answer(
            f"👆 پیش‌نمایش پیام بالا\n\n"
            f"مخاطب: <b>{_TARGET_LABELS[target]}</b> — {count:,} نفر\n\n"
            f"آماده ارسال هستی؟",
            reply_markup=admin_broadcast_confirm_keyboard(count, target),
            parse_mode="HTML"
        )

    @dp.callback_query(Broadcast.waiting_for_confirm, F.data == "broadcast_confirm")
    async def broadcast_confirm(callback: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        await state.clear()

        status_msg = await callback.message.edit_text(
            "📢 شروع ارسال...\n\n✅ موفق: 0\n❌ ناموفق: 0\n📊 0/..."
        )
        asyncio.create_task(_do_broadcast(
            bot=callback.bot,
            status_chat_id=status_msg.chat.id,
            status_msg_id=status_msg.message_id,
            user_ids=data["user_ids"],
            content_type=data["content_type"],
            file_id=data.get("file_id"),
            caption=data["caption"],
            ents_json=data.get("ents_json"),
        ))
        await callback.answer("ارسال شروع شد.")

    @dp.callback_query(F.data == "broadcast_cancel")
    async def broadcast_cancel(callback: types.CallbackQuery, state: FSMContext):
        await state.clear()
        try:
            await callback.message.edit_text(
                "📢 <b>پیام همگانی</b>\n\nمخاطبان را انتخاب کنید:",
                reply_markup=admin_broadcast_menu(),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            await callback.message.delete()
            await callback.message.answer(
                "📢 <b>پیام همگانی</b>\n\nمخاطبان را انتخاب کنید:",
                reply_markup=admin_broadcast_menu(),
                parse_mode="HTML"
            )
        await callback.answer()
