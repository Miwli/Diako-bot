from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from shared_lib.db import get_setting, get_text
from keyboards import force_join_keyboard
from force_join_check import get_missing_channels


class ForceJoinMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        if user is None:
            return await handler(event, data)

        from bot import is_admin
        if is_admin(user.id):
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "check_force_join":
            return await handler(event, data)

        enabled = await get_setting("force_join_enabled")
        if enabled != "1":
            return await handler(event, data)

        missing = await get_missing_channels(event.bot, user.id)
        if not missing:
            return await handler(event, data)

        text = get_text("force_join_prompt")
        markup = force_join_keyboard(missing)
        if isinstance(event, CallbackQuery):
            await event.answer()
            try:
                await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
            except Exception:
                await event.message.answer(text, reply_markup=markup, parse_mode="HTML")
        elif isinstance(event, Message):
            await event.answer(text, reply_markup=markup, parse_mode="HTML")
        return None
