"""Одна цифра ٠–٩ в обе стороны."""

from __future__ import annotations

from ...domain.digits import DIGITS
from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext, build_choices, distractors
from ..registry import register


@register
class DigitSingle(ExerciseGenerator):
    id = "digit_single"
    title = "Цифры ٠–٩"
    weight = 10
    difficulty = 1
    uses_letters = False

    def generate(self, ctx: GenContext) -> Exercise | None:
        digit = ctx.rng.choice(DIGITS)
        if ctx.rng.random() < 0.6:
            return Exercise(
                generator_id=self.id,
                prompt="Какая это цифра? Напишите её обычными цифрами.",
                display=digit.char,
                answer_mode=AnswerMode.NUMBER,
                accepted=(str(digit.value),),
                explanation=f"{digit.char} — это {digit.value} ({digit.name_ru})",
            )

        # Обратное направление: арабскую цифру с клавиатуры не набрать, поэтому кнопки.
        wrong = distractors(ctx.rng, [d.char for d in DIGITS], [digit.char], 3)
        choices = build_choices(ctx.rng, digit.char, wrong)
        correct_key = next(c.key for c in choices if c.correct)
        return Exercise(
            generator_id=self.id,
            prompt=f"Как по-арабски пишется цифра {digit.value}?",
            answer_mode=AnswerMode.CHOICE,
            accepted=(correct_key, digit.char),
            choices=choices,
            explanation=f"{digit.value} — это {digit.char} ({digit.name_ru})",
        )
