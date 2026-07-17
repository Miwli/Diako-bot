import asyncio

import aiosqlite

import shared_lib.db as db


def _run(coro):
    return asyncio.run(coro)


async def _seed_faqs(n):
    ids = []
    for i in range(n):
        ids.append(await db.create_faq(f"question {i}", f"answer {i}"))
    return ids


def test_migration_adds_col_index(db_module):
    async def go():
        async with aiosqlite.connect(db_module.DB_PATH) as conn:
            for table in ("faqs", "tutorials"):
                cur = await conn.execute(f"PRAGMA table_info({table})")
                cols = {r[1] for r in await cur.fetchall()}
                assert "col_index" in cols, f"{table} missing col_index"
    _run(go())


def test_back_button_seeded(db_module):
    async def go():
        rows = await db_module.get_all_keyboard_buttons("user_faqs")
        assert any(r["callback_data"] == "tutorial" for r in rows), "faq back not seeded"
        trows = await db_module.get_all_keyboard_buttons("user_tutorials")
        cbs = {r["callback_data"] for r in trows}
        assert "back_to_start" in cbs and "user_faqs" in cbs, "tutorial static buttons not seeded"
    _run(go())


def test_multicolumn_roundtrip(db_module):
    async def go():
        ids = await _seed_faqs(3)
        # editor puts q0 and q1 on the same row (side by side), q2 on its own row
        layout = [
            {"callback_data": f"faq_detail_{ids[0]}", "row_index": 0, "col_index": 0},
            {"callback_data": f"faq_detail_{ids[1]}", "row_index": 0, "col_index": 1},
            {"callback_data": f"faq_detail_{ids[2]}", "row_index": 1, "col_index": 0},
        ]
        await db_module.save_faq_order(layout)

        faqs = await db_module.get_faqs(active_only=True)
        by_id = {f["id"]: (f["order_index"], f["col_index"]) for f in faqs}
        assert by_id[ids[0]] == (0, 0)
        assert by_id[ids[1]] == (0, 1)
        assert by_id[ids[2]] == (1, 0)

        # order returned respects row then col
        ordered = [f["id"] for f in faqs]
        assert ordered[:3] == [ids[0], ids[1], ids[2]]
    _run(go())


def test_bot_keyboard_grid(db_module):
    import keyboards as kb  # bot/ is on sys.path via conftest

    async def go():
        ids = await _seed_faqs(2)
        await db_module.save_faq_order([
            {"callback_data": f"faq_detail_{ids[0]}", "row_index": 0, "col_index": 0},
            {"callback_data": f"faq_detail_{ids[1]}", "row_index": 0, "col_index": 1},
        ])
        # refresh the in-memory keyboard cache so the seeded back button is visible
        await db_module.init_keyboards_cache()
        faqs = await db_module.get_faqs(active_only=True)
        markup = kb.user_faqs_keyboard(faqs)
        # first row must hold both questions side by side
        first = markup.inline_keyboard[0]
        assert len(first) == 2, f"expected 2 buttons in row 0, got {len(first)}"
        assert first[0].callback_data == f"faq_view_{ids[0]}"
        assert first[1].callback_data == f"faq_view_{ids[1]}"
        # back button rendered somewhere after
        all_cb = [b.callback_data for row in markup.inline_keyboard for b in row]
        assert "tutorial" in all_cb, "back button missing from faq keyboard"
    _run(go())
