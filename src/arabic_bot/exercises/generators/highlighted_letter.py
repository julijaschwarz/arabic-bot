"""Слово-картинка с одной подсвеченной буквой — назвать её.

Единственный способ показать букву именно в том виде, в каком она стоит
внутри связного слова, поэтому здесь картинка обязательна.
"""

from __future__ import annotations

from ...domain.models import AnswerMode, Exercise, ImageSpec
from ..base import (
    ExerciseGenerator,
    GenContext,
    letter_answers,
    pick,
)
from ..registry import register


@register
class HighlightedLetter(ExerciseGenerator):
    id = "highlighted_letter"
    title = "Выделенная буква в слове"
    weight = 12
    difficulty = 3

    def can_generate(self, ctx: GenContext) -> bool:
        return ctx.images_enabled

    def generate(self, ctx: GenContext) -> Exercise | None:
        for letter in ctx.shuffled_letters():
            word = pick(ctx.rng, ctx.lexicon.where(contains=letter, min_length=3))
            if word is None:
                continue
            positions = [i for i, unit in enumerate(word.units) if unit is letter]
            index = ctx.rng.choice(positions)

            return Exercise(
                generator_id=self.id,
                # Подсказывать позицию не нужно: её показывает сама подсветка,
                # иначе задание вырождается в «первая буква слова».
                prompt="Какая буква выделена цветом?",
                answer_mode=AnswerMode.TEXT,
                accepted=letter_answers(letter),
                image=ImageSpec(text=word.text, highlight=index, caption=word.ru),
                hint="Внутри слова буква меняет форму, но остаётся собой.",
                explanation=(
                    f"Выделена {letter.char} — {letter.name_ru}. "
                    f"Слово: {word.text} ({word.translit}, {word.ru})"
                ),
                focus_letters=(letter.id,),
                payload={
                    "word": word.text,
                    "index": index,
                    # Если картинку нарисовать не удалось, про цвет говорить нельзя.
                    "prompt_without_image": (
                        f"Какая буква стоит на {index + 1}-м месте от начала "
                        f"(то есть справа) в этом слове?"
                    ),
                },
            )
        return None
