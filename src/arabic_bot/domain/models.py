"""Ядро предметной области: как выглядит одно упражнение.

`Exercise` — единственный контракт между генераторами заданий, проверкой ответов
и слоем Telegram. Он полностью сериализуем в JSON, поэтому текущий вопрос
переживает перезапуск контейнера.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class AnswerMode(StrEnum):
    """Как пользователь отвечает на вопрос."""

    TEXT = "text"
    """Свободный ввод названия: «ба», «баа», «baa»."""

    LETTER_SEQUENCE = "letter_sequence"
    """Несколько названий букв через пробел: «алиф лям мим»."""

    NUMBER = "number"
    """Число: «345», «٣٤٥» или «семь»."""

    CHOICE = "choice"
    """Выбор кнопкой — только там, где ответ невозможно набрать с клавиатуры."""


@dataclass(frozen=True, slots=True)
class Choice:
    """Вариант ответа. `key` уходит в callback_data, `label` видит пользователь."""

    key: str
    label: str
    correct: bool = False


@dataclass(frozen=True, slots=True)
class ImageSpec:
    """Что нарисовать картинкой.

    `highlight` — индекс буквы в логическом (не визуальном) порядке строки `text`,
    считая слева направо по кодовым точкам, то есть с начала слова.
    """

    text: str
    highlight: int | None = None
    caption: str | None = None
    font_size: int = 160


@dataclass(frozen=True, slots=True)
class Exercise:
    generator_id: str
    prompt: str
    answer_mode: AnswerMode
    accepted: tuple[str, ...]
    explanation: str
    display: str | None = None
    image: ImageSpec | None = None
    choices: tuple[Choice, ...] | None = None
    hint: str | None = None
    focus_letters: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Инвариант: в TEXT-режиме `accepted` уже нормализован. Иначе генератор,
        # положивший туда сырое «أسود», молча ломал бы проверку: normalize_answer
        # сводит أ к ا, и сравнение не сходилось бы.
        if self.answer_mode is AnswerMode.TEXT:
            from .normalize import normalize_answer

            object.__setattr__(
                self,
                "accepted",
                tuple(sorted({n for n in map(normalize_answer, self.accepted) if n})),
            )

    # --- сериализация для хранения сессии в SQLite ---

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["answer_mode"] = str(self.answer_mode)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Exercise:
        image = data.get("image")
        choices = data.get("choices")
        return cls(
            generator_id=data["generator_id"],
            prompt=data["prompt"],
            answer_mode=AnswerMode(data["answer_mode"]),
            accepted=tuple(data["accepted"]),
            explanation=data["explanation"],
            display=data.get("display"),
            image=ImageSpec(**image) if image else None,
            choices=tuple(Choice(**c) for c in choices) if choices else None,
            hint=data.get("hint"),
            focus_letters=tuple(data.get("focus_letters", ())),
            payload=data.get("payload", {}),
        )


@dataclass(frozen=True, slots=True)
class Verdict:
    """Результат проверки ответа."""

    correct: bool
    comment: str = ""
    """Уточнение при ошибке — например, на какой позиции разошлась разборка слова."""
