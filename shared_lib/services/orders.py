"""Order lifecycle service — approve/reject with actor-aware signatures.

Business logic only: state transition, provisioning, DB writes, rollback and
referral crediting. No aiogram/Telegram dependency, so the bot handler and the
panel view can share one path. Callers own the user-facing messaging (QR photo,
notifications) using the returned result.
"""

import json
import logging
from dataclasses import dataclass

from shared_lib.services import provisioning
from shared_lib.db import (
    get_order,
    get_plan_with_server,
    create_order,
    update_order_status,
    update_order_vpn_info,
    update_order_discount,
    use_discount_code,
    deduct_balance_if_sufficient,
    add_balance,
    add_transaction,
    get_referral_by_referred,
    add_balance_and_transaction,
    mark_first_purchase_rewarded,
    add_referral_commission,
    decrement_free_test_uses,
    get_setting,
)

log = logging.getLogger(__name__)


@dataclass
class ApproveResult:
    # status: ok | not_found | already_processed | no_service_config
    #         | no_live_service | api_error | save_error
    status: str
    username: str = ""
    subscription_url: str = ""
    user_id: int = 0
    price: int = 0
    error: str = ""
    referrer_notify: tuple | None = None  # (referrer_id, commission) or None


@dataclass
class RejectResult:
    status: str  # ok | not_found | already_processed
    user_id: int = 0


@dataclass
class FulfillResult:
    # status: ok | no_service_config | no_balance | no_live_service
    #         | api_error | save_error
    status: str
    username: str = ""
    subscription_url: str = ""
    order_id: int = 0
    error: str = ""


async def fulfill(
    plan: dict,
    user_id: int,
    username_display: str,
    *,
    order_type: str,
    final_price: int,
    charge_wallet: bool,
    verify_live: bool,
    discount_amount: int = 0,
    discount_code: str = None,
    discount_code_id: int = None,
) -> FulfillResult:
    """Provision and record an immediately-paid order (wallet or full discount).

    Charges the wallet up front when `charge_wallet` is set, provisions the panel
    user, then writes the order. Any failure after the charge refunds it, and a
    failure after provisioning removes the just-created panel user so nothing
    leaks. The caller renders the QR / success message from the result.
    """
    import json

    service_ids = json.loads(plan["service_ids"] or "[]")
    if not service_ids:
        return FulfillResult(status="no_service_config")

    charged = charge_wallet and final_price > 0
    if charged:
        if not await deduct_balance_if_sufficient(user_id, final_price):
            return FulfillResult(status="no_balance")

    try:
        result = await provisioning.provision_service(
            plan["panel_url"], plan["panel_token"],
            service_ids, plan["traffic"],
            duration_days=plan["duration"], ip_limit=plan["ip_limit"],
            verify_live=verify_live,
        )
    except provisioning.NoLiveServiceError:
        if charged:
            await add_balance(user_id, final_price)
        return FulfillResult(status="no_live_service")
    except Exception as e:
        if charged:
            await add_balance(user_id, final_price)
        return FulfillResult(status="api_error", error=str(e))

    username = result["username"]
    subscription_url = result["subscription_url"]

    try:
        order_id = await create_order(user_id, username_display, plan["id"], order_type)
        await update_order_status(order_id, "approved")
        await update_order_vpn_info(order_id, username, subscription_url)
        if charged:
            # balance was already atomically deducted above; just record the txn.
            # (the old inline path also called add_balance_and_transaction here,
            #  double-charging the wallet — record-only fixes that.)
            await add_transaction(
                user_id, -final_price, "purchase", f"خرید پلن {plan['name']}"
            )
        if discount_code:
            await update_order_discount(order_id, discount_code, discount_amount)
            if discount_code_id:
                await use_discount_code(discount_code_id, user_id)
    except Exception as e:
        # roll back the panel user and the wallet charge so nothing is left dangling
        try:
            await provisioning.remove_service(plan["panel_url"], plan["panel_token"], username)
        except Exception:
            pass
        if charged:
            await add_balance(user_id, final_price)
        return FulfillResult(status="save_error", error=str(e))

    return FulfillResult(
        status="ok",
        username=username,
        subscription_url=subscription_url,
        order_id=order_id,
    )


async def approve(order_id: int, actor: str = "system") -> ApproveResult:
    """Approve a pending order: provision the panel user, store the sub link,
    apply referral rewards. Idempotent — a non-pending order is left untouched."""
    order = await get_order(order_id)
    if not order:
        return ApproveResult(status="not_found")
    if order["status"] != "pending":
        return ApproveResult(status="already_processed")

    plan = await get_plan_with_server(order["plan_id"])
    try:
        stored_ids = json.loads(plan["service_ids"] or "[]")
    except Exception as e:
        return ApproveResult(status="api_error", error=str(e))
    if not stored_ids:
        return ApproveResult(status="no_service_config")

    try:
        result = await provisioning.provision_service(
            plan["panel_url"], plan["panel_token"],
            stored_ids, plan["traffic"],
            duration_days=plan["duration"], ip_limit=plan["ip_limit"],
        )
    except provisioning.NoLiveServiceError:
        return ApproveResult(status="no_live_service")
    except Exception as e:
        return ApproveResult(status="api_error", error=str(e))

    username = result["username"]
    subscription_url = result["subscription_url"]

    try:
        await update_order_status(order_id, "approved")
        await update_order_vpn_info(order_id, username, subscription_url)
    except Exception as e:
        # rollback the just-created panel user so we don't leak an orphan
        try:
            await provisioning.remove_service(plan["panel_url"], plan["panel_token"], username)
        except Exception:
            pass
        return ApproveResult(status="save_error", error=str(e), username=username)

    referrer_notify = await _apply_referral_rewards(order["user_id"], plan["price"])

    return ApproveResult(
        status="ok",
        username=username,
        subscription_url=subscription_url,
        user_id=order["user_id"],
        price=plan["price"],
        referrer_notify=referrer_notify,
    )


async def reject(order_id: int, actor: str = "system", reason: str = None) -> RejectResult:
    """Reject a pending order. Idempotent — a non-pending order is left untouched."""
    order = await get_order(order_id)
    if not order:
        return RejectResult(status="not_found")
    if order["status"] != "pending":
        return RejectResult(status="already_processed")
    await update_order_status(order_id, "rejected", rejection_reason=reason)
    return RejectResult(status="ok", user_id=order["user_id"])


async def _apply_referral_rewards(buyer_id: int, price: int):
    """Credit referral rewards (DB only). Returns (referrer_id, commission) when
    a commission notification should be sent, else None. Sending it is the
    caller's job so this stays free of any Telegram dependency."""
    referral = await get_referral_by_referred(buyer_id)
    if not referral:
        return None
    referrer_id = referral["referrer_id"]
    is_first = not referral["first_purchase_rewarded"]

    cfg_keys = [
        "referral_enabled", "referral_flat_enabled", "referral_flat_amount",
        "referral_percent_enabled", "referral_percent_value",
        "referral_free_test_enabled",
        "referral_discount_enabled", "referral_discount_value",
    ]
    cfg = {k: (await get_setting(k) or "0") for k in cfg_keys}
    if cfg["referral_enabled"] != "1":
        return None

    total_reward = 0

    if is_first:
        if cfg["referral_flat_enabled"] == "1":
            flat = int(cfg["referral_flat_amount"] or "0")
            if flat > 0:
                await add_balance_and_transaction(referrer_id, flat, f"جایزه دعوت کاربر {buyer_id}")
                total_reward += flat

        if cfg["referral_free_test_enabled"] == "1":
            try:
                await decrement_free_test_uses(referrer_id)
            except Exception as e:
                log.error("free test reward for %s failed: %s", referrer_id, e)

        if cfg["referral_discount_enabled"] == "1":
            pct = int(cfg["referral_discount_value"] or "0")
            if pct > 0:
                credit = price * pct // 100
                await add_balance_and_transaction(buyer_id, credit, f"اعتبار خوش‌آمدگویی {pct}٪ اولین خرید")

        await mark_first_purchase_rewarded(buyer_id, total_reward)

    if cfg["referral_percent_enabled"] == "1":
        pct = int(cfg["referral_percent_value"] or "0")
        if pct > 0:
            commission = price * pct // 100
            if commission > 0:
                await add_balance_and_transaction(referrer_id, commission, f"پورسانت {pct}٪ خرید کاربر {buyer_id}")
                await add_referral_commission(buyer_id, commission)
                return (referrer_id, commission)

    return None
