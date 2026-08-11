"""Показ заданий в чате: текст либо картинка с подписью, кнопки.

Отделено от хендлеров, потому что вопрос отправляется из четырёх мест:
команда /go, кнопка «Дальше», утренняя рассылка и напоминание.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup

from ..domain.models import Exercise
from ..learning.service import LessonService
from ..media.images import ImageRenderer
from . import keyboards, texts

log = logging.getLogger(__name__)

CAPTION_LIMIT = 1024
"""Ограничение Telegram на подпись к медиа."""


class Presenter:
    def __init__(self, images: ImageRenderer) -> None:
        self._images = images

    async def send_question(
        self, bot: Bot, chat_id: int, exercise: Exercise, *, position: int, total: int
    ) -> None:
        photo = self._render(exercise)
        caption = texts.question_text(
            exercise, position, total, textual_fallback=photo is None
        )
        markup = keyboards.question(exercise)

        if photo is not None and len(caption) <= CAPTION_LIMIT:
            await bot.send_photo(
                chat_id, FSInputFile(photo), caption=caption, reply_markup=markup
            )
            return
        await bot.send_message(chat_id, caption, reply_markup=markup)

    async def send_explanation(
        self, bot: Bot, chat_id: int, exercise: Exercise, *, markup: InlineKeyboardMarkup | None
    ) -> None:
        await bot.send_message(
            chat_id, f"{texts.REVEALED} {exercise.explanation}", reply_markup=markup
        )

    async def advance(
        self, bot: Bot, chat_id: int, user_id: int, service: LessonService
    ) -> bool:
        """Показать следующий вопрос. False — занятие закончилось."""
        exercise = await service.next_exercise(user_id)
        if exercise is None:
            await self.send_summary(bot, chat_id, user_id, service)
            return False

        session = await service.active_session(user_id)
        position = session.position if session else 1
        total = session.planned_count if session else position
        await self.send_question(bot, chat_id, exercise, position=position, total=total)
        return True

    async def send_summary(
        self, bot: Bot, chat_id: int, user_id: int, service: LessonService
    ) -> None:
        summary = await service.summary(user_id)
        await bot.send_message(
            chat_id,
            texts.SESSION_DONE.format(
                correct=summary.correct,
                total=summary.total,
                percent=texts.percent(summary.correct, summary.total),
                cycle=summary.cycle_no,
                fresh_left=summary.fresh_left,
            ),
            reply_markup=keyboards.session_finished(),
        )

    # --- внутреннее ---

    def _render(self, exercise: Exercise) -> Path | None:
        if exercise.image is None or not self._images.enabled:
            return None
        return self._images.render_word(
            exercise.image.text,
            highlight=exercise.image.highlight,
            caption=exercise.image.caption,
            font_size=exercise.image.font_size,
        )
