import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared-data", "bot.db")


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
        await db.commit()

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