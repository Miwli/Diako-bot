from aiogram import types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from keyboards import admin_main_menu, admin_panel_menu, user_main_menu
from states import AdminAction
from database import get_order, get_plan, update_order_status

def register_admin_handlers(dp):
    
    @dp.message(CommandStart())
    async def cmd_start(message: types.Message):
        from bot import is_admin, logger
        logger.info(f"کاربر {message.from_user.id} دستور /start فرستاد")
        if is_admin(message.from_user.id):
            await message.answer(
                "سلام ادمین! 👋",
                reply_markup=admin_main_menu()
            )
        else:
            await message.answer(
                "سلام! 👋 به bping خوش اومدی 🚀",
                reply_markup=user_main_menu()
            )

    @dp.callback_query(F.data == "admin_panel")
    async def admin_panel(callback: types.CallbackQuery):
        await callback.message.edit_text(
            "⚙️ پنل ادمین",
            reply_markup=admin_panel_menu()
        )
        await callback.answer()

    @dp.callback_query(F.data == "back_to_start")
    async def back_to_start(callback: types.CallbackQuery):
        await callback.message.edit_text(
            "🏠 دوباره اومدی صفحه اصلی!",
            reply_markup=admin_main_menu()
        )
        await callback.answer()

    @dp.callback_query(F.data == "cancel")
    async def cancel_operation(callback: types.CallbackQuery, state: FSMContext):
        """لغو هر عملیات در حال انجام و بازگشت به پنل ادمین"""
        await state.clear()
        await callback.message.edit_text(
            "❌ عملیات لغو شد.",
            reply_markup=admin_panel_menu()
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("order_approve_"))
    async def order_approve(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("order_approve_", ""))
        order = await get_order(order_id)
        if not order:
            await callback.answer("سفارش یافت نشد.", show_alert=True)
            return

        await update_order_status(order_id, "approved")
        await callback.message.edit_caption(
            callback.message.caption + "\n\n✅ <b>تایید شد</b>",
            parse_mode="HTML"
        )
        await callback.bot.send_message(
            chat_id=order["user_id"],
            text="✅ سفارش شما تایید شد!\nبه زودی اطلاعات اتصال برای شما ارسال خواهد شد."
        )
        await callback.answer("سفارش تایید شد.")

    @dp.callback_query(F.data.startswith("order_reject_") & ~F.data.startswith("order_reject_reason_"))
    async def order_reject(callback: types.CallbackQuery):
        order_id = int(callback.data.replace("order_reject_", ""))
        order = await get_order(order_id)
        if not order:
            await callback.answer("سفارش یافت نشد.", show_alert=True)
            return

        await update_order_status(order_id, "rejected")
        await callback.message.edit_caption(
            callback.message.caption + "\n\n❌ <b>رد شد</b>",
            parse_mode="HTML"
        )
        await callback.bot.send_message(
            chat_id=order["user_id"],
            text="❌ متأسفانه سفارش شما تایید نشد.\nدر صورت نیاز با پشتیبانی تماس بگیرید."
        )
        await callback.answer("سفارش رد شد.")

    @dp.callback_query(F.data.startswith("order_reject_reason_"))
    async def order_reject_reason_start(callback: types.CallbackQuery, state: FSMContext):
        order_id = int(callback.data.replace("order_reject_reason_", ""))
        await state.update_data(order_id=order_id, admin_message_id=callback.message.message_id)
        await state.set_state(AdminAction.waiting_for_rejection_reason)
        await callback.message.reply(
            "✏️ دلیل رد را بنویسید (یا /skip برای رد بدون دلیل):"
        )
        await callback.answer()

    @dp.message(AdminAction.waiting_for_rejection_reason)
    async def order_reject_with_reason(message: types.Message, state: FSMContext):
        data = await state.get_data()
        order_id = data["order_id"]
        order = await get_order(order_id)

        reason = message.text if message.text and message.text != "/skip" else None
        await update_order_status(order_id, "rejected", rejection_reason=reason)
        await state.clear()

        await message.bot.send_message(
            chat_id=order["user_id"],
            text="❌ متأسفانه سفارش شما تایید نشد."
        )
        if message.text != "/skip":
            await message.copy_to(chat_id=order["user_id"])

        await message.answer("✅ سفارش رد شد و کاربر مطلع شد.")