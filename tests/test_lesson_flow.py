"""Сквозной прогон урока через настоящую SQLite — без Telegram."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from arabic_bot.config import Settings
from arabic_bot.domain.lexicon import Lexicon
from arabic_bot.learning.planner import SessionPlanner
from arabic_bot.learning.service import LessonService
from arabic_bot.storage.db import Database
from arabic_bot.storage.repositories import AnswerRepo, ProgressRepo, SessionRepo, UserRepo

USER_ID = 4242
CHAT_ID = 4242


@pytest.fixture
async def lesson(tmp_path: Path):
    settings = Settings(
        BOT_TOKEN="test:token",
        DATA_DIR=str(tmp_path),
        DB_PATH=str(tmp_path / "test.db"),
        DAILY_TASK_COUNT="5",
        IMAGES_ENABLED="false",
    )
    database = Database(settings.db_path)
    await database.connect()

    users = UserRepo(database)
    progress = ProgressRepo(database)
    sessions = SessionRepo(database)
    answers = AnswerRepo(database)
    await users.ensure(USER_ID, CHAT_ID, "Тест")

    service = LessonService(
        settings,
        users=users,
        progress=progress,
        sessions=sessions,
        answers=answers,
        planner=SessionPlanner(Lexicon.load(), random.Random(1)),
    )
    yield service, progress, answers, sessions
    await database.close()


async def test_full_session_of_correct_answers(lesson):
    service, _, answers, _ = lesson
    await service.start(USER_ID)

    for step in range(5):
        exercise = await service.next_exercise(USER_ID)
        assert exercise is not None, f"вопрос {step + 1} не пришёл"
        outcome = await service.submit(USER_ID, exercise.accepted[0])
        assert outcome is not None and outcome.verdict.correct

    assert await service.next_exercise(USER_ID) is None, "сессия должна была закончиться"

    summary = await service.summary(USER_ID)
    assert summary.correct == 5
    assert summary.total == 5

    import datetime as dt

    from arabic_bot.storage.repositories import utcnow

    logged = await answers.summary(USER_ID, utcnow() - dt.timedelta(minutes=5))
    assert logged["total"] == 5 and logged["correct"] == 5


async def test_wrong_answer_keeps_the_same_question(lesson):
    service, _, _, _ = lesson
    await service.start(USER_ID)
    exercise = await service.next_exercise(USER_ID)

    outcome = await service.submit(USER_ID, "заведомо неверно")
    assert outcome is not None and not outcome.verdict.correct

    # Вопрос остаётся тем же: пользователь выбрал «попробовать ещё».
    assert await service.next_exercise(USER_ID) == exercise

    second = await service.submit(USER_ID, exercise.accepted[0])
    assert second.verdict.correct and not second.first_try


async def test_reveal_closes_question_and_counts_as_mistake(lesson):
    service, progress, answers, _ = lesson
    await service.start(USER_ID)
    exercise = await service.next_exercise(USER_ID)

    outcome = await service.reveal(USER_ID)
    assert outcome is not None and outcome.exercise == exercise

    following = await service.next_exercise(USER_ID)
    assert following is not None and following != exercise

    if exercise.focus_letters:
        stored = await progress.all(USER_ID)
        touched = stored[exercise.focus_letters[0]]
        assert touched.times_seen == 1 and touched.times_correct == 0


async def test_session_survives_restart(lesson, tmp_path):
    """Контейнер перезапустился — текущий вопрос не должен потеряться."""
    service, _, _, sessions = lesson
    await service.start(USER_ID)
    exercise = await service.next_exercise(USER_ID)

    reopened = await sessions.active(USER_ID)
    assert reopened is not None
    assert reopened.current_exercise == exercise


async def test_extend_adds_more_questions(lesson):
    service, _, _, _ = lesson
    await service.start(USER_ID)
    for _ in range(5):
        exercise = await service.next_exercise(USER_ID)
        await service.submit(USER_ID, exercise.accepted[0])
    assert await service.next_exercise(USER_ID) is None

    await service.extend(USER_ID, 5)
    assert await service.next_exercise(USER_ID) is not None


async def test_new_cycle_reset_is_persisted(lesson):
    """Круг обязан сбрасываться в базе, иначе он «закрывается» каждый день."""
    service, progress, _, _ = lesson
    await service.start(USER_ID)
    stored = await progress.all(USER_ID)

    # Отмечаем все буквы как показанные — круг пройден.
    for item in stored.values():
        await progress.save(USER_ID, type(item)(**{**_as_dict(item), "seen_in_cycle": True}))

    await service.start(USER_ID)
    after = await progress.all(USER_ID)
    assert all(item.cycle_no == 2 for item in after.values())
    assert sum(1 for item in after.values() if not item.seen_in_cycle) >= 22


def _as_dict(item) -> dict:
    return {field: getattr(item, field) for field in item.__slots__}


async def test_outcome_reports_the_real_number_of_attempts(lesson):
    """Бот писал «со второй попытки» даже когда их было четыре."""
    from arabic_bot.bot import texts

    service, _, _, _ = lesson
    await service.start(USER_ID)
    exercise = await service.next_exercise(USER_ID)

    for _ in range(3):
        wrong = await service.submit(USER_ID, "заведомо неверный ответ")
        assert not wrong.verdict.correct

    outcome = await service.submit(USER_ID, exercise.accepted[0])
    assert outcome.verdict.correct
    assert outcome.attempts == 4, f"учтено попыток: {outcome.attempts}"

    message = texts.outcome_text(correct=True, attempts=outcome.attempts)
    assert "с 4-й попытки" in message
    assert "со второй" not in message


def test_outcome_text_wording():
    from arabic_bot.bot import texts

    assert texts.outcome_text(correct=True, attempts=1) == "Done ✅"
    assert "с 2-й попытки" in texts.outcome_text(correct=True, attempts=2)
    assert "с 7-й попытки" in texts.outcome_text(correct=True, attempts=7)


async def test_reveal_reports_attempts_made_before_giving_up(lesson):
    service, _, _, _ = lesson
    await service.start(USER_ID)
    await service.next_exercise(USER_ID)

    await service.submit(USER_ID, "мимо")
    await service.submit(USER_ID, "снова мимо")
    outcome = await service.reveal(USER_ID)

    assert outcome.attempts == 3
