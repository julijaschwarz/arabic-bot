"""Контракт генератора заданий.

Чтобы добавить новый тип задания, достаточно положить файл в
`exercises/generators/` с классом-наследником `ExerciseGenerator` и декоратором
`@register`. Реестр импортирует пакет целиком, планировщик увидит новый тип
автоматически — больше нигде править ничего не нужно.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from random import Random
from typing import ClassVar, Sequence, TypeVar

from ..domain.lexicon import Lexicon
from ..domain.letters import Letter
from ..domain.models import Choice, Exercise, ImageSpec

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class GenContext:
    """Всё, что нужно генератору: буквы дня, словарь и источник случайности."""

    letters: tuple[Letter, ...]
    lexicon: Lexicon
    rng: Random
    images_enabled: bool = True

    def shuffled_letters(self) -> list[Letter]:
        """Буквы фокуса в случайном порядке — чтобы задания не шли по алфавиту."""
        letters = list(self.letters)
        self.rng.shuffle(letters)
        return letters


class ExerciseGenerator(ABC):
    id: ClassVar[str]
    title: ClassVar[str]
    """Название типа для статистики и логов."""

    weight: ClassVar[int] = 10
    """Относительная частота появления в сессии."""

    difficulty: ClassVar[int] = 1
    """1 — узнавание, 2 — воспроизведение, 3 — разбор слова."""

    uses_letters: ClassVar[bool] = True
    """False у чисто цифровых заданий: они не привязаны к буквам дня."""

    def can_generate(self, ctx: GenContext) -> bool:
        return True

    @abstractmethod
    def generate(self, ctx: GenContext) -> Exercise | None:
        """Вернуть упражнение либо None, если под этот контекст материала не нашлось."""


# --- утилиты, которыми пользуются генераторы ---


def pick(rng: Random, items: Sequence[T]) -> T | None:
    return rng.choice(list(items)) if items else None


def distractors(rng: Random, pool: Sequence[T], exclude: Sequence[T], count: int) -> list[T]:
    """Набрать `count` неправильных вариантов, не пересекающихся с `exclude`."""
    candidates = [item for item in pool if item not in exclude]
    rng.shuffle(candidates)
    return candidates[:count]


def build_choices(rng: Random, correct: str, wrong: Sequence[str]) -> tuple[Choice, ...]:
    """Собрать перемешанные варианты; ключ — порядковый номер после перемешивания."""
    labels = [correct, *wrong]
    rng.shuffle(labels)
    return tuple(
        Choice(key=str(index), label=label, correct=(label == correct))
        for index, label in enumerate(labels, start=1)
    )


def numbered(options: Sequence[str]) -> str:
    """«1) بيت  2) كتاب» — нумерация, чтобы можно было ответить номером."""
    return "\n".join(f"{i}) {option}" for i, option in enumerate(options, start=1))


def letter_answers(letter: Letter) -> tuple[str, ...]:
    """Нормализованные написания названия буквы — готовы к подстановке в `accepted`."""
    return tuple(sorted(letter.accepted))


__all__ = [
    "Choice",
    "Exercise",
    "ExerciseGenerator",
    "GenContext",
    "ImageSpec",
    "build_choices",
    "distractors",
    "letter_answers",
    "numbered",
    "pick",
]
