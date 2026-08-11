"""Показана цифра ٧ — написать её арабское название («сабаа»)."""

from __future__ import annotations

from ...domain.digits import DIGITS
from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext
from ..registry import register


@register
class DigitToName(ExerciseGenerator):
    id = "digit_to_name"
    title = "Цифра → название"
    weight = 10
    difficulty = 2
    uses_letters = False

    def generate(self, ctx: GenContext) -> Exercise | None:
        digit = ctx.rng.choice(DIGITS)
        return Exercise(
            generator_id=self.id,
            prompt="Как называется эта цифра по-арабски? Напишите название словом.",
            display=digit.char,
            answer_mode=AnswerMode.TEXT,
            accepted=tuple(sorted(digit.accepted)),
            hint="Можно по-русски или латиницей.",
            explanation=(
                f"{digit.char} — {digit.name_ru} ({digit.name_en}), "
                f"{digit.name_ar}, это {digit.value}"
            ),
            payload={"value": digit.value},
        )
