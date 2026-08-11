"""Главный инвариант проекта: генератор не имеет права выдать задание,
правильный ответ на которое не проходит собственную же проверку."""

from __future__ import annotations

import pytest

from arabic_bot.domain import letters as L
from arabic_bot.domain.models import AnswerMode
from arabic_bot.exercises import registry
from arabic_bot.exercises.base import GenContext
from arabic_bot.exercises.checkers import check

ROUNDS = 500

ALL_GENERATORS = registry.all_generators()


def test_registry_loaded_every_generator_file():
    assert len(ALL_GENERATORS) >= 16
    assert len(set(registry.known_ids())) == len(ALL_GENERATORS)


@pytest.mark.parametrize("generator", ALL_GENERATORS, ids=lambda g: g.id)
def test_generator_produces_self_consistent_exercises(generator, lexicon, rng):
    produced = 0
    for _ in range(ROUNDS):
        ctx = GenContext(letters=tuple(rng.sample(L.LETTERS, 6)), lexicon=lexicon, rng=rng)
        if not generator.can_generate(ctx):
            continue
        exercise = generator.generate(ctx)
        if exercise is None:
            continue
        produced += 1

        assert exercise.generator_id == generator.id
        assert exercise.prompt.strip()
        assert exercise.explanation.strip()
        assert exercise.accepted, "у задания должен быть хотя бы один верный ответ"

        for answer in exercise.accepted:
            verdict = check(exercise, answer)
            assert verdict.correct, (
                f"{generator.id}: заявленный верный ответ {answer!r} не прошёл проверку "
                f"({verdict.comment}) для вопроса {exercise.prompt!r}"
            )

    assert produced > 0, f"{generator.id} не смог собрать ни одного задания"


@pytest.mark.parametrize("generator", ALL_GENERATORS, ids=lambda g: g.id)
def test_generator_rejects_nonsense(generator, lexicon, rng):
    for _ in range(60):
        ctx = GenContext(letters=tuple(rng.sample(L.LETTERS, 6)), lexicon=lexicon, rng=rng)
        exercise = generator.generate(ctx) if generator.can_generate(ctx) else None
        if exercise is None or exercise.answer_mode is AnswerMode.NUMBER:
            # У числовых заданий любая строка цифр может случайно совпасть с ответом.
            continue
        assert not check(exercise, "ъъъ").correct


@pytest.mark.parametrize("generator", ALL_GENERATORS, ids=lambda g: g.id)
def test_exercise_survives_serialisation(generator, lexicon, rng):
    from arabic_bot.domain.models import Exercise

    ctx = GenContext(letters=tuple(L.LETTERS[:6]), lexicon=lexicon, rng=rng)
    exercise = generator.generate(ctx) if generator.can_generate(ctx) else None
    if exercise is None:
        pytest.skip("нет материала под этот фокус")
    restored = Exercise.from_dict(exercise.to_dict())
    assert restored == exercise


def test_choice_questions_only_where_typing_is_impossible(lexicon, rng):
    """Пользователь просил отвечать текстом везде, где это физически возможно."""
    allowed = {"name_to_letter", "form_initial", "form_final", "digit_single", "name_to_digit"}
    for generator in ALL_GENERATORS:
        ctx = GenContext(letters=tuple(L.LETTERS[:6]), lexicon=lexicon, rng=rng)
        exercise = generator.generate(ctx) if generator.can_generate(ctx) else None
        if exercise and exercise.answer_mode is AnswerMode.CHOICE:
            assert generator.id in allowed, (
                f"{generator.id} требует выбора кнопкой, хотя ответ можно набрать текстом"
            )


@pytest.mark.parametrize("generator", ALL_GENERATORS, ids=lambda g: g.id)
def test_hint_never_gives_away_the_answer(generator, lexicon, rng):
    """Подсказка не имеет права содержать правильный ответ.

    Так протекали сразу четыре типа: в «какая это буква» подсказкой шло
    описание звука («обычная т» — то есть «та»), в разборе слова примером было
    «kitab» ровно тогда, когда попадалось كتاب, у цифр примером было «сабаа»
    при ٧, а в подсчёте буквы подсказка называла ноль, когда ноль и был ответом.
    """
    from arabic_bot.domain.normalize import normalize_answer, split_tokens

    for _ in range(ROUNDS):
        ctx = GenContext(letters=tuple(rng.sample(L.LETTERS, 6)), lexicon=lexicon, rng=rng)
        if not generator.can_generate(ctx):
            continue
        exercise = generator.generate(ctx)
        if exercise is None or not exercise.hint:
            continue

        hint_tokens = set(split_tokens(exercise.hint))
        hint_flat = normalize_answer(exercise.hint)

        for answer in exercise.accepted:
            # Номера вариантов («1», «2») подсказкой не считаются: в ней их нет,
            # а вот содержательный ответ искать нужно и целиком, и по словам.
            if answer in hint_tokens or (len(answer) > 2 and answer in hint_flat):
                pytest.fail(
                    f"{generator.id}: подсказка «{exercise.hint}» содержит ответ «{answer}» "
                    f"на вопрос «{exercise.prompt[:60]}»"
                )


@pytest.mark.parametrize("generator", ALL_GENERATORS, ids=lambda g: g.id)
def test_pronunciation_note_is_not_a_hint_when_the_answer_is_the_name(generator, lexicon, rng):
    """`note_ru` описывает звук буквы, то есть выдаёт её название.

    Проверка литеральных утечек этот случай не ловит: подсказка «обычная т»
    слова «та» не содержит, но однозначно на него указывает. Поэтому запрет
    структурный — note_ru нельзя показывать до ответа там, где ответ и есть
    название буквы.
    """
    notes = {letter.note_ru for letter in L.LETTERS if letter.note_ru}
    name_answer_sets = {letter.id: letter.accepted for letter in L.LETTERS}

    for _ in range(120):
        ctx = GenContext(letters=tuple(rng.sample(L.LETTERS, 6)), lexicon=lexicon, rng=rng)
        if not generator.can_generate(ctx):
            continue
        exercise = generator.generate(ctx)
        if exercise is None or not exercise.hint:
            continue
        if exercise.answer_mode is not AnswerMode.TEXT:
            continue

        answer_is_a_letter_name = set(exercise.accepted) in (
            set(accepted) for accepted in name_answer_sets.values()
        )
        if answer_is_a_letter_name:
            assert exercise.hint not in notes, (
                f"{generator.id}: подсказка «{exercise.hint}» описывает звук буквы, "
                f"а спрашивается как раз её название"
            )
