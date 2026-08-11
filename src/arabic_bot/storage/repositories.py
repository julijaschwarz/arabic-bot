"""Репозитории: единственное место, где проект знает про SQL."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from typing import Any, Sequence

import aiosqlite

from ..domain.letters import LETTERS
from ..domain.models import Exercise
from .db import Database


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def iso(moment: dt.datetime | None) -> str | None:
    return moment.astimezone(dt.UTC).isoformat() if moment else None


def parse_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    parsed = dt.datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)


@dataclass(slots=True)
class User:
    user_id: int
    chat_id: int
    first_name: str
    daily_time: str | None
    tasks_per_day: int | None
    notifications_on: bool
    last_activity_at: dt.datetime | None
    last_nudge_at: dt.datetime | None
    last_daily_on: str | None

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> User:
        return cls(
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            first_name=row["first_name"],
            daily_time=row["daily_time"],
            tasks_per_day=row["tasks_per_day"],
            notifications_on=bool(row["notifications_on"]),
            last_activity_at=parse_dt(row["last_activity_at"]),
            last_nudge_at=parse_dt(row["last_nudge_at"]),
            last_daily_on=row["last_daily_on"],
        )


@dataclass(slots=True)
class LetterProgress:
    letter_id: str
    cycle_no: int
    seen_in_cycle: bool
    times_seen: int
    times_correct: int
    ease: float
    interval_days: float
    due_at: dt.datetime | None
    last_seen_at: dt.datetime | None

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> LetterProgress:
        return cls(
            letter_id=row["letter_id"],
            cycle_no=row["cycle_no"],
            seen_in_cycle=bool(row["seen_in_cycle"]),
            times_seen=row["times_seen"],
            times_correct=row["times_correct"],
            ease=row["ease"],
            interval_days=row["interval_days"],
            due_at=parse_dt(row["due_at"]),
            last_seen_at=parse_dt(row["last_seen_at"]),
        )


@dataclass(slots=True)
class Session:
    id: int
    user_id: int
    kind: str
    status: str
    planned_count: int
    position: int
    correct_count: int
    focus_letters: tuple[str, ...]
    current_exercise: Exercise | None
    current_attempts: int
    last_generator_id: str | None

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> Session:
        raw = row["current_exercise"]
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            kind=row["kind"],
            status=row["status"],
            planned_count=row["planned_count"],
            position=row["position"],
            correct_count=row["correct_count"],
            focus_letters=tuple(json.loads(row["focus_letters"])),
            current_exercise=Exercise.from_dict(json.loads(raw)) if raw else None,
            current_attempts=row["current_attempts"],
            last_generator_id=row["last_generator_id"],
        )

    @property
    def is_last(self) -> bool:
        return self.position >= self.planned_count


class UserRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def ensure(self, user_id: int, chat_id: int, first_name: str = "") -> User:
        await self._db.conn.execute(
            """
            INSERT INTO users (user_id, chat_id, first_name, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET chat_id = excluded.chat_id
            """,
            (user_id, chat_id, first_name, iso(utcnow())),
        )
        await self._db.conn.commit()
        user = await self.get(user_id)
        assert user is not None
        return user

    async def get(self, user_id: int) -> User | None:
        async with self._db.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return User.from_row(row) if row else None

    async def all(self) -> list[User]:
        async with self._db.conn.execute("SELECT * FROM users") as cursor:
            return [User.from_row(row) for row in await cursor.fetchall()]

    async def touch_activity(self, user_id: int) -> None:
        await self._db.conn.execute(
            "UPDATE users SET last_activity_at = ? WHERE user_id = ?",
            (iso(utcnow()), user_id),
        )
        await self._db.conn.commit()

    async def mark_nudged(self, user_id: int) -> None:
        await self._db.conn.execute(
            "UPDATE users SET last_nudge_at = ? WHERE user_id = ?",
            (iso(utcnow()), user_id),
        )
        await self._db.conn.commit()

    async def mark_daily_sent(self, user_id: int, on_date: str) -> None:
        await self._db.conn.execute(
            "UPDATE users SET last_daily_on = ? WHERE user_id = ?", (on_date, user_id)
        )
        await self._db.conn.commit()

    async def update(self, user_id: int, **fields: Any) -> None:
        allowed = {"daily_time", "tasks_per_day", "notifications_on"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        assignments = ", ".join(f"{key} = ?" for key in updates)
        await self._db.conn.execute(
            f"UPDATE users SET {assignments} WHERE user_id = ?",
            (*updates.values(), user_id),
        )
        await self._db.conn.commit()


class ProgressRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def ensure_rows(self, user_id: int) -> None:
        """Завести строки под все 28 букв — так планировщику не нужны NULL-проверки."""
        await self._db.conn.executemany(
            """
            INSERT INTO letter_progress (user_id, letter_id) VALUES (?, ?)
            ON CONFLICT(user_id, letter_id) DO NOTHING
            """,
            [(user_id, letter.id) for letter in LETTERS],
        )
        await self._db.conn.commit()

    async def all(self, user_id: int) -> dict[str, LetterProgress]:
        async with self._db.conn.execute(
            "SELECT * FROM letter_progress WHERE user_id = ?", (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        return {row["letter_id"]: LetterProgress.from_row(row) for row in rows}

    async def save(self, user_id: int, progress: LetterProgress) -> None:
        await self._db.conn.execute(
            """
            UPDATE letter_progress
               SET cycle_no = ?, seen_in_cycle = ?, times_seen = ?, times_correct = ?,
                   ease = ?, interval_days = ?, due_at = ?, last_seen_at = ?
             WHERE user_id = ? AND letter_id = ?
            """,
            (
                progress.cycle_no,
                int(progress.seen_in_cycle),
                progress.times_seen,
                progress.times_correct,
                progress.ease,
                progress.interval_days,
                iso(progress.due_at),
                iso(progress.last_seen_at),
                user_id,
                progress.letter_id,
            ),
        )
        await self._db.conn.commit()

    async def start_new_cycle(self, user_id: int) -> None:
        """Все 28 показаны — круг закрыт, начинаем следующий."""
        await self._db.conn.execute(
            """
            UPDATE letter_progress
               SET cycle_no = cycle_no + 1, seen_in_cycle = 0
             WHERE user_id = ?
            """,
            (user_id,),
        )
        await self._db.conn.commit()


class SessionRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def active(self, user_id: int) -> Session | None:
        async with self._db.conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? AND status = 'active'"
            " ORDER BY id DESC LIMIT 1",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return Session.from_row(row) if row else None

    async def create(
        self,
        user_id: int,
        planned_count: int,
        focus_letters: Sequence[str],
        kind: str = "daily",
    ) -> Session:
        await self._db.conn.execute(
            "UPDATE sessions SET status = 'abandoned', finished_at = ?"
            " WHERE user_id = ? AND status = 'active'",
            (iso(utcnow()), user_id),
        )
        cursor = await self._db.conn.execute(
            """
            INSERT INTO sessions (user_id, kind, planned_count, focus_letters, started_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, kind, planned_count, json.dumps(list(focus_letters)), iso(utcnow())),
        )
        await self._db.conn.commit()
        session = await self.by_id(cursor.lastrowid)
        assert session is not None
        return session

    async def by_id(self, session_id: int) -> Session | None:
        async with self._db.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return Session.from_row(row) if row else None

    async def set_current(self, session_id: int, exercise: Exercise) -> None:
        await self._db.conn.execute(
            """
            UPDATE sessions
               SET current_exercise = ?, current_attempts = 0,
                   last_generator_id = ?, position = position + 1
             WHERE id = ?
            """,
            (
                json.dumps(exercise.to_dict(), ensure_ascii=False),
                exercise.generator_id,
                session_id,
            ),
        )
        await self._db.conn.commit()

    async def last(self, user_id: int) -> Session | None:
        """Последняя сессия любого статуса — нужна для кнопки «Ещё 5 заданий»."""
        async with self._db.conn.execute(
            "SELECT * FROM sessions WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return Session.from_row(row) if row else None

    async def add_attempt(self, session_id: int) -> None:
        await self._db.conn.execute(
            "UPDATE sessions SET current_attempts = current_attempts + 1 WHERE id = ?",
            (session_id,),
        )
        await self._db.conn.commit()

    async def close_question(self, session_id: int, *, correct: bool) -> None:
        await self._db.conn.execute(
            """
            UPDATE sessions
               SET last_exercise = current_exercise,
                   current_exercise = NULL,
                   current_attempts = 0,
                   correct_count = correct_count + ?
             WHERE id = ?
            """,
            (1 if correct else 0, session_id),
        )
        await self._db.conn.commit()

    async def finish(self, session_id: int) -> None:
        await self._db.conn.execute(
            "UPDATE sessions SET status = 'done', finished_at = ? WHERE id = ?",
            (iso(utcnow()), session_id),
        )
        await self._db.conn.commit()

    async def extend(self, session_id: int, extra: int) -> None:
        await self._db.conn.execute(
            "UPDATE sessions SET planned_count = planned_count + ?, status = 'active',"
            " finished_at = NULL WHERE id = ?",
            (extra, session_id),
        )
        await self._db.conn.commit()

    async def completed_today(self, user_id: int, since: dt.datetime) -> int:
        async with self._db.conn.execute(
            "SELECT COUNT(*) AS n FROM sessions"
            " WHERE user_id = ? AND status = 'done' AND finished_at >= ?",
            (user_id, iso(since)),
        ) as cursor:
            row = await cursor.fetchone()
        return int(row["n"]) if row else 0


class AnswerRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    async def add(
        self,
        *,
        session_id: int | None,
        user_id: int,
        generator_id: str,
        focus_letters: Sequence[str],
        correct: bool,
        attempts: int,
        revealed: bool,
    ) -> None:
        await self._db.conn.execute(
            """
            INSERT INTO answers
                (session_id, user_id, generator_id, focus_letters, correct,
                 attempts, revealed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                user_id,
                generator_id,
                json.dumps(list(focus_letters)),
                int(correct),
                attempts,
                int(revealed),
                iso(utcnow()),
            ),
        )
        await self._db.conn.commit()

    async def summary(self, user_id: int, since: dt.datetime) -> dict[str, int]:
        async with self._db.conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(correct) AS correct,
                   SUM(revealed) AS revealed
              FROM answers
             WHERE user_id = ? AND created_at >= ?
            """,
            (user_id, iso(since)),
        ) as cursor:
            row = await cursor.fetchone()
        return {
            "total": int(row["total"] or 0),
            "correct": int(row["correct"] or 0),
            "revealed": int(row["revealed"] or 0),
        }

    async def hardest_letters(self, user_id: int, limit: int = 5) -> list[tuple[str, int, int]]:
        """Буквы с наибольшей долей ошибок — по журналу ответов."""
        async with self._db.conn.execute(
            "SELECT focus_letters, correct FROM answers WHERE user_id = ?", (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()

        stats: dict[str, list[int]] = {}
        for row in rows:
            for letter_id in json.loads(row["focus_letters"]):
                bucket = stats.setdefault(letter_id, [0, 0])
                bucket[0] += 1
                bucket[1] += int(row["correct"])

        ranked = sorted(
            ((lid, seen, ok) for lid, (seen, ok) in stats.items() if seen >= 3),
            key=lambda item: (item[2] / item[1], -item[1]),
        )
        return ranked[:limit]
