"""Сборка приложения.

Все зависимости создаются здесь и передаются в хендлеры через workflow-данные
диспетчера. Глобальных объектов нет: тесты собирают своё приложение с другими
настройками, ничего не переопределяя.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from random import Random

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from ..config import Settings
from ..domain.lexicon import Lexicon
from ..learning.planner import SessionPlanner
from ..learning.service import LessonService
from ..media.images import ImageRenderer
from ..scheduler.jobs import Jobs
from ..storage.db import Database
from ..storage.repositories import AnswerRepo, ProgressRepo, SessionRepo, UserRepo
from .handlers import commands, session
from .middlewares import AccessMiddleware, ActivityMiddleware
from .presenter import Presenter

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Application:
    settings: Settings
    bot: Bot
    dispatcher: Dispatcher
    database: Database
    jobs: Jobs

    async def run(self) -> None:
        self.jobs.start()
        try:
            await self.dispatcher.start_polling(self.bot, handle_signals=True)
        finally:
            self.jobs.shutdown()
            await self.bot.session.close()
            await self.database.close()


async def build(
    settings: Settings, *, rng: Random | None = None, bot: Bot | None = None
) -> Application:
    """Собрать приложение. `bot` подменяется в тестах на записывающий двойник."""
    settings.ensure_dirs()

    database = Database(settings.db_path)
    await database.connect()

    users = UserRepo(database)
    progress = ProgressRepo(database)
    sessions = SessionRepo(database)
    answers = AnswerRepo(database)

    lexicon = Lexicon.load()
    planner = SessionPlanner(lexicon, rng)
    service = LessonService(
        settings,
        users=users,
        progress=progress,
        sessions=sessions,
        answers=answers,
        planner=planner,
    )

    images = ImageRenderer(settings.image_cache_dir, enabled=settings.images_enabled)
    presenter = Presenter(images)

    bot = bot or Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dispatcher = Dispatcher(
        settings=settings,
        service=service,
        presenter=presenter,
        users=users,
        progress=progress,
        answers=answers,
    )
    dispatcher.update.outer_middleware(AccessMiddleware(settings.allowed_ids))
    dispatcher.update.outer_middleware(ActivityMiddleware(users))
    dispatcher.include_router(commands.create_router())
    dispatcher.include_router(session.create_router())

    jobs = Jobs(settings, bot, users, service, presenter)

    log.info(
        "Готово: %d генераторов заданий, %d слов, картинки %s",
        len(planner.generators),
        len(lexicon),
        "вкл" if images.enabled else "выкл",
    )
    return Application(
        settings=settings, bot=bot, dispatcher=dispatcher, database=database, jobs=jobs
    )
