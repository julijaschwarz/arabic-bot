"""«В каком из слов есть буква ب?»"""

from __future__ import annotations

from ...domain.models import AnswerMode, Exercise
from ...domain.normalize import normalize_answer
from ..base import ExerciseGenerator, GenContext, numbered, pick
from ..registry import register


@register
class WhichWordHas(ExerciseGenerator):
    id = "which_word_has"
    title = "В каком слове есть буква"
    weight = 12
    difficulty = 2

    def generate(self, ctx: GenContext) -> Exercise | None:
        for letter in ctx.shuffled_letters():
            target = pick(ctx.rng, ctx.lexicon.where(contains=letter, max_length=5))
            if target is None:
                continue
            pool = list(ctx.lexicon.where(excludes=letter, max_length=5))
            if len(pool) < 3:
                continue
            ctx.rng.shuffle(pool)
            options = [target, *pool[:3]]
            ctx.rng.shuffle(options)
            index = options.index(target) + 1

            accepted = {str(index), target.text, normalize_answer(target.translit)}
            return Exercise(
                generator_id=self.id,
                prompt=(
                    f"В каком из слов есть буква {letter.char} ({letter.name_ru})?\n\n"
                    + numbered([w.text for w in options])
                ),
                answer_mode=AnswerMode.TEXT,
                accepted=tuple(sorted(a for a in accepted if a)),
                hint="Можно ответить номером или самим словом.",
                explanation=(
                    f"Ответ {index}) {target.text} — {target.translit}, {target.ru}. "
                    f"Буква {letter.char} стоит здесь "
                    f"{target.count(letter)} раз(а)."
                ),
                focus_letters=(letter.id,),
                payload={"options": [w.text for w in options], "answer_index": index},
            )
        return None
