"""Названо имя буквы — выбрать её глиф.

Единственный тип, где ответ кнопкой обязателен: арабскую букву не набрать
с обычной клавиатуры.
"""

from __future__ import annotations

from ...domain.letters import LETTERS
from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext, build_choices, distractors
from ..registry import register


@register
class NameToLetter(ExerciseGenerator):
    id = "name_to_letter"
    title = "Название → буква"
    weight = 12
    difficulty = 1

    def generate(self, ctx: GenContext) -> Exercise | None:
        letter = ctx.shuffled_letters()[0]
        wrong = distractors(ctx.rng, [l.char for l in LETTERS], [letter.char], 3)
        choices = build_choices(ctx.rng, letter.char, wrong)
        correct_key = next(c.key for c in choices if c.correct)
        return Exercise(
            generator_id=self.id,
            prompt=f"Какая буква называется «{letter.name_ru}»?",
            answer_mode=AnswerMode.CHOICE,
            accepted=(correct_key, letter.char),
            choices=choices,
            hint=letter.note_ru or None,
            explanation=f"{letter.name_ru} пишется как {letter.char}",
            focus_letters=(letter.id,),
        )
