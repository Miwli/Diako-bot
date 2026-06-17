from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def admin_main_menu():
    """منوی اصلی ادمین"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ پنل ادمین", callback_data="admin_panel")]
    ])
    return keyboard
 
def admin_panel_menu():
    """پنل ادمین"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 پلن‌ها", callback_data="admin_plans")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_start")],
    ])
    return keyboard