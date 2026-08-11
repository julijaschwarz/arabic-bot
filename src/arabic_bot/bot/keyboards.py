"""Инлайн-клавиатуры.

callback_data держим коротким: Telegram ограничивает его 64 байтами.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from ..domain.models import Exercise

RETRY = "retry"
REVEAL = "reveal"
NEXT = "next"
SKIP = "skip"
START_SESSION = "start"
MORE = "more"
ANSWER_PREFIX = "ans"


def _row(*buttons: InlineKeyboardButton) -> list[InlineKeyboardButton]:
    return list(buttons)


def question(exercise: Exercise) -> InlineKeyboardMarkup:
    """Кнопки задания.

    Отдельной кнопки «прослушать» нет: озвучка приезжает вместе с самим
    заданием, и её плеер уже встроен в сообщение. Кнопка могла бы только
    прислать ещё одно сообщение — Telegram не умеет запускать звук по нажатию.
    """
    rows: list[list[InlineKeyboardButton]] = []

    if exercise.choices:
        # По две кнопки в ряд: арабские глифы крупные, в один ряд не помещаются.
        buttons = [
            InlineKeyboardButton(
                text=f"{choice.key}) {choice.label}",
                callback_data=f"{ANSWER_PREFIX}:{choice.key}",
            )
            for choice in exercise.choices
        ]
        rows.extend(buttons[i : i + 2] for i in range(0, len(buttons), 2))

    rows.append([InlineKeyboardButton(text="Пропустить", callback_data=SKIP)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_wrong() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            _row(
                InlineKeyboardButton(text="🔁 Попробовать ещё", callback_data=RETRY),
                InlineKeyboardButton(text="👀 Показать ответ", callback_data=REVEAL),
            )
        ]
    )


def after_reveal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_row(InlineKeyboardButton(text="➡️ Дальше", callback_data=NEXT))]
    )


def session_finished() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            _row(InlineKeyboardButton(text="➕ Ещё 5 заданий", callback_data=MORE))
        ]
    )


def start_session(label: str = "Поехали") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_row(InlineKeyboardButton(text=label, callback_data=START_SESSION))]
    )
