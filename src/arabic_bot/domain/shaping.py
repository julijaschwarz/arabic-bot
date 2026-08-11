"""Разбор слова на глифы для отрисовки.

Чтобы подсветить в слове ровно одну букву, нужно знать позицию каждого глифа.
Поэтому слово раскладывается вручную: для каждой буквы вычисляется её форма
(отдельная / начальная / срединная / конечная) и подбирается соответствующий
символ из блока Arabic Presentation Forms-B.

Таблица форм не захардкожена — она строится из имён Unicode («ARABIC LETTER
BEH INITIAL FORM»), поэтому в ней нет опечаток и её легко проверить.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .letters import VARIANTS, base_char
from .normalize import strip_tashkeel

POSITIONS = ("isolated", "final", "initial", "medial")

_FORM_RE = re.compile(r"^ARABIC LETTER (?P<base>.+?) (?P<form>ISOLATED|FINAL|INITIAL|MEDIAL) FORM$")
_LIGATURE_RE = re.compile(
    r"^ARABIC LIGATURE LAM WITH (?P<second>ALEF(?: WITH (?:MADDA|HAMZA) ABOVE| WITH HAMZA BELOW)?) "
    r"(?P<form>ISOLATED|FINAL) FORM$"
)

LAM = "ل"
ALEF_FORMS = frozenset({"ا", "أ", "إ", "آ", "ٱ"})


def _build_form_table() -> dict[str, dict[str, str]]:
    """{'ب': {'isolated': 'ﺏ', 'initial': 'ﺑ', ...}} — собрано из имён Unicode."""
    by_unicode_name: dict[str, str] = {}
    for code in range(0x0620, 0x0660):
        char = chr(code)
        name = unicodedata.name(char, "")
        if name.startswith("ARABIC LETTER "):
            by_unicode_name[name.removeprefix("ARABIC LETTER ")] = char

    table: dict[str, dict[str, str]] = {}
    for code in range(0xFE70, 0xFF00):
        glyph = chr(code)
        match = _FORM_RE.match(unicodedata.name(glyph, ""))
        if not match:
            continue
        base = by_unicode_name.get(match["base"])
        if base:
            table.setdefault(base, {})[match["form"].lower()] = glyph
    return table


def _build_ligature_table() -> dict[tuple[str, str], dict[str, str]]:
    """Лям + алиф сливаются в один глиф لا — единственная обязательная лигатура."""
    names = {
        "ALEF": "ا",
        "ALEF WITH MADDA ABOVE": "آ",
        "ALEF WITH HAMZA ABOVE": "أ",
        "ALEF WITH HAMZA BELOW": "إ",
    }
    table: dict[tuple[str, str], dict[str, str]] = {}
    for code in range(0xFE70, 0xFF00):
        glyph = chr(code)
        match = _LIGATURE_RE.match(unicodedata.name(glyph, ""))
        if not match:
            continue
        second = names.get(match["second"])
        if second:
            table.setdefault((LAM, second), {})[match["form"].lower()] = glyph
    return table


FORMS: dict[str, dict[str, str]] = _build_form_table()
LIGATURES: dict[tuple[str, str], dict[str, str]] = _build_ligature_table()

# Буквы, не соединяющиеся со следующей, — по данным самого Unicode-блока:
# у них просто нет начальной и срединной формы.
NON_JOINING: frozenset[str] = frozenset(
    char for char, forms in FORMS.items() if "initial" not in forms
)


@dataclass(frozen=True, slots=True)
class Glyph:
    char: str
    """Готовый к отрисовке символ — уже нужной формы."""

    sources: tuple[int, ...]
    """Индексы исходных букв слова. У лигатуры لا их два."""

    position: str


def shape(word: str) -> list[Glyph]:
    """Слово → список глифов в порядке написания (справа налево при отрисовке)."""
    chars = list(strip_tashkeel(word))
    glyphs: list[Glyph] = []
    index = 0
    connected_from_left = False  # соединяется ли текущий знак с предыдущим

    while index < len(chars):
        char = chars[index]
        ligature_key: tuple[str, str] | None = None
        if (
            char == LAM
            and index + 1 < len(chars)
            and chars[index + 1] in ALEF_FORMS
        ):
            ligature_key = (LAM, base_char_for_ligature(chars[index + 1]))

        if ligature_key and ligature_key in LIGATURES:
            # Лигатура ни с чем не соединяется слева — как и сам алиф.
            position = "final" if connected_from_left else "isolated"
            variants = LIGATURES[ligature_key]
            glyphs.append(
                Glyph(
                    char=variants.get(position, variants["isolated"]),
                    sources=(index, index + 1),
                    position=position,
                )
            )
            connected_from_left = False
            index += 2
            continue

        forms = FORMS.get(char)
        if forms is None:
            index += 1
            continue

        joins_next = char not in NON_JOINING and index + 1 < len(chars) and chars[index + 1] in FORMS
        if connected_from_left and joins_next:
            position = "medial"
        elif connected_from_left:
            position = "final"
        elif joins_next:
            position = "initial"
        else:
            position = "isolated"

        glyphs.append(
            Glyph(char=forms.get(position, forms["isolated"]), sources=(index,), position=position)
        )
        connected_from_left = joins_next
        index += 1

    return glyphs


def base_char_for_ligature(char: str) -> str:
    """Алиф с хамзой остаётся собой — у него своя лигатура с лямом."""
    return char if (LAM, char) in LIGATURES else base_char(char)


def unit_index_map(word: str) -> dict[int, int]:
    """Позиция буквы в разборе `letters_of` → индекс символа в исходной строке.

    `letters_of` пропускает огласовки, поэтому нумерации не совпадают.
    """
    mapping: dict[int, int] = {}
    unit = 0
    for position, char in enumerate(strip_tashkeel(word)):
        if base_char(char) in FORMS or char in VARIANTS or char in FORMS:
            mapping[unit] = position
            unit += 1
    return mapping
