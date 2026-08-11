"""Как буква выглядит в начале слова."""

from __future__ import annotations

from ...domain.letters import CONNECTING
from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext, build_choices, pick
from ..registry import register


@register
class FormInitial(ExerciseGenerator):
    id = "form_initial"
    title = "Начальная форма"
    weight = 10
    difficulty = 2

    def generate(self, ctx: GenContext) -> Exercise | None:
        # У непривязываемых букв начальная форма совпадает с отдельной —
        # спрашивать про неё бессмысленно.
        letter = pick(ctx.rng, [l for l in ctx.letters if l.connects_forward])
        if letter is None:
            return None

        other = pick(ctx.rng, [l for l in CONNECTING if l is not letter])
        wrong = [letter.medial, letter.final, other.initial if other else letter.isolated]
        wrong = list(dict.fromkeys(w for w in wrong if w != letter.initial))[:3]
        choices = build_choices(ctx.rng, letter.initial, wrong)
        correct_key = next(c.key for c in choices if c.correct)

        return Exercise(
            generator_id=self.id,
            prompt=f"Как буква {letter.name_ru} выглядит в начале слова?",
            display=letter.char,
            answer_mode=AnswerMode.CHOICE,
            accepted=(correct_key, letter.initial),
            choices=choices,
            hint="В начале слова буква соединяется только слева.",
            explanation=(
                f"{letter.name_ru}: отдельно {letter.isolated}, в начале {letter.initial}, "
                f"в середине {letter.medial}, в конце {letter.final}"
            ),
            focus_letters=(letter.id,),
        )
