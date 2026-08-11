from __future__ import annotations

import datetime as dt
from dataclasses import replace

from arabic_bot.domain.letters import LETTERS
from arabic_bot.learning import focus as focus_module
from arabic_bot.learning import srs
from arabic_bot.learning.planner import SessionPlanner
from arabic_bot.storage.repositories import LetterProgress

NOW = dt.datetime(2026, 7, 29, 9, 0, tzinfo=dt.UTC)


def fresh_progress() -> dict[str, LetterProgress]:
    return {
        letter.id: LetterProgress(letter.id, 1, False, 0, 0, 2.5, 0.0, None, None)
        for letter in LETTERS
    }


def test_srs_lengthens_interval_after_correct_answer():
    item = fresh_progress()["ba"]
    first = srs.review(item, correct=True, now=NOW)
    second = srs.review(first, correct=True, now=NOW)
    assert first.interval_days == srs.FIRST_INTERVAL_DAYS
    assert second.interval_days > first.interval_days
    assert second.due_at > first.due_at


def test_srs_brings_a_mistake_back_within_hours():
    item = replace(fresh_progress()["ba"], interval_days=30.0, ease=2.5)
    after = srs.review(item, correct=False, now=NOW)
    assert after.interval_days == srs.RELEARN_INTERVAL_DAYS
    assert after.ease < item.ease
    assert after.due_at - NOW < dt.timedelta(days=1)


def test_srs_ease_never_falls_below_floor():
    item = fresh_progress()["ba"]
    for _ in range(50):
        item = srs.review(item, correct=False, now=NOW)
    assert item.ease >= srs.MIN_EASE


def test_focus_marks_letters_as_seen_within_cycle():
    progress = fresh_progress()
    picked = focus_module.choose(progress, count=6, now=NOW)
    assert len(picked.letters) == 6
    assert len(set(picked.letters)) == 6


def test_cycle_covers_all_28_letters_and_then_restarts():
    """Ключевое требование: каждая буква показывается по разу за круг."""
    progress = fresh_progress()
    seen: set[str] = set()
    cycle_starts: list[int] = []

    for day in range(40):
        moment = NOW + dt.timedelta(days=day)
        picked = focus_module.choose(progress, count=6, now=moment)
        if picked.new_cycle_started:
            cycle_starts.append(day)
            if len(cycle_starts) == 2:
                # Первый полный круг закончился — он обязан покрыть весь алфавит.
                assert seen == {letter.id for letter in LETTERS}
            seen = set()
            progress = {
                key: replace(item, cycle_no=picked.cycle_no, seen_in_cycle=False)
                for key, item in progress.items()
            }

        for letter in picked.letters:
            progress[letter.id] = srs.review(progress[letter.id], correct=True, now=moment)
            seen.add(letter.id)

    assert len(cycle_starts) >= 2, "за 40 дней круг должен закрыться хотя бы дважды"


def test_planner_builds_a_full_session(lexicon, rng):
    planner = SessionPlanner(lexicon, rng)
    focus = tuple(LETTERS[:6])
    last: str | None = None
    seen_types: set[str] = set()

    for position in range(10):
        exercise = planner.next_exercise(focus, position=position, last_generator_id=last)
        assert exercise is not None, f"нет задания на позиции {position}"
        seen_types.add(exercise.generator_id)
        last = exercise.generator_id

    assert len(seen_types) >= 4, "сессия не должна состоять из одного типа заданий"


def test_planner_mixes_in_digit_questions(lexicon, rng):
    planner = SessionPlanner(lexicon, rng)
    focus = tuple(LETTERS[:6])
    ids = [
        planner.next_exercise(focus, position=position).generator_id for position in range(40)
    ]
    assert any(name.startswith("digit") for name in ids), "цифры должны попадать в сессию"


def test_planner_avoids_repeating_the_same_type(lexicon, rng):
    planner = SessionPlanner(lexicon, rng)
    focus = tuple(LETTERS[:6])
    last: str | None = None
    repeats = 0
    for position in range(100):
        exercise = planner.next_exercise(focus, position=position, last_generator_id=last)
        if exercise.generator_id == last:
            repeats += 1
        last = exercise.generator_id
    assert repeats < 15, f"слишком часто повторяется тип задания подряд: {repeats}/100"
