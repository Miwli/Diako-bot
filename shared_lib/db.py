import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared-data", "bot.db")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


async def init_db():
    """ساخت جداول دیتابیس"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                panel_url   TEXT NOT NULL,
                panel_token TEXT NOT NULL,
                service_ids TEXT,
                is_active   INTEGER DEFAULT 1
            )
        """)
        # migration: اضافه کردن ستون‌های جدید به servers
        server_migrations = {
            "service_id":         "TEXT",
            "service_ids":        "TEXT",
            "free_test_enabled":  "INTEGER DEFAULT 0",
            "free_test_duration": "INTEGER DEFAULT 1",
            "free_test_traffic":  "INTEGER DEFAULT 1",
            "order_index":        "INTEGER DEFAULT 0",
        }
        for col, col_type in server_migrations.items():
            try:
                await db.execute(f"ALTER TABLE servers ADD COLUMN {col} {col_type}")
                await db.commit()
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER,
                name      TEXT NOT NULL,
                price     INTEGER NOT NULL,
                duration  INTEGER NOT NULL,
                traffic   INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (server_id) REFERENCES servers(id)
            )
        """)
        # migration: تبدیل server_id از NOT NULL به nullable
        cursor = await db.execute("PRAGMA table_info(plans)")
        columns = await cursor.fetchall()
        for col in columns:
            if col[1] == "server_id" and col[3] == 1:
                await db.execute("""
                    CREATE TABLE plans_new (
                        id        INTEGER PRIMARY KEY AUTOINCREMENT,
                        server_id INTEGER,
                        name      TEXT NOT NULL,
                        price     INTEGER NOT NULL,
                        duration  INTEGER NOT NULL,
                        traffic   INTEGER NOT NULL,
                        is_active INTEGER DEFAULT 1,
                        FOREIGN KEY (server_id) REFERENCES servers(id)
                    )
                """)
                await db.execute("INSERT INTO plans_new SELECT * FROM plans")
                await db.execute("DROP TABLE plans")
                await db.execute("ALTER TABLE plans_new RENAME TO plans")
                await db.commit()
                break
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER NOT NULL,
                username         TEXT,
                plan_id          INTEGER NOT NULL,
                receipt_file_id  TEXT NOT NULL,
                status           TEXT NOT NULL DEFAULT 'pending',
                rejection_reason TEXT,
                vpn_username     TEXT,
                subscription_url TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES plans(id)
            )
        """)
        for col, col_type in {
            "vpn_username":       "TEXT",
            "subscription_url":   "TEXT",
            "order_type":         "TEXT DEFAULT 'purchase'",
            "free_test_server_id":"INTEGER",
        }.items():
            try:
                await db.execute(f"ALTER TABLE orders ADD COLUMN {col} {col_type}")
                await db.commit()
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       INTEGER PRIMARY KEY,
                first_name    TEXT,
                username      TEXT,
                balance       INTEGER DEFAULT 0,
                referral_code TEXT UNIQUE,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col, col_type in {
            "referral_code":  "TEXT",
            "free_test_uses": "INTEGER DEFAULT 0",
            "referral_by":    "TEXT",
            "is_banned":      "INTEGER DEFAULT 0",
        }.items():
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
                await db.commit()
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      INTEGER NOT NULL,
                type        TEXT NOT NULL,
                description TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS top_up_requests (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                username        TEXT,
                amount          INTEGER NOT NULL,
                receipt_file_id TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                topic_id   INTEGER,
                group_id   INTEGER,
                status     TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id             INTEGER NOT NULL,
                referred_id             INTEGER NOT NULL UNIQUE,
                first_purchase_rewarded INTEGER DEFAULT 0,
                total_commission        INTEGER DEFAULT 0,
                created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tutorials (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                title            TEXT NOT NULL,
                content_type     TEXT NOT NULL DEFAULT 'text',
                file_id          TEXT,
                caption          TEXT,
                caption_entities TEXT,
                order_index      INTEGER DEFAULT 0,
                is_active        INTEGER DEFAULT 1,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col in ["caption_entities"]:
            try:
                await db.execute(f"ALTER TABLE tutorials ADD COLUMN {col} TEXT")
                await db.commit()
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS faqs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                question        TEXT NOT NULL,
                answer          TEXT NOT NULL,
                answer_entities TEXT,
                order_index     INTEGER DEFAULT 0,
                is_active       INTEGER DEFAULT 1,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col in ["answer_entities"]:
            try:
                await db.execute(f"ALTER TABLE faqs ADD COLUMN {col} TEXT")
                await db.commit()
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code        TEXT UNIQUE NOT NULL,
                type        TEXT NOT NULL DEFAULT 'percent',
                value       INTEGER NOT NULL,
                max_uses    INTEGER DEFAULT 0,
                used_count  INTEGER DEFAULT 0,
                is_active   INTEGER DEFAULT 1,
                expires_at  TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col, col_type in {
            "discount_code":   "TEXT",
            "discount_amount": "INTEGER DEFAULT 0",
        }.items():
            try:
                await db.execute(f"ALTER TABLE orders ADD COLUMN {col} {col_type}")
                await db.commit()
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discount_code_uses (
                code_id    INTEGER NOT NULL,
                user_id    INTEGER NOT NULL,
                used_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (code_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS keyboard_buttons (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                keyboard_name TEXT NOT NULL,
                label         TEXT NOT NULL,
                callback_data TEXT NOT NULL,
                row_index     INTEGER NOT NULL DEFAULT 0,
                col_index     INTEGER NOT NULL DEFAULT 0,
                is_active     INTEGER NOT NULL DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS keyboard_actions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                action_name   TEXT NOT NULL UNIQUE,
                label         TEXT NOT NULL,
                callback_data TEXT NOT NULL
            )
        """)
        await db.commit()
    # migration: ستون callback_template اگه وجود نداشت اضافه می‌شه
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("ALTER TABLE keyboard_buttons ADD COLUMN callback_template TEXT")
            await db.commit()
        except Exception:
            pass
    # migration: ستون grp برای دسته‌بندی اکشن‌ها در کاتالوگ
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("ALTER TABLE keyboard_actions ADD COLUMN grp TEXT DEFAULT 'user'")
            await db.commit()
        except Exception:
            pass
    # migration: ستون admin_only برای دکمه‌هایی که فقط ادمین می‌بینه
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("ALTER TABLE keyboard_buttons ADD COLUMN admin_only INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass
        # دکمه‌ی پنل ادمین در user_main — اگه وجود نداشت اضافه می‌کنیم
        await db.execute("""
            INSERT OR IGNORE INTO keyboard_buttons
              (keyboard_name, label, callback_data, row_index, col_index, is_active, admin_only)
            SELECT 'user_main','⚙️ پنل ادمین','admin_panel',99,0,1,1
            WHERE NOT EXISTS (
              SELECT 1 FROM keyboard_buttons
              WHERE keyboard_name='user_main' AND callback_data='admin_panel'
            )
        """)
        # دکمه‌ی بازگشت در buy_vpn — اگه وجود نداشت اضافه می‌کنیم
        await db.execute("""
            INSERT OR IGNORE INTO keyboard_buttons
              (keyboard_name, label, callback_data, row_index, col_index, is_active, admin_only)
            SELECT 'buy_vpn','🔙 بازگشت','user_main',999,0,1,0
            WHERE NOT EXISTS (
              SELECT 1 FROM keyboard_buttons WHERE keyboard_name='buy_vpn'
            )
        """)
        await db.commit()
    await _seed_keyboard_buttons()
    await init_texts_cache()
    await init_keyboards_cache()

# ─── توابع تیکت ──────────────────────────────

async def create_ticket(user_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO tickets (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()
        return cursor.lastrowid

async def get_ticket(ticket_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        return await cursor.fetchone()

async def get_ticket_by_topic(topic_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tickets WHERE topic_id = ?", (topic_id,))
        return await cursor.fetchone()

async def get_user_open_ticket(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE user_id = ? AND status = 'open' ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        return await cursor.fetchone()

async def get_user_tickets(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        return await cursor.fetchall()

async def set_ticket_topic(ticket_id: int, topic_id: int, group_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET topic_id = ?, group_id = ? WHERE id = ?",
            (topic_id, group_id, ticket_id)
        )
        await db.commit()

async def close_ticket(ticket_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET status = 'closed' WHERE id = ?", (ticket_id,)
        )
        await db.commit()

# ─── توابع سرورها ─────────────────────────────

async def add_server(name: str, panel_url: str, panel_token: str, service_ids: list = None):
    """اضافه کردن سرور جدید"""
    import json
    ids_json = json.dumps(service_ids) if service_ids else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO servers (name, panel_url, panel_token, service_ids) VALUES (?, ?, ?, ?)",
            (name, panel_url, panel_token, ids_json)
        )
        await db.commit()

async def get_servers(only_active: bool = True):
    """گرفتن لیست سرورها"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if only_active:
            cursor = await db.execute("SELECT * FROM servers WHERE is_active = 1")
        else:
            cursor = await db.execute("SELECT * FROM servers")
        return await cursor.fetchall()

async def get_server(server_id: int):
    """گرفتن یک سرور با id"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM servers WHERE id = ?", (server_id,))
        return await cursor.fetchone()

async def delete_server(server_id: int):
    """حذف سرور و یتیم کردن پلن‌هاش"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE plans SET server_id = NULL WHERE server_id = ?", (server_id,))
        await db.execute("DELETE FROM servers WHERE id = ?", (server_id,))
        await db.commit()

async def toggle_server_status(server_id: int):
    """تغییر وضعیت فعال/غیرفعال سرور"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE servers SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (server_id,)
        )
        await db.commit()

async def update_server_services(server_id: int, service_ids: list):
    """بروزرسانی سرویس‌های یک سرور"""
    import json
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE servers SET service_ids = ? WHERE id = ?",
            (json.dumps(service_ids), server_id)
        )
        await db.commit()

async def update_server_url(server_id: int, panel_url: str):
    """بروزرسانی آدرس پنل سرور"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE servers SET panel_url = ? WHERE id = ?",
            (panel_url, server_id)
        )
        await db.commit()

async def update_server_token(server_id: int, panel_token: str):
    """بروزرسانی توکن API سرور"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE servers SET panel_token = ? WHERE id = ?",
            (panel_token, server_id)
        )
        await db.commit()

async def update_server_free_test(server_id: int, enabled: int = None, duration: float = None, traffic: float = None):
    """بروزرسانی تنظیمات تست رایگان یک سرور"""
    async with aiosqlite.connect(DB_PATH) as db:
        if enabled is not None:
            await db.execute("UPDATE servers SET free_test_enabled = ? WHERE id = ?", (enabled, server_id))
        if duration is not None:
            await db.execute("UPDATE servers SET free_test_duration = ? WHERE id = ?", (duration, server_id))
        if traffic is not None:
            await db.execute("UPDATE servers SET free_test_traffic = ? WHERE id = ?", (traffic, server_id))
        await db.commit()

async def apply_free_test_to_all(duration: float, traffic: float):
    """اعمال تنظیمات تست رایگان روی همه سرورها"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE servers SET free_test_duration = ?, free_test_traffic = ?",
            (duration, traffic)
        )
        await db.commit()

async def increment_free_test_uses(user_id: int):
    """یک واحد به تعداد دفعات استفاده از تست رایگان اضافه کن"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET free_test_uses = COALESCE(free_test_uses, 0) + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

async def decrement_free_test_uses(user_id: int):
    """یک تست رایگان رایگان اضافه بده (با کم کردن شمارنده)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET free_test_uses = MAX(0, COALESCE(free_test_uses, 0) - 1) WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()

async def get_free_test_uses(user_id: int) -> int:
    """تعداد دفعاتی که کاربر تست گرفته"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT free_test_uses FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row[0] if row and row[0] is not None else 0

async def reset_free_test_uses(user_id: int = None):
    """ریست تعداد استفاده — اگه user_id داده نشه همه رو ریست می‌کنه"""
    async with aiosqlite.connect(DB_PATH) as db:
        if user_id is not None:
            await db.execute("UPDATE users SET free_test_uses = 0 WHERE user_id = ?", (user_id,))
        else:
            await db.execute("UPDATE users SET free_test_uses = 0")
        await db.commit()

# ─── توابع پلن‌ها ──────────────────────────────

async def add_plan(server_id: int, name: str, price: int, duration: int, traffic: int):
    """اضافه کردن پلن جدید"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO plans (server_id, name, price, duration, traffic) VALUES (?, ?, ?, ?, ?)",
            (server_id, name, price, duration, traffic)
        )
        await db.commit()

async def get_plans(server_id: int, only_active: bool = True):
    """گرفتن پلن‌های یه سرور"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if only_active:
            cursor = await db.execute(
                "SELECT * FROM plans WHERE server_id = ? AND is_active = 1", (server_id,)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM plans WHERE server_id = ?", (server_id,)
            )
        return await cursor.fetchall()

async def get_plan_by_name(server_id: int, name: str):
    """چک کردن تکراری بودن اسم پلن داخل یه سرور"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM plans WHERE server_id = ? AND name = ?", (server_id, name)
        )
        return await cursor.fetchone()

async def delete_plan(plan_id: int):
    """حذف پلن"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        await db.commit()

async def toggle_plan_status(plan_id: int):
    """تغییر وضعیت فعال/غیرفعال پلن"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE plans SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (plan_id,)
        )
        await db.commit()

_ALLOWED_PLAN_FIELDS = {"price", "duration", "traffic"}

async def update_plan_field(plan_id: int, field: str, value: int):
    """ویرایش یک فیلد از پلن"""
    if field not in _ALLOWED_PLAN_FIELDS:
        raise ValueError(f"فیلد مجاز نیست: {field}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE plans SET {field} = ? WHERE id = ?", (value, plan_id))
        await db.commit()

async def update_plan(plan_id: int, name: str, price: int, duration: int, traffic: int):
    """ویرایش پلن"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE plans SET name=?, price=?, duration=?, traffic=? WHERE id=?",
            (name, price, duration, traffic, plan_id)
        )
        await db.commit()

async def get_plan(plan_id: int):
    """گرفتن یک پلن با id"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
        return await cursor.fetchone()

async def get_plan_with_server(plan_id: int):
    """گرفتن اطلاعات پلن به همراه سرور مربوطه"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT plans.*, servers.panel_url, servers.panel_token, servers.service_ids
            FROM plans
            JOIN servers ON plans.server_id = servers.id
            WHERE plans.id = ?
        """, (plan_id,))
        return await cursor.fetchone()

# ─── توابع تنظیمات ─────────────────────────────

async def get_setting(key: str):
    """گرفتن یک تنظیم"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else None

async def set_setting(key: str, value: str):
    """ذخیره یا آپدیت یک تنظیم"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        await db.commit()

# ─── متن‌های ربات (کش حافظه) ─────────────────

_DEFAULT_TEXTS: dict[str, str] = {
    # ─── استارت ────────────────────────────────────────────────────────
    "start_welcome_default":      "سلام {name} 👋 خوش اومدی",
    "start_banned":               "⛔️ دسترسی شما به ربات محدود شده است.",
    # ─── تست رایگان ────────────────────────────────────────────────────
    "free_test_max_uses":         "❌ شما قبلاً از تست رایگان استفاده کرده‌اید.",
    "free_test_unavailable":      "در حال حاضر تست رایگان در دسترس نیست.",
    "free_test_server_unavailable": "این سرور در دسترس نیست.",
    "free_test_no_service_config": "سرویسی برای این سرور تنظیم نشده. با پشتیبانی تماس بگیرید.",
    "free_test_creating":         "⏳ در حال ساخت سرویس تست...",
    "free_test_error_no_service": "❌ خطا در ساخت سرویس. با پشتیبانی تماس بگیرید.",
    "free_test_error_api":        "❌ خطا در اتصال به پنل:\n{error}\n\nدوباره امتحان کنید.",
    "free_test_success":          "✅ <b>سرویس تست رایگان آماده‌ست!</b>\n\n🖥 سرور: {server}\n\n🔗 لینک اشتراک:\n<code>{url}</code>\n\nلینک را در اپلیکیشن VPN وارد کنید یا QR Code را اسکن کنید.",
    # ─── خرید VPN ──────────────────────────────────────────────────────
    "buy_no_servers":             "⚠️ در حال حاضر سرویسی برای فروش وجود ندارد.\nلطفاً بعداً مراجعه کنید.",
    "buy_select_server":          "🖥 لطفاً یک سرور انتخاب کنید:",
    "buy_no_plans":               "⚠️ این سرور در حال حاضر پلن فعالی ندارد.\nلطفاً بعداً مراجعه کنید.",
    "buy_select_plan":            "📦 یک پلن انتخاب کنید:",
    # ─── پرداخت ────────────────────────────────────────────────────────
    "payment_card_unavailable":   "در حال حاضر امکان پرداخت وجود ندارد. لطفاً بعداً مراجعه کنید.",
    "payment_not_photo":          "📸 لطفاً تصویر رسید را ارسال کنید.",
    "payment_submitted":          "✅ رسید شما دریافت شد.\n⏳ پس از بررسی توسط پشتیبانی، نتیجه به شما اعلام خواهد شد.",
    "payment_cancelled":          "❌ پرداخت لغو شد.",
    "wallet_menu":                "💎 کیف پول",
    "wallet_no_balance":          "موجودی کافی نیست.",
    "wallet_error_api":           "خطا در اتصال به پنل: {error}",
    "wallet_error_order":         "خطا در ثبت سفارش. مبلغ به حسابتان برگشت داده شد.",
    "wallet_no_transactions":     "هنوز تراکنشی ثبت نشده.",
    "wallet_purchase_success":    "✅ <b>خرید با کیف پول انجام شد!</b>\n\n🔗 لینک اشتراک:\n<code>{url}</code>\n\nلینک را در اپلیکیشن VPN وارد کنید یا QR Code را اسکن کنید.",
    "discount_free_success":      "✅ <b>سرویس با کد تخفیف ۱۰۰٪ فعال شد!</b>\n\n🔗 لینک اشتراک:\n<code>{url}</code>\n\nلینک را در اپلیکیشن VPN وارد کنید یا QR Code را اسکن کنید.",
    # ─── نتیجه سفارش (پیام از ادمین به کاربر) ─────────────────────────
    "order_approved":             "✅ <b>سفارش شما تایید شد!</b>\n\n🔗 لینک اشتراک:\n<code>{url}</code>\n\nلینک را در اپلیکیشن VPN وارد کنید یا QR Code را اسکن کنید.",
    "order_rejected":             "❌ متأسفانه سفارش شما تایید نشد.\nدر صورت نیاز با پشتیبانی تماس بگیرید.",
    "order_rejected_with_reason": "❌ متأسفانه سفارش شما تایید نشد.",
    # ─── شارژ حساب ─────────────────────────────────────────────────────
    "topup_prompt":               "💳 <b>شارژ حساب</b>\n\nمبلغ مورد نظر را به <b>تومان</b> وارد کنید:\nمثلاً: <code>50000</code>",
    "topup_invalid_amount":       "❌ مبلغ معتبر نیست.\nحداقل شارژ <b>۱۰,۰۰۰ تومان</b> است.",
    "topup_not_photo":            "لطفاً تصویر رسید پرداخت را ارسال کنید.",
    "topup_submitted":            "✅ درخواست شارژ شما ثبت شد.\nپس از تایید ادمین، موجودی به حسابتان اضافه می‌شود.",
    "topup_approved":             "✅ <b>شارژ حساب تایید شد!</b>\n\n💰 مبلغ <b>{amount}</b> تومان به کیف پول شما اضافه شد.",
    "topup_rejected":             "❌ متأسفانه درخواست شارژ حساب شما تایید نشد.\nدر صورت نیاز با پشتیبانی تماس بگیرید.",
    # ─── کد تخفیف ──────────────────────────────────────────────────────
    "discount_prompt":            "🎟 کد تخفیف خود را وارد کنید:",
    "discount_invalid":           "❌ این کد تخفیف معتبر نیست، منقضی شده یا قبلاً استفاده کرده‌اید.",
    "discount_plan_not_found":    "❌ پلن یافت نشد.",
    # ─── سرویس‌های من ───────────────────────────────────────────────────
    "services_empty":             "📋 <b>سرویس‌های من</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\nهنوز هیچ سرویسی نداری.",
    "services_header":            "📋 <b>سرویس‌های من</b>",
    "service_not_found":          "سرویس یافت نشد.",
    # ─── وضعیت سرویس ────────────────────────────────────────────────────
    "status_active":              "✅ فعال",
    "status_expired":             "❌ منقضی شده",
    "status_limited":             "❌ ترافیک تمام شده",
    "status_disabled":            "⚠️ غیرفعال",
    "status_unknown":             "❓ نامشخص",
    "service_no_live":            "⚠️ اطلاعات زنده در دسترس نیست",
    "service_traffic_unlimited":  "📊 ترافیک : نامحدود",
    "service_expire_unlimited":   "نامحدود",
    # ─── عملیات سرویس ───────────────────────────────────────────────────
    "renew_free_test_error":      "سرویس تست رایگان قابل تمدید نیست.",
    "renew_no_server":            "سرور این سرویس در دسترس نیست.",
    "renew_no_plans":             "این سرور در حال حاضر پلن فعالی ندارد.",
    "renew_prompt":               "🔄 <b>تمدید سرویس</b>\n\nیک پلن انتخاب کنید:",
    "delete_confirm":             "⚠️ مطمئنی می‌خوای سرویس <code>{name}</code> رو حذف کنی؟\n\nاین عمل قابل بازگشت نیست.",
    "delete_error":               "❌ خطا در حذف سرویس: {error}",
    "delete_done_empty":          "🗑 سرویس حذف شد.\n\n📋 <b>سرویس‌های من</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\nهنوز هیچ سرویسی نداری.",
    "delete_done_has_more":       "🗑 سرویس حذف شد.\n\n📋 <b>سرویس‌های من</b>",
    "sublink_unavailable":        "لینک در دسترس نیست.",
    "sublink_sent":               "🔗 لینک اشتراک:\n\n<code>{url}</code>",
    # ─── پشتیبانی ───────────────────────────────────────────────────────
    "support_menu":               "🎧 پشتیبانی\n\nبرای ارتباط با تیم پشتیبانی یک تیکت ارسال کنید.\nپاسخ پشتیبانی مستقیماً اینجا نمایش داده می‌شود.",
    "support_unavailable":        "پشتیبانی در حال حاضر در دسترس نیست.",
    "support_has_open_ticket":    "شما یک تیکت باز (#{id}) دارید.\nاز بخش «تیکت‌های من» ادامه دهید.",
    "support_new_ticket_prompt":  "📨 تیکت جدید\n\nپیام خود را بنویسید\n(متن، عکس، فایل — همه قبوله)",
    "support_error_creating":     "❌ خطا در ایجاد تیکت. لطفاً دوباره امتحان کنید.\n{error}",
    "support_ticket_closed":      "❌ تیکت شما بسته شده است.",
    "support_error_send":         "❌ خطا در ارسال پیام. دوباره امتحان کنید.",
    "support_closed_by_support":  "❌ تیکت #{id} توسط پشتیبانی بسته شد.\n\nدر صورت نیاز می‌توانید تیکت جدید باز کنید.",
    "support_close_self":         "✅ تیکت #{id} بسته شد.",
    "support_tickets_empty":      "📋 تیکت‌های من\n\nهیچ تیکتی ندارید.",
    "support_tickets_list":       "📋 تیکت‌های من\n\n🟢 باز  |  🔴 بسته",
    "support_view_open":          "🎫 تیکت #{id}\nوضعیت: 🟢 باز\n\nپیام بعدی شما به پشتیبانی ارسال می‌شود.",
    "support_view_closed":        "🎫 تیکت #{id}\nوضعیت: 🔴 بسته",
    # ─── آموزش‌ها ────────────────────────────────────────────────────────
    "tutorial_empty":             "📚 آموزش و راهنما\n\nهنوز آموزشی اضافه نشده.",
    "tutorial_has_list":          "📚 آموزش و راهنما\n\nیکی از موضوعات زیر را انتخاب کنید:",
    "tutorial_unavailable":       "این آموزش در دسترس نیست.",
    # ─── سوالات متداول ──────────────────────────────────────────────────
    "faq_empty":                  "❓ سوالات متداول\n\nهنوز سوالی اضافه نشده.",
    "faq_has_list":               "❓ سوالات متداول\n\nسوال مورد نظر را انتخاب کنید:",
    "faq_unavailable":            "این سوال در دسترس نیست.",
    # ─── دعوت دوستان ────────────────────────────────────────────────────
    "referral_error":             "خطا در دریافت اطلاعات.",
    "referral_disabled":          "سیستم دعوت دوستان در حال حاضر غیرفعال است.",
    "referral_commission_notify": "💰 <b>پورسانت دریافت کردی!</b>\nدوستت خرید کرد و <b>{amount}</b> تومان به کیف پولت اضافه شد.",
    # ─── متن‌های عمومی کاربر (قبلاً hardcode بودند) ──────────────────────
    "coming_soon":             "🔜 به زودی...",
    "free_test_select_server": "🎁 <b>تست رایگان</b>\n\nسرور مورد نظر را انتخاب کنید:",
    "free_test_confirm_text":  "🎁 <b>تست رایگان</b>\n────────────────────────\n🖥 سرور: <b>{server}</b>\n⏱ مدت: <b>{duration}</b>\n📊 حجم: <b>{traffic}</b>\n────────────────────────\n\nبا زدن دکمه زیر سرویس تست برات ساخته می‌شه:",
    "profile_text":            "👤 {name}\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n🆔 آیدی تلگرام : <code>{user_id}</code>\n{username_line}\n📅 تاریخ عضویت : {join_date}\n💰 موجودی : <b>{balance} تومان</b>\n🎫 کد معرف : <code>{referral_code}</code>\n━━━━━━━━━━━━━━━━━━━━━━━━",
    "payment_card_info":       "💳 <b>اطلاعات پرداخت</b>\n\nمبلغ: <b>{amount} تومان</b>\n\nشماره کارت:\n<code>{card_number}</code>\nبه نام: <b>{card_owner}</b>\n\nبعد از واریز، تصویر رسید را ارسال کنید.",
    "wallet_balance_text":     "👤 {name} عزیز\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n💰 موجودی\n<b>{balance} تومان</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n🛒 سرویس‌های خریداری‌شده    <b>{services}</b> عدد\n📑 فاکتورهای پرداخت‌شده     <b>{invoices}</b> عدد",
    # ─── پنل ادمین (admin.py) ─────────────────────────────────────────────
    "admin_panel_title":              "⚙️ پنل ادمین",
    "admin_general_title":            "⚙️ تنظیمات عمومی",
    "admin_banner_and_text_title":    "🎨 ظاهر ربات",
    "admin_text_settings_title":      "✏️ تنظیمات متن",
    "admin_banner_status_active":     "✅ بنر فعال است.",
    "admin_banner_status_none":       "❌ بنر تنظیم نشده.",
    "admin_banner_upload_prompt":     "🖼 عکس بنر را ارسال کنید:",
    "admin_banner_saved":             "✅ بنر ذخیره شد.",
    "admin_caption_edit_prompt":      "✏️ متن فعلی بنر:\n<blockquote>{current}</blockquote>\n\nمتن جدید را ارسال کنید.\nاز {{name}} برای نام کاربر استفاده کنید.\n<i>ایموجی پرمیوم هم پشتیبانی می‌شه.</i>",
    "admin_caption_saved":            "✅ متن بنر{note} ذخیره شد.",
    "admin_build_text_prompt":        "🛠 پیام خود را همراه با استیکر پرمیوم ارسال کنید.\nربات اموجی‌ها را با تگ HTML جایگزین می‌کند.",
    "admin_cancel_op":                "❌ عملیات لغو شد.",
    "admin_free_test_title":          "🎁 تنظیمات تست رایگان",
    "admin_free_test_global_text":    "⚙️ تنظیمات پیش‌فرض تست رایگان\n\n⏱ مدت: <b>{duration}</b>\n📊 حجم: <b>{traffic} گیگابایت</b>\n🔢 تعداد مجاز: <b>{max_uses}</b>",
    "admin_free_test_ask_duration":   "⏱ مدت پیش‌فرض تست رایگان را به <b>ساعت</b> وارد کنید:\n<i>برای بی‌نهایت (بدون انقضا) عدد 0 را وارد کنید</i>",
    "admin_free_test_ask_traffic":    "📊 حجم پیش‌فرض تست رایگان را به <b>گیگابایت</b> وارد کنید:",
    "admin_free_test_ask_max_uses":   "🔢 تعداد دفعات مجاز دریافت تست رایگان برای هر کاربر:\n\nمقدار فعلی: <b>{current}</b>\n\nعدد جدید را وارد کنید:\n<i>برای بی‌نهایت عدد 0 را وارد کنید</i>",
    "admin_free_test_server_text":    "🎁 تنظیمات تست رایگان — <b>{name}</b>\n────────────────────────────\nوضعیت: {status}\n⏱ مدت: <b>{duration}</b>\n📊 حجم: <b>{traffic}</b>",
    "admin_free_test_ask_server_dur": "⏱ مدت تست رایگان این سرور را به <b>ساعت</b> وارد کنید:\n<i>برای بی‌نهایت (بدون انقضا) عدد 0 را وارد کنید</i>",
    "admin_free_test_ask_server_trf": "📊 حجم تست رایگان این سرور را به <b>گیگابایت</b> وارد کنید:",
    "admin_invalid_number":           "❌ عدد وارد کنید. مثال: 24 یا 0.5 یا 0 برای بی‌نهایت",
    "admin_invalid_pos_number":       "❌ عدد مثبت وارد کنید. مثال: 1 یا 0.5",
    "admin_invalid_int":              "❌ عدد صحیح وارد کنید. مثال: 1 یا 2 یا 0 برای بی‌نهایت",
    # ─── مدیریت سرورها (servers.py) ──────────────────────────────────────
    "admin_servers_title":            "🖥 مدیریت سرورها",
    "admin_servers_list_title":       "🖥 <b>لیست سرورها</b>",
    "admin_servers_empty":            "❌ هیچ سروری ثبت نشده!",
    "admin_server_ask_name":          "🖥 اسم سرور رو بفرست:\n\nمثلاً: سرور آلمان 🇩🇪",
    "admin_server_ask_url":           "🔗 آدرس پنل رو بفرست:\n\nمثلاً: https://rebeccapanel.com:8880",
    "admin_server_ask_token":         "🔑 توکن API پنل رو بفرست:",
    "admin_server_url_invalid":       "❌ <b>آدرس معتبر نیست!</b>\n\nفرمت: <code>https://domain.com:PORT</code>\n\n⚠️ آدرس نباید به <code>/</code> ختم بشه.",
    "admin_server_panel_error":       "❌ خطا در اتصال به پنل:\n<code>{error}</code>",
    "admin_server_no_services":       "⚠️ هیچ سرویسی در پنل تعریف نشده!",
    "admin_server_select_services":   "🔧 سرویس‌هایی که می‌خوای این سرور داشته باشه رو انتخاب کن:",
    "admin_server_edit_services":     "✏️ سرویس‌های این سرور رو ویرایش کن:",
    "admin_server_min_service":       "حداقل یک سرویس انتخاب کن!",
    "admin_server_services_updated":  "✅ سرویس‌های سرور <b>{name}</b> بروزرسانی شد.",
    "admin_server_added":             "✅ سرور با موفقیت اضافه شد!\n🔧 {count} سرویس انتخاب شد.",
    "admin_server_settings_text":     "⚙️ <b>تنظیمات سرور</b>\n────────────────────────\n🖥 <b>{name}</b>\n🔗 {url}\n📊 وضعیت: {status}\n🔧 سرویس‌ها: {services} سرویس",
    "admin_server_url_updated":       "✅ آدرس سرور بروزرسانی شد.\n\n{settings}",
    "admin_server_token_updated":     "✅ توکن سرور بروزرسانی شد.\n\n{settings}",
    "admin_server_ask_edit_url":      "🔗 آدرس جدید پنل رو بفرست:\n\nمثلاً: https://rebeccapanel.com:8880",
    "admin_server_ask_edit_token":    "🔑 توکن جدید API پنل رو بفرست:",
    "admin_server_delete_confirm":    "⚠️ مطمئنی می‌خوای سرور <b>{name}</b> رو حذف کنی؟\nاین عمل قابل بازگشت نیست.",
    "admin_server_deleted_list":      "🗑 سرور <b>{name}</b> حذف شد.\n\n🖥 <b>لیست سرورها</b>",
    "admin_server_deleted_empty":     "🗑 سرور <b>{name}</b> حذف شد.\n\n❌ هیچ سروری باقی نمونده.",
    # ─── مدیریت پلن‌ها (plans.py) ─────────────────────────────────────────
    "admin_plans_title":              "📦 مدیریت پلن‌ها",
    "admin_plans_no_servers":         "❌ هیچ سروری ثبت نشده!\nاول از بخش مدیریت سرورها یه سرور اضافه کن.",
    "admin_plans_select_server":      "🖥 سرور مورد نظر رو انتخاب کن:",
    "admin_plans_select_server_view": "🖥 برای دیدن پلن‌ها، سرور رو انتخاب کن:",
    "admin_plan_ask_name":            "📝 اسم پلن رو بفرست:",
    "admin_plan_ask_price":           "💰 قیمت رو بفرست (تومان):",
    "admin_plan_ask_duration":        "📅 مدت رو بفرست (روز):\n<i>برای بی‌نهایت عدد 0 وارد کن</i>",
    "admin_plan_ask_traffic":         "📊 حجم رو بفرست (گیگابایت):\n<i>برای بی‌نهایت عدد 0 وارد کن</i>",
    "admin_plan_added":               "✅ پلن با موفقیت اضافه شد!",
    "admin_plans_empty_for_server":   "❌ هیچ پلنی برای این سرور ثبت نشده!",
    "admin_plans_list_text":          "📦 <b>لیست پلن‌ها</b>\n\n💡 برای تنظیمات پلن روی اسمش کلیک کن.",
    "admin_plan_settings_text":       "⚙️ <b>تنظیمات پلن</b>\n────────────────────────\n📦 <b>{name}</b>\n📊 حجم: {traffic}\n📅 مدت: {duration}\n💰 قیمت: {price} تومان\n📌 وضعیت: {status}",
    "admin_plan_ask_edit_price":      "💰 قیمت فعلی پلن <b>{name}</b>: {price} تومان\n\nقیمت جدید را به <b>تومان</b> وارد کنید:",
    "admin_plan_price_invalid":       "❌ قیمت معتبر نیست. حداقل ۱,۰۰۰ تومان وارد کنید.",
    "admin_plan_price_ask_int":       "❌ قیمت باید عدد باشه! دوباره بفرست:",
    "admin_plan_updated_list":        "✅ {field} بروزرسانی شد.\n\n📦 <b>لیست پلن‌ها</b>\n\n💡 برای ویرایش روز، حجم یا قیمت روی مقدار مربوطه کلیک کنید.",
    "admin_plan_ask_edit_duration":   "📅 مدت فعلی پلن <b>{name}</b>: {duration}\n\nمدت جدید را به <b>روز</b> وارد کنید:\n<i>برای بی‌نهایت عدد 0 وارد کنید</i>",
    "admin_plan_ask_edit_traffic":    "📊 حجم فعلی پلن <b>{name}</b>: {traffic}\n\nحجم جدید را به <b>گیگابایت</b> وارد کنید:\n<i>برای بی‌نهایت عدد 0 وارد کنید</i>",
    "admin_plan_duration_invalid":    "❌ عدد صحیح وارد کن. مثال: 30 یا 0 برای بی‌نهایت",
    "admin_plan_traffic_invalid":     "❌ عدد صحیح وارد کن. مثال: 50 یا 0 برای بی‌نهایت",
    "admin_plan_delete_confirm":      "⚠️ مطمئنی می‌خوای پلن <b>{name}</b> رو حذف کنی؟\nاین عمل قابل بازگشت نیست.",
    "admin_plan_deleted_list":        "🗑 پلن <b>{name}</b> حذف شد.\n\n📦 <b>لیست پلن‌ها</b>",
    "admin_plan_deleted_empty":       "🗑 پلن <b>{name}</b> حذف شد.\n\n❌ هیچ پلنی باقی نمونده.",
    # ─── مدیریت مالی (finance.py) ─────────────────────────────────────────
    "admin_finance_title":            "💰 <b>مدیریت مالی</b>\n\nروش‌های پرداخت فعال را مدیریت کنید:",
    "admin_card_settings_text":       "⚙️ <b>تنظیمات کارت به کارت</b>\n────────────────────────\n💳 شماره کارت: <code>{number}</code>\n👤 نام صاحب کارت: {owner}",
    "admin_card_ask_number":          "💳 شماره کارت جدید را وارد کنید:\n\nمثال: <code>6219 8610 3452 9876</code>",
    "admin_card_invalid":             "❌ شماره کارت باید ۱۶ رقم باشد.\nدوباره وارد کنید:",
    "admin_card_number_saved":        "✅ شماره کارت ذخیره شد:\n<code>{number}</code>",
    "admin_card_ask_owner":           "👤 نام صاحب کارت را وارد کنید:",
    "admin_card_owner_saved":         "✅ نام صاحب کارت ذخیره شد: {name}",
    # ─── پیام همگانی (broadcast.py) ───────────────────────────────────────
    "admin_broadcast_title":          "📢 <b>پیام همگانی</b>\n\nمخاطبان را انتخاب کنید:",
    "admin_broadcast_ask_content":    "📢 <b>ارسال به {target}</b>\n\nپیام خود را ارسال کنید:\n<i>(متن، عکس یا ویدیو با کپشن)</i>",
    "admin_broadcast_invalid":        "❌ فقط متن، عکس یا ویدیو ارسال کنید.",
    "admin_broadcast_confirm_text":   "👆 پیش‌نمایش پیام بالا\n\nمخاطب: <b>{target}</b> — {count} نفر\n\nآماده ارسال هستی؟",
    "admin_broadcast_starting":       "📢 شروع ارسال...\n\n✅ موفق: 0\n❌ ناموفق: 0\n📊 0/...",
    "admin_broadcast_progress":       "📢 در حال ارسال...\n\n✅ موفق: {sent}\n❌ ناموفق: {failed}\n📊 {done}/{total}",
    "admin_broadcast_done":           "✅ پیام همگانی ارسال شد!\n\n📨 موفق: {sent}\n❌ ناموفق (بلاک یا ارور): {failed}\n👥 کل: {total}",
    # ─── کد تخفیف (discount.py — ادمین) ─────────────────────────────────
    "admin_discount_list_title":      "🎟 <b>کدهای تخفیف</b>",
    "admin_discount_ask_code":        "🎟 <b>افزودن کد تخفیف</b>\n\nکد تخفیف را وارد کنید:\n<i>(فقط حروف انگلیسی و اعداد — مثال: SUMMER30)</i>",
    "admin_discount_code_invalid":    "❌ کد باید ۲ تا ۲۰ کاراکتر انگلیسی یا عدد باشد.",
    "admin_discount_code_exists":     "❌ این کد قبلاً ثبت شده.",
    "admin_discount_ask_value":       "مقدار تخفیف را وارد کنید ({hint}):",
    "admin_discount_ask_max_uses":    "حداکثر تعداد استفاده را وارد کنید:\n<i>(۰ = نامحدود)</i>",
    "admin_discount_ask_expiry":      "تاریخ انقضا را وارد کنید:\n<i>(فرمت: YYYY-MM-DD  مثال: 2025-12-31)</i>",
    "admin_discount_expiry_invalid":  "❌ فرمت اشتباه. مثال: 2025-12-31",
    "admin_discount_value_invalid":   "❌ عدد مثبت وارد کنید.",
    "admin_discount_percent_invalid": "❌ درصد باید بین ۱ تا ۱۰۰ باشد.",
    "admin_discount_int_invalid":     "❌ عدد صحیح وارد کنید.",
    "admin_discount_created":         "✅ <b>کد تخفیف ساخته شد!</b>\n\n🎟 کد: <code>{code}</code>\n🏷 تخفیف: {discount}\n📊 محدودیت: {max_uses}\n📅 انقضا: {expiry}",
    "admin_discount_deleted":         "✅ کد حذف شد.",
    # ─── پشتیبانی (support.py — ادمین) ───────────────────────────────────
    "admin_support_settings_text":    "🎧 <b>تنظیمات پشتیبانی</b>\n\n🆔 آیدی گروه: <code>{group_id}</code>",
    "admin_support_ask_group_id":     "🆔 آیدی گروه پشتیبانی را وارد کنید:\n\nربات <b>@userinfobot</b> را به گروه اضافه کنید تا آیدی رو بهتون بده.\n<i>مثال: <code>-1001234567890</code></i>",
    "admin_support_group_id_invalid": "❌ آیدی معتبر نیست. باید عدد باشد.\nمثال: <code>-1001234567890</code>",
    "admin_support_group_id_saved":   "✅ آیدی گروه ذخیره شد: <code>{group_id}</code>",
    "admin_support_ask_ticket_msg":   "✏️ <b>ویرایش متن تأییدیه تیکت</b>\n\nمتن فعلی:\n<blockquote>{current}</blockquote>\n\nمتن جدید را ارسال کنید.\n<i>اگه ایموجی پرمیوم داری همینجا بفرست — خودکار ذخیره می‌شه.</i>",
    "admin_support_ticket_msg_saved": "✅ متن{note} ذخیره شد.",
    # ─── آموزش‌ها (tutorial.py — ادمین) ──────────────────────────────────
    "admin_tutorials_title":          "📚 <b>مدیریت آموزش‌ها</b>",
    "admin_tutorial_list_title":      "📖 <b>آموزش‌ها</b>\n\n{count} آموزش ثبت شده",
    "admin_faqs_list_title":          "❓ <b>سوالات متداول</b>\n\n{count} سوال ثبت شده",
    "admin_tutorial_ask_title":       "📝 عنوان آموزش را وارد کنید:\n<i>(این متن روی دکمه نمایش داده می‌شه)</i>",
    "admin_tutorial_ask_content":     "📎 محتوای آموزش را ارسال کنید:\n<i>متن، عکس یا ویدیو — ربات نوع را تشخیص می‌دهد.</i>",
    "admin_tutorial_content_invalid": "❌ نوع پیام پشتیبانی نمی‌شود. متن، عکس یا ویدیو ارسال کنید.",
    "admin_tutorial_added":           "✅ آموزش «{title}» اضافه شد.",
    "admin_tutorial_title_saved":     "✅ عنوان ذخیره شد.",
    "admin_tutorial_content_saved":   "✅ محتوا ذخیره شد.",
    "admin_tutorial_ask_edit_title":  "✏️ عنوان فعلی: <b>{title}</b>\n\nعنوان جدید:",
    "admin_tutorial_ask_edit_content":"📎 محتوای جدید را ارسال کنید:\n<i>متن، عکس یا ویدیو</i>",
    "admin_tutorial_delete_confirm":  "🗑 حذف «{title}»؟",
    "admin_tutorial_deleted":         "🗑 «{title}» حذف شد.",
    "admin_faq_ask_question":         "❓ سوال را وارد کنید:",
    "admin_faq_ask_answer":           "💬 جواب را وارد کنید:",
    "admin_faq_added":                "✅ سوال اضافه شد.",
    "admin_faq_question_saved":       "✅ سوال ذخیره شد.",
    "admin_faq_answer_saved":         "✅ جواب ذخیره شد.",
    "admin_faq_ask_edit_question":    "✏️ سوال فعلی: <b>{question}</b>\n\nسوال جدید:",
    "admin_faq_ask_edit_answer":      "✏️ جواب فعلی:\n{answer}\n\nجواب جدید:",
    "admin_faq_delete_confirm":       "🗑 حذف «{question}»؟",
    "admin_faq_deleted":              "🗑 «{question}» حذف شد.",
}

_texts_cache: dict[str, str] = {}


def get_text(key: str, **fmt) -> str:
    """گرفتن متن از کش — سریع و بدون await"""
    text = _texts_cache.get(key) or _DEFAULT_TEXTS.get(key, "")
    if fmt:
        try:
            return text.format_map(fmt)
        except (KeyError, ValueError):
            return text
    return text


async def set_text(key: str, value: str) -> None:
    """ویرایش یک متن — در DB ذخیره و کش آپدیت می‌شه"""
    _texts_cache[key] = value
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bot_texts (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value)
        )
        await db.commit()


async def get_all_texts() -> list:
    """همه متن‌ها با مقدار فعلیشان (برای پنل ادمین)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT key, value FROM bot_texts ORDER BY key")
        return await cur.fetchall()


async def init_texts_cache() -> None:
    """جدول bot_texts رو می‌سازه، مقادیر پیش‌فرض رو seed می‌کنه، کش رو بارگذاری می‌کنه"""
    global _texts_cache
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS bot_texts (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        for key, text in _DEFAULT_TEXTS.items():
            await db.execute(
                "INSERT OR IGNORE INTO bot_texts (key, value) VALUES (?, ?)",
                (key, text)
            )
        await db.commit()
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT key, value FROM bot_texts")
        rows = await cur.fetchall()
        _texts_cache = {row["key"]: row["value"] for row in rows}


async def reload_texts_cache() -> None:
    """کش متن‌ها رو از دیتابیس بارگذاری مجدد می‌کنه — بدون seed"""
    global _texts_cache
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT key, value FROM bot_texts")
        rows = await cur.fetchall()
        _texts_cache = {row["key"]: row["value"] for row in rows}


# ─── کش کیبوردها (در حافظه) ─────────────────────

_keyboards_cache: dict[str, list[dict]] = {}


def get_keyboard_rows(name: str) -> list[dict]:
    """برگرداندن دکمه‌های یک کیبورد از کش — sync، بدون await"""
    return _keyboards_cache.get(name, [])


async def init_keyboards_cache() -> None:
    """همه کیبوردهای فعال (غیر ادمین) رو از DB می‌خونه و در کش نگه می‌داره"""
    global _keyboards_cache
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT * FROM keyboard_buttons
               WHERE is_active = 1 AND (admin_only IS NULL OR admin_only = 0)
               ORDER BY keyboard_name, row_index, col_index"""
        )
        rows = await cur.fetchall()
        cache: dict[str, list[dict]] = {}
        for row in rows:
            cache.setdefault(row["keyboard_name"], []).append(dict(row))
        _keyboards_cache = cache


async def reload_keyboards_cache() -> None:
    """بارگذاری مجدد کش کیبوردها — برای loop تازه‌سازی بات"""
    await init_keyboards_cache()


# ─── توابع سفارش‌ها ────────────────────────────

async def create_order(user_id: int, username: str, plan_id: int, receipt_file_id: str) -> int:
    """ساخت سفارش جدید و برگرداندن id آن"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO orders (user_id, username, plan_id, receipt_file_id) VALUES (?, ?, ?, ?)",
            (user_id, username, plan_id, receipt_file_id)
        )
        await db.commit()
        return cursor.lastrowid

async def get_order(order_id: int):
    """گرفتن یک سفارش با id"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        return await cursor.fetchone()

async def update_order_vpn_info(order_id: int, vpn_username: str, subscription_url: str):
    """ذخیره اطلاعات VPN بعد از تایید سفارش"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET vpn_username = ?, subscription_url = ? WHERE id = ?",
            (vpn_username, subscription_url, order_id)
        )
        await db.commit()

async def create_free_test_order(user_id: int, username: str, server_id: int) -> int:
    """ساخت سفارش تست رایگان"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO orders (user_id, username, plan_id, receipt_file_id, order_type, free_test_server_id) "
            "VALUES (?, ?, 0, 'free_test', 'free_test', ?)",
            (user_id, username, server_id)
        )
        await db.commit()
        return cursor.lastrowid

async def get_free_test_servers():
    """سرورهای دارای تست رایگان فعال"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM servers WHERE is_active = 1 AND free_test_enabled = 1"
        )
        return await cursor.fetchall()

_SERVICE_SELECT = """
    SELECT o.*,
        COALESCE(p.name, '🎁 تست رایگان') as plan_name,
        COALESCE(s1.name, s2.name)         as server_name,
        COALESCE(s1.panel_url, s2.panel_url)     as panel_url,
        COALESCE(s1.panel_token, s2.panel_token) as panel_token
    FROM orders o
    LEFT JOIN plans   p  ON o.plan_id = p.id
    LEFT JOIN servers s1 ON p.server_id = s1.id
    LEFT JOIN servers s2 ON o.free_test_server_id = s2.id
"""

async def get_user_services(user_id: int):
    """لیست سرویس‌های فعال یک کاربر"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            _SERVICE_SELECT +
            "WHERE o.user_id = ? AND o.status = 'approved' ORDER BY o.created_at DESC",
            (user_id,)
        )
        return await cursor.fetchall()

async def get_user_service(order_id: int, user_id: int):
    """گرفتن یک سرویس با تایید مالکیت"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            _SERVICE_SELECT +
            "WHERE o.id = ? AND o.user_id = ? AND o.status = 'approved'",
            (order_id, user_id)
        )
        return await cursor.fetchone()

async def update_order_status(order_id: int, status: str, rejection_reason: str = None):
    """آپدیت وضعیت سفارش"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = ?, rejection_reason = ? WHERE id = ?",
            (status, rejection_reason, order_id)
        )
        await db.commit()

# ─── توابع کاربران و کیف پول ───────────────────

async def get_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone()

async def get_or_create_user(user_id: int, first_name: str, username: str = None):
    """ساخت یا بروزرسانی رکورد کاربر"""
    import random, string
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        existing = await cursor.fetchone()
        if existing:
            update_code = ""
            params = [first_name, username]
            if not existing["referral_code"]:
                while True:
                    code = "BP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
                    cur = await db.execute("SELECT 1 FROM users WHERE referral_code = ?", (code,))
                    if not await cur.fetchone():
                        break
                update_code = ", referral_code = ?"
                params.append(code)
            params.append(user_id)
            await db.execute(
                f"UPDATE users SET first_name = ?, username = ?{update_code} WHERE user_id = ?",
                params
            )
        else:
            while True:
                code = "BP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
                cur = await db.execute("SELECT 1 FROM users WHERE referral_code = ?", (code,))
                if not await cur.fetchone():
                    break
            await db.execute(
                "INSERT INTO users (user_id, first_name, username, referral_code) VALUES (?, ?, ?, ?)",
                (user_id, first_name, username, code)
            )
        await db.commit()
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()

async def get_user_wallet_stats(user_id: int) -> dict:
    """آمار کیف پول: موجودی، تعداد سرویس‌ها، تعداد فاکتورها"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        user = await cursor.fetchone()
        balance = user["balance"] if user else 0

        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM orders WHERE user_id = ? AND status = 'approved'",
            (user_id,)
        )
        services = (await cursor.fetchone())["cnt"]

        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM orders WHERE user_id = ? AND status != 'rejected'",
            (user_id,)
        )
        invoices = (await cursor.fetchone())["cnt"]

        return {"balance": balance, "services": services, "invoices": invoices}

async def get_transactions(user_id: int, limit: int = 20):
    """گرفتن تاریخچه تراکنش‌های کاربر"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return await cursor.fetchall()

async def add_transaction(user_id: int, amount: int, type: str, description: str = None):
    """ثبت تراکنش جدید"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
            (user_id, amount, type, description)
        )
        await db.commit()

async def add_balance(user_id: int, amount: int):
    """اضافه کردن موجودی به کیف پول کاربر"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()

async def add_balance_and_transaction(user_id: int, amount: int, type: str, description: str = None):
    """تغییر موجودی + ثبت تراکنش در یک transaction اتمیک"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
            (user_id, amount, type, description)
        )
        await db.commit()

async def deduct_balance_if_sufficient(user_id: int, amount: int) -> bool:
    """کسر موجودی فقط اگه کافی باشه — اتمیک، بدون race condition"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?",
            (amount, user_id, amount)
        )
        await db.commit()
        return cursor.rowcount > 0

async def create_top_up_request(user_id: int, username: str, amount: int, receipt_file_id: str) -> int:
    """ثبت درخواست شارژ حساب"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO top_up_requests (user_id, username, amount, receipt_file_id) VALUES (?, ?, ?, ?)",
            (user_id, username, amount, receipt_file_id)
        )
        await db.commit()
        return cursor.lastrowid

async def get_top_up_request(request_id: int):
    """گرفتن یک درخواست شارژ با id"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM top_up_requests WHERE id = ?", (request_id,))
        return await cursor.fetchone()

async def update_top_up_status(request_id: int, status: str):
    """آپدیت وضعیت درخواست شارژ"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE top_up_requests SET status = ? WHERE id = ?",
            (status, request_id)
        )
        await db.commit()

async def approve_top_up_atomic(request_id: int) -> bool:
    """تایید اتمیک — فقط اگه هنوز pending باشه موفق می‌شه"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE top_up_requests SET status = 'approved' WHERE id = ? AND status = 'pending'",
            (request_id,)
        )
        await db.commit()
        return cursor.rowcount > 0

# ─── توابع آموزش ─────────────────────────────

async def get_tutorials(active_only: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = "SELECT * FROM tutorials"
        if active_only:
            q += " WHERE is_active = 1"
        q += " ORDER BY order_index, id"
        cursor = await db.execute(q)
        return await cursor.fetchall()

async def get_tutorial(tutorial_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tutorials WHERE id = ?", (tutorial_id,))
        return await cursor.fetchone()

async def create_tutorial(title: str, content_type: str, file_id: str | None, caption: str | None, caption_entities: str | None = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO tutorials (title, content_type, file_id, caption, caption_entities, order_index) "
            "SELECT ?, ?, ?, ?, ?, COALESCE(MAX(order_index) + 1, 0) FROM tutorials",
            (title, content_type, file_id, caption, caption_entities)
        )
        await db.commit()
        return cursor.lastrowid

async def update_tutorial(tutorial_id: int, title: str, content_type: str, file_id: str | None, caption: str | None, caption_entities: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tutorials SET title=?, content_type=?, file_id=?, caption=?, caption_entities=? WHERE id=?",
            (title, content_type, file_id, caption, caption_entities, tutorial_id)
        )
        await db.commit()

async def toggle_tutorial(tutorial_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE tutorials SET is_active = 1 - is_active WHERE id = ?", (tutorial_id,))
        await db.commit()

async def delete_tutorial(tutorial_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tutorials WHERE id = ?", (tutorial_id,))
        await db.commit()

async def move_tutorial(tutorial_id: int, direction: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT order_index FROM tutorials WHERE id = ?", (tutorial_id,))
        row = await cur.fetchone()
        if not row:
            return
        idx = row["order_index"]
        if direction == "up":
            swap = await db.execute(
                "SELECT id, order_index FROM tutorials WHERE order_index < ? ORDER BY order_index DESC LIMIT 1", (idx,))
        else:
            swap = await db.execute(
                "SELECT id, order_index FROM tutorials WHERE order_index > ? ORDER BY order_index ASC LIMIT 1", (idx,))
        other = await swap.fetchone()
        if other:
            await db.execute("UPDATE tutorials SET order_index=? WHERE id=?", (other["order_index"], tutorial_id))
            await db.execute("UPDATE tutorials SET order_index=? WHERE id=?", (idx, other["id"]))
            await db.commit()

# ─── توابع FAQ ───────────────────────────────

async def get_faqs(active_only: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        q = "SELECT * FROM faqs"
        if active_only:
            q += " WHERE is_active = 1"
        q += " ORDER BY order_index, id"
        cursor = await db.execute(q)
        return await cursor.fetchall()

async def get_faq(faq_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM faqs WHERE id = ?", (faq_id,))
        return await cursor.fetchone()

async def create_faq(question: str, answer: str, answer_entities: str | None = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO faqs (question, answer, answer_entities, order_index) "
            "SELECT ?, ?, ?, COALESCE(MAX(order_index) + 1, 0) FROM faqs",
            (question, answer, answer_entities)
        )
        await db.commit()
        return cursor.lastrowid

async def update_faq(faq_id: int, question: str, answer: str, answer_entities: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE faqs SET question=?, answer=?, answer_entities=? WHERE id=?", (question, answer, answer_entities, faq_id))
        await db.commit()

async def toggle_faq(faq_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE faqs SET is_active = 1 - is_active WHERE id = ?", (faq_id,))
        await db.commit()

async def delete_faq(faq_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
        await db.commit()

# ─── توابع دعوت دوستان ───────────────────────

async def get_user_by_referral_code(code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE referral_code = ?", (code,))
        return await cur.fetchone()

async def set_referral_by(user_id: int, referral_code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET referral_by = ? WHERE user_id = ? AND referral_by IS NULL",
            (referral_code, user_id)
        )
        await db.commit()

async def create_referral(referrer_id: int, referred_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                (referrer_id, referred_id)
            )
            await db.commit()
        except Exception:
            pass

async def get_referral_by_referred(referred_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM referrals WHERE referred_id = ?", (referred_id,)
        )
        return await cur.fetchone()

async def mark_first_purchase_rewarded(referred_id: int, commission: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE referrals SET first_purchase_rewarded = 1, total_commission = total_commission + ? WHERE referred_id = ?",
            (commission, referred_id)
        )
        await db.commit()

async def add_referral_commission(referred_id: int, commission: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE referrals SET total_commission = total_commission + ? WHERE referred_id = ?",
            (commission, referred_id)
        )
        await db.commit()

async def get_referral_stats(referrer_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT COUNT(*) as count, COALESCE(SUM(total_commission), 0) as total "
            "FROM referrals WHERE referrer_id = ?",
            (referrer_id,)
        )
        row = await cur.fetchone()
        return {"count": row["count"], "total": row["total"]}

# ─── توابع مدیریت کاربران (ادمین) ─────────────

_USERS_PER_PAGE = 8

async def get_users_count(filter_type: str = "newest") -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        if filter_type == "banned":
            cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
        else:
            cur = await db.execute("SELECT COUNT(*) FROM users")
        row = await cur.fetchone()
        return row[0]

async def get_users_paginated(page: int, filter_type: str = "newest"):
    offset = page * _USERS_PER_PAGE
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if filter_type == "topbuyers":
            cur = await db.execute(
                """SELECT u.*, COUNT(o.id) as order_count
                   FROM users u
                   LEFT JOIN orders o ON u.user_id = o.user_id AND o.status = 'approved'
                   GROUP BY u.user_id
                   ORDER BY order_count DESC LIMIT ? OFFSET ?""",
                (_USERS_PER_PAGE, offset)
            )
        elif filter_type == "banned":
            cur = await db.execute(
                "SELECT * FROM users WHERE is_banned = 1 ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (_USERS_PER_PAGE, offset)
            )
        else:
            cur = await db.execute(
                "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (_USERS_PER_PAGE, offset)
            )
        return await cur.fetchall()

async def search_users(query: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if query.lstrip('-').isdigit():
            cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (int(query),))
            rows = await cur.fetchall()
            if rows:
                return rows
        username = query.lstrip('@')
        cur = await db.execute(
            "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ? LIMIT 20",
            (f"%{username}%", f"%{query}%")
        )
        return await cur.fetchall()

async def ban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        await db.commit()

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        await db.commit()

async def admin_adjust_balance(user_id: int, delta: int, description: str):
    async with aiosqlite.connect(DB_PATH) as db:
        if delta >= 0:
            await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id))
        else:
            await db.execute("UPDATE users SET balance = MAX(0, balance + ?) WHERE user_id = ?", (delta, user_id))
        tx_type = "admin_credit" if delta >= 0 else "admin_deduct"
        await db.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
            (user_id, abs(delta), tx_type, description)
        )
        await db.commit()

async def get_user_ticket_counts(user_id: int) -> tuple:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT status, COUNT(*) FROM tickets WHERE user_id = ? GROUP BY status",
            (user_id,)
        )
        rows = await cur.fetchall()
        counts = {row[0]: row[1] for row in rows}
        return counts.get("open", 0), counts.get("closed", 0)

async def get_user_order_counts(user_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT status, COUNT(*) FROM orders WHERE user_id = ? GROUP BY status",
            (user_id,)
        )
        rows = await cur.fetchall()
        return {row[0]: row[1] for row in rows}

# ─── توابع پیام همگانی ────────────────────────

async def get_all_user_ids() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT user_id FROM users WHERE is_banned = 0 OR is_banned IS NULL"
        )
        return [row[0] for row in await cur.fetchall()]

async def get_active_service_user_ids() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """SELECT DISTINCT o.user_id FROM orders o
               JOIN users u ON o.user_id = u.user_id
               WHERE o.status = 'approved'
                 AND (u.is_banned = 0 OR u.is_banned IS NULL)"""
        )
        return [row[0] for row in await cur.fetchall()]

# ─── آمار ────────────────────────────────────────

_IR = "+3 hours', '+30 minutes"  # Iran time offset برای SQLite

async def get_admin_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:

        def q(sql, *a): return db.execute(sql, a)

        async def one(sql, *a):
            cur = await db.execute(sql, a)
            return (await cur.fetchone())[0]

        total_users   = await one("SELECT COUNT(*) FROM users")
        users_today   = await one(f"SELECT COUNT(*) FROM users WHERE date(created_at, '{_IR}') = date('now', '{_IR}')")
        users_week    = await one(f"SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-7 days')")
        users_month   = await one(f"SELECT COUNT(*) FROM users WHERE strftime('%Y-%m', created_at, '{_IR}') = strftime('%Y-%m', 'now', '{_IR}')")
        banned_users  = await one("SELECT COUNT(*) FROM users WHERE is_banned = 1")

        total_orders   = await one("SELECT COUNT(*) FROM orders WHERE status = 'approved' AND (order_type = 'purchase' OR order_type IS NULL)")
        pending_orders = await one("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
        free_tests     = await one("SELECT COUNT(*) FROM orders WHERE status = 'approved' AND order_type = 'free_test'")

        rev_total = await one(
            "SELECT COALESCE(SUM(p.price),0) FROM orders o LEFT JOIN plans p ON o.plan_id=p.id "
            "WHERE o.status='approved' AND (o.order_type='purchase' OR o.order_type IS NULL)"
        )
        rev_month = await one(
            f"SELECT COALESCE(SUM(p.price),0) FROM orders o LEFT JOIN plans p ON o.plan_id=p.id "
            f"WHERE o.status='approved' AND (o.order_type='purchase' OR o.order_type IS NULL) "
            f"AND strftime('%Y-%m', o.created_at, '{_IR}') = strftime('%Y-%m', 'now', '{_IR}')"
        )
        rev_today = await one(
            f"SELECT COALESCE(SUM(p.price),0) FROM orders o LEFT JOIN plans p ON o.plan_id=p.id "
            f"WHERE o.status='approved' AND (o.order_type='purchase' OR o.order_type IS NULL) "
            f"AND date(o.created_at, '{_IR}') = date('now', '{_IR}')"
        )

        total_wallet   = await one("SELECT COALESCE(SUM(balance),0) FROM users WHERE balance > 0")
        total_referrals= await one("SELECT COUNT(*) FROM referrals")
        open_tickets   = await one("SELECT COUNT(*) FROM tickets WHERE status='open'")
        total_tickets  = await one("SELECT COUNT(*) FROM tickets")

        cur = await db.execute(
            "SELECT COALESCE(p.name,'—'), COUNT(*) as cnt FROM orders o "
            "LEFT JOIN plans p ON o.plan_id=p.id "
            "WHERE o.status='approved' AND (o.order_type='purchase' OR o.order_type IS NULL) "
            "GROUP BY o.plan_id ORDER BY cnt DESC LIMIT 3"
        )
        top_plans = [(r[0], r[1]) for r in await cur.fetchall()]

        return {
            "total_users": total_users, "users_today": users_today,
            "users_week": users_week, "users_month": users_month,
            "banned_users": banned_users,
            "total_orders": total_orders, "pending_orders": pending_orders,
            "free_tests": free_tests,
            "rev_total": rev_total, "rev_month": rev_month, "rev_today": rev_today,
            "total_wallet": total_wallet, "total_referrals": total_referrals,
            "open_tickets": open_tickets, "total_tickets": total_tickets,
            "top_plans": top_plans,
        }

# ─── توابع کد تخفیف ──────────────────────────

async def create_discount_code(code: str, type_: str, value: int, max_uses: int, expires_at: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO discount_codes (code, type, value, max_uses, expires_at) VALUES (?,?,?,?,?)",
            (code.upper(), type_, value, max_uses, expires_at)
        )
        await db.commit()

async def get_discount_codes():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM discount_codes ORDER BY created_at DESC")
        return await cur.fetchall()

async def get_discount_code_by_id(code_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM discount_codes WHERE id = ?", (code_id,))
        return await cur.fetchone()

async def validate_discount_code(code_text: str, user_id: int = None):
    """اگه کد معتبر باشه row برمی‌گردونه، وگرنه None"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM discount_codes WHERE code = ? AND is_active = 1",
            (code_text.upper(),)
        )
        row = await cur.fetchone()
        if not row:
            return None
        if row["max_uses"] > 0 and row["used_count"] >= row["max_uses"]:
            return None
        if row["expires_at"] and row["expires_at"] < __import__("datetime").date.today().isoformat():
            return None
        if user_id is not None:
            cur2 = await db.execute(
                "SELECT 1 FROM discount_code_uses WHERE code_id = ? AND user_id = ?",
                (row["id"], user_id)
            )
            if await cur2.fetchone():
                return None
        return row

async def use_discount_code(code_id: int, user_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE discount_codes SET used_count = used_count + 1 WHERE id = ?", (code_id,)
        )
        if user_id is not None:
            await db.execute(
                "INSERT OR IGNORE INTO discount_code_uses (code_id, user_id) VALUES (?, ?)",
                (code_id, user_id)
            )
        await db.commit()

async def toggle_discount_code(code_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE discount_codes SET is_active = 1 - is_active WHERE id = ?", (code_id,)
        )
        await db.commit()

async def delete_discount_code(code_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM discount_codes WHERE id = ?", (code_id,))
        await db.commit()

async def update_order_discount(order_id: int, discount_code: str, discount_amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET discount_code = ?, discount_amount = ? WHERE id = ?",
            (discount_code, discount_amount, order_id)
        )
        await db.commit()


# ─── کیبورد ادیتور ───────────────────────────

_DEFAULT_KEYBOARDS: dict[str, list[tuple]] = {
    # ── کاربر ──────────────────────────────────────────────────────────────
    "user_main": [
        ("user_main", "🔐 خرید اشتراک",      "buy_vpn",          0, 0, None),
        ("user_main", "💎 کیف پول",           "wallet",           1, 0, None),
        ("user_main", "🎁 تست رایگان",        "free_test",        1, 1, None),
        ("user_main", "📡 سرویس‌های من",      "my_services",      1, 2, None),
        ("user_main", "🎧 پشتیبانی",          "support",          2, 0, None),
        ("user_main", "👤 پروفایل",           "profile",          2, 1, None),
        ("user_main", "📚 آموزش و راهنما",    "tutorial",         2, 2, None),
        ("user_main", "💰 دعوت دوستان",       "referral",         3, 0, None),
        ("user_main", "🌐 تغییر زبان",        "language",         3, 1, None),
    ],
    "wallet": [
        ("wallet", "💳 شارژ حساب",            "top_up",           0, 0, None),
        ("wallet", "📜 تاریخچه تراکنش‌ها",    "wallet_history",   1, 0, None),
        ("wallet", "🔙 بازگشت",               "user_main",        2, 0, None),
    ],
    "support": [
        ("support", "📨 تیکت جدید",           "new_ticket",       0, 0, None),
        ("support", "📋 تیکت‌های من",         "my_tickets",       1, 0, None),
        ("support", "🔙 بازگشت",              "user_main",        2, 0, None),
    ],
    "free_test_confirm": [
        ("free_test_confirm", "✅ دریافت تست رایگان", "_",  0, 0, "free_test_confirm_{id}"),
        ("free_test_confirm", "🔙 بازگشت",             "user_main",              1, 0, None),
    ],
    "ticket": [
        ("ticket", "❌ بستن تیکت",      "_",          0, 0, "close_ticket_{id}"),
        ("ticket", "🔙 بازگشت به منو", "user_main",   1, 0, None),
    ],
    "cancel": [
        ("cancel", "❌ لغو", "cancel", 0, 0, None),
    ],
    "payment_info": [
        ("payment_info", "❌ انصراف", "cancel_payment", 0, 0, None),
    ],
    "subscription_approved": [
        ("subscription_approved", "🗂 سرویس‌های من", "my_services", 0, 0, None),
    ],
    "back_to_tutorials": [
        ("back_to_tutorials", "🔙 بازگشت", "tutorial", 0, 0, None),
    ],
    "back_to_faqs": [
        ("back_to_faqs", "🔙 بازگشت", "user_faqs", 0, 0, None),
    ],
    # ── ادمین — منوها ──────────────────────────────────────────────────────
    "admin_panel": [
        ("admin_panel", "🖥 مدیریت سرورها",          "admin_servers",    0,  0, None),
        ("admin_panel", "📦 پلن‌ها",                  "admin_plans",      1,  0, None),
        ("admin_panel", "💰 مدیریت مالی",            "admin_finance",    2,  0, None),
        ("admin_panel", "👥 مدیریت کاربران",         "admin_users",      3,  0, None),
        ("admin_panel", "🎟 کدهای تخفیف",            "admin_discount",   4,  0, None),
        ("admin_panel", "🎁 تنظیمات تست رایگان",     "admin_free_test",  5,  0, None),
        ("admin_panel", "🤝 تنظیمات دعوت دوستان",   "admin_referral",   6,  0, None),
        ("admin_panel", "🎧 تنظیمات پشتیبانی",       "admin_support",    7,  0, None),
        ("admin_panel", "📚 مدیریت آموزش‌ها",        "admin_tutorials",  8,  0, None),
        ("admin_panel", "📢 پیام همگانی",             "admin_broadcast",  9,  0, None),
        ("admin_panel", "📊 آمار و گزارش",           "admin_stats",      10, 0, None),
        ("admin_panel", "⚙️ تنظیمات عمومی",         "admin_general",    11, 0, None),
        ("admin_panel", "🔙 بازگشت",                 "back_to_start",    12, 0, None),
    ],
    "admin_general": [
        ("admin_general", "🎨 ظاهر ربات", "admin_banner_and_text", 0, 0, None),
        ("admin_general", "🔙 بازگشت",    "admin_panel",           1, 0, None),
    ],
    "admin_banner_and_text": [
        ("admin_banner_and_text", "🖼 تنظیمات بنر",  "admin_banner_settings", 0, 0, None),
        ("admin_banner_and_text", "✏️ تنظیمات متن",  "admin_text_settings",   1, 0, None),
        ("admin_banner_and_text", "🔙 بازگشت",        "admin_general",          2, 0, None),
    ],
    "admin_text_settings": [
        ("admin_text_settings", "✏️ ویرایش متن",  "admin_banner_caption",  0, 0, None),
        ("admin_text_settings", "🛠 ساخت متن",    "admin_build_text",      1, 0, None),
        ("admin_text_settings", "🔙 بازگشت",       "admin_banner_and_text", 2, 0, None),
    ],
    "admin_servers": [
        ("admin_servers", "➕ سرور جدید",   "add_server",   0, 0, None),
        ("admin_servers", "📋 لیست سرورها", "list_servers", 1, 0, None),
        ("admin_servers", "🔙 بازگشت",      "admin_panel",  2, 0, None),
    ],
    "admin_free_test_global": [
        ("admin_free_test_global", "✏️ ویرایش مدت",           "admin_free_test_global_duration", 0, 0, None),
        ("admin_free_test_global", "✏️ ویرایش حجم",           "admin_free_test_global_traffic",  0, 1, None),
        ("admin_free_test_global", "🔢 تعداد مجاز دریافت",    "admin_free_test_max_uses",         1, 0, None),
        ("admin_free_test_global", "📡 اعمال روی همه سرورها", "admin_free_test_apply_all",        2, 0, None),
        ("admin_free_test_global", "🔄 ریست همه کاربران",     "admin_free_test_reset_all",        3, 0, None),
        ("admin_free_test_global", "🔙 بازگشت",               "admin_free_test",                  4, 0, None),
    ],
    "admin_support_settings": [
        ("admin_support_settings", "🆔 تنظیم آیدی گروه",   "admin_support_set_group", 0, 0, None),
        ("admin_support_settings", "✏️ ویرایش متن تیکت",   "admin_support_edit_msg",  1, 0, None),
        ("admin_support_settings", "🔙 بازگشت",             "admin_panel",             2, 0, None),
    ],
    "admin_tutorials": [
        ("admin_tutorials", "📖 آموزش‌ها",       "admin_tutorial_list", 0, 0, None),
        ("admin_tutorials", "📋 سوالات متداول",  "admin_faqs",          1, 0, None),
        ("admin_tutorials", "🔙 بازگشت",         "admin_panel",         2, 0, None),
    ],
    "admin_stats": [
        ("admin_stats", "🔄 بروزرسانی", "admin_stats", 0, 0, None),
        ("admin_stats", "🔙 بازگشت",    "admin_panel", 1, 0, None),
    ],
    "admin_broadcast": [
        ("admin_broadcast", "📢 همه کاربران",           "broadcast_target_all",    0, 0, None),
        ("admin_broadcast", "✅ کاربران با سرویس فعال", "broadcast_target_active", 1, 0, None),
        ("admin_broadcast", "🔙 بازگشت",                "admin_panel",             2, 0, None),
    ],
    "admin_users": [
        ("admin_users", "🔍 جستجوی کاربر",   "admin_users_search",   0, 0, None),
        ("admin_users", "🕐 جدیدترین‌ها",     "admin_ul_newest_0",    1, 0, None),
        ("admin_users", "🏆 بیشترین خرید",    "admin_ul_topbuyers_0", 2, 0, None),
        ("admin_users", "🚫 کاربران بن‌شده",  "admin_ul_banned_0",    3, 0, None),
        ("admin_users", "🔙 بازگشت",          "admin_panel",          4, 0, None),
    ],
    "card_settings": [
        ("card_settings", "💳 تغییر شماره کارت",    "set_card_number", 0, 0, None),
        ("card_settings", "👤 تغییر نام صاحب کارت", "set_card_owner",  1, 0, None),
        ("card_settings", "🔙 بازگشت",              "admin_finance",   2, 0, None),
    ],
    "after_order": [
        ("after_order", "⚙️ پنل ادمین", "admin_panel",   0, 0, None),
        ("after_order", "🏠 منوی اصلی", "back_to_start", 0, 1, None),
    ],
    "discount_type": [
        ("discount_type", "٪ درصدی",     "discount_type_percent", 0, 0, None),
        ("discount_type", "💵 مبلغ ثابت", "discount_type_fixed",   1, 0, None),
        ("discount_type", "🔙 انصراف",    "admin_discount",         2, 0, None),
    ],
    "discount_expiry": [
        ("discount_expiry", "♾ بدون تاریخ انقضا", "discount_expiry_none", 0, 0, None),
        ("discount_expiry", "🔙 انصراف",           "admin_discount",        1, 0, None),
    ],
    # ── Action keyboards — با callback_template ────────────────────────────
    "confirm_delete_server": [
        ("confirm_delete_server", "🗑 بله، حذف کن", "_", 0, 0, "confirmed_delete_server_{id}"),
        ("confirm_delete_server", "❌ انصراف",       "_", 0, 1, "server_settings_{id}"),
    ],
    "confirm_delete_plan": [
        ("confirm_delete_plan", "🗑 بله، حذف کن", "_", 0, 0, "confirmed_delete_plan_{id}"),
        ("confirm_delete_plan", "❌ انصراف",       "_", 0, 1, "plan_settings_{id}"),
    ],
    "confirm_delete_service": [
        ("confirm_delete_service", "🗑 بله، حذف کن", "_", 0, 0, "confirmed_delete_service_{id}"),
        ("confirm_delete_service", "❌ انصراف",       "_", 0, 1, "my_service_{id}"),
    ],
    "admin_order": [
        ("admin_order", "✅ تایید",       "_", 0, 0, "order_approve_{id}"),
        ("admin_order", "❌ رد",          "_", 1, 0, "order_reject_{id}"),
        ("admin_order", "❌ رد با دلیل", "_", 1, 1, "order_reject_reason_{id}"),
    ],
    "admin_topup": [
        ("admin_topup", "✅ تایید شارژ", "_", 0, 0, "topup_approve_{id}"),
        ("admin_topup", "❌ رد",          "_", 1, 0, "topup_reject_{id}"),
    ],
    # ── صفحات داینامیک کاربر (دکمه‌های ثابت — داینامیک از API میاد) ──
    "user_plans": [
        ("user_plans", "🔙 بازگشت",         "buy_vpn",    999, 0, None),
    ],
    "user_proforma": [
        ("user_proforma", "💎 پرداخت با کیف پول", "pay_wallet_0",    0, 0, None),
        ("user_proforma", "💳 پرداخت با کارت",     "user_pay_0",      1, 0, None),
        ("user_proforma", "🎟 کد تخفیف",           "apply_discount_0",2, 0, None),
        ("user_proforma", "🔙 بازگشت",             "user_plans",      3, 0, None),
    ],
    "my_services": [
        ("my_services", "🔙 بازگشت",  "user_main", 999, 0, None),
    ],
    "user_service_detail": [
        ("user_service_detail", "🔄 تمدید سرویس",   "renew_0",          0, 0, None),
        ("user_service_detail", "🗑 حذف سرویس",      "delete_service_0", 1, 0, None),
        ("user_service_detail", "🔙 بازگشت",         "my_services",      2, 0, None),
    ],
    "my_tickets": [
        ("my_tickets", "🔙 بازگشت", "support", 999, 0, None),
    ],
    "user_tutorials": [
        ("user_tutorials", "🔙 بازگشت", "user_main", 999, 0, None),
    ],
    "user_faqs": [
        ("user_faqs", "🔙 بازگشت", "user_main", 999, 0, None),
    ],
    # ── صفحات داینامیک ادمین ──────────────────────────
    "admin_plans": [
        ("admin_plans", "➕ پلن جدید",  "add_plan",    998, 0, None),
        ("admin_plans", "🔙 بازگشت",    "admin_panel", 999, 0, None),
    ],
    "admin_discount": [
        ("admin_discount", "➕ کد تخفیف جدید", "discount_add", 998, 0, None),
        ("admin_discount", "🔙 بازگشت",         "admin_panel",  999, 0, None),
    ],
    "admin_referral": [
        ("admin_referral", "💰 تنظیم درصد کمیسیون",  "admin_referral_edit_pct",   0, 0, None),
        ("admin_referral", "🎟 تنظیم مبلغ ثابت",      "admin_referral_edit_fixed", 1, 0, None),
        ("admin_referral", "🔄 فعال/غیرفعال کردن",    "admin_referral_toggle",     2, 0, None),
        ("admin_referral", "🔙 بازگشت",               "admin_panel",               3, 0, None),
    ],
}

_DEFAULT_KEYBOARD_ACTIONS = [
    # (action_name, label, callback_data, grp)
    # ── کاربر ─────────────────────────────────────────
    ("buy_vpn",              "🔐 خرید اشتراک",               "buy_vpn",              "user"),
    ("wallet",               "💎 کیف پول",                   "wallet",               "user"),
    ("free_test",            "🎁 تست رایگان",                "free_test",            "user"),
    ("my_services",          "📡 سرویس‌های من",              "my_services",          "user"),
    ("support",              "🎧 پشتیبانی",                  "support",              "user"),
    ("profile",              "👤 پروفایل",                   "profile",              "user"),
    ("tutorial",             "📚 آموزش و راهنما",            "tutorial",             "user"),
    ("referral",             "💰 دعوت دوستان",               "referral",             "user"),
    ("language",             "🌐 تغییر زبان",                "language",             "user"),
    ("top_up",               "💳 شارژ حساب",                 "top_up",               "user"),
    ("wallet_history",       "📜 تاریخچه تراکنش‌ها",         "wallet_history",       "user"),
    ("new_ticket",           "📨 تیکت جدید",                 "new_ticket",           "user"),
    ("my_tickets",           "📋 تیکت‌های من",               "my_tickets",           "user"),
    ("user_main",            "🏠 منوی اصلی",                 "user_main",            "user"),
    ("back_to_start",        "🏠 بازگشت به شروع",            "back_to_start",        "user"),
    ("user_faqs",            "❓ سوالات متداول",              "user_faqs",            "user"),
    ("cancel",               "❌ لغو",                       "cancel",               "user"),
    ("cancel_payment",       "❌ انصراف از پرداخت",          "cancel_payment",       "user"),
    # ── ادمین ─────────────────────────────────────────
    ("admin_panel",                  "⚙️ پنل ادمین",                     "admin_panel",                  "admin"),
    ("admin_general",                "⚙️ تنظیمات عمومی",                 "admin_general",                "admin"),
    ("admin_banner_and_text",        "🎨 ظاهر ربات",                     "admin_banner_and_text",        "admin"),
    ("admin_banner_settings",        "🖼 تنظیمات بنر",                   "admin_banner_settings",        "admin"),
    ("admin_text_settings",          "✏️ تنظیمات متن",                   "admin_text_settings",          "admin"),
    ("admin_banner_caption",         "✏️ ویرایش متن خوش‌آمدگویی",       "admin_banner_caption",         "admin"),
    ("admin_build_text",             "🛠 ساخت متن",                      "admin_build_text",             "admin"),
    ("admin_servers",                "🖥 مدیریت سرورها",                 "admin_servers",                "admin"),
    ("add_server",                   "➕ سرور جدید",                     "add_server",                   "admin"),
    ("list_servers",                 "📋 لیست سرورها",                   "list_servers",                 "admin"),
    ("admin_plans",                  "📦 مدیریت پلن‌ها",                 "admin_plans",                  "admin"),
    ("admin_finance",                "💰 مدیریت مالی",                   "admin_finance",                "admin"),
    ("set_card_number",              "💳 تغییر شماره کارت",              "set_card_number",              "admin"),
    ("set_card_owner",               "👤 تغییر نام صاحب کارت",          "set_card_owner",               "admin"),
    ("admin_users",                  "👥 مدیریت کاربران",               "admin_users",                  "admin"),
    ("admin_users_search",           "🔍 جستجوی کاربر",                 "admin_users_search",           "admin"),
    ("admin_ul_newest_0",            "🕐 جدیدترین کاربران",             "admin_ul_newest_0",            "admin"),
    ("admin_ul_topbuyers_0",         "🏆 بیشترین خرید",                  "admin_ul_topbuyers_0",         "admin"),
    ("admin_ul_banned_0",            "🚫 کاربران بن‌شده",               "admin_ul_banned_0",            "admin"),
    ("admin_discount",               "🎟 کدهای تخفیف",                  "admin_discount",               "admin"),
    ("discount_type_percent",        "٪ درصدی",                          "discount_type_percent",        "admin"),
    ("discount_type_fixed",          "💵 مبلغ ثابت",                     "discount_type_fixed",          "admin"),
    ("discount_expiry_none",         "♾ بدون تاریخ انقضا",              "discount_expiry_none",         "admin"),
    ("admin_free_test",              "🎁 تنظیمات تست رایگان",            "admin_free_test",              "admin"),
    ("admin_free_test_global_dur",   "✏️ ویرایش مدت تست",               "admin_free_test_global_duration","admin"),
    ("admin_free_test_global_trf",   "✏️ ویرایش حجم تست",               "admin_free_test_global_traffic","admin"),
    ("admin_free_test_max_uses",     "🔢 حداکثر تعداد تست",             "admin_free_test_max_uses",     "admin"),
    ("admin_free_test_apply_all",    "📡 اعمال روی همه سرورها",         "admin_free_test_apply_all",    "admin"),
    ("admin_free_test_reset_all",    "🔄 ریست استفاده‌کنندگان تست",     "admin_free_test_reset_all",    "admin"),
    ("admin_referral",               "🤝 تنظیمات دعوت دوستان",          "admin_referral",               "admin"),
    ("admin_support",                "🎧 تنظیمات پشتیبانی",             "admin_support",                "admin"),
    ("admin_support_set_group",      "🆔 تنظیم آیدی گروه",             "admin_support_set_group",      "admin"),
    ("admin_support_edit_msg",       "✏️ ویرایش متن تیکت",              "admin_support_edit_msg",       "admin"),
    ("admin_tutorials",              "📚 مدیریت آموزش‌ها",              "admin_tutorials",              "admin"),
    ("admin_tutorial_list",          "📖 لیست آموزش‌ها",                "admin_tutorial_list",          "admin"),
    ("admin_faqs",                   "📋 لیست سوالات متداول",            "admin_faqs",                   "admin"),
    ("admin_broadcast",              "📢 پیام همگانی",                   "admin_broadcast",              "admin"),
    ("broadcast_target_all",         "📢 ارسال به همه",                  "broadcast_target_all",         "admin"),
    ("broadcast_target_active",      "✅ ارسال به کاربران فعال",        "broadcast_target_active",      "admin"),
    ("admin_stats",                  "📊 آمار و گزارش",                 "admin_stats",                  "admin"),
]


async def _seed_keyboard_buttons():
    async with aiosqlite.connect(DB_PATH) as db:
        for kb_name, buttons in _DEFAULT_KEYBOARDS.items():
            cursor = await db.execute(
                "SELECT COUNT(*) FROM keyboard_buttons WHERE keyboard_name = ?", (kb_name,)
            )
            count = (await cursor.fetchone())[0]
            if count == 0:
                await db.executemany(
                    """INSERT INTO keyboard_buttons
                       (keyboard_name, label, callback_data, row_index, col_index, callback_template)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    [(b[0], b[1], b[2], b[3], b[4], b[5] if len(b) > 5 else None) for b in buttons]
                )
        for action in _DEFAULT_KEYBOARD_ACTIONS:
            await db.execute(
                """INSERT OR REPLACE INTO keyboard_actions
                   (action_name, label, callback_data, grp) VALUES (?, ?, ?, ?)""",
                action
            )
        await db.commit()


async def get_keyboard_buttons(keyboard_name: str, admin: bool = False) -> list[dict]:
    """برگرداندن دکمه‌های فعال یک کیبورد؛ admin=True دکمه‌های admin_only را هم برمی‌گرداند"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if admin:
            cursor = await db.execute(
                """SELECT * FROM keyboard_buttons
                   WHERE keyboard_name = ? AND is_active = 1
                   ORDER BY row_index, col_index""",
                (keyboard_name,)
            )
        else:
            cursor = await db.execute(
                """SELECT * FROM keyboard_buttons
                   WHERE keyboard_name = ? AND is_active = 1
                     AND (admin_only IS NULL OR admin_only = 0)
                   ORDER BY row_index, col_index""",
                (keyboard_name,)
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_all_keyboard_buttons(keyboard_name: str) -> list[dict]:
    """همه‌ی دکمه‌ها (فعال و غیرفعال) برای ادیتور"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM keyboard_buttons
               WHERE keyboard_name = ?
               ORDER BY row_index, col_index""",
            (keyboard_name,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def save_keyboard_layout(keyboard_name: str, buttons: list[dict]):
    """ذخیره‌ی چینش جدید کیبورد — از ادیتور جنگو صدا زده می‌شه"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM keyboard_buttons WHERE keyboard_name = ?", (keyboard_name,)
        )
        if buttons:
            await db.executemany(
                """INSERT INTO keyboard_buttons
                   (keyboard_name, label, callback_data, row_index, col_index, is_active, callback_template)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (keyboard_name, b["label"], b["callback_data"],
                     b["row_index"], b["col_index"], b.get("is_active", 1),
                     b.get("callback_template"))
                    for b in buttons
                ]
            )
        await db.commit()
    _keyboards_cache[keyboard_name] = [dict(b) for b in buttons if b.get("is_active", 1)]


async def get_servers_as_buttons() -> list[dict]:
    """سرورها را به فرمت دکمه‌ی کیبورد برمی‌گرداند — برای کیبورد داینامیک buy_vpn"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, is_active FROM servers ORDER BY order_index, id"
        )
        rows = await cursor.fetchall()
        return [
            {
                "id":            r["id"],
                "keyboard_name": "buy_vpn",
                "label":         r["name"],
                "callback_data": f"server_{r['id']}",
                "row_index":     i,
                "col_index":     0,
                "is_active":     r["is_active"],
                "is_dynamic":    True,
            }
            for i, r in enumerate(rows)
        ]


async def save_server_order(buttons: list[dict]):
    """ترتیب و وضعیت سرورها را از ادیتور کیبورد ذخیره می‌کند"""
    async with aiosqlite.connect(DB_PATH) as db:
        for btn in buttons:
            cb = btn.get("callback_data", "")
            if not cb.startswith("server_"):
                continue
            server_id_str = cb[len("server_"):]
            if not server_id_str.isdigit():
                continue
            server_id = int(server_id_str)
            order_idx = btn.get("row_index", 0) * 10 + btn.get("col_index", 0)
            is_active  = 1 if btn.get("is_active", 1) else 0
            await db.execute(
                "UPDATE servers SET order_index = ?, is_active = ? WHERE id = ?",
                (order_idx, is_active, server_id),
            )
        await db.commit()


async def get_keyboard_actions() -> list[dict]:
    """کاتالوگ همه‌ی امکانات ممکن برای دکمه‌ها"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM keyboard_actions ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


def _dyn(kb, label, cb, row, *, col=0, is_dynamic=True):
    return {"keyboard_name": kb, "label": label, "callback_data": cb,
            "row_index": row, "col_index": col, "is_active": 1, "is_dynamic": is_dynamic}


async def get_plans_as_buttons() -> list[dict]:
    """پلن‌های فعال — داینامیک برای ادیتور (user_plans)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT p.id, p.name, p.price, s.name as sname
               FROM plans p LEFT JOIN servers s ON p.server_id = s.id
               WHERE p.is_active=1 AND p.server_id IS NOT NULL
               ORDER BY p.server_id, p.id"""
        )
        rows = await cur.fetchall()
    result = [
        _dyn("user_plans", f"{r['name']} — {r['price']:,} تومان", f"user_plan_{r['id']}", i)
        for i, r in enumerate(rows)
    ]
    result += await get_all_keyboard_buttons("user_plans")  # دکمه‌های ثابت (بازگشت)
    return result


async def get_services_as_buttons() -> list[dict]:
    """سرویس‌های اخیر — داینامیک برای ادیتور (my_services)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT o.id, pl.name, s.name as sname
               FROM orders o
               LEFT JOIN plans pl ON o.plan_id = pl.id
               LEFT JOIN servers s ON pl.server_id = s.id
               WHERE o.status='approved'
               ORDER BY o.id DESC LIMIT 8"""
        )
        rows = await cur.fetchall()
    result = [
        _dyn("my_services", f"📡 {r['name'] or 'سرویس'} ({r['sname'] or '?'})",
             f"service_detail_{r['id']}", i)
        for i, r in enumerate(rows)
    ]
    result += await get_all_keyboard_buttons("my_services")
    return result


async def get_tickets_as_buttons() -> list[dict]:
    """تیکت‌های اخیر — داینامیک برای ادیتور (my_tickets)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, subject FROM support_tickets ORDER BY id DESC LIMIT 6"
        )
        rows = await cur.fetchall()
    result = [
        _dyn("my_tickets", f"🎫 {r['subject'][:30]}", f"ticket_detail_{r['id']}", i)
        for i, r in enumerate(rows)
    ]
    if not result:
        result = [_dyn("my_tickets", "🎫 تیکت نمونه ۱", "ticket_detail_1", 0),
                  _dyn("my_tickets", "🎫 تیکت نمونه ۲", "ticket_detail_2", 1)]
    result += await get_all_keyboard_buttons("my_tickets")
    return result


async def get_tutorials_as_buttons() -> list[dict]:
    """آموزش‌ها — داینامیک برای ادیتور (user_tutorials)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, title FROM tutorials WHERE is_active=1 ORDER BY order_index, id LIMIT 8"
        )
        rows = await cur.fetchall()
    result = [
        _dyn("user_tutorials", f"📖 {r['title'][:30]}", f"tutorial_detail_{r['id']}", i)
        for i, r in enumerate(rows)
    ]
    if not result:
        result = [_dyn("user_tutorials", "📖 راهنمای نصب ویندوز", "tutorial_detail_1", 0)]
    result += await get_all_keyboard_buttons("user_tutorials")
    return result


async def get_faqs_as_buttons() -> list[dict]:
    """سوالات متداول — داینامیک برای ادیتور (user_faqs)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, question FROM faqs WHERE is_active=1 ORDER BY order_index, id LIMIT 8"
        )
        rows = await cur.fetchall()
    result = [
        _dyn("user_faqs", f"❓ {r['question'][:30]}", f"faq_detail_{r['id']}", i)
        for i, r in enumerate(rows)
    ]
    if not result:
        result = [_dyn("user_faqs", "❓ چطور وصل شم؟", "faq_detail_1", 0)]
    result += await get_all_keyboard_buttons("user_faqs")
    return result


async def get_admin_plans_as_buttons() -> list[dict]:
    """پلن‌های ادمین — داینامیک برای ادیتور (admin_plans)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT p.id, p.name, p.price, p.is_active, s.name as sname
               FROM plans p LEFT JOIN servers s ON p.server_id = s.id
               ORDER BY p.server_id, p.id"""
        )
        rows = await cur.fetchall()
    result = [
        _dyn("admin_plans",
             f"{'✅' if r['is_active'] else '❌'} {r['name']} | {r['sname'] or '?'}",
             f"toggle_plan_settings_{r['id']}_0", i)
        for i, r in enumerate(rows)
    ]
    result += await get_all_keyboard_buttons("admin_plans")
    return result


async def get_discount_codes_as_buttons() -> list[dict]:
    """کدهای تخفیف — داینامیک برای ادیتور (admin_discount)"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, code, is_active FROM discount_codes ORDER BY id DESC LIMIT 8"
        )
        rows = await cur.fetchall()
    result = [
        _dyn("admin_discount",
             f"{'✅' if r['is_active'] else '❌'} {r['code']}",
             f"discount_item_{r['id']}", i)
        for i, r in enumerate(rows)
    ]
    if not result:
        result = [_dyn("admin_discount", "✅ SUMMER20", "discount_item_1", 0)]
    result += await get_all_keyboard_buttons("admin_discount")
    return result