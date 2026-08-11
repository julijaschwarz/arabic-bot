"""SQLite-хранилище: подключение и миграции.

Схема сразу содержит `user_id` во всех таблицах, поэтому подключить второго
человека позже можно без переписывания — достаточно расширить whitelist.
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)

MIGRATIONS: tuple[str, ...] = (
    # 1 — пользователи и их настройки
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id           INTEGER PRIMARY KEY,
        chat_id           INTEGER NOT NULL,
        first_name        TEXT    NOT NULL DEFAULT '',
        daily_time        TEXT,            -- 'HH:MM', NULL = значение из .env
        tasks_per_day     INTEGER,         -- NULL = значение из .env
        notifications_on  INTEGER NOT NULL DEFAULT 1,
        created_at        TEXT    NOT NULL,
        last_activity_at  TEXT,
        last_nudge_at     TEXT,
        last_daily_on     TEXT             -- дата последней утренней рассылки, YYYY-MM-DD
    );
    """,
    # 2 — круг по 28 буквам и интервальное повторение
    """
    CREATE TABLE IF NOT EXISTS letter_progress (
        user_id        INTEGER NOT NULL,
        letter_id      TEXT    NOT NULL,
        cycle_no       INTEGER NOT NULL DEFAULT 1,
        seen_in_cycle  INTEGER NOT NULL DEFAULT 0,
        times_seen     INTEGER NOT NULL DEFAULT 0,
        times_correct  INTEGER NOT NULL DEFAULT 0,
        ease           REAL    NOT NULL DEFAULT 2.5,
        interval_days  REAL    NOT NULL DEFAULT 0,
        due_at         TEXT,
        last_seen_at   TEXT,
        PRIMARY KEY (user_id, letter_id)
    );
    """,
    # 3 — сессия: текущий вопрос живёт в БД, а не в памяти процесса
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id           INTEGER NOT NULL,
        kind              TEXT    NOT NULL DEFAULT 'daily',
        status            TEXT    NOT NULL DEFAULT 'active',  -- active | done | abandoned
        planned_count     INTEGER NOT NULL,
        position          INTEGER NOT NULL DEFAULT 0,
        correct_count     INTEGER NOT NULL DEFAULT 0,
        focus_letters     TEXT    NOT NULL DEFAULT '[]',
        current_exercise  TEXT,
        current_attempts  INTEGER NOT NULL DEFAULT 0,
        last_generator_id TEXT,
        last_exercise     TEXT,   -- предыдущий вопрос: осталось от прежних версий
        started_at        TEXT    NOT NULL,
        finished_at       TEXT
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_sessions_user_status
        ON sessions (user_id, status);
    """,
    # 4 — история ответов для статистики
    """
    CREATE TABLE IF NOT EXISTS answers (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id    INTEGER,
        user_id       INTEGER NOT NULL,
        generator_id  TEXT    NOT NULL,
        focus_letters TEXT    NOT NULL DEFAULT '[]',
        correct       INTEGER NOT NULL,
        attempts      INTEGER NOT NULL DEFAULT 1,
        revealed      INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT    NOT NULL
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_answers_user_date
        ON answers (user_id, created_at);
    """,
)


class Database:
    """Тонкая обёртка над aiosqlite: одно соединение на процесс."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("База не подключена — вызовите connect()")
        return self._conn

    async def connect(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self.migrate()
        log.info("База готова: %s", self._path)

    async def migrate(self) -> None:
        for statement in MIGRATIONS:
            await self.conn.executescript(statement)
        await self.conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
