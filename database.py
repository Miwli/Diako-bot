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