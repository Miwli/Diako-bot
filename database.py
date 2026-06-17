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
                is_active   INTEGER DEFAULT 1
            )
        """)
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
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (plan_id) REFERENCES plans(id)
            )
        """)
        await db.commit()

# ─── توابع سرورها ─────────────────────────────

async def add_server(name: str, panel_url: str, panel_token: str):
    """اضافه کردن سرور جدید"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO servers (name, panel_url, panel_token) VALUES (?, ?, ?)",
            (name, panel_url, panel_token)
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

async def update_order_status(order_id: int, status: str, rejection_reason: str = None):
    """آپدیت وضعیت سفارش"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE orders SET status = ?, rejection_reason = ? WHERE id = ?",
            (status, rejection_reason, order_id)
        )
        await db.commit()