import aiosqlite

DB_PATH = "bot.db"  # فایل دیتابیس کنار bot.py ساخته می‌شه

async def init_db():
    """ساخت جداول دیتابیس (اگه وجود نداشته باشن)"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL,
                price     INTEGER NOT NULL,
                duration  INTEGER NOT NULL,
                traffic   INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.commit()

async def add_plans(name: str, price: int, duration: int, traffic: int):
    """اضافه کردن پلن جدید"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO plans (name, price, duration, traffic) VALUES (?, ?, ?, ?)",
            (name, price, duration, traffic)           
        )
        await db.commit()

async def get_plans(only_active: bool=True):
    """دریافت لیست پلن ها"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if only_active:
            cursor = await db.execute("SELECT * FROM plans WHERE is_active = 1")
        else:
            cursor = await db.execute("SELECT * FROM plans")
        return await cursor.fetchall()

async def update_plan(plan_id: int, name:str, price:int, duration:int, traffic:int):
    """ویرایش پلن"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE plans SET name=?, price=?, duration=?, traffic=? WHERE id=?",
            (name, price, duration, traffic, plan_id)
        )
        await db.commit()

async def delete_plan(plan_id: int):
    """حذف پلن"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        await db.commit()