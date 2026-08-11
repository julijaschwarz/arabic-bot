from __future__ import annotations

import pytest

from arabic_bot.domain.models import AnswerMode, Choice, Exercise
from arabic_bot.exercises.checkers import check


def text_exercise(*accepted: str) -> Exercise:
    return Exercise(
        generator_id="t",
        prompt="?",
        answer_mode=AnswerMode.TEXT,
        accepted=accepted,
        explanation="—",
    )


@pytest.mark.parametrize("answer", ["ба", "БА", "баа", "ba", "Baa", "bāʼ"])
def test_text_answer_is_tolerant_to_spelling(answer):
    assert check(text_exercise("ба", "ba"), answer).correct


def test_text_answer_rejects_other_letter():
    assert not check(text_exercise("ба", "ba"), "мим").correct


def test_accepted_is_normalised_even_if_generator_forgot():
    # Генератор положил сырое «أسود»; проверка всё равно должна сойтись.
    exercise = text_exercise("أسود")
    assert check(exercise, "أسود").correct


def choice_exercise(*labels: str, correct_index: int) -> Exercise:
    choices = tuple(
        Choice(key=str(i), label=label, correct=(i - 1 == correct_index))
        for i, label in enumerate(labels, start=1)
    )
    return Exercise(
        generator_id="t",
        prompt="?",
        answer_mode=AnswerMode.CHOICE,
        accepted=(str(correct_index + 1),),
        explanation="—",
        choices=choices,
    )


def test_choice_by_button_key():
    exercise = choice_exercise("٧", "٣", "٥", "٩", correct_index=0)
    assert check(exercise, "1").correct
    assert not check(exercise, "2").correct


def test_choice_matches_exact_label_before_number():
    """٣ нормализуется в «3» и раньше сталкивалась с номером варианта."""
    exercise = choice_exercise("٧", "٣", "٥", "٩", correct_index=1)
    assert check(exercise, "٣").correct


def test_choice_of_letter_forms_is_not_confused_by_kashida():
    """مـ, ـمـ и ـم после нормализации неразличимы — нужен точный разбор."""
    exercise = choice_exercise("مـ", "ـمـ", "ـم", "م", correct_index=0)
    assert check(exercise, "مـ").correct
    assert not check(exercise, "ـم").correct
    # Голая «م» — это ровно четвёртый вариант, его и засчитываем (неверный).
    assert not check(exercise, "م").correct


def test_choice_asks_for_a_button_when_answer_is_ambiguous():
    """Если написанное подходит сразу к нескольким вариантам, гадать нельзя."""
    exercise = choice_exercise("مـ", "ـمـ", "ـم", "بـ", correct_index=0)
    verdict = check(exercise, "م")
    assert not verdict.correct and "кнопк" in verdict.comment


def sequence_exercise() -> Exercise:
    return Exercise(
        generator_id="spell_word",
        prompt="?",
        answer_mode=AnswerMode.LETTER_SEQUENCE,
        accepted=("гайн ра фа та марбута",),
        explanation="—",
        payload={
            "units": ["ghayn", "ra", "fa", "sign:ة"],
            "whole_word_accepted": ["ghurfa"],
        },
    )


def test_letter_sequence_accepts_letter_names():
    assert check(sequence_exercise(), "гайн ра фа та марбута").correct


def test_letter_sequence_accepts_multiword_sign_name():
    """«та марбута» — два слова, но один знак."""
    assert check(sequence_exercise(), "гайн, ра, фа, та марбута").correct


def test_letter_sequence_accepts_whole_word():
    assert check(sequence_exercise(), "ghurfa").correct


def test_letter_sequence_reports_position_of_mistake():
    verdict = check(sequence_exercise(), "гайн ра ба та марбута")
    assert not verdict.correct
    assert "позиции 3" in verdict.comment


def test_letter_sequence_rejects_short_answer():
    verdict = check(sequence_exercise(), "гайн ра")
    assert not verdict.correct
    assert "оборвался" in verdict.comment


def number_exercise(value: str) -> Exercise:
    return Exercise(
        generator_id="t",
        prompt="?",
        answer_mode=AnswerMode.NUMBER,
        accepted=(value,),
        explanation="—",
    )


@pytest.mark.parametrize("answer", ["345", "٣٤٥", " 345 "])
def test_number_accepts_both_digit_systems(answer):
    assert check(number_exercise("345"), answer).correct


def test_zero_answer_is_valid():
    assert check(number_exercise("0"), "0").correct
    assert check(number_exercise("0"), "ни разу").correct
