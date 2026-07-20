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


async def make_plan_row(price: int = 10000, service_ids=None, traffic: int = 50, duration: int = 30):
    """Create a server + plan and return the joined plan row (what fulfill wants)."""
    if service_ids is None:
        service_ids = [1]
    await db.add_server("s1", "https://panel.test", "token", service_ids)
    server_id = (await db.get_servers(only_active=False))[-1]["id"]
    await db.add_plan(server_id, "p1", price, duration, traffic)
    plan_id = (await db.get_plans(server_id, only_active=False))[-1]["id"]
    return await db.get_plan_with_server(plan_id)


async def get_order_status(order_id: int) -> str:
    async with aiosqlite.connect(db.DB_PATH) as conn:
        cur = await conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        return row[0]


async def make_volume_request(order_id: int, traffic_gb: float = 10, user_id: int = 1) -> int:
    async with aiosqlite.connect(db.DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO extra_volume_plans (name, traffic_gb, price) VALUES ('v', ?, 100)",
            (traffic_gb,),
        )
        plan_id = cur.lastrowid
        await conn.commit()
    return await db.create_extra_volume_request(user_id, order_id, plan_id)


async def make_time_request(order_id: int, days: int = 15, user_id: int = 1) -> int:
    async with aiosqlite.connect(db.DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO extra_time_plans (name, days, price) VALUES ('t', ?, 100)",
            (days,),
        )
        plan_id = cur.lastrowid
        await conn.commit()
    return await db.create_extra_time_request(user_id, order_id, plan_id)


async def get_extra_volume_status(req_id: int) -> str:
    async with aiosqlite.connect(db.DB_PATH) as conn:
        cur = await conn.execute("SELECT status FROM extra_volume_requests WHERE id = ?", (req_id,))
        return (await cur.fetchone())[0]


async def get_extra_time_status(req_id: int) -> str:
    async with aiosqlite.connect(db.DB_PATH) as conn:
        cur = await conn.execute("SELECT status FROM extra_time_requests WHERE id = ?", (req_id,))
        return (await cur.fetchone())[0]
