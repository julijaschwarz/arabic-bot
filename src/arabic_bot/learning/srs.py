"""Интервальное повторение (упрощённый SM-2).

Круг по 28 буквам сохраняется, но буквы, на которых были ошибки, возвращаются
в фокус раньше остальных.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace

from ..storage.repositories import LetterProgress

MIN_EASE = 1.3
MAX_EASE = 2.6
EASE_UP = 0.05
EASE_DOWN = 0.2

FIRST_INTERVAL_DAYS = 1.0
RELEARN_INTERVAL_DAYS = 0.25
"""Ошиблись — вернём букву уже через несколько часов, а не завтра."""

MAX_INTERVAL_DAYS = 60.0


def review(progress: LetterProgress, *, correct: bool, now: dt.datetime) -> LetterProgress:
    """Пересчитать состояние буквы после ответа."""
    ease = progress.ease
    if correct:
        ease = min(MAX_EASE, ease + EASE_UP)
        if progress.interval_days <= 0:
            interval = FIRST_INTERVAL_DAYS
        else:
            interval = min(MAX_INTERVAL_DAYS, progress.interval_days * ease)
    else:
        ease = max(MIN_EASE, ease - EASE_DOWN)
        interval = RELEARN_INTERVAL_DAYS

    return replace(
        progress,
        seen_in_cycle=True,
        times_seen=progress.times_seen + 1,
        times_correct=progress.times_correct + (1 if correct else 0),
        ease=round(ease, 3),
        interval_days=round(interval, 3),
        due_at=now + dt.timedelta(days=interval),
        last_seen_at=now,
    )


def accuracy(progress: LetterProgress) -> float | None:
    if not progress.times_seen:
        return None
    return progress.times_correct / progress.times_seen
