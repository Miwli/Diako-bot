import json
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, MessageEntity
from states import AddTutorial, EditTutorial, AddFAQ, EditFAQ
from keyboards import (
    admin_tutorials_menu, admin_tutorial_list_menu, admin_tutorial_item_keyboard,
    admin_faqs_menu, admin_faq_item_keyboard,
    user_tutorials_keyboard, user_faqs_keyboard,
    back_to_tutorials_keyboard, back_to_faqs_keyboard,
)
from database import (
    get_tutorials, get_tutorial, create_tutorial, update_tutorial,
    toggle_tutorial, delete_tutorial, move_tutorial,
    get_faqs, get_faq, create_faq, update_faq, toggle_faq, delete_faq,
)

_CANCEL_TUTORIALS = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_tutorial_list")]
])
_CANCEL_FAQS = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 انصراف", callback_data="admin_faqs")]
])

def register_tutorial_handlers(dp):

    # ── ادمین: صفحه اصلی آموزش‌ها ─────────────────

    @dp.callback_query(F.data == "admin_tutorials")
    async def admin_tutorials(callback: types.CallbackQuery, state: FSMContext):
        from handlers.user import _edit_or_replace
        await state.clear()
        await _edit_or_replace(callback, "📚 <b>مدیریت آموزش‌ها</b>", admin_tutorials_menu())
        await callback.answer()

    @dp.callback_query(F.data == "admin_tutorial_list")
    async def admin_tutorial_list(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        tutorials = await get_tutorials()
        await _edit_or_replace(
            callback,
            f"📖 <b>آموزش‌ها</b>\n\n{len(tutorials)} آموزش ثبت شده",
            admin_tutorial_list_menu(tutorials)
        )
        await callback.answer()

    # ── ادمین: افزودن آموزش ────────────────────────

    @dp.callback_query(F.data == "tutorial_add")
    async def tutorial_add_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(AddTutorial.waiting_for_title)
        await callback.message.edit_text(
            "📝 عنوان آموزش را وارد کنید:\n<i>(این متن روی دکمه نمایش داده می‌شه)</i>",
            reply_markup=_CANCEL_TUTORIALS, parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(AddTutorial.waiting_for_title, F.text)
    async def tutorial_add_title(message: types.Message, state: FSMContext):
        await state.update_data(title=message.text.strip())
        await state.set_state(AddTutorial.waiting_for_content)
        await message.answer(
            "📎 محتوای آموزش را ارسال کنید:\n"
            "<i>متن، عکس یا ویدیو — ربات نوع را تشخیص می‌دهد.</i>",
            reply_markup=_CANCEL_TUTORIALS, parse_mode="HTML"
        )

    @dp.message(AddTutorial.waiting_for_content)
    async def tutorial_add_content(message: types.Message, state: FSMContext):
        data = await state.get_data()
        content_type, file_id, caption, entities_json = _parse_content(message)
        if content_type is None:
            await message.answer("❌ نوع پیام پشتیبانی نمی‌شود. متن، عکس یا ویدیو ارسال کنید.")
            return
        await create_tutorial(data["title"], content_type, file_id, caption, entities_json)
        await state.clear()
        tutorials = await get_tutorials()
        await message.answer(
            f"✅ آموزش «{data['title']}» اضافه شد.",
            reply_markup=admin_tutorial_list_menu(tutorials)
        )

    # ── ادمین: مدیریت آموزش موجود ─────────────────

    async def _show_tutorial_item(callback: types.CallbackQuery, tid: int):
        from handlers.user import _edit_or_replace
        t = await get_tutorial(tid)
        if not t:
            await callback.answer("آموزش یافت نشد.", show_alert=True)
            return
        tutorials = await get_tutorials()
        ids = [x["id"] for x in tutorials]
        pos = ids.index(tid) if tid in ids else 0
        text = (
            f"📚 <b>{t['title']}</b>\n\n"
            f"نوع: {_type_label(t['content_type'])}\n"
            f"وضعیت: {'✅ فعال' if t['is_active'] else '❌ غیرفعال'}"
        )
        await _edit_or_replace(
            callback, text,
            admin_tutorial_item_keyboard(tid, bool(t["is_active"]), pos == 0, pos == len(ids) - 1)
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("tutorial_item_"))
    async def tutorial_item(callback: types.CallbackQuery):
        tid = int(callback.data.removeprefix("tutorial_item_"))
        await _show_tutorial_item(callback, tid)

    @dp.callback_query(F.data.startswith("tutorial_toggle_"))
    async def tutorial_toggle(callback: types.CallbackQuery):
        tid = int(callback.data.removeprefix("tutorial_toggle_"))
        await toggle_tutorial(tid)
        await _show_tutorial_item(callback, tid)

    @dp.callback_query(F.data.startswith("tutorial_move_up_"))
    async def tutorial_move_up(callback: types.CallbackQuery):
        tid = int(callback.data.removeprefix("tutorial_move_up_"))
        await move_tutorial(tid, "up")
        await _show_tutorial_item(callback, tid)

    @dp.callback_query(F.data.startswith("tutorial_move_down_"))
    async def tutorial_move_down(callback: types.CallbackQuery):
        tid = int(callback.data.removeprefix("tutorial_move_down_"))
        await move_tutorial(tid, "down")
        await _show_tutorial_item(callback, tid)

    @dp.callback_query(F.data.startswith("tutorial_delete_"))
    async def tutorial_delete(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        tid = int(callback.data.removeprefix("tutorial_delete_"))
        t = await get_tutorial(tid)
        if not t:
            await callback.answer("یافت نشد.", show_alert=True)
            return
        await _edit_or_replace(
            callback,
            f"🗑 حذف «{t['title']}»؟",
            InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ بله", callback_data=f"tutorial_delete_confirm_{tid}"),
                    InlineKeyboardButton(text="❌ خیر", callback_data=f"tutorial_item_{tid}"),
                ]
            ])
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("tutorial_delete_confirm_"))
    async def tutorial_delete_confirm(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        tid = int(callback.data.removeprefix("tutorial_delete_confirm_"))
        t = await get_tutorial(tid)
        title = t["title"] if t else "آموزش"
        await delete_tutorial(tid)
        tutorials = await get_tutorials()
        await _edit_or_replace(
            callback,
            f"🗑 «{title}» حذف شد.",
            admin_tutorials_menu(tutorials)
        )
        await callback.answer()

    # ── ادمین: ویرایش عنوان ────────────────────────

    @dp.callback_query(F.data.startswith("tutorial_edit_title_"))
    async def tutorial_edit_title_start(callback: types.CallbackQuery, state: FSMContext):
        tid = int(callback.data.removeprefix("tutorial_edit_title_"))
        await state.set_state(EditTutorial.waiting_for_title)
        await state.update_data(tutorial_id=tid)
        t = await get_tutorial(tid)
        await callback.message.edit_text(
            f"✏️ عنوان فعلی: <b>{t['title']}</b>\n\nعنوان جدید:",
            reply_markup=_CANCEL_TUTORIALS, parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(EditTutorial.waiting_for_title, F.text)
    async def tutorial_edit_title_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        tid = data["tutorial_id"]
        t = await get_tutorial(tid)
        await update_tutorial(tid, message.text.strip(), t["content_type"], t["file_id"], t["caption"])
        await state.clear()
        tutorials = await get_tutorials()
        await message.answer("✅ عنوان ذخیره شد.", reply_markup=admin_tutorial_list_menu(tutorials))

    # ── ادمین: ویرایش محتوا ────────────────────────

    @dp.callback_query(F.data.startswith("tutorial_edit_content_"))
    async def tutorial_edit_content_start(callback: types.CallbackQuery, state: FSMContext):
        tid = int(callback.data.removeprefix("tutorial_edit_content_"))
        await state.set_state(EditTutorial.waiting_for_content)
        await state.update_data(tutorial_id=tid)
        await callback.message.edit_text(
            "📎 محتوای جدید را ارسال کنید:\n<i>متن، عکس یا ویدیو</i>",
            reply_markup=_CANCEL_TUTORIALS, parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(EditTutorial.waiting_for_content)
    async def tutorial_edit_content_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        tid = data["tutorial_id"]
        t = await get_tutorial(tid)
        content_type, file_id, caption, entities_json = _parse_content(message)
        if content_type is None:
            await message.answer("❌ نوع پیام پشتیبانی نمی‌شود.")
            return
        await update_tutorial(tid, t["title"], content_type, file_id, caption, entities_json)
        await state.clear()
        tutorials = await get_tutorials()
        await message.answer("✅ محتوا ذخیره شد.", reply_markup=admin_tutorial_list_menu(tutorials))

    # ── ادمین: FAQ ─────────────────────────────────

    @dp.callback_query(F.data == "admin_faqs")
    async def admin_faqs(callback: types.CallbackQuery, state: FSMContext):
        from handlers.user import _edit_or_replace
        await state.clear()
        faqs = await get_faqs()
        await _edit_or_replace(
            callback,
            f"❓ <b>سوالات متداول</b>\n\n{len(faqs)} سوال ثبت شده",
            admin_faqs_menu(faqs)
        )
        await callback.answer()

    @dp.callback_query(F.data == "faq_add")
    async def faq_add_start(callback: types.CallbackQuery, state: FSMContext):
        await state.set_state(AddFAQ.waiting_for_question)
        await callback.message.edit_text(
            "❓ سوال را وارد کنید:", reply_markup=_CANCEL_FAQS
        )
        await callback.answer()

    @dp.message(AddFAQ.waiting_for_question, F.text)
    async def faq_add_question(message: types.Message, state: FSMContext):
        await state.update_data(question=message.text.strip())
        await state.set_state(AddFAQ.waiting_for_answer)
        await message.answer("💬 جواب را وارد کنید:", reply_markup=_CANCEL_FAQS)

    @dp.message(AddFAQ.waiting_for_answer, F.text)
    async def faq_add_answer(message: types.Message, state: FSMContext):
        data = await state.get_data()
        entities = message.entities or []
        ej = json.dumps([e.model_dump() for e in entities]) if entities else None
        await create_faq(data["question"], message.text, ej)
        await state.clear()
        faqs = await get_faqs()
        await message.answer("✅ سوال اضافه شد.", reply_markup=admin_faqs_menu(faqs))

    @dp.callback_query(F.data.startswith("faq_item_"))
    async def faq_item(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        fid = int(callback.data.removeprefix("faq_item_"))
        f = await get_faq(fid)
        if not f:
            await callback.answer("یافت نشد.", show_alert=True)
            return
        text = (
            f"❓ <b>{f['question']}</b>\n\n"
            f"💬 {f['answer']}\n\n"
            f"وضعیت: {'✅ فعال' if f['is_active'] else '❌ غیرفعال'}"
        )
        await _edit_or_replace(callback, text, admin_faq_item_keyboard(fid, bool(f["is_active"])))
        await callback.answer()

    @dp.callback_query(F.data.startswith("faq_toggle_"))
    async def faq_toggle(callback: types.CallbackQuery):
        fid = int(callback.data.removeprefix("faq_toggle_"))
        await toggle_faq(fid)
        await faq_item(callback)

    @dp.callback_query(F.data.startswith("faq_delete_"))
    async def faq_delete(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        fid = int(callback.data.removeprefix("faq_delete_"))
        f = await get_faq(fid)
        if not f:
            await callback.answer("یافت نشد.", show_alert=True)
            return
        await _edit_or_replace(
            callback,
            f"🗑 حذف «{f['question']}»؟",
            InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ بله", callback_data=f"faq_delete_confirm_{fid}"),
                    InlineKeyboardButton(text="❌ خیر", callback_data=f"faq_item_{fid}"),
                ]
            ])
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("faq_delete_confirm_"))
    async def faq_delete_confirm(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        fid = int(callback.data.removeprefix("faq_delete_confirm_"))
        f = await get_faq(fid)
        q = f["question"] if f else "سوال"
        await delete_faq(fid)
        faqs = await get_faqs()
        await _edit_or_replace(callback, f"🗑 «{q}» حذف شد.", admin_faqs_menu(faqs))
        await callback.answer()

    @dp.callback_query(F.data.startswith("faq_edit_q_"))
    async def faq_edit_q_start(callback: types.CallbackQuery, state: FSMContext):
        fid = int(callback.data.removeprefix("faq_edit_q_"))
        await state.set_state(EditFAQ.waiting_for_question)
        await state.update_data(faq_id=fid)
        f = await get_faq(fid)
        await callback.message.edit_text(
            f"✏️ سوال فعلی: <b>{f['question']}</b>\n\nسوال جدید:",
            reply_markup=_CANCEL_FAQS, parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(EditFAQ.waiting_for_question, F.text)
    async def faq_edit_q_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        fid = data["faq_id"]
        f = await get_faq(fid)
        await update_faq(fid, message.text.strip(), f["answer"])
        await state.clear()
        faqs = await get_faqs()
        await message.answer("✅ سوال ذخیره شد.", reply_markup=admin_faqs_menu(faqs))

    @dp.callback_query(F.data.startswith("faq_edit_a_"))
    async def faq_edit_a_start(callback: types.CallbackQuery, state: FSMContext):
        fid = int(callback.data.removeprefix("faq_edit_a_"))
        await state.set_state(EditFAQ.waiting_for_answer)
        await state.update_data(faq_id=fid)
        f = await get_faq(fid)
        await callback.message.edit_text(
            f"✏️ جواب فعلی:\n{f['answer']}\n\nجواب جدید:",
            reply_markup=_CANCEL_FAQS
        )
        await callback.answer()

    @dp.message(EditFAQ.waiting_for_answer, F.text)
    async def faq_edit_a_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        fid = data["faq_id"]
        f = await get_faq(fid)
        entities = message.entities or []
        ej = json.dumps([e.model_dump() for e in entities]) if entities else None
        await update_faq(fid, f["question"], message.text, ej)
        await state.clear()
        faqs = await get_faqs()
        await message.answer("✅ جواب ذخیره شد.", reply_markup=admin_faqs_menu(faqs))

    # ── کاربر: آموزش ───────────────────────────────

    @dp.callback_query(F.data == "tutorial")
    async def user_tutorials(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        tutorials = await get_tutorials(active_only=True)
        if not tutorials:
            await _edit_or_replace(
                callback,
                "📚 <b>آموزش و راهنما</b>\n\nهنوز آموزشی اضافه نشده.",
                InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_start")]
                ])
            )
        else:
            await _edit_or_replace(
                callback,
                "📚 <b>آموزش و راهنما</b>\n\nیکی از موضوعات زیر را انتخاب کنید:",
                user_tutorials_keyboard(tutorials)
            )
        await callback.answer()

    @dp.callback_query(F.data.startswith("tutorial_view_"))
    async def user_tutorial_view(callback: types.CallbackQuery):
        tid = int(callback.data.removeprefix("tutorial_view_"))
        t = await get_tutorial(tid)
        if not t or not t["is_active"]:
            await callback.answer("این آموزش در دسترس نیست.", show_alert=True)
            return
        kb = back_to_tutorials_keyboard()
        entities = _load_entities(t["caption_entities"])
        try:
            await callback.message.delete()
        except Exception:
            pass
        send_kw = {"reply_markup": kb}
        if entities:
            send_kw["entities" if t["content_type"] == "text" else "caption_entities"] = entities
        else:
            send_kw["parse_mode"] = "HTML"

        if t["content_type"] == "text":
            text = f"📖 <b>{t['title']}</b>\n\n{t['caption'] or ''}" if not entities else (t["caption"] or "")
            await callback.message.answer(text, **send_kw)
        elif t["content_type"] == "photo":
            cap = f"<b>{t['title']}</b>\n\n{t['caption'] or ''}" if not entities else (t["caption"] or "")
            await callback.message.answer_photo(photo=t["file_id"], caption=cap, **send_kw)
        elif t["content_type"] == "video":
            cap = f"<b>{t['title']}</b>\n\n{t['caption'] or ''}" if not entities else (t["caption"] or "")
            await callback.message.answer_video(video=t["file_id"], caption=cap, **send_kw)
        await callback.answer()

    @dp.callback_query(F.data == "user_faqs")
    async def user_faqs(callback: types.CallbackQuery):
        from handlers.user import _edit_or_replace
        faqs = await get_faqs(active_only=True)
        if not faqs:
            await _edit_or_replace(
                callback,
                "❓ <b>سوالات متداول</b>\n\nهنوز سوالی اضافه نشده.",
                back_to_tutorials_keyboard()
            )
        else:
            await _edit_or_replace(
                callback,
                "❓ <b>سوالات متداول</b>\n\nسوال مورد نظر را انتخاب کنید:",
                user_faqs_keyboard(faqs)
            )
        await callback.answer()

    @dp.callback_query(F.data.startswith("faq_view_"))
    async def user_faq_view(callback: types.CallbackQuery):
        fid = int(callback.data.removeprefix("faq_view_"))
        f = await get_faq(fid)
        if not f or not f["is_active"]:
            await callback.answer("این سوال در دسترس نیست.", show_alert=True)
            return
        entities = _load_entities(f["answer_entities"])
        kb = back_to_faqs_keyboard()
        try:
            await callback.message.delete()
        except Exception:
            pass
        if entities:
            await callback.message.answer(f["answer"], entities=entities, reply_markup=kb)
        else:
            await callback.message.answer(
                f"❓ <b>{f['question']}</b>\n\n{f['answer']}",
                parse_mode="HTML", reply_markup=kb
            )
        await callback.answer()


def _parse_content(message: types.Message):
    """نوع، file_id، caption، و entities رو از پیام استخراج می‌کنه"""
    if message.photo:
        entities = message.caption_entities or []
        ej = json.dumps([e.model_dump() for e in entities]) if entities else None
        return "photo", message.photo[-1].file_id, message.caption, ej
    if message.video:
        entities = message.caption_entities or []
        ej = json.dumps([e.model_dump() for e in entities]) if entities else None
        return "video", message.video.file_id, message.caption, ej
    if message.text:
        entities = message.entities or []
        ej = json.dumps([e.model_dump() for e in entities]) if entities else None
        return "text", None, message.text, ej
    return None, None, None, None

def _load_entities(entities_json: str | None) -> list | None:
    if not entities_json:
        return None
    try:
        return [MessageEntity(**e) for e in json.loads(entities_json)]
    except Exception:
        return None

def _type_label(content_type: str) -> str:
    return {"text": "📝 متن", "photo": "🖼 عکس", "video": "🎬 ویدیو"}.get(content_type, content_type)
