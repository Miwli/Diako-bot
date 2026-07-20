import logging
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states import ExtraVolume, ExtraTime
from shared_lib.db import (
    get_order, get_plan_with_server,
    get_extra_volume_plans, get_extra_volume_plan,
    create_extra_volume_request, update_extra_volume_request,
    get_extra_time_plans, get_extra_time_plan,
    create_extra_time_request, update_extra_time_request,
    get_user_wallet_stats, deduct_balance_if_sufficient, add_transaction,
    get_text,
)
from shared_lib.services import provisioning, extras
from shared_lib.formatters import fmt_traffic_gb

log = logging.getLogger(__name__)


def _alert(key: str, **fmt) -> str:
    # show_alert در تلگرام فقط تا ~۲۰۰ کاراکتر نشون می‌ده
    return get_text(key, **fmt)[:200]


def _plans_kb(plans: list, order_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"📊 {fmt_traffic_gb(p['traffic_gb'])} — {p['price']:,} تومان",
            callback_data=f"ev_plan_{p['id']}_{order_id}",
        )]
        for p in plans
    ]
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"my_service_{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_kb(plan_id: int, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 پرداخت با کیف پول", callback_data=f"ev_wallet_{plan_id}_{order_id}")],
        [InlineKeyboardButton(text="💳 پرداخت با کارت",   callback_data=f"ev_card_{plan_id}_{order_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت",           callback_data=f"extra_volume_{order_id}")],
    ])


def _admin_kb(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تایید",    callback_data=f"evr_approve_{req_id}"),
        InlineKeyboardButton(text="❌ رد کردن",  callback_data=f"evr_reject_{req_id}"),
    ]])


def _et_plans_kb(plans: list, order_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"📅 {p['days']} روز — {p['price']:,} تومان",
            callback_data=f"et_plan_{p['id']}_{order_id}",
        )]
        for p in plans
    ]
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"my_service_{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _et_confirm_kb(plan_id: int, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 پرداخت با کیف پول", callback_data=f"et_wallet_{plan_id}_{order_id}")],
        [InlineKeyboardButton(text="💳 پرداخت با کارت",   callback_data=f"et_card_{plan_id}_{order_id}")],
        [InlineKeyboardButton(text="🔙 بازگشت",           callback_data=f"extra_time_{order_id}")],
    ])


def _et_admin_kb(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ تایید",    callback_data=f"etr_approve_{req_id}"),
        InlineKeyboardButton(text="❌ رد کردن",  callback_data=f"etr_reject_{req_id}"),
    ]])


def register_services_handlers(dp):
    @dp.callback_query(F.data.startswith("extra_volume_"))
    async def extra_volume_open(callback: types.CallbackQuery):
        order_id = int(callback.data.removeprefix("extra_volume_"))
        order = await get_order(order_id)
        if not order or order["user_id"] != callback.from_user.id:
            await callback.answer(_alert("service_not_found"), show_alert=True)
            return
        # سرویس نامحدود حجم اضافه نمی‌پذیرد — add_volume بی‌صدا هیچ کاری نمی‌کند
        plan_data = await get_plan_with_server(order["plan_id"])
        if plan_data:
            try:
                live = await provisioning.get_live_user(plan_data["panel_url"], plan_data["panel_token"], order["vpn_username"])
                if (live.get("data_limit") or 0) == 0:
                    await callback.answer(_alert("extra_volume_unlimited"), show_alert=True)
                    return
            except Exception as e:
                log.error("extra_volume unlimited-check error: %s", e)
        plans = await get_extra_volume_plans()
        if not plans:
            await callback.answer(_alert("extra_volume_no_plans"), show_alert=True)
            return
        await callback.message.edit_text(
            get_text("extra_volume_select"),
            reply_markup=_plans_kb(plans, order_id),
            parse_mode="HTML",
        )

    @dp.callback_query(F.data.startswith("ev_plan_"))
    async def ev_plan_select(callback: types.CallbackQuery):
        _, plan_id_s, order_id_s = callback.data.rsplit("_", 2)
        plan_id, order_id = int(plan_id_s), int(order_id_s)
        plan = await get_extra_volume_plan(plan_id)
        if not plan:
            await callback.answer(_alert("extra_package_not_found"), show_alert=True)
            return
        stats = await get_user_wallet_stats(callback.from_user.id)
        balance_line = ("\n\n" + get_text("extra_volume_balance_line", balance=f"{stats['balance']:,}")) if stats["balance"] > 0 else ""
        await callback.message.edit_text(
            get_text(
                "extra_volume_confirm",
                plan_name=plan["name"],
                traffic=fmt_traffic_gb(plan["traffic_gb"]),
                price=f"{plan['price']:,}",
            ) + balance_line,
            reply_markup=_confirm_kb(plan_id, order_id),
            parse_mode="HTML",
        )

    @dp.callback_query(F.data.startswith("ev_wallet_"))
    async def ev_wallet_pay(callback: types.CallbackQuery):
        _, plan_id_s, order_id_s = callback.data.rsplit("_", 2)
        plan_id, order_id = int(plan_id_s), int(order_id_s)
        plan  = await get_extra_volume_plan(plan_id)
        order = await get_order(order_id)
        if not plan or not order or order["user_id"] != callback.from_user.id:
            await callback.answer(_alert("extra_generic_error"), show_alert=True)
            return
        deducted = await deduct_balance_if_sufficient(callback.from_user.id, plan["price"])
        if not deducted:
            await callback.answer(_alert("wallet_no_balance"), show_alert=True)
            return
        await add_transaction(
            callback.from_user.id, -plan["price"],
            "extra_volume", f"افزودن حجم — {plan['name']}",
        )
        plan_data = await get_plan_with_server(order["plan_id"])
        if not plan_data:
            await callback.message.edit_text(get_text("extra_volume_error"), parse_mode="HTML")
            return
        try:
            await provisioning.extend_volume(plan_data["panel_url"], plan_data["panel_token"], order["vpn_username"], plan["traffic_gb"])
        except Exception as e:
            log.error("ev_wallet add_volume error: %s", e)
            await callback.message.edit_text(get_text("extra_volume_error"), parse_mode="HTML")
            return
        await callback.message.edit_text(
            get_text("extra_volume_success_wallet", traffic=fmt_traffic_gb(plan["traffic_gb"])),
            parse_mode="HTML",
        )

    @dp.callback_query(F.data.startswith("ev_card_"))
    async def ev_card_pay(callback: types.CallbackQuery, state: FSMContext):
        _, plan_id_s, order_id_s = callback.data.rsplit("_", 2)
        plan_id, order_id = int(plan_id_s), int(order_id_s)
        await state.set_state(ExtraVolume.waiting_for_receipt)
        await state.update_data(ev_plan_id=plan_id, ev_order_id=order_id)
        await callback.message.edit_text(
            get_text("extra_volume_ask_receipt"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ انصراف", callback_data=f"ev_plan_{plan_id}_{order_id}")
            ]]),
            parse_mode="HTML",
        )

    @dp.message(ExtraVolume.waiting_for_receipt)
    async def ev_receipt(message: types.Message, state: FSMContext, bot):
        if not message.photo:
            await message.answer(get_text("extra_volume_ask_receipt"))
            return
        data     = await state.get_data()
        plan_id  = data["ev_plan_id"]
        order_id = data["ev_order_id"]
        await state.clear()

        plan = await get_extra_volume_plan(plan_id)
        if not plan:
            await message.answer(get_text("extra_generic_error"))
            return

        receipt_file_id = message.photo[-1].file_id
        req_id = await create_extra_volume_request(message.from_user.id, order_id, plan_id)
        await update_extra_volume_request(req_id, "waiting", receipt_file_id)
        await message.answer(get_text("extra_volume_submitted"), parse_mode="HTML")

        from bot import ADMIN_IDS
        notify_text = get_text(
            "admin_ev_notify",
            req_id=req_id,
            full_name=message.from_user.full_name,
            username_part=f" (@{message.from_user.username})" if message.from_user.username else "",
            user_id=message.from_user.id,
            plan_name=plan["name"],
            traffic=fmt_traffic_gb(plan["traffic_gb"]),
            price=f"{plan['price']:,}",
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_photo(
                    admin_id,
                    photo=receipt_file_id,
                    caption=notify_text,
                    reply_markup=_admin_kb(req_id),
                    parse_mode="HTML",
                )
            except Exception as exc:
                log.error("ev notify admin %s error: %s", admin_id, exc)

    @dp.callback_query(F.data.startswith("evr_approve_"))
    async def evr_approve(callback: types.CallbackQuery, bot):
        req_id = int(callback.data.removeprefix("evr_approve_"))
        res = await extras.approve_volume_request(req_id, actor=f"admin:{callback.from_user.id}")
        if res.status == "not_found":
            await callback.answer("❌ درخواست یافت نشد.", show_alert=True)
            return
        if res.status == "already_processed":
            await callback.answer("⚠️ قبلاً تایید شده.", show_alert=True)
            return
        if res.status == "plan_not_found":
            await callback.answer("❌ سرور یافت نشد.", show_alert=True)
            return
        if res.status == "api_error":
            log.error("evr_approve add_volume error: %s", res.error)
            await callback.answer(f"❌ خطای API: {res.error}", show_alert=True)
            return
        try:
            await callback.message.edit_caption(
                caption=(callback.message.caption or "") + "\n\n✅ <b>تایید شد</b>",
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception:
            pass
        try:
            await bot.send_message(
                res.user_id,
                get_text("extra_volume_approved", traffic=fmt_traffic_gb(res.traffic_gb)),
                parse_mode="HTML",
            )
        except Exception:
            pass

    @dp.callback_query(F.data.startswith("evr_reject_"))
    async def evr_reject(callback: types.CallbackQuery, bot):
        req_id = int(callback.data.removeprefix("evr_reject_"))
        res = await extras.reject_volume_request(req_id, actor=f"admin:{callback.from_user.id}")
        if res.status == "not_found":
            await callback.answer("❌ درخواست یافت نشد.", show_alert=True)
            return
        if res.status == "already_processed":
            await callback.answer("⚠️ قبلاً پردازش شده.", show_alert=True)
            return
        try:
            await callback.message.edit_caption(
                caption=(callback.message.caption or "") + "\n\n❌ <b>رد شد</b>",
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception:
            pass
        try:
            await bot.send_message(
                res.user_id,
                get_text("extra_volume_rejected"),
                parse_mode="HTML",
            )
        except Exception:
            pass

    # ─── افزودن زمان ────────────────────────────────────────────────────────

    @dp.callback_query(F.data.startswith("extra_time_"))
    async def extra_time_open(callback: types.CallbackQuery):
        order_id = int(callback.data.removeprefix("extra_time_"))
        order = await get_order(order_id)
        if not order or order["user_id"] != callback.from_user.id:
            await callback.answer(_alert("service_not_found"), show_alert=True)
            return
        plans = await get_extra_time_plans()
        if not plans:
            await callback.answer(_alert("extra_time_no_plans"), show_alert=True)
            return
        await callback.message.edit_text(
            get_text("extra_time_select"),
            reply_markup=_et_plans_kb(plans, order_id),
            parse_mode="HTML",
        )

    @dp.callback_query(F.data.startswith("et_plan_"))
    async def et_plan_select(callback: types.CallbackQuery):
        plan_id_str, order_id_str = callback.data.removeprefix("et_plan_").split("_", 1)
        plan_id, order_id = int(plan_id_str), int(order_id_str)
        plan = await get_extra_time_plan(plan_id)
        if not plan:
            await callback.answer(_alert("extra_package_not_found"), show_alert=True)
            return
        wallet = await get_user_wallet_stats(callback.from_user.id)
        balance = wallet["balance"] if wallet else 0
        text = get_text(
            "extra_time_confirm",
            plan_name=plan["name"],
            days=plan["days"],
            price=f"{plan['price']:,}",
        )
        text += "\n\n" + get_text("extra_time_balance_line", balance=f"{balance:,}")
        await callback.message.edit_text(
            text,
            reply_markup=_et_confirm_kb(plan_id, order_id),
            parse_mode="HTML",
        )

    @dp.callback_query(F.data.startswith("et_wallet_"))
    async def et_wallet_pay(callback: types.CallbackQuery):
        parts = callback.data.removeprefix("et_wallet_").split("_", 1)
        plan_id, order_id = int(parts[0]), int(parts[1])
        plan = await get_extra_time_plan(plan_id)
        order = await get_order(order_id)
        if not plan or not order:
            await callback.answer(_alert("extra_info_not_found"), show_alert=True)
            return
        ok = await deduct_balance_if_sufficient(callback.from_user.id, plan["price"])
        if not ok:
            await callback.answer(_alert("wallet_no_balance"), show_alert=True)
            return
        await add_transaction(
            user_id=callback.from_user.id,
            amount=-plan["price"],
            description=f"افزودن {plan['days']} روز به سرویس #{order_id}",
        )
        plan_info = await get_plan_with_server(order.get("plan_id"))
        if not plan_info:
            await callback.answer(_alert("extra_time_error"), show_alert=True)
            return
        try:
            await provisioning.extend_time(plan_info["panel_url"], plan_info["panel_token"], order["vpn_username"], plan["days"])
        except Exception as e:
            log.error("extra_time wallet error: %s", e)
            await callback.answer(_alert("extra_time_error"), show_alert=True)
            return
        await callback.message.edit_text(
            get_text("extra_time_success_wallet", days=plan["days"]),
            parse_mode="HTML",
        )

    @dp.callback_query(F.data.startswith("et_card_"))
    async def et_card_pay(callback: types.CallbackQuery, state: FSMContext):
        parts = callback.data.removeprefix("et_card_").split("_", 1)
        plan_id, order_id = int(parts[0]), int(parts[1])
        await state.set_state(ExtraTime.waiting_for_receipt)
        await state.update_data(plan_id=plan_id, order_id=order_id)
        await callback.message.edit_text(
            get_text("extra_time_ask_receipt"),
            parse_mode="HTML",
        )

    @dp.message(ExtraTime.waiting_for_receipt)
    async def et_receipt(message: types.Message, state: FSMContext):
        if not message.photo:
            await message.answer(get_text("extra_send_receipt_photo"))
            return
        data = await state.get_data()
        plan_id, order_id = data["plan_id"], data["order_id"]
        plan = await get_extra_time_plan(plan_id)
        if not plan:
            await message.answer(get_text("extra_package_not_found"))
            await state.clear()
            return
        file_id = message.photo[-1].file_id
        req_id = await create_extra_time_request(message.from_user.id, order_id, plan_id)
        await update_extra_time_request(req_id, "pending", file_id)
        await state.clear()
        await message.answer(get_text("extra_time_submitted"), parse_mode="HTML")
        user = message.from_user
        username_part = f" (@{user.username})" if user.username else ""
        admin_text = get_text(
            "admin_et_notify",
            req_id=req_id,
            full_name=user.full_name,
            username_part=username_part,
            user_id=user.id,
            plan_name=plan["name"],
            days=plan["days"],
            price=f"{plan['price']:,}",
        )
        from bot import bot, ADMIN_IDS
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_photo(
                    admin_id,
                    photo=file_id,
                    caption=admin_text,
                    reply_markup=_et_admin_kb(req_id),
                    parse_mode="HTML",
                )
            except Exception:
                pass

    @dp.callback_query(F.data.startswith("etr_approve_"))
    async def etr_approve(callback: types.CallbackQuery):
        from bot import bot
        req_id = int(callback.data.removeprefix("etr_approve_"))
        res = await extras.approve_time_request(req_id, actor=f"admin:{callback.from_user.id}")
        if res.status == "not_found":
            await callback.answer("❌ درخواست یافت نشد.", show_alert=True)
            return
        if res.status == "already_processed":
            await callback.answer("⚠️ قبلاً پردازش شده.", show_alert=True)
            return
        if res.status == "plan_not_found":
            await callback.answer(_alert("plan_service_not_found"), show_alert=True)
            return
        if res.status == "api_error":
            log.error("etr_approve error: %s", res.error)
            await callback.answer(_alert("extra_time_error"), show_alert=True)
            return
        try:
            await callback.message.edit_caption(
                caption=(callback.message.caption or "") + "\n\n✅ <b>تایید شد</b>",
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception:
            pass
        try:
            await bot.send_message(
                res.user_id,
                get_text("extra_time_approved", days=res.days),
                parse_mode="HTML",
            )
        except Exception:
            pass

    @dp.callback_query(F.data.startswith("etr_reject_"))
    async def etr_reject(callback: types.CallbackQuery):
        from bot import bot
        req_id = int(callback.data.removeprefix("etr_reject_"))
        res = await extras.reject_time_request(req_id, actor=f"admin:{callback.from_user.id}")
        if res.status == "not_found":
            await callback.answer("❌ درخواست یافت نشد.", show_alert=True)
            return
        if res.status == "already_processed":
            await callback.answer("⚠️ قبلاً پردازش شده.", show_alert=True)
            return
        try:
            await callback.message.edit_caption(
                caption=(callback.message.caption or "") + "\n\n❌ <b>رد شد</b>",
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception:
            pass
        try:
            await bot.send_message(
                res.user_id,
                get_text("extra_time_rejected"),
                parse_mode="HTML",
            )
        except Exception:
            pass
