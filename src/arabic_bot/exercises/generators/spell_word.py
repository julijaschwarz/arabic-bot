"""Разобрать слово по буквам.

Ответ принимается двумя способами, как и задумано: слово целиком
транслитерацией («kitab») либо названия букв через пробел («кяф та алиф ба»).
"""

from __future__ import annotations

from ...domain.letters import Letter
from ...domain.models import AnswerMode, Exercise, ImageSpec
from ...domain.normalize import normalize_answer
from ..base import ExerciseGenerator, GenContext, pick
from ..registry import register


@register
class SpellWord(ExerciseGenerator):
    id = "spell_word"
    title = "Разбор слова по буквам"
    weight = 10
    difficulty = 3

    def generate(self, ctx: GenContext) -> Exercise | None:
        focus_ids = {letter.id for letter in ctx.letters}

        # Берём короткие слова, где есть хотя бы одна буква из фокуса дня.
        candidates = [
            word
            for word in ctx.lexicon.where(min_length=3, max_length=4)
            if any(
                isinstance(unit, Letter) and unit.id in focus_ids for unit in word.units
            )
        ]
        word = pick(ctx.rng, candidates or ctx.lexicon.where(min_length=3, max_length=4))
        if word is None:
            return None

        units = [
            unit.id if isinstance(unit, Letter) else f"sign:{unit.char}"
            for unit in word.units
        ]
        names = " ".join(unit.name_ru for unit in word.units)

        return Exercise(
            generator_id=self.id,
            prompt=(
                f"Назовите все буквы этого слова по порядку — справа налево, "
                f"через пробел. ({word.ru})\n\n"
                f"Можно и одним словом целиком: как оно читается."
            ),
            answer_mode=AnswerMode.LETTER_SEQUENCE,
            accepted=(names,),
            # display не задаём: слово показывает картинка, а если она не вышла,
            # текст подставится из image.text.
            image=ImageSpec(text=word.text, caption=word.ru),
            hint="Названия через пробел, начиная с самой правой буквы.",
            explanation=f"{word.text} = {names} ({word.translit}, {word.ru})",
            focus_letters=tuple(
                unit.id for unit in word.units if isinstance(unit, Letter) and unit.id in focus_ids
            ),
            payload={
                "word": word.text,
                "units": units,
                "whole_word_accepted": sorted(
                    {normalize_answer(word.translit), normalize_answer(word.text)} - {""}
                ),
            },
        )
