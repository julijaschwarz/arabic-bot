"""Многозначные числа: ٣٤٥ → 345.

Цифры внутри числа пишутся слева направо, как и в европейской записи, — это
главное, что нужно усвоить, поэтому числа берём с разными разрядами.
"""

from __future__ import annotations

from ...domain.digits import to_arabic
from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext
from ..registry import register


@register
class DigitMulti(ExerciseGenerator):
    id = "digit_multi"
    title = "Многозначные числа"
    weight = 8
    difficulty = 2
    uses_letters = False

    def generate(self, ctx: GenContext) -> Exercise | None:
        length = ctx.rng.choice([2, 2, 3, 3, 4])
        low, high = 10 ** (length - 1), 10**length - 1
        number = ctx.rng.randint(low, high)
        arabic = to_arabic(number)

        return Exercise(
            generator_id=self.id,
            prompt="Какое это число? Напишите его обычными цифрами.",
            display=arabic,
            answer_mode=AnswerMode.NUMBER,
            accepted=(str(number),),
            hint="Цифры в числе читаются в том же порядке, что и у нас — слева направо.",
            explanation=f"{arabic} — это {number}",
            payload={"number": number},
        )
