"""Последняя буква в слове."""

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
class LastLetter(ExerciseGenerator):
    id = "last_letter"
    title = "Последняя буква слова"
    weight = 12
    difficulty = 2

    def generate(self, ctx: GenContext) -> Exercise | None:
        for letter in ctx.shuffled_letters():
            words = ctx.lexicon.where(ends_with=letter)
            word = pick(ctx.rng, words)
            if word is None:
                continue
            return Exercise(
                generator_id=self.id,
                prompt=f"На какую букву заканчивается это слово? ({word.ru})",
                display=word.text,
                answer_mode=AnswerMode.TEXT,
                accepted=letter_answers(letter),
                hint="Последняя буква — самая левая: письмо идёт справа налево.",
                explanation=(
                    f"{word.text} ({word.translit}, {word.ru}) заканчивается на "
                    f"{letter.char} — {letter.name_ru}"
                ),
                focus_letters=(letter.id,),
                payload={"word": word.text},
            )
        return None
