"""Точка входа: `python -m arabic_bot`."""

from __future__ import annotations

import asyncio
import logging

from .bot.setup import build
from .config import Settings

log = logging.getLogger("arabic_bot")


async def _run() -> None:
    settings = Settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)

    app = await build(settings)
    log.info("Бот запущен")
    await app.run()


def main() -> None:
    try:
        asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        log.info("Остановлено")


if __name__ == "__main__":
    main()
