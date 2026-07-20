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


async def make_vpn_order(user_id: int = 1, price: int = 10000, service_ids=None) -> int:
    """Create a server + plan + pending order, return the order id."""
    if service_ids is None:
        service_ids = [1]
    await db.add_server("s1", "https://panel.test", "token", service_ids)
    server_id = (await db.get_servers(only_active=False))[-1]["id"]
    await db.add_plan(server_id, "p1", price, 30, 50)
    plan_id = (await db.get_plans(server_id, only_active=False))[-1]["id"]
    return await db.create_order(user_id, "tester", plan_id, "receipt")


async def get_order_status(order_id: int) -> str:
    async with aiosqlite.connect(db.DB_PATH) as conn:
        cur = await conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        return row[0]
