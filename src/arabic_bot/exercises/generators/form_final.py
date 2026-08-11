"""Как буква выглядит в конце слова."""

from __future__ import annotations

from ...domain.letters import LETTERS
from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext, build_choices, pick
from ..registry import register


@register
class FormFinal(ExerciseGenerator):
    id = "form_final"
    title = "Конечная форма"
    weight = 10
    difficulty = 2

    def generate(self, ctx: GenContext) -> Exercise | None:
        letter = pick(ctx.rng, ctx.letters)
        if letter is None:
            return None

        other = pick(ctx.rng, [l for l in LETTERS if l is not letter])
        wrong = [letter.isolated, letter.initial, other.final if other else letter.medial]
        wrong = list(dict.fromkeys(w for w in wrong if w != letter.final))[:3]
        choices = build_choices(ctx.rng, letter.final, wrong)
        correct_key = next(c.key for c in choices if c.correct)

        return Exercise(
            generator_id=self.id,
            prompt=f"Как буква {letter.name_ru} выглядит в конце слова?",
            display=letter.char,
            answer_mode=AnswerMode.CHOICE,
            accepted=(correct_key, letter.final),
            choices=choices,
            hint="В конце слова буква присоединяется к предыдущей справа.",
            explanation=(
                f"{letter.name_ru}: отдельно {letter.isolated}, в начале {letter.initial}, "
                f"в середине {letter.medial}, в конце {letter.final}"
            ),
            focus_letters=(letter.id,),
        )
