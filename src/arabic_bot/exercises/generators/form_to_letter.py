"""Показана форма буквы (ـبـ) — узнать саму букву."""

from __future__ import annotations

from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext, letter_answers, pick
from ..registry import register

POSITIONS = {
    "initial": "в начале слова",
    "medial": "в середине слова",
    "final": "в конце слова",
}


@register
class FormToLetter(ExerciseGenerator):
    id = "form_to_letter"
    title = "Форма → буква"
    weight = 12
    difficulty = 2

    def generate(self, ctx: GenContext) -> Exercise | None:
        letter = pick(ctx.rng, ctx.letters)
        if letter is None:
            return None

        # Для непривязываемых букв начальная форма неотличима от отдельной.
        positions = list(POSITIONS) if letter.connects_forward else ["medial", "final"]
        position = ctx.rng.choice(positions)

        return Exercise(
            generator_id=self.id,
            prompt=f"Какая это буква? Она показана так, как пишется {POSITIONS[position]}.",
            display=letter.form(position),
            answer_mode=AnswerMode.TEXT,
            accepted=letter_answers(letter),
            explanation=(
                f"{letter.form(position)} — это {letter.name_ru}, отдельно она пишется "
                f"{letter.isolated}" + (f" ({letter.note_ru})" if letter.note_ru else "")
            ),
            focus_letters=(letter.id,),
            payload={"position": position},
        )
