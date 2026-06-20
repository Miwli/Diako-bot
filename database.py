import aiosqlite

DB_PATH = "bot.db"

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
                server_id INTEGER NOT NULL,
                name      TEXT NOT NULL,
                price     INTEGER NOT NULL,
                duration  INTEGER NOT NULL,
                traffic   INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (server_id) REFERENCES servers(id)
            )
        """)
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
        for col, col_type in {"referral_code": "TEXT", "free_test_uses": "INTEGER DEFAULT 0"}.items():
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
    """حذف سرور"""
    async with aiosqlite.connect(DB_PATH) as db:
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