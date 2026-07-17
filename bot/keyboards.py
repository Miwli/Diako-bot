import re
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CopyTextButton
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from shared_lib.db import get_keyboard_rows

# ─── helpers ──────────────────────────────────────────────────────────────────

def _strip_tg_emoji(text: str) -> str:
    """تگ‌های <tg-emoji> رو به fallback emoji تبدیل می‌کنه — چون InlineKeyboardButton از HTML پشتیبانی نمی‌کنه"""
    return re.sub(r'<tg-emoji[^>]*>([^<]*)</tg-emoji>', r'\1', text)


def _build_from_rows(rows: list[dict], template_id=None) -> InlineKeyboardMarkup:
    """ساخت InlineKeyboardMarkup از لیست دکمه‌های DB؛ template_id برای callback_template"""
    grid: dict[int, list] = {}
    for r in rows:
        if not r.get("is_active", 1):
            continue
        tmpl = r.get("callback_template")
        if tmpl:
            cb = tmpl.replace("{id}", str(template_id)) if template_id is not None else tmpl
        else:
            cb = r["callback_data"]
        label = _strip_tg_emoji(r["label"])
        grid.setdefault(r["row_index"], []).append(
            InlineKeyboardButton(text=label, callback_data=cb)
        )
    return InlineKeyboardMarkup(inline_keyboard=[grid[k] for k in sorted(grid)])


def _kb(name: str, template_id=None) -> InlineKeyboardMarkup | None:
    """اگه کیبورد در کش بود می‌سازه، وگرنه None برمی‌گردونه"""
    rows = get_keyboard_rows(name)
    if not rows:
        return None
    return _build_from_rows(rows, template_id)


def _merge_dynamic_grid(dyn_items: list[dict], static_name: str,
                        fallback: list[dict]) -> InlineKeyboardMarkup:
    """کیبورد داینامیک (سوالات/آموزش‌ها) رو با چیدمان چندستونه می‌سازه.

    dyn_items: آیتم‌های داینامیک، هرکدوم dict با label/callback_data/row/col
    static_name: نام کیبورد برای دکمه‌های ثابت (بازگشت و…) از کش
    fallback: دکمه‌های ثابت پیش‌فرض اگه هنوز چیزی در کش نبود
    """
    # (row, col) → دکمه؛ داینامیک‌ها و ثابت‌ها توی یه فضای مختصات مشترک ادغام می‌شن
    cells: list[tuple[int, int, InlineKeyboardButton]] = []
    for it in dyn_items:
        cells.append((it["row"], it["col"],
                      InlineKeyboardButton(text=_strip_tg_emoji(it["label"]),
                                           callback_data=it["callback_data"])))

    static_rows = get_keyboard_rows(static_name) or fallback
    for r in static_rows:
        if not r.get("is_active", 1):
            continue
        cells.append((r.get("row_index", 999), r.get("col_index", 0),
                      InlineKeyboardButton(text=_strip_tg_emoji(r["label"]),
                                           callback_data=r["callback_data"])))

    grid: dict[int, list[tuple[int, InlineKeyboardButton]]] = {}
    for row, col, btn in cells:
        grid.setdefault(row, []).append((col, btn))
    keyboard = [[btn for _, btn in sorted(grid[k], key=lambda x: x[0])] for k in sorted(grid)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ─── منوی اصلی ────────────────────────────────────────────────────────────────

def user_main_menu(rows: list[dict] | None = None) -> InlineKeyboardMarkup:
    if rows is not None:
        return _build_from_rows(rows)
    kb = _kb("user_main")
    if kb:
        return kb
    return InlineKeyboardMarkup(inline_keyboard=[
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


def admin_main_menu(rows: list[dict] | None = None) -> InlineKeyboardMarkup:
    base = user_main_menu(rows)
    buttons = list(base.inline_keyboard)
    buttons.append([InlineKeyboardButton(text="⚙️ پنل ادمین", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_panel_menu() -> InlineKeyboardMarkup:
    return _kb("admin_panel") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖥 مدیریت سرورها",          callback_data="admin_servers")],
        [InlineKeyboardButton(text="📦 پلن‌ها",                  callback_data="admin_plans")],
        [InlineKeyboardButton(text="💰 مدیریت مالی",            callback_data="admin_finance")],
        [InlineKeyboardButton(text="👥 مدیریت کاربران",         callback_data="admin_users")],
        [InlineKeyboardButton(text="🎟 کدهای تخفیف",            callback_data="admin_discount")],
        [InlineKeyboardButton(text="🎁 تنظیمات تست رایگان",     callback_data="admin_free_test")],
        [InlineKeyboardButton(text="🤝 تنظیمات دعوت دوستان",   callback_data="admin_referral")],
        [InlineKeyboardButton(text="🎧 تنظیمات پشتیبانی",       callback_data="admin_support")],
        [InlineKeyboardButton(text="📚 مدیریت آموزش‌ها",        callback_data="admin_tutorials")],
        [InlineKeyboardButton(text="📢 پیام همگانی",             callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 آمار و گزارش",           callback_data="admin_stats")],
        [InlineKeyboardButton(text="⚙️ تنظیمات عمومی",         callback_data="admin_general")],
        [InlineKeyboardButton(text="🔒 جوین اجباری",            callback_data="admin_force_join")],
        [InlineKeyboardButton(text="🔙 بازگشت",                 callback_data="back_to_start")],
    ])


def cancel_keyboard() -> InlineKeyboardMarkup:
    return _kb("cancel") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ لغو", callback_data="cancel")],
    ])


def admin_general_menu() -> InlineKeyboardMarkup:
    return _kb("admin_general") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 ظاهر ربات",     callback_data="admin_banner_and_text")],
        [InlineKeyboardButton(text="🔙 بازگشت",        callback_data="admin_panel")],
    ])


# ─── تست رایگان (ادمین) ────────────────────────────────────────────────────────

def admin_free_test_menu(servers: list) -> InlineKeyboardMarkup:
    rows_db = get_keyboard_rows("admin_free_test_global")
    global_label = rows_db[0]["label"] if rows_db else "⚙️ تنظیمات پیش‌فرض (همه سرورها)"
    rows = [[InlineKeyboardButton(text=global_label, callback_data="admin_free_test_global")]]
    for s in servers:
        status = "✅" if s["free_test_enabled"] else "❌"
        rows.append([InlineKeyboardButton(text=f"{s['name']}  {status}", callback_data=f"admin_free_test_server_{s['id']}")])
    back_rows = get_keyboard_rows("admin_panel")
    back_label = next((r["label"] for r in back_rows if r["callback_data"] == "back_to_start"), "🔙 بازگشت")
    rows.append([InlineKeyboardButton(text=back_label, callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_free_test_global_menu() -> InlineKeyboardMarkup:
    return _kb("admin_free_test_global") or InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ ویرایش مدت",    callback_data="admin_free_test_global_duration"),
            InlineKeyboardButton(text="✏️ ویرایش حجم",    callback_data="admin_free_test_global_traffic"),
        ],
        [InlineKeyboardButton(text="🔢 تعداد مجاز دریافت", callback_data="admin_free_test_max_uses")],
        [InlineKeyboardButton(text="📡 اعمال روی همه سرورها", callback_data="admin_free_test_apply_all")],
        [InlineKeyboardButton(text="🔄 ریست همه کاربران",  callback_data="admin_free_test_reset_all")],
        [InlineKeyboardButton(text="🔙 بازگشت",            callback_data="admin_free_test")],
    ])


def admin_free_test_server_menu(server_id: int, is_enabled: bool) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("admin_free_test_global")
    dur_label = next((r["label"] for r in rows if "مدت" in r["label"]), "✏️ ویرایش مدت")
    trf_label = next((r["label"] for r in rows if "حجم" in r["label"]), "✏️ ویرایش حجم")
    toggle_text = "❌ غیرفعال کردن" if is_enabled else "✅ فعال کردن"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"admin_free_test_toggle_{server_id}")],
        [
            InlineKeyboardButton(text=dur_label, callback_data=f"admin_free_test_duration_{server_id}"),
            InlineKeyboardButton(text=trf_label, callback_data=f"admin_free_test_traffic_{server_id}"),
        ],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_free_test")],
    ])


# ─── بنر و متن ─────────────────────────────────────────────────────────────────

def admin_banner_and_text_menu() -> InlineKeyboardMarkup:
    return _kb("admin_banner_and_text") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖼 تنظیمات بنر",  callback_data="admin_banner_settings")],
        [InlineKeyboardButton(text="✏️ تنظیمات متن",  callback_data="admin_text_settings")],
        [InlineKeyboardButton(text="🔙 بازگشت",        callback_data="admin_general")],
    ])


def admin_text_settings_menu() -> InlineKeyboardMarkup:
    return _kb("admin_text_settings") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش متن",  callback_data="admin_banner_caption")],
        [InlineKeyboardButton(text="🛠 ساخت متن",    callback_data="admin_build_text")],
        [InlineKeyboardButton(text="🔙 بازگشت",       callback_data="admin_banner_and_text")],
    ])


def admin_banner_settings_menu(has_banner: bool) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("admin_banner_and_text")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "admin_general"), "🔙 بازگشت")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 حذف بنر" if has_banner else "🖼 آپلود بنر",
            callback_data="admin_banner_delete" if has_banner else "admin_banner_upload"
        )],
        [InlineKeyboardButton(text=back_label, callback_data="admin_general")],
    ])


def back_to_servers_menu() -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("admin_servers")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "admin_panel"), "🔙 بازگشت")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=back_label, callback_data="admin_servers")],
    ])


# ─── سرورها ───────────────────────────────────────────────────────────────────

def admin_servers_menu() -> InlineKeyboardMarkup:
    return _kb("admin_servers") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ سرور جدید",   callback_data="add_server")],
        [InlineKeyboardButton(text="📋 لیست سرورها", callback_data="list_servers")],
        [InlineKeyboardButton(text="🔙 بازگشت",      callback_data="admin_panel")],
    ])


def servers_table_keyboard(servers: list) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("admin_servers")
    add_label  = next((r["label"] for r in rows if r["callback_data"] == "add_server"),   "➕ سرور جدید")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "admin_panel"),  "🔙 بازگشت")
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
    buttons.append([InlineKeyboardButton(text=add_label,  callback_data="add_server")])
    buttons.append([InlineKeyboardButton(text=back_label, callback_data="admin_servers")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def server_settings_keyboard(server_id: int, is_active: bool) -> InlineKeyboardMarkup:
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


def confirm_delete_server_keyboard(server_id: int) -> InlineKeyboardMarkup:
    return _kb("confirm_delete_server", server_id) or InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"confirmed_delete_server_{server_id}"),
            InlineKeyboardButton(text="❌ انصراف",       callback_data=f"server_settings_{server_id}"),
        ],
    ])


def rebecca_services_keyboard(services: list, selected_ids: list) -> InlineKeyboardMarkup:
    buttons = []
    rows = get_keyboard_rows("cancel")
    done_label   = "✅ انجام شد"
    cancel_label = next((r["label"] for r in rows if r["callback_data"] == "cancel"), "❌ لغو")
    for svc in services:
        mark = "✅" if svc["id"] in selected_ids else "⬜"
        buttons.append([InlineKeyboardButton(text=f"{mark} {svc['name']}", callback_data=f"toggle_svc_{svc['id']}")])
    buttons.append([
        InlineKeyboardButton(text=done_label,   callback_data="confirm_services"),
        InlineKeyboardButton(text=cancel_label, callback_data="cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── پلن‌ها ───────────────────────────────────────────────────────────────────

def admin_plans_menu(show_price: bool = False) -> InlineKeyboardMarkup:
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


def servers_list_keyboard(servers: list, mode: str = "select_server") -> InlineKeyboardMarkup:
    buttons = []
    for server in servers:
        buttons.append([InlineKeyboardButton(text=f"🖥 {server['name']}", callback_data=f"{mode}_{server['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_plans")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def plans_table_keyboard(plans: list, server_id: int) -> InlineKeyboardMarkup:
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


def plan_settings_keyboard(plan_id: int, server_id: int, is_active: bool) -> InlineKeyboardMarkup:
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


def confirm_delete_plan_keyboard(plan_id: int, server_id: int) -> InlineKeyboardMarkup:
    return _kb("confirm_delete_plan", f"{plan_id}_{server_id}") or InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"confirmed_delete_plan_{plan_id}_{server_id}"),
            InlineKeyboardButton(text="❌ انصراف",       callback_data=f"plan_settings_{plan_id}_{server_id}"),
        ],
    ])


# ─── مدیریت مالی ───────────────────────────────────────────────────────────────

def admin_finance_menu(card_active: bool) -> InlineKeyboardMarkup:
    status = "✅ روشن" if card_active else "❌ خاموش"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 کارت به کارت", callback_data="noop"),
            InlineKeyboardButton(text=status,             callback_data="toggle_card"),
        ],
        [InlineKeyboardButton(text="⚙️ تنظیمات کارت‌ها",  callback_data="card_settings")],
        [InlineKeyboardButton(text="🔙 بازگشت",          callback_data="admin_panel")],
    ])


def cards_table_keyboard(cards: list, mode: str) -> InlineKeyboardMarkup:
    buttons = [[
        InlineKeyboardButton(text="💳 کارت",  callback_data="noop"),
        InlineKeyboardButton(text="وضعیت",   callback_data="noop"),
        InlineKeyboardButton(text="تنظیمات", callback_data="noop"),
    ]]
    for c in cards:
        status = "✅ فعال" if c["is_active"] else "❌ غیرفعال"
        tail = c["number"][-4:] if c["number"] else "----"
        buttons.append([
            InlineKeyboardButton(text=f"💳 …{tail}", callback_data=f"card_settings_{c['id']}"),
            InlineKeyboardButton(text=status,         callback_data=f"toggle_card_item_{c['id']}"),
            InlineKeyboardButton(text="⚙️",           callback_data=f"card_settings_{c['id']}"),
        ])
    buttons.append([
        InlineKeyboardButton(text=("✅ " if mode == "round_robin" else "") + "🔁 نوبتی", callback_data="set_card_mode_round_robin"),
        InlineKeyboardButton(text=("✅ " if mode == "random" else "") + "🎲 تصادفی",     callback_data="set_card_mode_random"),
        InlineKeyboardButton(text=("✅ " if mode == "fixed" else "") + "📌 ثابت",        callback_data="set_card_mode_fixed"),
    ])
    buttons.append([InlineKeyboardButton(text="➕ کارت جدید", callback_data="add_card")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",   callback_data="admin_finance")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def card_item_keyboard(card_id: int, is_active: bool, is_fixed: bool, mode: str) -> InlineKeyboardMarkup:
    toggle_text = "❌ غیرفعال کردن" if is_active else "✅ فعال کردن"
    rows = [
        [
            InlineKeyboardButton(text="💳 ویرایش شماره", callback_data=f"edit_card_number_{card_id}"),
            InlineKeyboardButton(text="👤 ویرایش نام",   callback_data=f"edit_card_owner_{card_id}"),
        ],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_card_item_{card_id}")],
    ]
    if mode == "fixed":
        fixed_text = "⭐️ کارت پیش‌فرض" if is_fixed else "☆ تنظیم به‌عنوان پیش‌فرض"
        rows.append([InlineKeyboardButton(text=fixed_text, callback_data=f"set_fixed_card_{card_id}")])
    rows.append([InlineKeyboardButton(text="🗑 حذف کارت", callback_data=f"delete_card_{card_id}")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت",   callback_data="card_settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete_card_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return _kb("confirm_delete_card", card_id) or InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"confirmed_delete_card_{card_id}"),
            InlineKeyboardButton(text="❌ انصراف",       callback_data=f"card_settings_{card_id}"),
        ],
    ])


# ─── کاربر ────────────────────────────────────────────────────────────────────

def free_test_servers_keyboard(servers: list) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("free_test_confirm")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "user_main"), "🔙 بازگشت")
    buttons = []
    for s in servers:
        buttons.append([InlineKeyboardButton(text=f"🖥 {s['name']}", callback_data=f"free_test_server_{s['id']}")])
    buttons.append([InlineKeyboardButton(text=back_label, callback_data="user_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def free_test_confirm_keyboard(server_id: int) -> InlineKeyboardMarkup:
    return _kb("free_test_confirm", server_id) or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ دریافت تست رایگان", callback_data=f"free_test_confirm_{server_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت",            callback_data="user_main")],
    ])


def user_servers_keyboard(servers: list) -> InlineKeyboardMarkup:
    static_rows = get_keyboard_rows("buy_vpn")
    buttons = []
    for server in servers:
        buttons.append([InlineKeyboardButton(text=f"🖥 {server['name']}", callback_data=f"user_server_{server['id']}")])
    if static_rows:
        for r in static_rows:
            label = _strip_tg_emoji(r["label"])
            buttons.append([InlineKeyboardButton(text=label, callback_data=r["callback_data"])])
    else:
        buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="user_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_plans_keyboard(plans: list, server_id: int, multiple_servers: bool = False, show_price: bool = False) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("user_main")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "user_main"), "🔙 بازگشت")
    buttons = []
    for plan in plans:
        label = plan["name"]
        if show_price:
            label += f" — {plan['price']:,} تومان"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"user_plan_{plan['id']}")])
    back_target = "buy_vpn" if multiple_servers else "user_main"
    buttons.append([InlineKeyboardButton(text=back_label, callback_data=back_target)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def proforma_keyboard(plan_id, has_balance: bool = False, has_discount: bool = False) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("payment_info")
    cancel_label = next((r["label"] for r in rows if r["callback_data"] == "cancel_payment"), "❌ انصراف")
    buttons = []
    if has_balance:
        buttons.append([InlineKeyboardButton(text="💎 پرداخت با کیف پول", callback_data=f"pay_wallet_{plan_id}")])
    buttons.append([InlineKeyboardButton(text="💳 پرداخت کارت به کارت", callback_data=f"pay_{plan_id}")])
    if not has_discount:
        buttons.append([InlineKeyboardButton(text="🎟 وارد کردن کد تخفیف", callback_data=f"apply_discount_{plan_id}")])
    buttons.append([InlineKeyboardButton(text=cancel_label, callback_data="user_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_info_keyboard() -> InlineKeyboardMarkup:
    return _kb("payment_info") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_payment")],
    ])


def profile_keyboard() -> InlineKeyboardMarkup:
    # از DB می‌سازه تا ادمین بتونه از پنل دکمه اضافه/جابجا کنه
    return _kb("profile") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="user_main")],
    ])


def user_services_keyboard(orders: list) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("user_main")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "user_main"), "🔙 بازگشت")
    buttons = []
    for order in orders:
        label = order["vpn_username"] or f"سرویس #{order['id']}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"my_service_{order['id']}")])
    if not orders:
        rows_main = get_keyboard_rows("user_main")
        buy_label = next((r["label"] for r in rows_main if r["callback_data"] == "buy_vpn"), "🛒 خرید VPN")
        buttons.append([InlineKeyboardButton(text=buy_label, callback_data="buy_vpn")])
    buttons.append([InlineKeyboardButton(text=back_label, callback_data="user_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_service_detail_keyboard(order_id: int, subscription_url: str = None) -> InlineKeyboardMarkup:
    buttons = []
    # لینک اشتراک همیشه اول است — از DB نمی‌آید (CopyTextButton خاص aiogram است)
    if subscription_url:
        buttons.append([InlineKeyboardButton(text="📋 کپی لینک اشتراک", copy_text=CopyTextButton(text=subscription_url))])
    else:
        buttons.append([InlineKeyboardButton(text="🔗 لینک اشتراک", callback_data=f"sub_link_{order_id}")])
    # بقیه دکمه‌ها از DB — ادمین از پنل مدیریت می‌کند (تمدید، حذف، و فیچرهای جدید)
    rows = get_keyboard_rows("user_service_detail")
    if rows:
        db_part = _build_from_rows(rows, template_id=order_id)
        buttons.extend(db_part.inline_keyboard)
    else:
        buttons.append([
            InlineKeyboardButton(text="🔄 تمدید",     callback_data=f"renew_service_{order_id}"),
            InlineKeyboardButton(text="🗑 حذف سرویس", callback_data=f"delete_service_{order_id}"),
        ])
        buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="my_services")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_service_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return _kb("confirm_delete_service", order_id) or InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"confirmed_delete_service_{order_id}"),
            InlineKeyboardButton(text="❌ انصراف",       callback_data=f"my_service_{order_id}"),
        ],
    ])


def confirm_changestatus_keyboard(order_id: int, target_active: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ بله", callback_data=f"confirmed_changestatus_{order_id}_{int(target_active)}"),
            InlineKeyboardButton(text="❌ انصراف", callback_data=f"my_service_{order_id}"),
        ],
    ])


def cancel_changenote_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"my_service_{order_id}")],
    ])


def changeloc_servers_keyboard(order_id: int, servers: list) -> InlineKeyboardMarkup:
    # لیست داینامیک — از جدول سرورها میاد، نه از keyboard_buttons
    rows = [
        [InlineKeyboardButton(text=s["name"], callback_data=f"chgloc_srv_{order_id}_{s['id']}")]
        for s in servers
    ]
    rows.append([InlineKeyboardButton(text="❌ انصراف", callback_data=f"my_service_{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_changeloc_keyboard(order_id: int, server_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ بله، منتقل کن", callback_data=f"chgloc_go_{order_id}_{server_id}"),
            InlineKeyboardButton(text="❌ انصراف",        callback_data=f"my_service_{order_id}"),
        ],
    ])


def admin_changeloc_keyboard(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید انتقال", callback_data=f"chgloc_approve_{req_id}")],
        [InlineKeyboardButton(text="❌ رد",            callback_data=f"chgloc_reject_{req_id}")],
    ])


# ─── سفارش‌ها ──────────────────────────────────────────────────────────────────

def admin_order_keyboard(order_id) -> InlineKeyboardMarkup:
    return _kb("admin_order", order_id) or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید", callback_data=f"order_approve_{order_id}")],
        [
            InlineKeyboardButton(text="❌ رد",          callback_data=f"order_reject_{order_id}"),
            InlineKeyboardButton(text="❌ رد با دلیل",  callback_data=f"order_reject_reason_{order_id}"),
        ],
    ])


def subscription_approved_keyboard(subscription_url: str) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("subscription_approved")
    services_label = next((r["label"] for r in rows if r["callback_data"] == "my_services"), "🗂 سرویس‌های من")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 کپی لینک اشتراک", copy_text=CopyTextButton(text=subscription_url))],
        [InlineKeyboardButton(text=services_label, callback_data="my_services")],
    ])


def wallet_keyboard() -> InlineKeyboardMarkup:
    return _kb("wallet") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 شارژ حساب",          callback_data="top_up")],
        [InlineKeyboardButton(text="📜 تاریخچه تراکنش‌ها", callback_data="wallet_history")],
        [InlineKeyboardButton(text="🔙 بازگشت",             callback_data="user_main")],
    ])


def admin_topup_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return _kb("admin_topup", request_id) or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تایید شارژ", callback_data=f"topup_approve_{request_id}")],
        [InlineKeyboardButton(text="❌ رد",          callback_data=f"topup_reject_{request_id}")],
    ])


def after_order_keyboard() -> InlineKeyboardMarkup:
    return _kb("after_order") or InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚙️ پنل ادمین", callback_data="admin_panel"),
            InlineKeyboardButton(text="🏠 منوی اصلی", callback_data="back_to_start"),
        ],
    ])


# ─── پشتیبانی ─────────────────────────────────────────────────────────────────

def support_menu_keyboard() -> InlineKeyboardMarkup:
    return _kb("support") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 تیکت جدید",    callback_data="new_ticket")],
        [InlineKeyboardButton(text="📋 تیکت‌های من",  callback_data="my_tickets")],
        [InlineKeyboardButton(text="🔙 بازگشت",       callback_data="user_main")],
    ])


def ticket_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    return _kb("ticket", ticket_id) or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ بستن تیکت",      callback_data=f"close_ticket_{ticket_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت به منو", callback_data="user_main")],
    ])


def my_tickets_keyboard(tickets: list) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("support")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "support"), "🔙 بازگشت")
    result = []
    for t in tickets:
        icon = "🟢" if t["status"] == "open" else "🔴"
        result.append([InlineKeyboardButton(text=f"{icon} تیکت #{t['id']}", callback_data=f"view_ticket_{t['id']}")])
    result.append([InlineKeyboardButton(text=back_label, callback_data="support")])
    return InlineKeyboardMarkup(inline_keyboard=result)


def admin_support_settings_keyboard() -> InlineKeyboardMarkup:
    return _kb("admin_support_settings") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆔 تنظیم آیدی گروه",   callback_data="admin_support_set_group")],
        [InlineKeyboardButton(text="✏️ ویرایش متن تیکت",   callback_data="admin_support_edit_msg")],
        [InlineKeyboardButton(text="🔙 بازگشت",             callback_data="admin_panel")],
    ])


# ─── آموزش‌ها (ادمین) ──────────────────────────────────────────────────────────

def admin_tutorials_menu() -> InlineKeyboardMarkup:
    return _kb("admin_tutorials") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 آموزش‌ها",        callback_data="admin_tutorial_list")],
        [InlineKeyboardButton(text="📋 سوالات متداول",   callback_data="admin_faqs")],
        [InlineKeyboardButton(text="🔙 بازگشت",          callback_data="admin_panel")],
    ])


def admin_tutorial_list_menu(tutorials: list) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("admin_tutorials")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "admin_tutorials"), "🔙 بازگشت")
    result = [[InlineKeyboardButton(text="➕ افزودن آموزش جدید", callback_data="tutorial_add")]]
    for t in tutorials:
        status = "✅" if t["is_active"] else "❌"
        result.append([InlineKeyboardButton(text=f"{status} {t['title']}", callback_data=f"tutorial_item_{t['id']}")])
    result.append([InlineKeyboardButton(text=back_label, callback_data="admin_tutorials")])
    return InlineKeyboardMarkup(inline_keyboard=result)


def admin_tutorial_item_keyboard(tutorial_id: int, is_active: bool, is_first: bool, is_last: bool) -> InlineKeyboardMarkup:
    order_row = []
    if not is_first:
        order_row.append(InlineKeyboardButton(text="⬆️ بالاتر", callback_data=f"tutorial_move_up_{tutorial_id}"))
    order_row.append(InlineKeyboardButton(
        text="✅ فعال" if is_active else "❌ غیرفعال",
        callback_data=f"tutorial_toggle_{tutorial_id}"
    ))
    if not is_last:
        order_row.append(InlineKeyboardButton(text="⬇️ پایین‌تر", callback_data=f"tutorial_move_down_{tutorial_id}"))
    rows = get_keyboard_rows("admin_tutorials")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "admin_tutorials"), "🔙 بازگشت")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ ویرایش عنوان", callback_data=f"tutorial_edit_title_{tutorial_id}"),
            InlineKeyboardButton(text="🔄 ویرایش محتوا", callback_data=f"tutorial_edit_content_{tutorial_id}"),
        ],
        order_row,
        [InlineKeyboardButton(text="🗑 حذف", callback_data=f"tutorial_delete_{tutorial_id}")],
        [InlineKeyboardButton(text=back_label, callback_data="admin_tutorials")],
    ])


def admin_faqs_menu(faqs: list) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("admin_tutorials")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "admin_tutorials"), "🔙 بازگشت")
    result = [[InlineKeyboardButton(text="➕ افزودن سوال جدید", callback_data="faq_add")]]
    for f in faqs:
        status = "✅" if f["is_active"] else "❌"
        result.append([InlineKeyboardButton(text=f"{status} {f['question']}", callback_data=f"faq_item_{f['id']}")])
    result.append([InlineKeyboardButton(text=back_label, callback_data="admin_tutorials")])
    return InlineKeyboardMarkup(inline_keyboard=result)


def admin_faq_item_keyboard(faq_id: int, is_active: bool) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("admin_tutorials")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "admin_faqs"), "🔙 بازگشت")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ ویرایش سوال",  callback_data=f"faq_edit_q_{faq_id}"),
            InlineKeyboardButton(text="✏️ ویرایش جواب",  callback_data=f"faq_edit_a_{faq_id}"),
        ],
        [InlineKeyboardButton(
            text="✅ فعال" if is_active else "❌ غیرفعال",
            callback_data=f"faq_toggle_{faq_id}"
        )],
        [InlineKeyboardButton(text="🗑 حذف", callback_data=f"faq_delete_{faq_id}")],
        [InlineKeyboardButton(text=back_label, callback_data="admin_faqs")],
    ])


# ─── آموزش‌ها (کاربر) ──────────────────────────────────────────────────────────

def user_tutorials_keyboard(tutorials: list) -> InlineKeyboardMarkup:
    dyn = [
        {"label": t["title"], "callback_data": f"tutorial_view_{t['id']}",
         "row": t["order_index"], "col": t["col_index"]}
        for t in tutorials
    ]
    fallback = [
        {"label": "❓ سوالات متداول", "callback_data": "user_faqs",     "row_index": 998, "col_index": 0},
        {"label": "🔙 بازگشت",        "callback_data": "back_to_start", "row_index": 999, "col_index": 0},
    ]
    return _merge_dynamic_grid(dyn, "user_tutorials", fallback)


def user_faqs_keyboard(faqs: list) -> InlineKeyboardMarkup:
    dyn = [
        {"label": f["question"], "callback_data": f"faq_view_{f['id']}",
         "row": f["order_index"], "col": f["col_index"]}
        for f in faqs
    ]
    fallback = [{"label": "🔙 بازگشت", "callback_data": "tutorial", "row_index": 999, "col_index": 0}]
    return _merge_dynamic_grid(dyn, "user_faqs", fallback)


def back_to_tutorials_keyboard() -> InlineKeyboardMarkup:
    return _kb("back_to_tutorials") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="tutorial")]
    ])


def back_to_faqs_keyboard() -> InlineKeyboardMarkup:
    return _kb("back_to_faqs") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="user_faqs")]
    ])


# ─── دعوت دوستان (ادمین) ───────────────────────────────────────────────────────

def admin_referral_menu(enabled: bool, flat_en: bool, flat_amt: int,
                        pct_en: bool, pct_val: int,
                        free_en: bool,
                        disc_en: bool, disc_val: int) -> InlineKeyboardMarkup:
    def _row(label, cb, active, detail=""):
        mark = "✅" if active else "❌"
        txt = f"{mark} {label}"
        if detail:
            txt += f" — {detail}"
        return [InlineKeyboardButton(text=txt, callback_data=cb)]

    system_btn = "🟢 سیستم فعال است" if enabled else "🔴 سیستم غیرفعال است"
    rows = get_keyboard_rows("admin_panel")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "admin_panel"), "🔙 بازگشت")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=system_btn, callback_data="referral_toggle_system")],
        _row("💵 جایزه ثابت دعوت‌کننده", "referral_flat",      flat_en, f"{flat_amt:,} تومان" if flat_en else ""),
        _row("📊 پورسانت از هر خرید",     "referral_percent",   pct_en,  f"{pct_val}٪" if pct_en else ""),
        _row("🎁 تست رایگان اضافه",        "referral_free_test", free_en),
        _row("🎫 اعتبار خوش‌آمدگویی",     "referral_discount",  disc_en, f"{disc_val}٪ خرید" if disc_en else ""),
        [InlineKeyboardButton(text=back_label, callback_data="admin_panel")],
    ])


def admin_referral_sub_keyboard(cb_toggle: str, cb_edit: str | None, back: str = "admin_referral") -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("admin_panel")
    back_label = next((r["label"] for r in rows if "بازگشت" in r["label"]), "🔙 بازگشت")
    result = [[InlineKeyboardButton(text="🔄 روشن / خاموش", callback_data=cb_toggle)]]
    if cb_edit:
        result.append([InlineKeyboardButton(text="✏️ تغییر مقدار", callback_data=cb_edit)])
    result.append([InlineKeyboardButton(text=back_label, callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=result)


# ─── دعوت دوستان (کاربر) ───────────────────────────────────────────────────────

def user_referral_keyboard(ref_link: str) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("user_main")
    back_label = next((r["label"] for r in rows if r["callback_data"] == "user_main"), "🔙 بازگشت")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 کپی لینک دعوت", copy_text=CopyTextButton(text=ref_link))],
        [InlineKeyboardButton(text=back_label, callback_data="back_to_start")],
    ])


# ─── کد تخفیف ─────────────────────────────────────────────────────────────────

def admin_discount_menu(codes: list) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("admin_panel")
    back_label = next((r["label"] for r in rows if "بازگشت" in r["label"]), "🔙 بازگشت")
    result = [[InlineKeyboardButton(text="➕ افزودن کد تخفیف", callback_data="discount_add")]]
    for c in codes:
        mark  = "✅" if c["is_active"] else "❌"
        type_ = "٪" if c["type"] == "percent" else "T"
        uses  = f"{c['used_count']}" + (f"/{c['max_uses']}" if c["max_uses"] else "")
        result.append([InlineKeyboardButton(
            text=f"{mark} {c['code']}  —  {c['value']}{type_}  ({uses})",
            callback_data=f"discount_item_{c['id']}"
        )])
    result.append([InlineKeyboardButton(text=back_label, callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=result)


def admin_discount_item_keyboard(code_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle = "❌ غیرفعال کردن" if is_active else "✅ فعال کردن"
    rows = get_keyboard_rows("admin_panel")
    back_label = next((r["label"] for r in rows if "بازگشت" in r["label"]), "🔙 بازگشت")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle,      callback_data=f"discount_toggle_{code_id}"),
            InlineKeyboardButton(text="🗑 حذف",    callback_data=f"discount_delete_{code_id}"),
        ],
        [InlineKeyboardButton(text=back_label, callback_data="admin_discount")],
    ])


def discount_type_keyboard() -> InlineKeyboardMarkup:
    return _kb("discount_type") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="٪ درصدی",        callback_data="discount_type_percent")],
        [InlineKeyboardButton(text="💵 مبلغ ثابت",   callback_data="discount_type_fixed")],
        [InlineKeyboardButton(text="🔙 انصراف",      callback_data="admin_discount")],
    ])


def discount_expiry_keyboard() -> InlineKeyboardMarkup:
    return _kb("discount_expiry") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♾ بدون تاریخ انقضا", callback_data="discount_expiry_none")],
        [InlineKeyboardButton(text="🔙 انصراف",           callback_data="admin_discount")],
    ])


# ─── آمار ─────────────────────────────────────────────────────────────────────

def admin_stats_keyboard() -> InlineKeyboardMarkup:
    return _kb("admin_stats") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 بازگشت",    callback_data="admin_panel")],
    ])


# ─── پیام همگانی ───────────────────────────────────────────────────────────────

def admin_broadcast_menu() -> InlineKeyboardMarkup:
    return _kb("admin_broadcast") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 همه کاربران",             callback_data="broadcast_target_all")],
        [InlineKeyboardButton(text="✅ کاربران با سرویس فعال",   callback_data="broadcast_target_active")],
        [InlineKeyboardButton(text="🔙 بازگشت",                  callback_data="admin_panel")],
    ])


def admin_broadcast_confirm_keyboard(count: int, target: str) -> InlineKeyboardMarkup:
    rows = get_keyboard_rows("admin_broadcast")
    all_label    = next((r["label"] for r in rows if r["callback_data"] == "broadcast_target_all"),    "همه کاربران")
    active_label = next((r["label"] for r in rows if r["callback_data"] == "broadcast_target_active"), "کاربران با سرویس فعال")
    cancel_label = next((r["label"] for r in rows if "بازگشت" in r["label"]), "❌ انصراف")
    label = all_label if target == "all" else active_label
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ ارسال به {count:,} {label}", callback_data="broadcast_confirm")],
        [InlineKeyboardButton(text=cancel_label, callback_data="broadcast_cancel")],
    ])


# ─── مدیریت کاربران ────────────────────────────────────────────────────────────

def admin_users_menu() -> InlineKeyboardMarkup:
    return _kb("admin_users") or InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 جستجوی کاربر",      callback_data="admin_users_search")],
        [InlineKeyboardButton(text="🕐 جدیدترین‌ها",        callback_data="admin_ul_newest_0")],
        [InlineKeyboardButton(text="🏆 بیشترین خرید",       callback_data="admin_ul_topbuyers_0")],
        [InlineKeyboardButton(text="🚫 کاربران بن‌شده",     callback_data="admin_ul_banned_0")],
        [InlineKeyboardButton(text="🔙 بازگشت",             callback_data="admin_panel")],
    ])


def admin_user_list_keyboard(users: list, page: int, filter_type: str, total: int) -> InlineKeyboardMarkup:
    per_page = 8
    rows_db  = get_keyboard_rows("admin_users")
    back_label = next((r["label"] for r in rows_db if "بازگشت" in r["label"]), "🔙 بازگشت")
    buttons = []
    for u in users:
        ban_mark = "🚫 " if u.get("is_banned") else ""
        name = u.get("first_name") or f"user_{u['user_id']}"
        username = f" (@{u['username']})" if u.get("username") else ""
        buttons.append([InlineKeyboardButton(
            text=f"{ban_mark}{name}{username}",
            callback_data=f"admin_up_{u['user_id']}"
        )])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"admin_ul_{filter_type}_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page + 1}", callback_data="noop"))
    if (page + 1) * per_page < total:
        nav.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"admin_ul_{filter_type}_{page + 1}"))
    if len(nav) > 1:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text=back_label, callback_data="admin_users")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_user_profile_keyboard(user_id: int, is_banned: bool) -> InlineKeyboardMarkup:
    rows_db    = get_keyboard_rows("admin_users")
    back_label = next((r["label"] for r in rows_db if "بازگشت" in r["label"]), "🔙 بازگشت")
    ban_text   = "✅ آنبن کاربر" if is_banned else "🚫 بن کردن"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ban_text,              callback_data=f"admin_ua_{'unban' if is_banned else 'ban'}_{user_id}")],
        [
            InlineKeyboardButton(text="➕ افزودن موجودی", callback_data=f"admin_ua_addbal_{user_id}"),
            InlineKeyboardButton(text="➖ کسر موجودی",   callback_data=f"admin_ua_dedbal_{user_id}"),
        ],
        [InlineKeyboardButton(text="🎁 اعطای تست رایگان", callback_data=f"admin_ua_freetest_{user_id}")],
        [
            InlineKeyboardButton(text="📋 سرویس‌ها",     callback_data=f"admin_ua_services_{user_id}"),
            InlineKeyboardButton(text="📨 ارسال پیام",   callback_data=f"admin_ua_msg_{user_id}"),
        ],
        [InlineKeyboardButton(text=back_label,            callback_data="admin_users")],
    ])


# ─── جوین اجباری ────────────────────────────────────────────────────────────

def admin_force_join_menu(enabled: bool) -> InlineKeyboardMarkup:
    status = "✅ روشن" if enabled else "❌ خاموش"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔒 جوین اجباری", callback_data="noop"),
            InlineKeyboardButton(text=status,            callback_data="toggle_force_join"),
        ],
        [InlineKeyboardButton(text="📋 لیست کانال‌ها",  callback_data="list_channels")],
        [InlineKeyboardButton(text="🔙 بازگشت",         callback_data="admin_panel")],
    ])


def channels_table_keyboard(channels: list) -> InlineKeyboardMarkup:
    buttons = [[
        InlineKeyboardButton(text="📢 کانال", callback_data="noop"),
        InlineKeyboardButton(text="وضعیت",   callback_data="noop"),
        InlineKeyboardButton(text="تنظیمات", callback_data="noop"),
    ]]
    for c in channels:
        status = "✅ فعال" if c["is_active"] else "❌ غیرفعال"
        buttons.append([
            InlineKeyboardButton(text=c["title"] or c["chat_id"], callback_data=f"channel_settings_{c['id']}"),
            InlineKeyboardButton(text=status,                      callback_data=f"toggle_channel_{c['id']}"),
            InlineKeyboardButton(text="⚙️",                        callback_data=f"channel_settings_{c['id']}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ کانال جدید", callback_data="add_channel")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",     callback_data="admin_force_join")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def channel_item_keyboard(channel_id: int, is_active: bool) -> InlineKeyboardMarkup:
    toggle_text = "❌ غیرفعال کردن" if is_active else "✅ فعال کردن"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆔 ویرایش آیدی/یوزرنیم", callback_data=f"edit_channel_id_{channel_id}")],
        [InlineKeyboardButton(text="📝 ویرایش عنوان",         callback_data=f"edit_channel_title_{channel_id}")],
        [InlineKeyboardButton(text="🔗 ویرایش لینک دعوت",     callback_data=f"edit_channel_link_{channel_id}")],
        [InlineKeyboardButton(text=toggle_text,               callback_data=f"toggle_channel_{channel_id}")],
        [InlineKeyboardButton(text="🗑 حذف کانال",            callback_data=f"delete_channel_{channel_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت",               callback_data="list_channels")],
    ])


def confirm_delete_channel_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    return _kb("confirm_delete_channel", channel_id) or InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"confirmed_delete_channel_{channel_id}"),
            InlineKeyboardButton(text="❌ انصراف",       callback_data=f"channel_settings_{channel_id}"),
        ],
    ])


def _channel_join_url(invite_link: str, chat_id: str) -> str | None:
    raw = (invite_link or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("t.me/") or raw.startswith("telegram.me/"):
        return "https://" + raw
    if raw.startswith("@"):
        return "https://t.me/" + raw[1:]
    if raw:
        return "https://t.me/" + raw.lstrip("/")
    cid = (chat_id or "").strip()
    if cid.startswith("@"):
        return "https://t.me/" + cid[1:]
    return None


def force_join_keyboard(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for c in channels:
        link = _channel_join_url(c["invite_link"], c["chat_id"])
        if link:
            buttons.append([InlineKeyboardButton(text=f"📢 {c['title'] or c['chat_id']}", url=link)])
    buttons.append([InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_force_join")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
