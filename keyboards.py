from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def admin_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 خرید VPN", callback_data="buy_vpn")],
        [InlineKeyboardButton(text="⚙️ پنل ادمین", callback_data="admin_panel")],
    ])
    return keyboard

def admin_panel_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖥 مدیریت سرورها", callback_data="admin_servers")],
        [InlineKeyboardButton(text="📦 پلن‌ها", callback_data="admin_plans")],
        [InlineKeyboardButton(text="💰 مدیریت مالی", callback_data="admin_finance")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_start")],
    ])
    return keyboard

def cancel_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="cancel")],
    ])
    return keyboard

def back_to_servers_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_servers")],
    ])
    return keyboard

# ─── سرورها ───────────────────────────────────

def admin_servers_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ سرور جدید", callback_data="add_server")],
        [InlineKeyboardButton(text="📋 لیست سرورها", callback_data="list_servers")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_panel")],
    ])
    return keyboard

def servers_table_keyboard(servers):
    """لیست سرورها — هدر + هر ردیف: نام | وضعیت | تنظیمات"""
    buttons = [
        [
            InlineKeyboardButton(text="🖥 سرور", callback_data="noop"),
            InlineKeyboardButton(text="وضعیت", callback_data="noop"),
            InlineKeyboardButton(text="تنظیمات", callback_data="noop"),
        ]
    ]
    for s in servers:
        status = "✅ فعال" if s["is_active"] else "❌ غیرفعال"
        buttons.append([
            InlineKeyboardButton(text=s["name"], callback_data="noop"),
            InlineKeyboardButton(text=status, callback_data=f"toggle_server_{s['id']}"),
            InlineKeyboardButton(text="⚙️", callback_data=f"server_settings_{s['id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ سرور جدید", callback_data="add_server")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_servers")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def server_settings_keyboard(server_id: int, is_active: bool):
    toggle_text = "❌ غیرفعال کردن" if is_active else "✅ فعال کردن"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش سرویس‌ها", callback_data=f"edit_server_services_{server_id}")],
        [InlineKeyboardButton(text="🔗 ویرایش آدرس", callback_data=f"edit_server_url_{server_id}")],
        [InlineKeyboardButton(text="🔑 ویرایش توکن", callback_data=f"edit_server_token_{server_id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_server_settings_{server_id}")],
        [InlineKeyboardButton(text="🗑 حذف سرور", callback_data=f"delete_server_{server_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="list_servers")],
    ])
    return keyboard

def confirm_delete_server_keyboard(server_id: int):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"confirmed_delete_server_{server_id}")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"server_settings_{server_id}")],
    ])
    return keyboard

def rebecca_services_keyboard(services: list, selected_ids: list):
    buttons = []
    for svc in services:
        mark = "✅" if svc["id"] in selected_ids else "⬜"
        buttons.append([
            InlineKeyboardButton(
                text=f"{mark} {svc['name']}",
                callback_data=f"toggle_svc_{svc['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="✅ انجام شد", callback_data="confirm_services")])
    buttons.append([InlineKeyboardButton(text="❌ لغو", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ─── پلن‌ها ───────────────────────────────────

def admin_plans_menu(show_price: bool = False):
    price_status = "✅ روشن" if show_price else "❌ خاموش"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ پلن جدید", callback_data="add_plan")],
        [InlineKeyboardButton(text="📋 لیست پلن‌ها", callback_data="list_plans")],
        [
            InlineKeyboardButton(text="💰 نمایش قیمت", callback_data="noop"),
            InlineKeyboardButton(text=price_status, callback_data="toggle_show_price"),
        ],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_panel")],
    ])
    return keyboard

def servers_list_keyboard(servers, mode="select_server"):
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

def plans_table_keyboard(plans, server_id: int):
    """لیست پلن‌ها — هر پلن دو ردیف: اطلاعات + وضعیت/تنظیمات"""
    buttons = []
    for p in plans:
        status = "✅" if p["is_active"] else "❌"
        label = f"📦 {p['name']} | {p['traffic']} گیگ / {p['duration']} روز / {p['price']:,} ت"
        buttons.append([InlineKeyboardButton(text=label, callback_data="noop")])
        buttons.append([
            InlineKeyboardButton(text=f"{status} وضعیت", callback_data=f"toggle_plan_{p['id']}"),
            InlineKeyboardButton(text="⚙️ تنظیمات", callback_data=f"plan_settings_{p['id']}_{server_id}"),
        ])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_plans")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def plan_settings_keyboard(plan_id: int, server_id: int, is_active: bool):
    toggle_text = "❌ غیرفعال کردن" if is_active else "✅ فعال کردن"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_plan_settings_{plan_id}_{server_id}")],
        [InlineKeyboardButton(text="🗑 حذف پلن", callback_data=f"delete_plan_{plan_id}_{server_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"view_plans_{server_id}")],
    ])
    return keyboard

def confirm_delete_plan_keyboard(plan_id: int, server_id: int):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"confirmed_delete_plan_{plan_id}_{server_id}")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"plan_settings_{plan_id}_{server_id}")],
    ])
    return keyboard

# ─── مدیریت مالی ──────────────────────────────

def admin_finance_menu(card_active: bool):
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
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 تغییر شماره کارت", callback_data="set_card_number")],
        [InlineKeyboardButton(text="👤 تغییر نام صاحب کارت", callback_data="set_card_owner")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_finance")],
    ])
    return keyboard

# ─── کاربر ────────────────────────────────────

def user_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 خرید VPN", callback_data="buy_vpn")],
    ])
    return keyboard

def user_servers_keyboard(servers):
    buttons = []
    for server in servers:
        buttons.append([
            InlineKeyboardButton(
                text=f"🖥 {server['name']}",
                callback_data=f"user_server_{server['id']}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def user_plans_keyboard(plans, server_id, multiple_servers: bool = False, show_price: bool = False):
    buttons = []
    for plan in plans:
        label = plan["name"]
        if show_price:
            label += f" — {plan['price']:,} تومان"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"user_plan_{plan['id']}")
        ])
    back_target = "buy_vpn" if multiple_servers else "user_main"
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def proforma_keyboard(plan_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت", callback_data=f"pay_{plan_id}")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="user_main")],
    ])
    return keyboard

def payment_info_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_payment")],
    ])
    return keyboard

# ─── سفارش‌ها ─────────────────────────────────

def admin_order_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید", callback_data=f"order_approve_{order_id}")],
        [
            InlineKeyboardButton(text="❌ رد", callback_data=f"order_reject_{order_id}"),
            InlineKeyboardButton(text="❌ رد با دلیل", callback_data=f"order_reject_reason_{order_id}"),
        ],
    ])
    return keyboard

def after_order_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ پنل ادمین", callback_data="admin_panel")],
        [InlineKeyboardButton(text="🏠 منوی اصلی", callback_data="back_to_start")],
    ])
    return keyboard
