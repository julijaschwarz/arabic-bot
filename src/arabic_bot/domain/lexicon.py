"""Загрузка и фильтрация словаря.

Лексикон — это данные (`data/words.yaml`), а не задания. Задания генераторы
строят сами, комбинируя слова с буквами дня.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Iterable, Sequence

import yaml

from .letters import Letter, Sign, letters_of


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    translit: str
    ru: str
    units: tuple[Letter | Sign, ...] = field(default=(), repr=False)
    """Разбор слова по знакам: буквы и та марбута/хамза в порядке написания."""

    @property
    def letters(self) -> tuple[Letter, ...]:
        """Только полноценные буквы — без та марбуты и хамзы."""
        return tuple(u for u in self.units if isinstance(u, Letter))

    @property
    def length(self) -> int:
        return len(self.units)

    @property
    def label(self) -> str:
        return f"{self.text} — {self.ru}"

    def count(self, letter: Letter) -> int:
        return sum(1 for unit in self.units if unit is letter)

    def has(self, letter: Letter) -> bool:
        return any(unit is letter for unit in self.units)


class Lexicon:
    """Словарь с фильтрами, на которых генераторы собирают задания."""

    def __init__(self, words: Sequence[Word]) -> None:
        self._words = tuple(words)

    @classmethod
    def load(cls, path: Path | None = None) -> Lexicon:
        if path is None:
            source = resources.files("arabic_bot.data").joinpath("words.yaml")
            raw = yaml.safe_load(source.read_text(encoding="utf-8"))
        else:
            raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))

        words = []
        for entry in raw or ():
            text = str(entry["w"]).strip()
            units = tuple(letters_of(text))
            if not units:
                continue
            words.append(
                Word(
                    text=text,
                    translit=str(entry.get("t", "")).strip(),
                    ru=str(entry.get("ru", "")).strip(),
                    units=units,
                )
            )
        return cls(words)

    def __len__(self) -> int:
        return len(self._words)

    def __iter__(self):
        return iter(self._words)

    def all(self) -> tuple[Word, ...]:
        return self._words

    # --- фильтры ---

    def where(
        self,
        *,
        contains: Letter | None = None,
        excludes: Letter | None = None,
        starts_with: Letter | None = None,
        ends_with: Letter | None = None,
        exact_count: tuple[Letter, int] | None = None,
        min_count: tuple[Letter, int] | None = None,
        min_length: int = 0,
        max_length: int = 99,
        letters_only: bool = False,
        pool: Iterable[Word] | None = None,
    ) -> tuple[Word, ...]:
        """Единая точка фильтрации — новые генераторы обходятся без своих циклов."""
        result = []
        for word in pool if pool is not None else self._words:
            if not (min_length <= word.length <= max_length):
                continue
            if letters_only and len(word.letters) != word.length:
                continue
            if contains is not None and not word.has(contains):
                continue
            if excludes is not None and word.has(excludes):
                continue
            if starts_with is not None and word.units[0] is not starts_with:
                continue
            if ends_with is not None and word.units[-1] is not ends_with:
                continue
            if exact_count is not None and word.count(exact_count[0]) != exact_count[1]:
                continue
            if min_count is not None and word.count(min_count[0]) < min_count[1]:
                continue
            result.append(word)
        return tuple(result)

    def starting_letters(self) -> set[Letter]:
        return {w.units[0] for w in self._words if isinstance(w.units[0], Letter)}

    def ending_letters(self) -> set[Letter]:
        return {w.units[-1] for w in self._words if isinstance(w.units[-1], Letter)}
