"""Конфигурация бота.

Все настройки берутся из окружения контейнера (`.env`), ничего не хардкодится
и не пишется на хост. Экземпляр `Settings` создаётся один раз в `__main__`
и дальше передаётся явно: изменяемого глобального состояния в проекте нет,
всё, что меняется, живёт в базе.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _parse_hhmm(value: str) -> dt.time:
    hours, _, minutes = value.strip().partition(":")
    return dt.time(hour=int(hours), minute=int(minutes or 0))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(alias="BOT_TOKEN")
    allowed_user_ids: str = Field(default="", alias="ALLOWED_USER_IDS")

    timezone: str = Field(default="Europe/Moscow", alias="TZ")
    daily_time: str = Field(default="09:00", alias="DAILY_TIME")
    daily_task_count: int = Field(default=10, ge=1, le=100, alias="DAILY_TASK_COUNT")
    focus_letters_per_day: int = Field(default=6, ge=1, le=28, alias="FOCUS_LETTERS_PER_DAY")
    idle_hours: float = Field(default=6.0, gt=0, alias="IDLE_HOURS")
    quiet_hours: str = Field(default="22:00-08:00", alias="QUIET_HOURS")
    idle_check_minutes: int = Field(default=30, ge=1, alias="IDLE_CHECK_MINUTES")

    images_enabled: bool = Field(default=True, alias="IMAGES_ENABLED")

    data_dir: Path = Field(default=Path("/data"), alias="DATA_DIR")
    db_path: Path = Field(default=Path("/data/arabic.db"), alias="DB_PATH")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("bot_token")
    @classmethod
    def _token_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("BOT_TOKEN пуст — получите токен у @BotFather и впишите в .env")
        return value.strip()

    # --- производные значения ---

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def allowed_ids(self) -> frozenset[int]:
        """Пустое множество означает «пускать всех» (удобно на этапе отладки)."""
        raw = self.allowed_user_ids.replace(";", ",")
        return frozenset(int(part) for part in raw.split(",") if part.strip())

    @property
    def daily_at(self) -> dt.time:
        return _parse_hhmm(self.daily_time)

    @property
    def quiet_from(self) -> dt.time:
        return _parse_hhmm(self.quiet_hours.split("-")[0])

    @property
    def quiet_to(self) -> dt.time:
        parts = self.quiet_hours.split("-")
        return _parse_hhmm(parts[1] if len(parts) > 1 else "08:00")

    @property
    def image_cache_dir(self) -> Path:
        return self.data_dir / "images"

    @property
    def heartbeat_path(self) -> Path:
        return self.data_dir / "heartbeat"

    def is_quiet_now(self, moment: dt.datetime) -> bool:
        """Тихие часы могут пересекать полночь (22:00-08:00)."""
        now = moment.astimezone(self.tz).time()
        start, end = self.quiet_from, self.quiet_to
        if start <= end:
            return start <= now < end
        return now >= start or now < end

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.image_cache_dir):
            path.mkdir(parents=True, exist_ok=True)
