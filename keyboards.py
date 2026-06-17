from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def admin_main_menu():
    """منوی اصلی ادمین"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 خرید VPN", callback_data="buy_vpn")],
        [InlineKeyboardButton(text="⚙️ پنل ادمین", callback_data="admin_panel")],
    ])
    return keyboard
 
def admin_panel_menu():
    """پنل ادمین"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖥 مدیریت سرورها", callback_data="admin_servers")],
        [InlineKeyboardButton(text="📦 پلن‌ها", callback_data="admin_plans")],
        [InlineKeyboardButton(text="💰 مدیریت مالی", callback_data="admin_finance")],
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

def servers_list_keyboard(servers, mode="select_server"):
    """لیست سرورها"""
    buttons = []
    for server in servers:
        buttons.append([
            InlineKeyboardButton(
                text=f"🖥 {server['name']}",
                callback_data=f"{mode}_{server['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_plans")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def back_to_servers_menu():
    """فقط دکمه بازگشت به منوی سرورها"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_servers")],
    ])
    return keyboard

def cancel_keyboard():
    """دکمه لغو عملیات در حین فرایندهای چندمرحله‌ای"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="cancel")],
    ])
    return keyboard

def servers_list_view_keyboard():
    """کیبورد نمایش لیست سرورها"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ سرور جدید", callback_data="add_server")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_servers")],
    ])
    return keyboard

def plans_list_view_keyboard():
    """کیبورد نمایش لیست پلن‌های یک سرور"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_plans")],
    ])
    return keyboard

# ─── کیبوردهای مدیریت مالی ────────────────────

def admin_finance_menu(card_active: bool):
    """منوی مدیریت مالی — لیست روش‌های پرداخت"""
    status = "✅ روشن" if card_active else "❌ خاموش"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 کارت به کارت", callback_data="noop"),
            InlineKeyboardButton(text=status, callback_data="toggle_card"),
            InlineKeyboardButton(text="⚙️ تنظیمات", callback_data="card_settings"),
        ],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_panel")],
    ])
    return keyboard

def card_settings_keyboard():
    """تنظیمات روش پرداخت کارت به کارت"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 تغییر شماره کارت", callback_data="set_card_number")],
        [InlineKeyboardButton(text="👤 تغییر نام صاحب کارت", callback_data="set_card_owner")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_finance")],
    ])
    return keyboard

# ─── کیبوردهای کاربر ───────────────────────────

def user_main_menu():
    """منوی اصلی کاربر"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 خرید VPN", callback_data="buy_vpn")],
    ])
    return keyboard

def user_servers_keyboard(servers):
    """لیست سرورها برای انتخاب کاربر"""
    buttons = []
    for server in servers:
        buttons.append([
            InlineKeyboardButton(
                text=f"🖥 {server['name']}",
                callback_data=f"user_server_{server['id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def user_plans_keyboard(plans, server_id):
    """لیست پلن‌های یک سرور برای انتخاب کاربر"""
    buttons = []
    for plan in plans:
        buttons.append([
            InlineKeyboardButton(
                text=f"📦 {plan['name']} — {plan['price']:,} تومان",
                callback_data=f"user_plan_{plan['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"user_server_{server_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def proforma_keyboard(plan_id):
    """کیبورد پیش‌فاکتور — پرداخت یا انصراف"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت", callback_data=f"pay_{plan_id}")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="buy_vpn")],
    ])
    return keyboard

def payment_info_keyboard():
    """کیبورد صفحه اطلاعات پرداخت — فقط دکمه انصراف"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_payment")],
    ])
    return keyboard

def admin_order_keyboard(order_id):
    """کیبورد تایید/رد سفارش برای ادمین"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید", callback_data=f"order_approve_{order_id}")],
        [
            InlineKeyboardButton(text="❌ رد", callback_data=f"order_reject_{order_id}"),
            InlineKeyboardButton(text="❌ رد با دلیل", callback_data=f"order_reject_reason_{order_id}"),
        ],
    ])
    return keyboard