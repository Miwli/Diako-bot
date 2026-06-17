from aiogram import types, F
from aiogram.filters import CommandStart
from keyboards import admin_main_menu, admin_panel_menu

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
            await message.answer("سلام! 👋 به bping خوش اومدی 🚀")

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