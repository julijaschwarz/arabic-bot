"""Напоминания и утренняя рассылка."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from aiogram.methods import SendMessage

from arabic_bot.bot.setup import build
from arabic_bot.config import Settings
from arabic_bot.storage.repositories import iso, utcnow
from test_bot_flow import USER_ID, RecordingBot, _message

CHAT_ID = USER_ID


async def _make_app(tmp_path: Path, **overrides):
    settings = Settings(
        BOT_TOKEN="42:TEST",
        ALLOWED_USER_IDS=str(USER_ID),
        DATA_DIR=str(tmp_path),
        DB_PATH=str(tmp_path / "sched.db"),
        DAILY_TASK_COUNT="3",
        IMAGES_ENABLED="false",
        QUIET_HOURS="22:00-08:00",
        **overrides,
    )
    bot = RecordingBot()
    app = await build(settings, bot=bot)
    # Регистрируем пользователя так же, как это делает первое сообщение боту.
    await app.dispatcher.feed_update(bot, _message("/help"))
    bot.clear()
    return app, bot


async def _set_activity(app, *, hours_ago: float) -> None:
    """Отодвинуть активность в прошлое и считать занятие дня уже отправленным.

    Второе важно: иначе проверка сперва пришлёт занятие, а оно вытесняет
    напоминание — и тесты про напоминание проверяли бы не то.
    """
    moment = utcnow() - dt.timedelta(hours=hours_ago)
    today = utcnow().astimezone(app.settings.tz).date().isoformat()
    await app.database.conn.execute(
        "UPDATE users SET last_activity_at = ?, last_nudge_at = NULL, last_daily_on = ?",
        (iso(moment), today),
    )
    await app.database.conn.commit()


def _set_quiet(monkeypatch, quiet: bool) -> None:
    """Тесты не должны зависеть от того, в котором часу их запустили.

    Патчим класс, а не экземпляр: pydantic не даёт присваивать поля, которых нет
    в модели.
    """
    monkeypatch.setattr(Settings, "is_quiet_now", lambda self, moment: quiet)


@pytest.fixture
async def app(tmp_path: Path):
    application, bot = await _make_app(tmp_path)
    yield application, bot
    await application.database.close()
    await bot.session.close()


async def test_nudge_is_sent_after_idle_period(app, monkeypatch):
    application, bot = app
    await _set_activity(application, hours_ago=7)
    _set_quiet(monkeypatch, False)

    await application.jobs.idle_nudge()

    assert any("Пора повторить арабский!" in text for text in bot.texts())


async def test_no_nudge_while_the_user_is_active(app, monkeypatch):
    application, bot = app
    await _set_activity(application, hours_ago=1)
    _set_quiet(monkeypatch, False)

    await application.jobs.idle_nudge()

    assert not any("Пора повторить" in text for text in bot.texts())


async def test_no_nudge_during_quiet_hours(app, monkeypatch):
    application, bot = app
    await _set_activity(application, hours_ago=12)
    _set_quiet(monkeypatch, True)

    await application.jobs.idle_nudge()

    assert not any("Пора повторить" in text for text in bot.texts())


async def test_nudge_is_not_repeated_too_soon(app, monkeypatch):
    application, bot = app
    await _set_activity(application, hours_ago=12)
    _set_quiet(monkeypatch, False)

    await application.jobs.idle_nudge()
    bot.clear()
    await application.jobs.idle_nudge()

    assert not any("Пора повторить" in text for text in bot.texts())


async def test_no_nudge_on_the_tick_after_the_daily_lesson(app, monkeypatch):
    """Занятие ушло по расписанию — ближайшая проверка простоя молчит.

    Пользователь, не ответивший на занятие, формально простаивает, и до этой
    правки проверка присылала «Пора повторить» поверх нетронутого занятия:
    рассылка и проверка — разные тики, а набор skip гасит дубль только внутри
    одного. Особенно заметно с тихими часами до 09:00, когда первый свободный
    слот для напоминания приходится как раз на тик после рассылки.
    """
    application, bot = app
    await _set_activity(application, hours_ago=12)
    _set_quiet(monkeypatch, False)
    users = application.dispatcher.workflow_data["users"]
    # Занятие за сегодня ещё не уходило, а час рассылки заведомо наступил.
    await users.update(USER_ID, daily_time="00:00")
    await application.database.conn.execute("UPDATE users SET last_daily_on = NULL")
    await application.database.conn.commit()

    await application.jobs.daily_session()
    assert bot.texts(), "занятие дня должно было уйти"
    bot.clear()

    await application.jobs.idle_nudge()

    assert not any("Пора повторить" in text for text in bot.texts())


async def test_nudge_respects_notifications_switch(app, monkeypatch):
    application, bot = app
    await _set_activity(application, hours_ago=12)
    _set_quiet(monkeypatch, False)
    await application.dispatcher.workflow_data["users"].update(USER_ID, notifications_on=0)
    bot.clear()

    await application.jobs.idle_nudge()

    assert not any("Пора повторить" in text for text in bot.texts())


async def test_daily_session_sends_a_question_once_per_day(app):
    application, bot = app

    await application.jobs.daily_session()
    assert any("Вопрос 1 из 3" in text for text in bot.texts())

    bot.clear()
    await application.jobs.daily_session()
    assert not any("Вопрос 1 из 3" in text for text in bot.texts())


async def test_heartbeat_file_is_written(app):
    application, _ = app
    await application.jobs.heartbeat()
    assert application.settings.heartbeat_path.exists()


def test_quiet_hours_wrap_around_midnight():
    settings = Settings(BOT_TOKEN="x", QUIET_HOURS="22:00-08:00", TZ="UTC")
    at = lambda hour: dt.datetime(2026, 7, 29, hour, tzinfo=dt.UTC)  # noqa: E731
    assert settings.is_quiet_now(at(23))
    assert settings.is_quiet_now(at(3))
    assert not settings.is_quiet_now(at(12))


async def test_jobs_tolerate_being_late(app):
    """Причина, по которой утренняя рассылка и напоминания не приходили.

    APScheduler по умолчанию отбрасывает задание, опоздавшее больше чем на
    секунду. На ноутбуке, который засыпает, опаздывает каждое — и в логах
    было ровно «Run time of job was missed». Прежние тесты этого не видели,
    потому что вызывали задания напрямую, минуя планировщик.
    """
    application, _ = app
    application.jobs.start()
    try:
        jobs = {job.id: job for job in application.jobs.scheduler.get_jobs()}
        assert set(jobs) == {"daily_session", "idle_nudge", "heartbeat"}
        for job_id, job in jobs.items():
            assert job.misfire_grace_time and job.misfire_grace_time >= 600, (
                f"{job_id}: без запаса по опозданию задание будет молча пропускаться"
            )
            assert job.coalesce, f"{job_id}: пропущенные срабатывания должны слипаться"
    finally:
        application.jobs.shutdown()


async def test_daily_lesson_is_caught_up_after_a_missed_slot(app, monkeypatch):
    """Проспали 09:00 — занятие должно уйти при следующей проверке, а не пропасть."""
    application, bot = app
    _set_quiet(monkeypatch, False)

    # Момент рассылки давно прошёл, но за сегодня она не уходила.
    await application.database.conn.execute("UPDATE users SET last_daily_on = NULL")
    await application.database.conn.commit()

    await application.jobs.idle_nudge()

    assert any("Вопрос 1 из 3" in text for text in bot.texts())
    user = await application.dispatcher.workflow_data["users"].get(USER_ID)
    assert user.last_daily_on is not None, "повторно в тот же день слать нельзя"


async def test_caught_up_lesson_is_not_sent_twice(app, monkeypatch):
    application, bot = app
    _set_quiet(monkeypatch, False)

    await application.jobs.idle_nudge()
    bot.clear()
    await application.jobs.idle_nudge()

    assert not any("Вопрос 1 из 3" in text for text in bot.texts())


async def test_no_daily_lesson_before_the_appointed_hour(app, monkeypatch):
    application, bot = app
    _set_quiet(monkeypatch, False)
    # Назначаем время, которое сегодня ещё не наступило.
    await application.dispatcher.workflow_data["users"].update(USER_ID, daily_time="23:59")

    await application.jobs.send_due_lessons()

    assert not any("Вопрос 1 из 3" in text for text in bot.texts())


async def test_daily_lesson_skipped_if_already_practised_today(app, monkeypatch):
    """Уже позанимались — навязывать вторую сессию незачем."""
    application, bot = app
    _set_quiet(monkeypatch, False)
    service = application.dispatcher.workflow_data["service"]

    await service.start(USER_ID)
    for _ in range(3):
        exercise = await service.next_exercise(USER_ID)
        await service.submit(USER_ID, exercise.accepted[0])
    assert await service.next_exercise(USER_ID) is None, "сессия должна быть завершена"
    bot.clear()

    await application.jobs.send_due_lessons()

    assert not any("Вопрос 1 из 3" in text for text in bot.texts())
    user = await application.dispatcher.workflow_data["users"].get(USER_ID)
    assert user.last_daily_on is not None


async def test_nudge_survives_a_failing_chat(app, monkeypatch):
    """Ошибка отправки одному не должна ронять задание целиком."""
    application, bot = app
    await _set_activity(application, hours_ago=12)
    _set_quiet(monkeypatch, False)

    bot.fail = lambda method: (
        RuntimeError("Telegram недоступен") if isinstance(method, SendMessage) else None
    )
    await application.jobs.idle_nudge()  # не должно выбросить исключение
    assert any(isinstance(call, SendMessage) for call in bot.calls), "попытка была"


async def test_lesson_and_nudge_do_not_arrive_together(app, monkeypatch):
    """После долгого простоя приходили сразу два сообщения: занятие и напоминание.

    Занятие само по себе — приглашение позаниматься, напоминание поверх лишнее.
    """
    application, bot = app
    _set_quiet(monkeypatch, False)
    await _set_activity(application, hours_ago=20)
    await application.database.conn.execute("UPDATE users SET last_daily_on = NULL")
    await application.database.conn.commit()

    await application.jobs.idle_nudge()

    assert any("Вопрос 1 из 3" in text for text in bot.texts()), "занятие должно прийти"
    assert not any("Пора повторить" in text for text in bot.texts()), (
        "напоминание поверх занятия — лишнее сообщение"
    )


async def test_nudge_still_arrives_when_no_lesson_was_due(app, monkeypatch):
    """Занятие за сегодня уже уходило — тогда напоминание работает как обычно."""
    application, bot = app
    _set_quiet(monkeypatch, False)
    await _set_activity(application, hours_ago=20)

    local = utcnow().astimezone(application.settings.tz)
    await application.dispatcher.workflow_data["users"].mark_daily_sent(
        USER_ID, local.date().isoformat()
    )
    bot.clear()

    await application.jobs.idle_nudge()

    assert any("Пора повторить" in text for text in bot.texts())
