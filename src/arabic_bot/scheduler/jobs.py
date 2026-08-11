"""Расписание: утреннее занятие и напоминание при простое.

Оба задания живут внутри процесса бота (APScheduler), отдельный контейнер не нужен.

Главное здесь — устойчивость к спящему компьютеру. По умолчанию APScheduler
отбрасывает задание, опоздавшее больше чем на секунду (`misfire_grace_time=1`),
а на ноутбуке, который засыпает, опаздывает буквально каждое. Поэтому:
  * задания заводятся с большим запасом по опозданию и с `coalesce`;
  * утренняя рассылка не полагается только на срабатывание в 09:00 — она
    догоняется на каждой проверке простоя, если за сегодня ещё не уходила.
"""

from __future__ import annotations

import datetime as dt
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..bot import keyboards, texts
from ..bot.presenter import Presenter
from ..config import Settings
from ..learning.service import LessonService
from ..storage.repositories import User, UserRepo, utcnow

log = logging.getLogger(__name__)

HEARTBEAT_MINUTES = 1

STARTUP_DELAY = 30
"""Через сколько секунд после запуска пройдёт первая проверка."""

MISFIRE_GRACE_SECONDS = 3600
"""Сколько задание может опоздать и всё-таки выполниться.

Час — осознанный запас: ноутбук просыпается, и занятие лучше прислать с
задержкой, чем не прислать совсем. Опоздания больше часа догоняет проверка
простоя, ей не нужен точный момент.
"""


class Jobs:
    def __init__(
        self,
        settings: Settings,
        bot: Bot,
        users: UserRepo,
        service: LessonService,
        presenter: Presenter,
    ) -> None:
        self._settings = settings
        self._bot = bot
        self._users = users
        self._service = service
        self._presenter = presenter
        self._scheduler = AsyncIOScheduler(timezone=settings.tz)

    def start(self) -> None:
        daily = self._settings.daily_at
        self._scheduler.add_job(
            self.daily_session,
            CronTrigger(hour=daily.hour, minute=daily.minute, timezone=self._settings.tz),
            id="daily_session",
            replace_existing=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
            coalesce=True,
        )
        self._scheduler.add_job(
            self.idle_nudge,
            IntervalTrigger(minutes=self._settings.idle_check_minutes),
            id="idle_nudge",
            replace_existing=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
            coalesce=True,
            # Первая проверка — сразу после старта, а не через полчаса: бот часто
            # поднимается уже после того, как компьютер проспал утро.
            next_run_time=dt.datetime.now(self._settings.tz) + dt.timedelta(seconds=STARTUP_DELAY),
        )
        self._scheduler.add_job(
            self.heartbeat,
            IntervalTrigger(minutes=HEARTBEAT_MINUTES),
            id="heartbeat",
            replace_existing=True,
            misfire_grace_time=MISFIRE_GRACE_SECONDS,
            coalesce=True,
        )
        self._scheduler.start()
        log.info(
            "Расписание: занятие в %s (%s), проверка простоя каждые %d мин",
            self._settings.daily_time,
            self._settings.timezone,
            self._settings.idle_check_minutes,
        )

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    @property
    def scheduler(self) -> AsyncIOScheduler:
        """Нужен тестам: настройки заданий — часть поведения, а не деталь."""
        return self._scheduler

    # --- задания ---

    async def daily_session(self) -> None:
        """Срабатывание в назначенный час. Быстрый путь, не единственный."""
        await self.send_due_lessons()

    async def idle_nudge(self) -> None:
        """Проверка каждые N минут: догнать рассылку и напомнить при простое."""
        # Кому только что ушло занятие — тем напоминание уже ни к чему: после
        # долгого простоя иначе прилетали бы сразу два сообщения подряд.
        await self.nudge_idle(skip=await self.send_due_lessons())

    async def send_due_lessons(self) -> set[int]:
        """Отправить занятие тем, кому оно на сегодня причитается, но не уходило.

        Возвращает id тех, кому занятие ушло прямо сейчас.
        """
        now = utcnow()
        local = now.astimezone(self._settings.tz)
        today = local.date().isoformat()
        sent: set[int] = set()

        for user in await self._users.all():
            if user.last_daily_on == today:
                continue
            if not self._time_has_come(user, local):
                continue
            if self._settings.is_quiet_now(now):
                continue

            # Уже занимались сегодня — навязывать ещё одну сессию незачем.
            if await self._service.finished_today(user.user_id, since=_local_midnight(local)):
                await self._users.mark_daily_sent(user.user_id, today)
                continue

            try:
                await self._send_lesson(user)
                await self._users.mark_daily_sent(user.user_id, today)
                sent.add(user.user_id)
                log.info("Занятие дня отправлено пользователю %s", user.user_id)
            except Exception:  # noqa: BLE001
                log.exception("Не удалось отправить занятие пользователю %s", user.user_id)

        return sent

    async def nudge_idle(self, skip: set[int] | None = None) -> None:
        """«Пора повторить арабский!» — если тишина дольше заданного порога."""
        now = utcnow()
        idle = dt.timedelta(hours=self._settings.idle_hours)
        skip = skip or set()

        for user in await self._users.all():
            if user.user_id in skip or not user.notifications_on:
                continue
            if self._settings.is_quiet_now(now):
                continue
            if user.last_activity_at and now - user.last_activity_at < idle:
                continue
            if user.last_nudge_at and now - user.last_nudge_at < idle:
                continue

            try:
                await self._bot.send_message(
                    user.chat_id, texts.NUDGE, reply_markup=keyboards.start_session("Начать")
                )
                await self._users.mark_nudged(user.user_id)
                log.info("Напоминание отправлено пользователю %s", user.user_id)
            except Exception:  # noqa: BLE001
                log.exception("Не удалось напомнить пользователю %s", user.user_id)

    async def heartbeat(self) -> None:
        """Отметка живости для healthcheck контейнера."""
        try:
            self._settings.heartbeat_path.write_text(utcnow().isoformat())
        except OSError:
            log.warning("Не удалось обновить heartbeat")

    # --- внутреннее ---

    def _time_has_come(self, user: User, local: dt.datetime) -> bool:
        raw = user.daily_time or self._settings.daily_time
        hour, _, minute = raw.partition(":")
        return (local.hour, local.minute) >= (int(hour), int(minute or 0))

    async def _send_lesson(self, user: User) -> None:
        from ..bot.handlers.commands import start_lesson

        await start_lesson(
            self._bot, user.chat_id, user.user_id, self._service, self._presenter
        )


def _local_midnight(local: dt.datetime) -> dt.datetime:
    return local.replace(hour=0, minute=0, second=0, microsecond=0)
