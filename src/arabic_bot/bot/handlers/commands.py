"""Команды: /start, /go, /more, /stats, /settings, /stop, /help."""

from __future__ import annotations

import datetime as dt
import re

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from ...config import Settings
from ...domain.digits import DIGITS
from ...domain.letters import BY_ID, LETTERS
from ...learning.service import LessonService
from ...storage.repositories import AnswerRepo, ProgressRepo, UserRepo, utcnow
from .. import keyboards, texts
from ..presenter import Presenter

TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


async def start_lesson(
    bot: Bot, chat_id: int, user_id: int, service: LessonService, presenter: Presenter
) -> None:
    """Общая точка входа: используется и командой, и кнопкой, и расписанием."""
    active = await service.active_session(user_id)
    if active is not None and active.current_exercise is not None:
        await bot.send_message(chat_id, texts.ALREADY_RUNNING)
        await presenter.send_question(
            bot,
            chat_id,
            active.current_exercise,
            position=active.position,
            total=active.planned_count,
        )
        return

    session = await service.start(user_id)
    letters = ", ".join(BY_ID[letter_id].char for letter_id in session.focus_letters)
    await bot.send_message(chat_id, texts.SESSION_START.format(letters=letters))
    await presenter.advance(bot, chat_id, user_id, service)


def create_router() -> Router:
    """Свежий роутер на каждый вызов: aiogram запрещает переиспользовать один."""
    router = Router(name="commands")

    @router.message(CommandStart())
    async def cmd_start(message: Message, settings: Settings) -> None:
        await message.answer(
            texts.START.format(count=settings.daily_task_count),
            reply_markup=keyboards.start_session(),
        )


    @router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(texts.HELP)


    @router.message(Command("go"))
    async def cmd_go(
        message: Message, bot: Bot, service: LessonService, presenter: Presenter
    ) -> None:
        await start_lesson(bot, message.chat.id, message.from_user.id, service, presenter)


    @router.message(Command("more"))
    async def cmd_more(
        message: Message, bot: Bot, service: LessonService, presenter: Presenter
    ) -> None:
        session = await service.extend(message.from_user.id, 5)
        if session is None:
            await start_lesson(bot, message.chat.id, message.from_user.id, service, presenter)
            return
        await presenter.advance(bot, message.chat.id, message.from_user.id, service)


    @router.message(Command("stop"))
    async def cmd_stop(message: Message, service: LessonService) -> None:
        await service.stop(message.from_user.id)
        await message.answer("Занятие остановлено. Вернуться — /go")


    @router.message(Command("stats"))
    async def cmd_stats(
        message: Message, progress: ProgressRepo, answers: AnswerRepo
    ) -> None:
        user_id = message.from_user.id
        await progress.ensure_rows(user_id)
        stored = await progress.all(user_id)

        cycle = max((item.cycle_no for item in stored.values()), default=1)
        seen = sum(1 for item in stored.values() if item.seen_in_cycle)

        now = utcnow()
        week = await answers.summary(user_id, now - dt.timedelta(days=7))
        forever = await answers.summary(user_id, now - dt.timedelta(days=3650))

        body = texts.STATS.format(
            cycle=cycle,
            seen=seen,
            week_total=week["total"],
            week_correct=week["correct"],
            week_percent=texts.percent(week["correct"], week["total"]),
            all_total=forever["total"],
            all_correct=forever["correct"],
            all_percent=texts.percent(forever["correct"], forever["total"]),
        )

        hardest = await answers.hardest_letters(user_id)
        if hardest:
            lines = "\n".join(
                f"{BY_ID[letter_id].char} {BY_ID[letter_id].name_ru} — "
                f"{texts.percent(correct, seen_count)}% верно"
                for letter_id, seen_count, correct in hardest
                if letter_id in BY_ID
            )
            body += texts.STATS_HARD.format(letters=lines) if lines else texts.STATS_EMPTY
        else:
            body += texts.STATS_EMPTY

        await message.answer(body)


    @router.message(Command("settings"))
    async def cmd_settings(
        message: Message, command: CommandObject, settings: Settings, users: UserRepo
    ) -> None:
        user_id = message.from_user.id
        args = (command.args or "").split()

        if len(args) >= 2:
            key, value = args[0].lower(), args[1]
            if key == "time":
                if not TIME_RE.match(value):
                    await message.answer(texts.SETTINGS_BAD_TIME)
                    return
                await users.update(user_id, daily_time=value)
            elif key == "count":
                if not value.isdigit() or not 1 <= int(value) <= 50:
                    await message.answer(texts.SETTINGS_BAD_COUNT)
                    return
                await users.update(user_id, tasks_per_day=int(value))
            elif key == "notify":
                await users.update(user_id, notifications_on=int(value.lower() in {"on", "вкл", "1"}))
            else:
                await message.answer(texts.HELP)
                return
            await message.answer(texts.SETTINGS_SAVED)

        user = await users.get(user_id)
        await message.answer(
            texts.SETTINGS.format(
                count=(user.tasks_per_day if user else None) or settings.daily_task_count,
                time=(user.daily_time if user else None) or settings.daily_time,
                tz=settings.timezone,
                notifications="включены" if (user is None or user.notifications_on) else "выключены",
            )
        )


    @router.message(Command("digits"))
    async def cmd_digits(message: Message) -> None:
        """Шпаргалка по цифрам — без неё задания на названия не выучить."""
        lines = [
            f"{digit.char}  {digit.value}  — {digit.name_ru} ({digit.name_en}), {digit.name_ar}"
            for digit in DIGITS
        ]
        await message.answer(
            "<b>Цифры</b>\nзнак · значение · название\n<pre>" + "\n".join(lines) + "</pre>"
        )

    @router.message(Command("letters"))
    async def cmd_letters(message: Message) -> None:
        """Шпаргалка по алфавиту — полезно держать под рукой."""
        lines = [
            f"{letter.char}  {letter.initial} {letter.medial} {letter.final}  — {letter.name_ru}"
            + ("  •" if not letter.connects_forward else "")
            for letter in LETTERS
        ]
        await message.answer(
            "<b>Алфавит</b>\nотдельно · начало · середина · конец\n"
            "<pre>" + "\n".join(lines) + "</pre>\n"
            "• — буква не соединяется со следующей"
        )

    return router
