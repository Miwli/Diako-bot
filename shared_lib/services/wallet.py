"""Wallet service — top-up approval orchestration.

Owns the top-up approve/reject flow (atomic status flip + balance credit) so the
bot handler and the panel view share one path. No aiogram dependency: the caller
sends the user notification from the returned result. The low-level atomic
balance primitives stay in db.py until the repo split (phase E).
"""

from dataclasses import dataclass

from shared_lib.db import (
    approve_top_up_atomic,
    update_top_up_status,
    get_top_up_request,
    get_or_create_user,
    add_balance_and_transaction,
)


@dataclass
class TopUpResult:
    status: str  # ok | not_found | already_processed
    user_id: int = 0
    amount: int = 0


async def approve_top_up(request_id: int, actor: str = "system") -> TopUpResult:
    """Approve a pending top-up: flip status atomically, then credit the wallet.
    Idempotent — the atomic flip guarantees the balance is credited only once."""
    req = await get_top_up_request(request_id)
    if not req:
        return TopUpResult(status="not_found")
    if not await approve_top_up_atomic(request_id):
        return TopUpResult(status="already_processed")
    await get_or_create_user(req["user_id"], "", req["username"])
    await add_balance_and_transaction(
        req["user_id"], req["amount"], "charge", f"شارژ حساب #{request_id}"
    )
    return TopUpResult(status="ok", user_id=req["user_id"], amount=req["amount"])


async def reject_top_up(request_id: int, actor: str = "system") -> TopUpResult:
    """Reject a pending top-up. Idempotent — a non-pending request is untouched."""
    req = await get_top_up_request(request_id)
    if not req:
        return TopUpResult(status="not_found")
    if req["status"] != "pending":
        return TopUpResult(status="already_processed")
    await update_top_up_status(request_id, "rejected")
    return TopUpResult(status="ok", user_id=req["user_id"], amount=req["amount"])
