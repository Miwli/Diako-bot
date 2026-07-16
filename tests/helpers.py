import aiosqlite

import shared_lib.db as db


async def make_user(user_id: int, balance: int) -> None:
    async with aiosqlite.connect(db.DB_PATH) as conn:
        await conn.execute(
            "INSERT INTO users (user_id, balance) VALUES (?, ?)",
            (user_id, balance),
        )
        await conn.commit()


async def get_balance(user_id: int) -> int:
    async with aiosqlite.connect(db.DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT balance FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        return row[0]


async def make_top_up(user_id: int = 1, amount: int = 500) -> int:
    return await db.create_top_up_request(user_id, "tester", amount, "receipt")


async def get_top_up_status(request_id: int) -> str:
    async with aiosqlite.connect(db.DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT status FROM top_up_requests WHERE id = ?", (request_id,)
        )
        row = await cur.fetchone()
        return row[0]
