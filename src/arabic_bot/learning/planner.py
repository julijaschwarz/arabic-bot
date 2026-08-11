"""Сборка сессии: какой тип задания дать следующим.

Планировщик ничего не знает про конкретные типы — он работает со списком из
реестра. Новый генератор появляется в сессии сам, достаточно его веса.
"""

from __future__ import annotations

import logging
from random import Random

from ..domain.lexicon import Lexicon
from ..domain.letters import Letter
from ..domain.models import Exercise
from ..exercises import registry
from ..exercises.base import ExerciseGenerator, GenContext

log = logging.getLogger(__name__)

REPEAT_PENALTY = 0.15
"""Во сколько раз падает шанс повторить тот же тип задания подряд."""

DIGIT_EVERY = 4
"""Примерно каждый четвёртый вопрос — про цифры, чтобы счёт не выпадал."""

MAX_TRIES = 12


class SessionPlanner:
    def __init__(self, lexicon: Lexicon, rng: Random | None = None) -> None:
        self._lexicon = lexicon
        self._rng = rng or Random()
        self._generators: tuple[ExerciseGenerator, ...] = registry.all_generators()

    @property
    def generators(self) -> tuple[ExerciseGenerator, ...]:
        return self._generators

    def next_exercise(
        self,
        focus: tuple[Letter, ...],
        *,
        position: int,
        last_generator_id: str | None = None,
        images_enabled: bool = True,
    ) -> Exercise | None:
        ctx = GenContext(
            letters=focus,
            lexicon=self._lexicon,
            rng=self._rng,
            images_enabled=images_enabled,
        )
        available = [gen for gen in self._generators if gen.can_generate(ctx)]
        if not available:
            return None

        want_digits = position > 0 and position % DIGIT_EVERY == 0
        pool = self._filtered(available, want_digits=want_digits)

        for _ in range(MAX_TRIES):
            if not pool:
                pool = list(available)
            generator = self._weighted_pick(pool, last_generator_id)
            exercise = generator.generate(ctx)
            if exercise is not None:
                return exercise
            # Материала под этот тип не нашлось — больше его в этот раз не берём.
            pool = [gen for gen in pool if gen is not generator]

        log.warning("Не удалось собрать задание для фокуса %s", [l.id for l in focus])
        return None

    # --- внутреннее ---

    def _filtered(
        self, generators: list[ExerciseGenerator], *, want_digits: bool
    ) -> list[ExerciseGenerator]:
        subset = [gen for gen in generators if gen.uses_letters is not want_digits]
        return subset or list(generators)

    def _weighted_pick(
        self, pool: list[ExerciseGenerator], last_generator_id: str | None
    ) -> ExerciseGenerator:
        weights = [
            gen.weight * (REPEAT_PENALTY if gen.id == last_generator_id else 1.0) for gen in pool
        ]
        if sum(weights) <= 0:
            return self._rng.choice(pool)
        return self._rng.choices(pool, weights=weights, k=1)[0]
