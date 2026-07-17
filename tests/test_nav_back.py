import asyncio

import pytest
from aiogram.types import CallbackQuery, User

import middlewares as mw  # bot/ is on sys.path via conftest


def _cbq(uid, data):
    return CallbackQuery(
        id="x", from_user=User(id=uid, is_bot=False, first_name="t"),
        chat_instance="ci", data=data,
    )


async def _feed(uid, datas):
    """Runs a sequence of taps through the middleware, returns the data each
    tap actually reached the handler with (nav_back resolves to a screen)."""
    seen = []

    async def handler(event, data):
        seen.append(event.data)

    for d in datas:
        await mw.NavHistoryMiddleware()(handler, _cbq(uid, d), {})
    return seen


@pytest.fixture(autouse=True)
def clear_history():
    mw._nav_history.clear()
    yield
    mw._nav_history.clear()


def test_back_returns_previous_screen():
    seen = asyncio.run(_feed(1, ["buy_vpn", "user_server_5", "nav_back"]))
    assert seen == ["buy_vpn", "user_server_5", "buy_vpn"]


def test_actions_are_not_recorded():
    # toggle_card runs but is never recorded; back skips it to the previous screen
    seen = asyncio.run(_feed(2, ["wallet", "wallet_history", "toggle_card", "nav_back"]))
    assert seen[-1] == "wallet"


def test_money_actions_never_replayed():
    # pay_ / confirm_services must never become a back target
    seen = asyncio.run(_feed(3, ["buy_vpn", "user_plan_7", "pay_7", "confirm_services", "nav_back"]))
    assert seen[-1] == "buy_vpn"
    assert "pay_7" not in seen[-1] and seen[-1] != "confirm_services"


def test_back_on_empty_goes_home():
    seen = asyncio.run(_feed(4, ["nav_back"]))
    assert seen == ["user_main"]


def test_revisit_truncates_history():
    # returning to an ancestor screen collapses the branch above it
    seen = asyncio.run(_feed(5, ["buy_vpn", "user_server_5", "user_plan_3", "buy_vpn", "nav_back"]))
    assert seen[-1] == "user_main"  # buy_vpn revisited -> stack [buy_vpn], back -> home
