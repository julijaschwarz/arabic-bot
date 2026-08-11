"""«Сколько раз ل встречается в ليل?»

Иногда буквы в слове нет вовсе — правильный ответ 0. Без таких вопросов
привычка «раз спросили, значит есть» ломает счёт.
"""

from __future__ import annotations

from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext, pick
from ..registry import register


@register
class CountLetter(ExerciseGenerator):
    id = "count_letter"
    title = "Сколько раз встречается буква"
    weight = 10
    difficulty = 3

    def generate(self, ctx: GenContext) -> Exercise | None:
        for letter in ctx.shuffled_letters():
            # Сначала пробуем слова, где буква встречается дважды — это интереснее.
            candidates = ctx.lexicon.where(min_count=(letter, 2))
            if not candidates or ctx.rng.random() < 0.45:
                candidates = ctx.lexicon.where(contains=letter)
            if not candidates or ctx.rng.random() < 0.2:
                candidates = ctx.lexicon.where(excludes=letter, max_length=4) or candidates
            word = pick(ctx.rng, candidates)
            if word is None:
                continue

            times = word.count(letter)
            plural = "раз" if times in {0, 1} or times >= 5 else "раза"
            return Exercise(
                generator_id=self.id,
                prompt=(
                    f"Сколько раз буква {letter.char} ({letter.name_ru}) "
                    f"встречается в этом слове? ({word.ru})"
                ),
                display=word.text,
                answer_mode=AnswerMode.NUMBER,
                accepted=(str(times),),
                hint="Буквы может не быть в слове совсем.",
                explanation=(
                    f"В слове {word.text} ({word.translit}) буква {letter.char} "
                    f"встречается {times} {plural}."
                ),
                focus_letters=(letter.id,),
                payload={"word": word.text},
            )
        return None
