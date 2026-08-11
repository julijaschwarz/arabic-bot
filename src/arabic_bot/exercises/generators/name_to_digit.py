"""Названо арабское числительное — выбрать нужную цифру.

Ответ кнопкой: арабскую цифру не набрать с обычной клавиатуры.
"""

from __future__ import annotations

from ...domain.digits import DIGITS
from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext, build_choices, distractors
from ..registry import register


@register
class NameToDigit(ExerciseGenerator):
    id = "name_to_digit"
    title = "Название → цифра"
    weight = 10
    difficulty = 2
    uses_letters = False

    def generate(self, ctx: GenContext) -> Exercise | None:
        digit = ctx.rng.choice(DIGITS)
        # Показываем название то по-русски, то латиницей — чтобы узнавалось и так и так.
        name = digit.name_ru if ctx.rng.random() < 0.6 else digit.name_en

        wrong = distractors(ctx.rng, [d.char for d in DIGITS], [digit.char], 3)
        choices = build_choices(ctx.rng, digit.char, wrong)
        correct_key = next(c.key for c in choices if c.correct)

        return Exercise(
            generator_id=self.id,
            prompt=f"Какая это цифра — «{name}»?",
            answer_mode=AnswerMode.CHOICE,
            accepted=(correct_key, digit.char),
            choices=choices,
            explanation=(
                f"«{digit.name_ru}» ({digit.name_en}, {digit.name_ar}) — "
                f"это {digit.char}, то есть {digit.value}"
            ),
            payload={"value": digit.value},
        )
