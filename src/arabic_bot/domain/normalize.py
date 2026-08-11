"""Нормализация пользовательского ввода и арабского текста.

Проверка ответов должна быть терпимой: «баа», «ба», «Ба!», «baa», «bāʼ» —
это один и тот же ответ. Приводим всё к общему виду, а не плодим варианты.
"""

from __future__ import annotations

import re
import unicodedata

# Огласовки, шадда, сукун, а также кашида-удлинитель ـ
TASHKEEL = "".join(
    chr(code)
    for code in (
        *range(0x064B, 0x0653),  # фатха…сукун
        0x0653,
        0x0654,
        0x0655,
        0x0670,  # верхний алиф
    )
)
TATWEEL = "ـ"

_TASHKEEL_RE = re.compile(f"[{TASHKEEL}{TATWEEL}]")

# ٠١٢٣٤٥٦٧٨٩ (арабо-индийские) и ۰۱۲۳۴۵۶۷۸۹ (персидские) → 0123456789
_DIGIT_MAP = {
    **{0x0660 + i: str(i) for i in range(10)},
    **{0x06F0 + i: str(i) for i in range(10)},
}

# Числительные словами — чтобы «семь» и «seven» тоже засчитывались
_NUMBER_WORDS: dict[str, int] = {
    "ноль": 0, "нуль": 0, "zero": 0,
    "один": 1, "одна": 1, "одно": 1, "one": 1,
    "два": 2, "две": 2, "two": 2,
    "три": 3, "three": 3,
    "четыре": 4, "four": 4,
    "пять": 5, "five": 5,
    "шесть": 6, "six": 6,
    "семь": 7, "seven": 7,
    "восемь": 8, "eight": 8,
    "девять": 9, "nine": 9,
    "десять": 10, "ten": 10,
    "ни разу": 0, "нет": 0, "none": 0,
}


def strip_tashkeel(text: str) -> str:
    """Убрать огласовки и кашиду — для сравнения и подсчёта букв."""
    return _TASHKEEL_RE.sub("", text)


def arabic_digits_to_ascii(text: str) -> str:
    return text.translate(_DIGIT_MAP)


def normalize_answer(text: str) -> str:
    """Привести ответ к канону: «Ба-а!» → «ба», «Bāʼ» → «ba».

    Порядок важен: сначала снимаем диакритику Unicode (ā → a), потом чистим
    всё, кроме букв и цифр, и только затем схлопываем удвоения.
    """
    text = arabic_digits_to_ascii(text.strip().lower().replace("ё", "е"))
    # NFD раскладывает ā на «a» + макрон, комбинирующие знаки затем выбрасываются
    decomposed = unicodedata.normalize("NFD", text)
    cleaned = "".join(
        ch
        for ch in decomposed
        if (ch.isalnum() or ch.isspace())
        and not unicodedata.combining(ch)
        # категория Lm — модификаторы вроде ʼ ʻ ʾ в научной транслитерации и кашида ـ
        and unicodedata.category(ch) != "Lm"
    )
    cleaned = unicodedata.normalize("NFC", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # «баа» → «ба», «jeem» → «jem», «нуун» → «нун»
    return re.sub(r"(.)\1+", r"\1", cleaned)


def split_tokens(text: str) -> list[str]:
    """Разбить ввод на отдельные названия букв: «алиф лям мим» → 3 токена.

    Запятые и дефисы между названиями тоже считаем разделителями — люди пишут
    и «алиф, лям, мим», и «алиф-лям-мим».
    """
    parts = re.split(r"[\s,;/\-–—]+", text.strip())
    return [normalize_answer(part) for part in parts if normalize_answer(part)]


def parse_number(text: str) -> int | None:
    """Разобрать число из ответа: «345», «٣٤٥», «семь» → int."""
    raw = arabic_digits_to_ascii(text.strip().lower().replace("ё", "е"))
    digits = re.sub(r"[^\d-]", "", raw)
    if digits and digits.lstrip("-").isdigit():
        return int(digits)
    word = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", raw)).strip()
    return _NUMBER_WORDS.get(word)
