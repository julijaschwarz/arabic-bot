"""Арабо-индийские цифры ٠–٩, их названия и сборка многозначных чисел."""

from __future__ import annotations

from dataclasses import dataclass, field

from .normalize import normalize_answer

ARABIC_ZERO = 0x0660


@dataclass(frozen=True, slots=True)
class Digit:
    value: int
    char: str
    name_ar: str
    """Название по-арабски — показывается в пояснениях и шпаргалке."""
    name_ru: str
    name_en: str
    aliases: tuple[str, ...] = ()
    accepted: frozenset[str] = field(init=False, default=frozenset(), repr=False)
    """Написания названия, которые засчитываются как верные."""

    def __post_init__(self) -> None:
        raw = (self.name_ru, self.name_en, *self.aliases)
        object.__setattr__(
            self,
            "accepted",
            frozenset(filter(None, (normalize_answer(item) for item in raw))),
        )


def _digit(
    value: int, char: str, name_ar: str, name_ru: str, name_en: str, aliases: str = ""
) -> Digit:
    return Digit(
        value=value,
        char=char,
        name_ar=name_ar,
        name_ru=name_ru,
        name_en=name_en,
        aliases=tuple(a.strip() for a in aliases.split(",") if a.strip()),
    )


DIGITS: tuple[Digit, ...] = (
    _digit(0, "٠", "صفر", "сыфр", "sifr", "сифр,сифир,зеро"),
    _digit(1, "١", "واحد", "вахид", "wahid", "уахид,вахед,ваахид"),
    _digit(2, "٢", "اثنان", "иснан", "ithnan", "иснани,итнан,иснейн,isnan,itnan"),
    _digit(3, "٣", "ثلاثة", "саляса", "thalatha", "таляса,талата,саласа,thalatha,salasa"),
    _digit(4, "٤", "أربعة", "арбаа", "arbaa", "арба,арбъа,arbaa,arbaha"),
    _digit(5, "٥", "خمسة", "хамса", "khamsa", "хамсэ,hamsa,khamsah"),
    _digit(6, "٦", "ستة", "ситта", "sitta", "сита,ситтэ,sittah"),
    _digit(7, "٧", "سبعة", "сабаа", "sabaa", "саба,сабъа,sabah,sabaha"),
    _digit(8, "٨", "ثمانية", "самания", "thamaniya", "таманийя,самани,tamaniya,thamania"),
    _digit(9, "٩", "تسعة", "тисаа", "tisaa", "тиса,тисъа,tisah,tisaha"),
)

BY_VALUE: dict[int, Digit] = {digit.value: digit for digit in DIGITS}
BY_CHAR: dict[str, Digit] = {digit.char: digit for digit in DIGITS}


def to_arabic(number: int) -> str:
    """345 → ٣٤٥. Цифры пишутся слева направо, как и в европейской записи."""
    return "".join(chr(ARABIC_ZERO + int(ch)) for ch in str(abs(number)))


def resolve_candidates(token: str) -> set[int]:
    """Какие цифры может означать введённое название.

    Транслитерации арабских числительных расходятся по учебникам («саляса»,
    «таляса», «талата»), поэтому подходящих может оказаться несколько.
    """
    normalized = normalize_answer(token)
    if not normalized:
        return set()
    return {digit.value for digit in DIGITS if normalized in digit.accepted}
