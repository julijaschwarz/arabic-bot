"""Отрисовка арабских слов и букв в PNG.

Картинка нужна там, где текстом не обойтись: показать букву внутри связного
слова и подсветить именно её. Слово раскладывается на глифы (`domain.shaping`)
и рисуется по одному справа налево, поэтому позиция каждой буквы известна точно.

Результат кэшируется на диске: одно и то же слово рисуется один раз.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..domain.shaping import Glyph, shape

log = logging.getLogger(__name__)

# Первый шрифт, который действительно покрывает нужные глифы. В образе стоит
# Amiri; на macOS при локальной разработке подбирается системный.
FONT_CANDIDATES: tuple[str, ...] = (
    "/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-Regular.ttf",
    "/usr/share/fonts/truetype/fonts-hosny-amiri/Amiri-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Geeza Pro.ttc",
    "/System/Library/Fonts/Supplemental/Damascus.ttc",
    "/System/Library/Fonts/Supplemental/Al Nile.ttc",
    "/System/Library/Fonts/Supplemental/Baghdad.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
)

# Подписи под словом — по-русски, поэтому шрифт нужен другой.
CAPTION_FONT_CANDIDATES: tuple[str, ...] = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Verdana.ttf",
)

# Глифы, без которых картинки бессмысленны: изолированные и срединные формы
# букв, которые чаще всего встречаются в словах.
COVERAGE_PROBE = "ﺏﻡﺭﺎﺳﺘﻛﻞﻴ"

BACKGROUND = (255, 253, 247)
INK = (32, 33, 36)
ACCENT = (211, 47, 47)
CAPTION_INK = (120, 122, 126)

PADDING = 56
CAPTION_GAP = 28


class FontUnavailable(RuntimeError):
    """Ни один арабский шрифт не найден — картинки отключаются, текст остаётся."""


def _covers(font_path: Path, probe: str) -> bool:
    """Есть ли в шрифте реальные глифы для этих символов.

    Отсутствующий символ рисуется «квадратиком», причём одним и тем же для всех
    пропусков, — с ним и сравниваем. Проверка нужна: некоторые системные шрифты
    содержат арабские буквы, но не содержат их presentation-форм, и слово
    превращается в ряд квадратов.
    """
    try:
        font = ImageFont.truetype(str(font_path), 48)
        # \u0421\u0438\u043c\u0432\u043e\u043b \u0438\u0437 \u043e\u0431\u043b\u0430\u0441\u0442\u0438 \u0447\u0430\u0441\u0442\u043d\u043e\u0433\u043e \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d\u0438\u044f: \u0435\u0433\u043e \u043d\u0435\u0442 \u043d\u0438 \u0432 \u043e\u0434\u043d\u043e\u043c \u043e\u0431\u044b\u0447\u043d\u043e\u043c
        # \u0448\u0440\u0438\u0444\u0442\u0435, \u043f\u043e\u044d\u0442\u043e\u043c\u0443 \u0435\u0433\u043e \u043e\u0442\u0440\u0438\u0441\u043e\u0432\u043a\u0430 \u0438 \u0435\u0441\u0442\u044c \u00ab\u043a\u0432\u0430\u0434\u0440\u0430\u0442\u0438\u043a \u043f\u0440\u043e\u043f\u0443\u0441\u043a\u0430\u00bb.
        missing = _render_probe(font, "\ue000")
        return all(_render_probe(font, char) != missing for char in probe)
    except Exception:  # noqa: BLE001
        return False


def _render_probe(font: ImageFont.FreeTypeFont, char: str) -> bytes:
    canvas = Image.new("L", (80, 80), 0)
    ImageDraw.Draw(canvas).text((8, 8), char, font=font, fill=255)
    return canvas.tobytes()


FONT_DIRS: tuple[str, ...] = (
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/System/Library/Fonts",
    "/Library/Fonts",
)


def _first_usable(candidates: tuple[str | None, ...], probe: str) -> Path | None:
    for path in candidates:
        if path and Path(path).exists() and _covers(Path(path), probe):
            return Path(path)
    return None


def _scan(probe: str, prefer: tuple[str, ...] = ()) -> Path | None:
    """Обойти системные каталоги шрифтов.

    Дистрибутивы кладут пакеты по-разному (Amiri оказался в
    `opentype/fonts-hosny-amiri`, а не в `truetype/hosny-amiri`), поэтому
    полагаться на один жёсткий путь нельзя.
    """
    found: list[Path] = []
    for directory in FONT_DIRS:
        root = Path(directory)
        if not root.is_dir():
            continue
        for pattern in ("*.ttf", "*.otf", "*.ttc"):
            found.extend(sorted(root.rglob(pattern)))

    def rank(path: Path) -> tuple[int, str]:
        name = path.name.lower()
        for index, hint in enumerate(prefer):
            if hint in name:
                return (index, name)
        return (len(prefer), name)

    for path in sorted(found, key=rank):
        if _covers(path, probe):
            return path
    return None


def find_font() -> Path:
    override = os.getenv("FONT_PATH")
    found = _first_usable((override, *FONT_CANDIDATES), COVERAGE_PROBE) or _scan(
        COVERAGE_PROBE, prefer=("amiri", "naskh", "noto", "arab", "geeza", "damascus")
    )
    if found is None:
        raise FontUnavailable(
            "Не найден шрифт с арабскими presentation-формами. "
            "Укажите FONT_PATH или установите пакет fonts-hosny-amiri."
        )
    return found


def find_caption_font() -> Path | None:
    override = os.getenv("CAPTION_FONT_PATH")
    return _first_usable((override, *CAPTION_FONT_CANDIDATES), "Ялб") or _scan(
        "Ялб", prefer=("dejavusans.", "liberationsans", "arial", "helvetica")
    )


class ImageRenderer:
    def __init__(self, cache_dir: Path, enabled: bool = True) -> None:
        self._cache_dir = cache_dir
        self._enabled = enabled
        self._font_path: Path | None = None
        self._caption_font_path: Path | None = None
        if enabled:
            try:
                self._font_path = find_font()
                self._caption_font_path = find_caption_font()
                log.info(
                    "Шрифты: арабский %s, подписи %s",
                    self._font_path,
                    self._caption_font_path or "не найден (подписи отключены)",
                )
            except FontUnavailable as error:
                log.warning("%s Картинки отключены.", error)
                self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def render_word(
        self,
        text: str,
        *,
        highlight: int | None = None,
        caption: str | None = None,
        font_size: int = 160,
    ) -> Path | None:
        """Нарисовать слово; `highlight` — индекс буквы в порядке написания."""
        if not self._enabled or self._font_path is None:
            return None

        key = hashlib.sha256(
            f"{text}|{highlight}|{caption}|{font_size}|{self._font_path}|v3".encode()
        ).hexdigest()[:32]
        target = self._cache_dir / f"{key}.png"
        if target.exists():
            return target

        try:
            image = self._draw(text, highlight, caption, font_size)
        except Exception:  # noqa: BLE001 — картинка не должна ронять урок
            log.exception("Не удалось нарисовать слово %r", text)
            return None

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        image.save(target, format="PNG", optimize=True)
        return target

    def render_sound_card(self, caption: str | None = None) -> Path | None:
        """Нейтральная заставка со значком динамика.

        Нужна там, где показывать в кадре нечего: например, вопрос «какая буква
        называется ба?» — сам глиф в кадре был бы ответом.
        """
        if not self._enabled:
            return None

        key = hashlib.sha256(f"card|{caption}|{self._caption_font_path}|v1".encode()).hexdigest()[:32]
        target = self._cache_dir / f"{key}.png"
        if target.exists():
            return target

        image = Image.new("RGB", (640, 360), BACKGROUND)
        draw = ImageDraw.Draw(image)
        cx, cy = 320, 165 if caption else 180

        # Динамик рисуем примитивами: так он не зависит от шрифтов в системе.
        draw.rectangle((cx - 62, cy - 26, cx - 34, cy + 26), fill=INK)
        draw.polygon(
            [(cx - 34, cy - 26), (cx + 6, cy - 62), (cx + 6, cy + 62), (cx - 34, cy + 26)],
            fill=INK,
        )
        for index, radius in enumerate((34, 58, 82)):
            draw.arc(
                (cx + 6 - radius, cy - radius, cx + 6 + radius, cy + radius),
                start=-52,
                end=52,
                fill=ACCENT if index == 0 else CAPTION_INK,
                width=9,
            )

        caption_font = self._load_caption_font(30)
        if caption and caption_font:
            draw.text((cx, 316), caption, font=caption_font, fill=CAPTION_INK, anchor="ms")

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        image.save(target, format="PNG", optimize=True)
        return target

    # --- внутреннее ---

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(str(self._font_path), size)

    def _load_caption_font(self, size: int) -> ImageFont.FreeTypeFont | None:
        if self._caption_font_path is None:
            return None
        return ImageFont.truetype(str(self._caption_font_path), size)

    def _draw(
        self, text: str, highlight: int | None, caption: str | None, font_size: int
    ) -> Image.Image:
        font = self._load_font(font_size)
        glyphs = shape(text)
        if not glyphs:
            glyphs = [Glyph(char=text, sources=(0,), position="isolated")]

        widths = [font.getlength(glyph.char) for glyph in glyphs]
        word_width = sum(widths)

        ascent, descent = font.getmetrics()
        line_height = ascent + descent
        caption_font = self._load_caption_font(max(28, font_size // 4)) if caption else None
        caption_height = (
            caption_font.getmetrics()[0] + caption_font.getmetrics()[1] + CAPTION_GAP
            if caption_font
            else 0
        )

        width = int(word_width) + PADDING * 2
        height = int(line_height * 1.45) + PADDING * 2 + caption_height
        image = Image.new("RGB", (max(width, 320), height), BACKGROUND)
        draw = ImageDraw.Draw(image)

        # Арабский пишется справа налево: стартуем от правого края.
        cursor = image.width - PADDING
        baseline = PADDING + ascent + int(line_height * 0.15)
        for glyph, advance in zip(glyphs, widths):
            cursor -= advance
            is_target = highlight is not None and highlight in glyph.sources
            draw.text(
                (cursor, baseline),
                glyph.char,
                font=font,
                fill=ACCENT if is_target else INK,
                anchor="ls",
            )

        if caption_font and caption:
            draw.text(
                (image.width // 2, height - PADDING // 2),
                caption,
                font=caption_font,
                fill=CAPTION_INK,
                anchor="ms",
            )
        return image
