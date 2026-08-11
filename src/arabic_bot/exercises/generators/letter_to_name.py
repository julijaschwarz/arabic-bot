"""Показана буква — назвать её."""

from __future__ import annotations

from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext, letter_answers
from ..registry import register


@register
class LetterToName(ExerciseGenerator):
    id = "letter_to_name"
    title = "Буква → название"
    weight = 14
    difficulty = 1

    def generate(self, ctx: GenContext) -> Exercise | None:
        letter = ctx.shuffled_letters()[0]
        return Exercise(
            generator_id=self.id,
            prompt="Как называется эта буква?",
            display=letter.char,
            answer_mode=AnswerMode.TEXT,
            accepted=letter_answers(letter),
            # Подсказки нет намеренно: note_ru описывает звук буквы («обычная т»),
            # то есть выдаёт ответ. Он переехал в пояснение — после ответа.
            explanation=(
                f"{letter.char} — {letter.name_ru} ({letter.name_en}), {letter.name_ar}"
                + (f" — {letter.note_ru}" if letter.note_ru else "")
            ),
            focus_letters=(letter.id,),
        )
