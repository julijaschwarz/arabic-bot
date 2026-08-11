"""Мидлвари: доступ, регистрация пользователя, отметка активности.

Отметка активности нужна напоминаниям: «не было активности 6 часов» считается
именно по этой записи.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Chat, Message, TelegramObject, Update, User as TgUser

from ..storage.repositories import UserRepo
from . import texts

log = logging.getLogger(__name__)


def _inner_event(event: TelegramObject) -> TelegramObject:
    """Мидлварь висит на уровне Update — до конкретного события надо дойти."""
    return event.event if isinstance(event, Update) else event


class AccessMiddleware(BaseMiddleware):
    """Пускает только тех, кто в whitelist. Пустой список — пускать всех."""

    def __init__(self, allowed: frozenset[int]) -> None:
        self._allowed = allowed

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: TgUser | None = data.get("event_from_user")
        if user is None:
            return None
        if self._allowed and user.id not in self._allowed:
            log.warning("Отклонён пользователь %s (%s)", user.id, user.username)
            inner = _inner_event(event)
            if isinstance(inner, Message):
                await inner.answer(texts.NOT_ALLOWED)
            elif isinstance(inner, CallbackQuery):
                await inner.answer(texts.NOT_ALLOWED, show_alert=True)
            return None
        return await handler(event, data)


class ActivityMiddleware(BaseMiddleware):
    """Регистрирует пользователя при первом обращении и обновляет время активности."""

    def __init__(self, users: UserRepo) -> None:
        self._users = users

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: TgUser | None = data.get("event_from_user")
        chat: Chat | None = data.get("event_chat")
        if user is not None and chat is not None:
            # Регистрация здесь, а не в /start: иначе рассылка и напоминания
            # не знали бы, кому писать.
            await self._users.ensure(user.id, chat.id, user.first_name or "")
            await self._users.touch_activity(user.id)
        return await handler(event, data)
