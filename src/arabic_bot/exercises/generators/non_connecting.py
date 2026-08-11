"""Шесть букв ا د ذ ر ز و не соединяются со следующей — узнать их в ряду.

Спрашиваем в обе стороны: и «какая не соединяется», и «какая соединяется» —
иначе легко запомнить формулировку вместо самих букв.
"""

from __future__ import annotations

from ...domain.letters import CONNECTING, NON_CONNECTING, Letter
from ...domain.models import AnswerMode, Exercise
from ..base import ExerciseGenerator, GenContext, distractors, numbered
from ..registry import register


@register
class NonConnecting(ExerciseGenerator):
    id = "non_connecting"
    title = "Соединение со следующей буквой"
    weight = 8
    difficulty = 2

    def generate(self, ctx: GenContext) -> Exercise | None:
        focus_non_connecting = [l for l in ctx.letters if not l.connects_forward]
        # Если в фокусе дня нет непривязываемых букв — спрашиваем в обратную сторону.
        ask_non_connecting = bool(focus_non_connecting) and ctx.rng.random() < 0.7

        if ask_non_connecting:
            target: Letter = ctx.rng.choice(focus_non_connecting)
            others = distractors(ctx.rng, CONNECTING, [target], 3)
            question = "Какая из этих букв НЕ соединяется со следующей?"
        else:
            focus_connecting = [l for l in ctx.letters if l.connects_forward]
            if not focus_connecting:
                return None
            target = ctx.rng.choice(focus_connecting)
            others = distractors(ctx.rng, NON_CONNECTING, [target], 3)
            question = "Какая из этих букв соединяется со следующей?"

        if len(others) < 3:
            return None

        options = [target, *others]
        ctx.rng.shuffle(options)
        index = options.index(target) + 1

        accepted = {str(index), target.char, *target.accepted}
        rule = "не соединяются со следующей: " + " ".join(l.char for l in NON_CONNECTING)

        return Exercise(
            generator_id=self.id,
            prompt=f"{question}\n\n{numbered([l.char for l in options])}",
            answer_mode=AnswerMode.TEXT,
            accepted=tuple(sorted(accepted)),
            hint="Можно ответить номером или названием буквы.",
            explanation=f"Ответ {index}) {target.char} — {target.name_ru}. Всего шесть букв {rule}",
            focus_letters=(target.id,),
            payload={"options": [l.id for l in options]},
        )
