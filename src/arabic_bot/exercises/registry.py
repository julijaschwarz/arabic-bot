"""Реестр генераторов.

Заполняется один раз при импорте пакета `generators` и дальше не меняется.
Новый файл в этом пакете подхватывается сам — без правок в реестре, планировщике
или хендлерах.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import TypeVar

from .base import ExerciseGenerator

log = logging.getLogger(__name__)

_REGISTRY: dict[str, type[ExerciseGenerator]] = {}
_loaded = False

G = TypeVar("G", bound=type[ExerciseGenerator])


def register(cls: G) -> G:
    """Декоратор над классом генератора."""
    generator_id = getattr(cls, "id", None)
    if not generator_id:
        raise ValueError(f"{cls.__name__}: не задан атрибут id")
    if generator_id in _REGISTRY and _REGISTRY[generator_id] is not cls:
        raise ValueError(f"Генератор с id={generator_id!r} уже зарегистрирован")
    _REGISTRY[generator_id] = cls
    return cls


def load() -> None:
    """Импортировать все модули из `exercises.generators`."""
    global _loaded
    if _loaded:
        return
    from . import generators as package

    for module in pkgutil.iter_modules(package.__path__):
        if module.name.startswith("_"):
            continue
        importlib.import_module(f"{package.__name__}.{module.name}")
    _loaded = True
    log.info("Загружено генераторов заданий: %d", len(_REGISTRY))


def all_generators() -> tuple[ExerciseGenerator, ...]:
    load()
    return tuple(cls() for cls in _REGISTRY.values())


def by_id(generator_id: str) -> ExerciseGenerator | None:
    load()
    cls = _REGISTRY.get(generator_id)
    return cls() if cls else None


def known_ids() -> tuple[str, ...]:
    load()
    return tuple(_REGISTRY)
