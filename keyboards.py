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
        [InlineKeyboardButton(text="🖥 مدیریت سرورها", callback_data="admin_servers")],
        [InlineKeyboardButton(text="📦 پلن‌ها", callback_data="admin_plans")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_start")],
    ])
    return keyboard

def admin_servers_menu():
    """منوی مدیریت سرورها"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ سرور جدید", callback_data="add_server")],
        [InlineKeyboardButton(text="📋 لیست سرورها", callback_data="list_servers")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_panel")],
    ])
    return keyboard

def admin_plans_menu():
    """منوی مدیریت پلن‌ها"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ پلن جدید", callback_data="add_plan")],
        [InlineKeyboardButton(text="📋 لیست پلن‌ها", callback_data="list_plans")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_panel")],
        [InlineKeyboardButton(text="🏠 منوی اصلی", callback_data="back_to_start")]
    ])
    return keyboard

def servers_list_keyboard(servers):
    """لیست سرورها برای انتخاب هنگام ساخت پلن"""
    buttons = []
    for server in servers:
        buttons.append([
            InlineKeyboardButton(
                text=f"🖥 {server['name']}",
                callback_data=f"select_server_{server['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_plans")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)