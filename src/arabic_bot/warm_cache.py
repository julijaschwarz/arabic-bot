"""Прогрев кэша картинок.

Запускается один раз после установки (`make warm-cache`), чтобы первые задания
показывались без задержки на отрисовку.
"""

from __future__ import annotations

import asyncio
import logging

from .config import Settings
from .domain.lexicon import Lexicon
from .media.images import ImageRenderer

log = logging.getLogger("warm_cache")


async def warm(settings: Settings) -> None:
    settings.ensure_dirs()
    lexicon = Lexicon.load()
    renderer = ImageRenderer(settings.image_cache_dir, enabled=settings.images_enabled)

    if not renderer.enabled:
        log.info("Картинки выключены (IMAGES_ENABLED=false) — прогревать нечего.")
        return

    log.info("Рисую %d слов…", len(lexicon))
    drawn = sum(1 for word in lexicon if renderer.render_word(word.text, caption=word.ru))
    log.info("Картинки: %d из %d", drawn, len(lexicon))


def main() -> None:
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    asyncio.run(warm(settings))


if __name__ == "__main__":
    main()
