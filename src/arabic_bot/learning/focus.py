"""Выбор букв в фокус дня.

Два требования тянут в разные стороны: круг должен пройти все 28 букв по разу,
а трудные буквы должны возвращаться чаще. Компромисс — квота: не больше трети
мест отдаётся повторению, остальные достаются ещё не показанным буквам этого
круга. Так круг закрывается максимум за неделю и при этом ошибки не забываются.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace

from ..domain.letters import BY_ID, LETTERS, Letter
from ..storage.repositories import LetterProgress

REVIEW_SHARE = 3
"""Одно место из трёх — под повторение просроченных букв."""


@dataclass(frozen=True, slots=True)
class Focus:
    letters: tuple[Letter, ...]
    cycle_no: int
    new_cycle_started: bool
    fresh_left: int
    """Сколько букв текущего круга ещё ни разу не показывалось."""


def choose(
    progress: dict[str, LetterProgress],
    *,
    count: int,
    now: dt.datetime,
) -> Focus:
    """Подобрать `count` букв: сначала просроченные, добор — новыми из круга."""
    if not progress:
        return Focus(tuple(LETTERS[:count]), cycle_no=1, new_cycle_started=True, fresh_left=0)

    cycle_no = max(item.cycle_no for item in progress.values())
    new_cycle = False

    def unseen() -> list[LetterProgress]:
        return [item for item in progress.values() if not item.seen_in_cycle]

    overdue = sorted(
        (item for item in progress.values() if item.due_at and item.due_at <= now),
        key=lambda item: item.due_at or now,
    )

    chosen: list[str] = []
    for item in overdue[: max(1, count // REVIEW_SHARE)]:
        chosen.append(item.letter_id)

    fresh = unseen()
    if not fresh:
        # Все 28 букв показаны — круг закрыт, открываем следующий.
        cycle_no += 1
        new_cycle = True
        progress = {
            key: replace(item, cycle_no=cycle_no, seen_in_cycle=False)
            for key, item in progress.items()
        }
        fresh = unseen()

    # Внутри круга идём по алфавиту — так порядок предсказуем и ничего не теряется.
    fresh.sort(key=lambda item: _alphabet_index(item.letter_id))
    for item in fresh:
        if len(chosen) >= count:
            break
        if item.letter_id not in chosen:
            chosen.append(item.letter_id)

    # Если букв всё ещё мало (маленький круг, много повторов) — берём давно не виденные.
    if len(chosen) < count:
        rest = sorted(
            (item for item in progress.values() if item.letter_id not in chosen),
            key=lambda item: (item.last_seen_at or now, item.times_seen),
        )
        for item in rest[: count - len(chosen)]:
            chosen.append(item.letter_id)

    remaining = sum(
        1 for item in progress.values() if not item.seen_in_cycle and item.letter_id not in chosen
    )
    return Focus(
        letters=tuple(BY_ID[letter_id] for letter_id in chosen),
        cycle_no=cycle_no,
        new_cycle_started=new_cycle,
        fresh_left=remaining,
    )


def _alphabet_index(letter_id: str) -> int:
    return next(i for i, letter in enumerate(LETTERS) if letter.id == letter_id)
