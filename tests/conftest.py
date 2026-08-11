from __future__ import annotations

import random

import pytest

from arabic_bot.domain.lexicon import Lexicon


@pytest.fixture(scope="session")
def lexicon() -> Lexicon:
    return Lexicon.load()


@pytest.fixture
def rng() -> random.Random:
    # Фиксированное зерно: падение теста воспроизводится с первого раза.
    return random.Random(20260729)
