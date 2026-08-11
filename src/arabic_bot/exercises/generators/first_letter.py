"""Первая буква в слове."""

from __future__ import annotations

from ...domain.models import AnswerMode, Exercise
from ..base import (
    ExerciseGenerator,
    GenContext,
    letter_answers,
    pick,
)
from ..registry import register


@register
class FirstLetter(ExerciseGenerator):
    id = "first_letter"
    title = "Первая буква слова"
    weight = 12
    difficulty = 2

    def generate(self, ctx: GenContext) -> Exercise | None:
        for letter in ctx.shuffled_letters():
            words = ctx.lexicon.where(starts_with=letter)
            word = pick(ctx.rng, words)
            if word is None:
                continue
            return Exercise(
                generator_id=self.id,
                prompt=f"С какой буквы начинается это слово? ({word.ru})",
                display=word.text,
                answer_mode=AnswerMode.TEXT,
                accepted=letter_answers(letter),
                hint="Арабские слова читаются справа налево — первая буква самая правая.",
                explanation=(
                    f"{word.text} ({word.translit}, {word.ru}) начинается с "
                    f"{letter.char} — {letter.name_ru}"
                ),
                focus_letters=(letter.id,),
                payload={"word": word.text},
            )
        return None
