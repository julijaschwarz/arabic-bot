"""Сервис занятия — вся логика урока в одном месте.

Хендлеры Telegram только показывают то, что вернул сервис, и не принимают
решений сами. Благодаря этому урок целиком проверяется тестами без Telegram.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, replace

from ..config import Settings
from ..domain.letters import BY_ID
from ..domain.models import Exercise, Verdict
from ..exercises.checkers import check
from ..storage.repositories import (
    AnswerRepo,
    ProgressRepo,
    Session,
    SessionRepo,
    UserRepo,
    utcnow,
)
from . import focus as focus_module
from . import srs
from .planner import SessionPlanner

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Outcome:
    """Что произошло после ответа."""

    verdict: Verdict
    exercise: Exercise
    session_finished: bool = False
    attempts: int = 1
    """Сколько попыток ушло на этот вопрос — нужно, чтобы отчёт не врал."""

    @property
    def first_try(self) -> bool:
        return self.attempts == 1


@dataclass(frozen=True, slots=True)
class Summary:
    total: int
    correct: int
    cycle_no: int
    fresh_left: int


class LessonService:
    def __init__(
        self,
        settings: Settings,
        *,
        users: UserRepo,
        progress: ProgressRepo,
        sessions: SessionRepo,
        answers: AnswerRepo,
        planner: SessionPlanner,
    ) -> None:
        self._settings = settings
        self._users = users
        self._progress = progress
        self._sessions = sessions
        self._answers = answers
        self._planner = planner

    # --- запуск ---

    async def start(self, user_id: int, *, count: int | None = None, kind: str = "daily") -> Session:
        await self._progress.ensure_rows(user_id)
        now = utcnow()

        stored = await self._progress.all(user_id)
        focus = focus_module.choose(
            stored, count=self._settings.focus_letters_per_day, now=now
        )
        if focus.new_cycle_started:
            # Сброс обязателен: без него круг «закрывался» бы каждый день заново.
            await self._progress.start_new_cycle(user_id)
            log.info("Пользователь %s начал круг №%d", user_id, focus.cycle_no)

        user = await self._users.get(user_id)
        planned = count or (user.tasks_per_day if user else None) or self._settings.daily_task_count

        return await self._sessions.create(
            user_id,
            planned_count=planned,
            focus_letters=[letter.id for letter in focus.letters],
            kind=kind,
        )

    async def active_session(self, user_id: int) -> Session | None:
        return await self._sessions.active(user_id)

    # --- ход занятия ---

    async def next_exercise(self, user_id: int) -> Exercise | None:
        """Следующий вопрос, либо None — значит, сессия дня закончена."""
        session = await self._sessions.active(user_id)
        if session is None:
            return None
        if session.current_exercise is not None:
            return session.current_exercise
        if session.position >= session.planned_count:
            await self._sessions.finish(session.id)
            return None

        exercise = self._planner.next_exercise(
            tuple(BY_ID[letter_id] for letter_id in session.focus_letters),
            position=session.position,
            last_generator_id=session.last_generator_id,
            images_enabled=self._settings.images_enabled,
        )
        if exercise is None:
            await self._sessions.finish(session.id)
            return None

        await self._sessions.set_current(session.id, exercise)
        return exercise

    async def submit(self, user_id: int, raw: str) -> Outcome | None:
        session = await self._sessions.active(user_id)
        if session is None or session.current_exercise is None:
            return None

        exercise = session.current_exercise
        verdict = check(exercise, raw)
        await self._sessions.add_attempt(session.id)
        attempts = session.current_attempts + 1

        if not verdict.correct:
            return Outcome(verdict=verdict, exercise=exercise, attempts=attempts)

        # Ответ с первой попытки укрепляет букву; со второй — только не сбрасывает.
        await self._record(session, exercise, correct=True, strong=attempts == 1, revealed=False)
        finished = await self._close(session, correct=True)
        return Outcome(
            verdict=verdict, exercise=exercise, session_finished=finished, attempts=attempts
        )

    async def reveal(self, user_id: int) -> Outcome | None:
        """Показать ответ — засчитывается как ошибка, буква вернётся раньше."""
        session = await self._sessions.active(user_id)
        if session is None or session.current_exercise is None:
            return None

        exercise = session.current_exercise
        await self._record(session, exercise, correct=False, strong=False, revealed=True)
        finished = await self._close(session, correct=False)
        return Outcome(
            verdict=Verdict(False),
            exercise=exercise,
            session_finished=finished,
            attempts=session.current_attempts + 1,
        )

    async def extend(self, user_id: int, extra: int) -> Session | None:
        """Добавить вопросов к последней сессии — кнопка «Ещё 5 заданий»."""
        session = await self._sessions.active(user_id) or await self._sessions.last(user_id)
        if session is None:
            return None
        await self._sessions.extend(session.id, extra)
        return await self._sessions.by_id(session.id)

    async def finished_today(self, user_id: int, *, since: dt.datetime) -> bool:
        """Закончил ли пользователь хотя бы одну сессию с начала суток."""
        return await self._sessions.completed_today(user_id, since) > 0

    async def stop(self, user_id: int) -> None:
        session = await self._sessions.active(user_id)
        if session is not None:
            await self._sessions.finish(session.id)

    # --- сводка ---

    async def summary(self, user_id: int) -> Summary:
        session = await self._sessions.active(user_id) or await self._sessions.last(user_id)
        stored = await self._progress.all(user_id)
        cycle_no = max((item.cycle_no for item in stored.values()), default=1)
        fresh_left = sum(1 for item in stored.values() if not item.seen_in_cycle)
        return Summary(
            total=session.planned_count if session else 0,
            correct=session.correct_count if session else 0,
            cycle_no=cycle_no,
            fresh_left=fresh_left,
        )

    # --- внутреннее ---

    async def _close(self, session: Session, *, correct: bool) -> bool:
        await self._sessions.close_question(session.id, correct=correct)
        finished = session.position >= session.planned_count
        if finished:
            await self._sessions.finish(session.id)
        return finished

    async def _record(
        self,
        session: Session,
        exercise: Exercise,
        *,
        correct: bool,
        strong: bool,
        revealed: bool,
    ) -> None:
        now = utcnow()
        stored = await self._progress.all(session.user_id)
        for letter_id in exercise.focus_letters:
            item = stored.get(letter_id)
            if item is None:
                continue
            updated = srs.review(item, correct=correct and strong, now=now)
            if correct and not strong:
                # Ответ со второй попытки: букву не наказываем, но и не удлиняем интервал.
                updated = replace(updated, interval_days=item.interval_days or 1.0)
            await self._progress.save(session.user_id, updated)

        await self._answers.add(
            session_id=session.id,
            user_id=session.user_id,
            generator_id=exercise.generator_id,
            focus_letters=exercise.focus_letters,
            correct=correct,
            attempts=session.current_attempts + 1,
            revealed=revealed,
        )
