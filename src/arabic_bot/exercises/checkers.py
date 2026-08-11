"""Проверка ответов.

Правило простое: сомнение — в пользу отвечающего. Транслитерации арабских
названий неизбежно пересекаются («ха» — это и ح, и خ, и ه), поэтому такие
ответы засчитываются, а разницу бот поясняет в подсказке.
"""

from __future__ import annotations

from typing import Callable

from ..domain.letters import BY_ID, EXTRA_SIGNS, resolve_candidates, resolve_sign
from ..domain.models import AnswerMode, Exercise, Verdict
from ..domain.normalize import normalize_answer, parse_number, split_tokens


def _check_text(exercise: Exercise, raw: str) -> Verdict:
    answer = normalize_answer(raw)
    if not answer:
        return Verdict(False, "Пустой ответ.")
    return Verdict(answer in exercise.accepted)


def _check_number(exercise: Exercise, raw: str) -> Verdict:
    value = parse_number(raw)
    if value is None:
        return Verdict(False, "Не получилось разобрать число — напишите его цифрами.")
    return Verdict(str(value) in exercise.accepted)


def _check_choice(exercise: Exercise, raw: str) -> Verdict:
    """Три прохода по вариантам, от точного совпадения к приблизительному.

    Порядок принципиален. Формы одной буквы (مـ, ـمـ, ـم) после нормализации
    неразличимы — кашида отбрасывается, — а арабская цифра ٣ нормализуется
    в «3» и сталкивается с номером варианта. Поэтому сначала точная метка,
    потом номер, и только затем приблизительное сравнение.
    """
    choices = exercise.choices or ()
    stripped = raw.strip()

    for choice in choices:
        if stripped == choice.label:
            return Verdict(choice.correct)

    answer = normalize_answer(raw)
    for choice in choices:
        if answer == normalize_answer(choice.key):
            return Verdict(choice.correct)

    loose = [c for c in choices if answer and answer == normalize_answer(c.label)]
    if len(loose) == 1:
        return Verdict(loose[0].correct)
    if len(loose) > 1:
        return Verdict(False, "Так подходит сразу несколько вариантов — нажмите кнопку.")
    return Verdict(False, "Выберите один из вариантов кнопкой.")


def _check_letter_sequence(exercise: Exercise, raw: str) -> Verdict:
    """Разбор слова по буквам: «кяф та алиф ба».

    Целое слово транслитерацией («kitab») тоже принимается — так задумано в ТЗ.
    """
    whole = normalize_answer(raw)
    if whole and whole in set(exercise.payload.get("whole_word_accepted", ())):
        return Verdict(True)

    expected: list[str] = list(exercise.payload.get("units", ()))
    tokens = split_tokens(raw)
    if not tokens:
        return Verdict(False, "Пустой ответ.")

    cursor = 0
    for position, unit_id in enumerate(expected, start=1):
        span = _consume(unit_id, tokens, cursor)
        if span is None:
            if cursor >= len(tokens):
                return Verdict(
                    False, f"Ответ оборвался: не хватает знаков с позиции {position}."
                )
            return Verdict(
                False,
                f"Расхождение на позиции {position}: вы написали «{tokens[cursor]}», "
                f"а там {_unit_name(unit_id)}.",
            )
        cursor += span

    if cursor != len(tokens):
        extra = " ".join(tokens[cursor:])
        return Verdict(False, f"В конце оказалось лишнее: «{extra}».")
    return Verdict(True)


def _consume(unit_id: str, tokens: list[str], start: int) -> int | None:
    """Сколько токенов занимает знак: обычно один, но «та марбута» — два."""
    for span in (1, 2):
        if start + span > len(tokens):
            break
        candidate = " ".join(tokens[start : start + span])
        if unit_id.startswith("sign:"):
            sign = resolve_sign(candidate)
            if sign is not None and sign.char == unit_id.removeprefix("sign:"):
                return span
        elif unit_id in resolve_candidates(candidate):
            return span
    return None


def _unit_name(unit_id: str) -> str:
    if unit_id.startswith("sign:"):
        return next(
            (s.name_ru for s in EXTRA_SIGNS if s.char == unit_id.removeprefix("sign:")),
            unit_id,
        )
    return BY_ID[unit_id].name_ru


CHECKERS: dict[AnswerMode, Callable[[Exercise, str], Verdict]] = {
    AnswerMode.TEXT: _check_text,
    AnswerMode.NUMBER: _check_number,
    AnswerMode.CHOICE: _check_choice,
    AnswerMode.LETTER_SEQUENCE: _check_letter_sequence,
}


def check(exercise: Exercise, raw: str) -> Verdict:
    return CHECKERS[exercise.answer_mode](exercise, raw)
