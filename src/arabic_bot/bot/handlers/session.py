"""Ход занятия: ответы, повтор, показ ответа, переход к следующему вопросу."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from ...learning.service import LessonService
from .. import keyboards, texts
from ..presenter import Presenter
from .commands import start_lesson

log = logging.getLogger(__name__)

STALE_QUERY_MARKERS = ("query is too old", "query ID is invalid", "response timeout expired")


async def ack(callback: CallbackQuery, text: str | None = None) -> None:
    """Подтвердить нажатие, не падая на устаревшем запросе.

    Кнопка, нажатая пока бот был недоступен, приходит с истёкшим query id.
    Telegram отвечает ошибкой, и раньше на ней умирал весь хендлер — то есть
    само действие пользователя терялось. Само действие важнее подтверждения.
    """
    try:
        await callback.answer(text)
    except TelegramBadRequest as error:
        if not any(marker in str(error) for marker in STALE_QUERY_MARKERS):
            raise
        log.info("Устаревшее нажатие кнопки, продолжаю без подтверждения")


async def drop_keyboard(callback: CallbackQuery) -> None:
    """Убрать кнопки у сообщения. Старое сообщение изменить нельзя — и не нужно."""
    if callback.message is None:
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest as error:
        log.debug("Не удалось убрать кнопки: %s", error)


async def handle_answer(
    bot: Bot,
    chat_id: int,
    user_id: int,
    raw: str,
    service: LessonService,
    presenter: Presenter,
) -> None:
    """Проверить ответ и либо пойти дальше, либо предложить повтор."""
    outcome = await service.submit(user_id, raw)
    if outcome is None:
        await bot.send_message(chat_id, texts.NO_SESSION, reply_markup=keyboards.start_session())
        return

    if outcome.verdict.correct:
        await bot.send_message(
            chat_id, texts.outcome_text(correct=True, attempts=outcome.attempts)
        )
        if outcome.session_finished:
            await presenter.send_summary(bot, chat_id, user_id, service)
        else:
            await presenter.advance(bot, chat_id, user_id, service)
        return

    await bot.send_message(
        chat_id,
        texts.outcome_text(correct=False, comment=outcome.verdict.comment),
        reply_markup=keyboards.after_wrong(),
    )


def create_router() -> Router:
    """Свежий роутер на каждый вызов: aiogram запрещает переиспользовать один."""
    router = Router(name="session")

    @router.callback_query(F.data == keyboards.START_SESSION)
    async def on_start(
        callback: CallbackQuery, bot: Bot, service: LessonService, presenter: Presenter
    ) -> None:
        await ack(callback)
        await start_lesson(
            bot, callback.message.chat.id, callback.from_user.id, service, presenter
        )

    @router.callback_query(F.data == keyboards.MORE)
    async def on_more(
        callback: CallbackQuery, bot: Bot, service: LessonService, presenter: Presenter
    ) -> None:
        await ack(callback)
        session = await service.extend(callback.from_user.id, 5)
        if session is None:
            await start_lesson(
                bot, callback.message.chat.id, callback.from_user.id, service, presenter
            )
            return
        await presenter.advance(bot, callback.message.chat.id, callback.from_user.id, service)

    @router.callback_query(F.data == keyboards.RETRY)
    async def on_retry(callback: CallbackQuery) -> None:
        await ack(callback)
        await drop_keyboard(callback)
        await callback.message.answer("Жду ваш ответ ✍️")

    @router.callback_query(F.data.in_({keyboards.REVEAL, keyboards.SKIP}))
    async def on_reveal(
        callback: CallbackQuery, bot: Bot, service: LessonService, presenter: Presenter
    ) -> None:
        await ack(callback)
        outcome = await service.reveal(callback.from_user.id)
        if outcome is None:
            await callback.message.answer(texts.NO_SESSION)
            return

        await drop_keyboard(callback)

        # После показа ответа не спешим: даём прочитать, послушать и нажать «Дальше».
        finished = outcome.session_finished
        await presenter.send_explanation(
            bot,
            callback.message.chat.id,
            outcome.exercise,
            markup=None if finished else keyboards.after_reveal(),
        )
        if finished:
            await presenter.send_summary(
                bot, callback.message.chat.id, callback.from_user.id, service
            )

    @router.callback_query(F.data == keyboards.NEXT)
    async def on_next(
        callback: CallbackQuery, bot: Bot, service: LessonService, presenter: Presenter
    ) -> None:
        await ack(callback)
        session = await service.active_session(callback.from_user.id)
        if session is None:
            await presenter.send_summary(
                bot, callback.message.chat.id, callback.from_user.id, service
            )
            return
        await presenter.advance(bot, callback.message.chat.id, callback.from_user.id, service)

    @router.callback_query(F.data.startswith(f"{keyboards.ANSWER_PREFIX}:"))
    async def on_choice(
        callback: CallbackQuery, bot: Bot, service: LessonService, presenter: Presenter
    ) -> None:
        key = callback.data.split(":", 1)[1]
        await ack(callback)
        await handle_answer(
            bot, callback.message.chat.id, callback.from_user.id, key, service, presenter
        )

    @router.message(F.text)
    async def on_text(
        message: Message, bot: Bot, service: LessonService, presenter: Presenter
    ) -> None:
        session = await service.active_session(message.from_user.id)
        if session is None or session.current_exercise is None:
            await message.answer(texts.NO_SESSION, reply_markup=keyboards.start_session())
            return
        await handle_answer(
            bot, message.chat.id, message.from_user.id, message.text, service, presenter
        )

    return router
