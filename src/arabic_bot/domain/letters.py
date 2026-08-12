"""28 букв арабского алфавита: формы, названия, принимаемые написания.

Формы строятся через кашиду ـ (U+0640), а не через presentation forms из блока
FE70–FEFF: так они одинаково рисуются и в Telegram, и в Pillow, и корректно
обрабатываются arabic-reshaper.

Шесть букв (ا د ذ ر ز و) не соединяются со следующей — на этом строится
отдельный тип заданий.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .normalize import normalize_answer, strip_tashkeel

TATWEEL = "ـ"


@dataclass(frozen=True, slots=True)
class Letter:
    id: str
    char: str
    name_ar: str
    """Название буквы по-арабски — именно оно уходит в озвучку."""
    name_ru: str
    name_en: str
    connects_forward: bool
    aliases: tuple[str, ...] = ()
    note_ru: str = ""
    """Уточнение для подсказок: чем эта буква отличается от похожей по звучанию."""

    accepted: frozenset[str] = field(init=False, default=frozenset(), repr=False)
    """Все написания названия, которые засчитываются как верные."""

    def __post_init__(self) -> None:
        raw = (self.name_ru, self.name_en, *self.aliases)
        object.__setattr__(
            self,
            "accepted",
            frozenset(filter(None, (normalize_answer(item) for item in raw))),
        )

    # --- формы ---

    @property
    def isolated(self) -> str:
        return self.char

    @property
    def initial(self) -> str:
        """В начале слова. Непривязываемая буква и в начале выглядит как отдельная."""
        return self.char + TATWEEL if self.connects_forward else self.char

    @property
    def medial(self) -> str:
        """В середине. Непривязываемая соединяется только справа."""
        return (
            TATWEEL + self.char + TATWEEL
            if self.connects_forward
            else TATWEEL + self.char
        )

    @property
    def final(self) -> str:
        return TATWEEL + self.char

    def form(self, position: str) -> str:
        return {
            "isolated": self.isolated,
            "initial": self.initial,
            "medial": self.medial,
            "final": self.final,
        }[position]

    @property
    def title_ru(self) -> str:
        """Название с уточнением — для объяснений и итогов."""
        return f"{self.name_ru} ({self.char})" + (f", {self.note_ru}" if self.note_ru else "")


def _letter(
    id_: str,
    char: str,
    name_ar: str,
    name_ru: str,
    name_en: str,
    connects: bool,
    aliases: str = "",
    note: str = "",
) -> Letter:
    return Letter(
        id=id_,
        char=char,
        name_ar=name_ar,
        name_ru=name_ru,
        name_en=name_en,
        connects_forward=connects,
        aliases=tuple(a.strip() for a in aliases.split(",") if a.strip()),
        note_ru=note,
    )


# Порядок — алфавитный (тартиб хиджаи), как в учебниках.
LETTERS: tuple[Letter, ...] = (
    _letter("alif", "ا", "ألف", "алиф", "alif", False, "алеф,alef,aleph,хамза-алиф"),
    _letter("ba", "ب", "باء", "ба", "ba", True, "баа,бэ,baa,beh,bāʼ"),
    _letter("ta", "ت", "تاء", "та", "ta", True, "таа,тэ,taa,teh", "обычная т"),
    _letter("tha", "ث", "ثاء", "са", "tha", True, "саа,тса,тха,thaa,theh,sa", "межзубная, как в англ. think"),
    _letter("jim", "ج", "جيم", "джим", "jim", True, "джиим,jeem,geem,gim"),
    _letter("ha", "ح", "حاء", "ха", "ha", True, "хаа,haa,hha,ha", "гортанная, из глубины горла"),
    _letter("kha", "خ", "خاء", "кха", "kha", True, "ха,хаа,хэ,khaa,kh", "хриплая, как русское х"),
    _letter("dal", "د", "دال", "даль", "dal", False, "дал,daal,dāl"),
    _letter("dhal", "ذ", "ذال", "заль", "dhal", False, "зал,дзаль,заал,dhaal,zal,thal", "межзубная, как в англ. this"),
    _letter("ra", "ر", "راء", "ра", "ra", False, "раа,raa,reh"),
    _letter("zay", "ز", "زاي", "зайн", "zay", False,
            "зай,зэй,зэ,за,заа,zayn,zai,zaa,za,ze,zeen,zeh,zāy",
            "обычная з, не эмфатическая — в отличие от ظ"),
    _letter("sin", "س", "سين", "син", "sin", True, "сиин,seen"),
    _letter("shin", "ش", "شين", "шин", "shin", True, "шиин,sheen"),
    _letter("sad", "ص", "صاد", "сад", "sad", True, "саад,saad,ṣād", "эмфатическая, твёрдая с"),
    _letter("dad", "ض", "ضاد", "дад", "dad", True, "даад,daad,ḍād", "эмфатическая, твёрдая д"),
    _letter("ta_emph", "ط", "طاء", "то", "tah", True, "та,таа,тоh,tah,taa,ṭāʼ", "эмфатическая, твёрдая т"),
    _letter("za_emph", "ظ", "ظاء", "зо", "zah", True, "за,заа,зоh,zah,zaa,ẓāʼ", "эмфатическая, твёрдая з"),
    _letter("ayn", "ع", "عين", "айн", "ayn", True, "аин,айин,ain,3ayn"),
    _letter("ghayn", "غ", "غين", "гайн", "ghayn", True, "гаин,гайин,ghain,gayn"),
    _letter("fa", "ف", "فاء", "фа", "fa", True, "фаа,faa,feh"),
    _letter("qaf", "ق", "قاف", "каф", "qaf", True, "кааф,qaaf,каф-глубокий", "гортанная к"),
    _letter("kaf", "ك", "كاف", "кяф", "kaf", True, "кеф,каф,kaaf,keh", "обычная к"),
    _letter("lam", "ل", "لام", "лям", "lam", True, "лам,laam,lyam"),
    _letter("mim", "م", "ميم", "мим", "mim", True, "миим,meem"),
    _letter("nun", "ن", "نون", "нун", "nun", True, "нуун,noon"),
    _letter("ha_soft", "ه", "هاء", "хэ", "hah", True, "ха,хаа,heh,hah", "лёгкое придыхание"),
    _letter("waw", "و", "واو", "вав", "waw", False, "уау,вау,waaw,wow"),
    _letter("ya", "ي", "ياء", "йа", "ya", True, "я,йя,иа,yaa,yeh,ye"),
)

assert len(LETTERS) == 28, "в алфавите должно быть ровно 28 букв"

BY_ID: dict[str, Letter] = {letter.id: letter for letter in LETTERS}
BY_CHAR: dict[str, Letter] = {letter.char: letter for letter in LETTERS}

NON_CONNECTING: tuple[Letter, ...] = tuple(l for l in LETTERS if not l.connects_forward)
CONNECTING: tuple[Letter, ...] = tuple(l for l in LETTERS if l.connects_forward)

assert len(NON_CONNECTING) == 6


@dataclass(frozen=True, slots=True)
class Sign:
    """Знак вне круга из 28 букв: встречается в словах, но не отрабатывается отдельно."""

    char: str
    name_ar: str
    name_ru: str
    aliases: tuple[str, ...] = ()
    accepted: frozenset[str] = field(init=False, default=frozenset(), repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "accepted",
            frozenset(
                filter(None, (normalize_answer(a) for a in (self.name_ru, *self.aliases)))
            ),
        )


EXTRA_SIGNS: tuple[Sign, ...] = (
    Sign("ة", "تاء مربوطة", "та марбута", ("та-марбута", "тамарбута", "марбута", "ta marbuta")),
    Sign("ء", "همزة", "хамза", ("hamza", "гамза")),
)
SIGNS_BY_CHAR: dict[str, Sign] = {sign.char: sign for sign in EXTRA_SIGNS}

# Написательные варианты, которые читаются как базовая буква.
VARIANTS: dict[str, str] = {
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي",
    "ؤ": "و",
}


def base_char(char: str) -> str:
    """أ → ا, ى → ي. Знаки ة и ء остаются собой."""
    return VARIANTS.get(char, char)


def letters_of(word: str) -> list[Letter | Sign]:
    """Разложить слово на буквы: «كتاب» → [кяф, та, алиф, ба].

    Огласовки и кашида отбрасываются, письменные варианты сводятся к базовой букве.
    Неизвестные символы пропускаются — они не должны ронять генератор.
    """
    result: list[Letter | Sign] = []
    for char in strip_tashkeel(word):
        if char in SIGNS_BY_CHAR:
            result.append(SIGNS_BY_CHAR[char])
            continue
        letter = BY_CHAR.get(base_char(char))
        if letter is not None:
            result.append(letter)
    return result


def contains_letter(word: str, letter: Letter) -> bool:
    return any(item is letter for item in letters_of(word))


def count_letter(word: str, letter: Letter) -> int:
    return sum(1 for item in letters_of(word) if item is letter)


def resolve_candidates(token: str) -> set[str]:
    """Какие буквы может означать введённое название.

    Транслитерации неизбежно пересекаются («ха» — и ح, и خ, и ه). Возвращаем все
    подходящие; проверяющий засчитает ответ, если среди них есть ожидаемая буква,
    и добавит уточнение, чем эти буквы отличаются.
    """
    normalized = normalize_answer(token)
    if not normalized:
        return set()
    return {letter.id for letter in LETTERS if normalized in letter.accepted}


def resolve_sign(token: str) -> Sign | None:
    normalized = normalize_answer(token)
    for sign in EXTRA_SIGNS:
        if normalized in sign.accepted:
            return sign
    return None


def is_ambiguous(token: str) -> bool:
    return len(resolve_candidates(token)) > 1
