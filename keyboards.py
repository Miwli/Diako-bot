from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def admin_main_menu():
    """منوی اصلی ادمین"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ پنل ادمین", callback_data="admin_panel")]
    ])
    return keyboard