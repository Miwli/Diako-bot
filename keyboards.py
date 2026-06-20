from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton

# ─── منوی اصلی ────────────────────────────────

def user_main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔐 خرید اشتراک",      callback_data="buy_vpn")],
        [
            InlineKeyboardButton(text="💎 کیف پول",        callback_data="wallet"),
            InlineKeyboardButton(text="🎁 تست رایگان",     callback_data="free_test"),
            InlineKeyboardButton(text="📡 سرویس‌های من",   callback_data="my_services"),
        ],
        [
            InlineKeyboardButton(text="🎧 پشتیبانی",       callback_data="support"),
            InlineKeyboardButton(text="👤 پروفایل",        callback_data="profile"),
            InlineKeyboardButton(text="📚 آموزش و راهنما", callback_data="tutorial"),
        ],
        [
            InlineKeyboardButton(text="💰 دعوت دوستان",   callback_data="referral"),
            InlineKeyboardButton(text="🌐 تغییر زبان",    callback_data="language"),
        ],
    ])
    return keyboard

def admin_main_menu():
    buttons = list(user_main_menu().inline_keyboard)
    buttons.append([InlineKeyboardButton(text="⚙️ پنل ادمین", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_panel_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖥 مدیریت سرورها",          callback_data="admin_servers")],
        [InlineKeyboardButton(text="📦 پلن‌ها",                  callback_data="admin_plans")],
        [InlineKeyboardButton(text="💰 مدیریت مالی",            callback_data="admin_finance")],
        [InlineKeyboardButton(text="👥 مدیریت کاربران",         callback_data="admin_users")],
        [InlineKeyboardButton(text="🎟 کدهای تخفیف",            callback_data="admin_discount")],
        [InlineKeyboardButton(text="🎁 تنظیمات تست رایگان",     callback_data="admin_free_test")],
        [InlineKeyboardButton(text="💰 تنظیمات دعوت دوستان",   callback_data="admin_referral")],
        [InlineKeyboardButton(text="🎧 تنظیمات پشتیبانی",       callback_data="admin_support")],
        [InlineKeyboardButton(text="📢 پیام همگانی",             callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 آمار و گزارش",           callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ تنظیمات عمومی",         callback_data="admin_general")],
        [InlineKeyboardButton(text="🔙 بازگشت",                 callback_data="back_to_start")],
    ])
    return keyboard

def cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="cancel")],
    ])

def admin_general_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 ظاهر ربات",     callback_data="admin_banner_and_text")],
        [InlineKeyboardButton(text="🔙 بازگشت",        callback_data="admin_panel")],
    ])

def admin_free_test_menu(servers: list):
    rows = [[InlineKeyboardButton(
        text=f"⚙️ تنظیمات پیش‌فرض (همه سرورها)",
        callback_data="admin_free_test_global"
    )]]
    for s in servers:
        status = "✅" if s["free_test_enabled"] else "❌"
        rows.append([InlineKeyboardButton(
            text=f"{s['name']}  {status}",
            callback_data=f"admin_free_test_server_{s['id']}"
        )])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_free_test_global_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ ویرایش مدت",    callback_data="admin_free_test_global_duration"),
            InlineKeyboardButton(text="✏️ ویرایش حجم",    callback_data="admin_free_test_global_traffic"),
        ],
        [InlineKeyboardButton(text="🔢 تعداد مجاز دریافت", callback_data="admin_free_test_max_uses")],
        [InlineKeyboardButton(text="📡 اعمال روی همه سرورها", callback_data="admin_free_test_apply_all")],
        [InlineKeyboardButton(text="🔄 ریست همه کاربران",  callback_data="admin_free_test_reset_all")],
        [InlineKeyboardButton(text="🔙 بازگشت",            callback_data="admin_free_test")],
    ])

def admin_free_test_server_menu(server_id: int, is_enabled: bool):
    toggle_text = "❌ غیرفعال کردن" if is_enabled else "✅ فعال کردن"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin_free_test_toggle_{server_id}")],
        [
            InlineKeyboardButton(text="✏️ ویرایش مدت",  callback_data=f"admin_free_test_duration_{server_id}"),
            InlineKeyboardButton(text="✏️ ویرایش حجم",  callback_data=f"admin_free_test_traffic_{server_id}"),
        ],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_free_test")],
    ])

def admin_banner_and_text_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 تنظیمات بنر",  callback_data="admin_banner_settings")],
        [InlineKeyboardButton(text="✏️ تنظیمات متن",  callback_data="admin_text_settings")],
        [InlineKeyboardButton(text="🔙 بازگشت",        callback_data="admin_general")],
    ])

def admin_text_settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش متن",  callback_data="admin_banner_caption")],
        [InlineKeyboardButton(text="🛠 ساخت متن",    callback_data="admin_build_text")],
        [InlineKeyboardButton(text="🔙 بازگشت",       callback_data="admin_banner_and_text")],
    ])

def admin_banner_settings_menu(has_banner: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 حذف بنر" if has_banner else "🖼 آپلود بنر",
            callback_data="admin_banner_delete" if has_banner else "admin_banner_upload"
        )],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_general")],
    ])

def back_to_servers_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_servers")],
    ])

# ─── سرورها ───────────────────────────────────

def admin_servers_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ سرور جدید",   callback_data="add_server")],
        [InlineKeyboardButton(text="📋 لیست سرورها", callback_data="list_servers")],
        [InlineKeyboardButton(text="🔙 بازگشت",      callback_data="admin_panel")],
    ])

def servers_table_keyboard(servers):
    buttons = [[
        InlineKeyboardButton(text="🖥 سرور",  callback_data="noop"),
        InlineKeyboardButton(text="وضعیت",   callback_data="noop"),
        InlineKeyboardButton(text="تنظیمات", callback_data="noop"),
    ]]
    for s in servers:
        status = "✅ فعال" if s["is_active"] else "❌ غیرفعال"
        buttons.append([
            InlineKeyboardButton(text=s["name"], callback_data="noop"),
            InlineKeyboardButton(text=status,    callback_data=f"toggle_server_{s['id']}"),
            InlineKeyboardButton(text="⚙️",      callback_data=f"server_settings_{s['id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ سرور جدید", callback_data="add_server")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",    callback_data="admin_servers")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def server_settings_keyboard(server_id: int, is_active: bool):
    toggle_text = "❌ غیرفعال کردن" if is_active else "✅ فعال کردن"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش سرویس‌ها", callback_data=f"edit_server_services_{server_id}")],
        [
            InlineKeyboardButton(text="🔗 ویرایش آدرس",  callback_data=f"edit_server_url_{server_id}"),
            InlineKeyboardButton(text="🔑 ویرایش توکن",  callback_data=f"edit_server_token_{server_id}"),
        ],
        [InlineKeyboardButton(text=toggle_text,           callback_data=f"toggle_server_settings_{server_id}")],
        [InlineKeyboardButton(text="🗑 حذف سرور",        callback_data=f"delete_server_{server_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت",          callback_data="list_servers")],
    ])

def confirm_delete_server_keyboard(server_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"confirmed_delete_server_{server_id}"),
            InlineKeyboardButton(text="❌ انصراف",       callback_data=f"server_settings_{server_id}"),
        ],
    ])

def rebecca_services_keyboard(services: list, selected_ids: list):
    buttons = []
    for svc in services:
        mark = "✅" if svc["id"] in selected_ids else "⬜"
        buttons.append([InlineKeyboardButton(
            text=f"{mark} {svc['name']}",
            callback_data=f"toggle_svc_{svc['id']}"
        )])
    buttons.append([
        InlineKeyboardButton(text="✅ انجام شد", callback_data="confirm_services"),
        InlineKeyboardButton(text="❌ لغو",       callback_data="cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ─── پلن‌ها ───────────────────────────────────

def admin_plans_menu(show_price: bool = False):
    price_status = "✅ روشن" if show_price else "❌ خاموش"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ پلن جدید",    callback_data="add_plan")],
        [InlineKeyboardButton(text="📋 لیست پلن‌ها", callback_data="list_plans")],
        [
            InlineKeyboardButton(text="💰 نمایش قیمت", callback_data="noop"),
            InlineKeyboardButton(text=price_status,     callback_data="toggle_show_price"),
        ],
        [InlineKeyboardButton(text="🔙 بازگشت",       callback_data="admin_panel")],
    ])

def servers_list_keyboard(servers, mode="select_server"):
    buttons = []
    for server in servers:
        buttons.append([InlineKeyboardButton(
            text=f"🖥 {server['name']}",
            callback_data=f"{mode}_{server['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_plans")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def plans_table_keyboard(plans, server_id: int):
    buttons = [[
        InlineKeyboardButton(text="📦 پلن",  callback_data="noop"),
        InlineKeyboardButton(text="وضعیت", callback_data="noop"),
        InlineKeyboardButton(text="🗑 حذف", callback_data="noop"),
    ]]
    for p in plans:
        status = "✅" if p["is_active"] else "❌"
        pid, sid = p["id"], server_id
        buttons.append([
            InlineKeyboardButton(text=p["name"], callback_data=f"toggle_plan_settings_{pid}_{sid}"),
            InlineKeyboardButton(text=status,    callback_data=f"toggle_plan_{pid}_{sid}"),
            InlineKeyboardButton(text="🗑",      callback_data=f"delete_plan_{pid}_{sid}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ پلن جدید", callback_data="add_plan")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",   callback_data="admin_plans")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def plan_settings_keyboard(plan_id: int, server_id: int, is_active: bool):
    toggle_text = "❌ غیرفعال کردن" if is_active else "✅ فعال کردن"
    pid, sid = plan_id, server_id
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ویرایش قیمت",        callback_data=f"edit_plan_price_{pid}_{sid}")],
        [
            InlineKeyboardButton(text="📅 ویرایش روز",      callback_data=f"edit_plan_duration_{pid}_{sid}"),
            InlineKeyboardButton(text="📊 ویرایش حجم",      callback_data=f"edit_plan_traffic_{pid}_{sid}"),
        ],
        [
            InlineKeyboardButton(text=toggle_text,           callback_data=f"toggle_plan_settings_{pid}_{sid}"),
            InlineKeyboardButton(text="🗑 حذف پلن",         callback_data=f"delete_plan_{pid}_{sid}"),
        ],
        [InlineKeyboardButton(text="🔙 بازگشت",             callback_data=f"view_plans_{sid}")],
    ])

def confirm_delete_plan_keyboard(plan_id: int, server_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"confirmed_delete_plan_{plan_id}_{server_id}"),
            InlineKeyboardButton(text="❌ انصراف",       callback_data=f"plan_settings_{plan_id}_{server_id}"),
        ],
    ])

# ─── مدیریت مالی ──────────────────────────────

def admin_finance_menu(card_active: bool):
    status = "✅ روشن" if card_active else "❌ خاموش"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 کارت به کارت", callback_data="noop"),
            InlineKeyboardButton(text=status,             callback_data="toggle_card"),
        ],
        [InlineKeyboardButton(text="⚙️ تنظیمات",        callback_data="card_settings")],
        [InlineKeyboardButton(text="🔙 بازگشت",          callback_data="admin_panel")],
    ])

def card_settings_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 تغییر شماره کارت",    callback_data="set_card_number")],
        [InlineKeyboardButton(text="👤 تغییر نام صاحب کارت", callback_data="set_card_owner")],
        [InlineKeyboardButton(text="🔙 بازگشت",              callback_data="admin_finance")],
    ])

# ─── کاربر ────────────────────────────────────

def free_test_servers_keyboard(servers):
    buttons = []
    for s in servers:
        buttons.append([InlineKeyboardButton(
            text=f"🖥 {s['name']}",
            callback_data=f"free_test_server_{s['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="user_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def free_test_confirm_keyboard(server_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ دریافت تست رایگان", callback_data=f"free_test_confirm_{server_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت",            callback_data="user_main")],
    ])

def user_servers_keyboard(servers):
    buttons = []
    for server in servers:
        buttons.append([InlineKeyboardButton(
            text=f"🖥 {server['name']}",
            callback_data=f"user_server_{server['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="user_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def user_plans_keyboard(plans, server_id, multiple_servers: bool = False, show_price: bool = False):
    buttons = []
    for plan in plans:
        label = plan["name"]
        if show_price:
            label += f" — {plan['price']:,} تومان"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"user_plan_{plan['id']}")])
    back_target = "buy_vpn" if multiple_servers else "user_main"
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def proforma_keyboard(plan_id, has_balance: bool = False):
    buttons = []
    if has_balance:
        buttons.append([InlineKeyboardButton(text="💎 پرداخت با کیف پول", callback_data=f"pay_wallet_{plan_id}")])
    buttons.append([InlineKeyboardButton(text="💳 پرداخت کارت به کارت", callback_data=f"pay_{plan_id}")])
    buttons.append([InlineKeyboardButton(text="❌ انصراف", callback_data="user_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def payment_info_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_payment")],
    ])

def user_services_keyboard(orders):
    buttons = []
    for order in orders:
        label = order["vpn_username"] or f"سرویس #{order['id']}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"my_service_{order['id']}")])
    if not orders:
        buttons.append([InlineKeyboardButton(text="🛒 خرید VPN", callback_data="buy_vpn")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="user_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def user_service_detail_keyboard(order_id: int, subscription_url: str = None):
    buttons = []
    if subscription_url:
        buttons.append([InlineKeyboardButton(text="📋 کپی لینک اشتراک", copy_text=CopyTextButton(text=subscription_url))])
    else:
        buttons.append([InlineKeyboardButton(text="🔗 لینک اشتراک", callback_data=f"sub_link_{order_id}")])
    buttons.append([
        InlineKeyboardButton(text="🔄 تمدید",       callback_data=f"renew_service_{order_id}"),
        InlineKeyboardButton(text="🗑 حذف سرویس",   callback_data=f"delete_service_{order_id}"),
    ])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به سرویس‌ها", callback_data="my_services")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def confirm_delete_service_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"confirmed_delete_service_{order_id}"),
            InlineKeyboardButton(text="❌ انصراف",       callback_data=f"my_service_{order_id}"),
        ],
    ])

# ─── سفارش‌ها ─────────────────────────────────

def admin_order_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید", callback_data=f"order_approve_{order_id}")],
        [
            InlineKeyboardButton(text="❌ رد",          callback_data=f"order_reject_{order_id}"),
            InlineKeyboardButton(text="❌ رد با دلیل",  callback_data=f"order_reject_reason_{order_id}"),
        ],
    ])

def subscription_approved_keyboard(subscription_url: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 کپی لینک اشتراک", copy_text=CopyTextButton(text=subscription_url))],
        [InlineKeyboardButton(text="🗂 سرویس‌های من",     callback_data="my_services")],
    ])

def wallet_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 شارژ حساب",          callback_data="top_up")],
        [InlineKeyboardButton(text="📜 تاریخچه تراکنش‌ها", callback_data="wallet_history")],
        [InlineKeyboardButton(text="🔙 بازگشت",             callback_data="user_main")],
    ])

def admin_topup_keyboard(request_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید شارژ", callback_data=f"topup_approve_{request_id}")],
        [InlineKeyboardButton(text="❌ رد",          callback_data=f"topup_reject_{request_id}")],
    ])

def after_order_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚙️ پنل ادمین", callback_data="admin_panel"),
            InlineKeyboardButton(text="🏠 منوی اصلی", callback_data="back_to_start"),
        ],
    ])
