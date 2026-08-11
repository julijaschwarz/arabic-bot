"""Прогон настоящих хендлеров через диспетчер aiogram.

Telegram подменён записывающим двойником: проверяем, что маршрутизация,
мидлвари и передача зависимостей действительно работают, — ошибки здесь
иначе всплыли бы только в живом чате.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import SendMessage, SendPhoto, TelegramMethod
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from arabic_bot.bot import keyboards
from arabic_bot.bot.setup import build
from arabic_bot.config import Settings

USER_ID = 777
CHAT_ID = 777
STRANGER_ID = 999


class RecordingBot(Bot):
    """Ловит исходящие вызовы вместо похода в Telegram."""

    def __init__(self) -> None:
        super().__init__(
            "42:TEST", default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        self.calls: list[TelegramMethod] = []
        self.fail: Callable[[TelegramMethod], Exception | None] | None = None
        """Хук отказа. Подменять __call__ на экземпляре бесполезно:
        Python ищет dunder-методы на классе, и подмена молча не сработает."""

    async def __call__(self, method: TelegramMethod, request_timeout: int | None = None):
        self.calls.append(method)
        if self.fail is not None:
            error = self.fail(method)
            if error is not None:
                raise error
        return _stub_message()

    def texts(self) -> list[str]:
        out = []
        for call in self.calls:
            if isinstance(call, SendMessage):
                out.append(call.text)
            elif isinstance(call, SendPhoto):
                out.append(call.caption or "")
        return out

    def last_markup(self):
        for call in reversed(self.calls):
            markup = getattr(call, "reply_markup", None)
            if markup is not None:
                return markup
        return None

    def clear(self) -> None:
        self.calls.clear()


def _stub_message() -> Message:
    return Message(
        message_id=1,
        date=dt.datetime(2026, 7, 29, tzinfo=dt.UTC),
        chat=Chat(id=CHAT_ID, type="private"),
    ).as_(None)


def _message(text: str, user_id: int = USER_ID) -> Update:
    return Update(
        update_id=1,
        message=Message(
            message_id=2,
            date=dt.datetime(2026, 7, 29, tzinfo=dt.UTC),
            chat=Chat(id=user_id, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="Юля"),
            text=text,
        ),
    )


def _callback(data: str, user_id: int = USER_ID) -> Update:
    return Update(
        update_id=2,
        callback_query=CallbackQuery(
            id="cb",
            from_user=User(id=user_id, is_bot=False, first_name="Юля"),
            chat_instance="ci",
            data=data,
            message=Message(
                message_id=3,
                date=dt.datetime(2026, 7, 29, tzinfo=dt.UTC),
                chat=Chat(id=user_id, type="private"),
            ),
        ),
    )


@pytest.fixture
async def app(tmp_path: Path):
    settings = Settings(
        BOT_TOKEN="42:TEST",
        ALLOWED_USER_IDS=str(USER_ID),
        DATA_DIR=str(tmp_path),
        DB_PATH=str(tmp_path / "bot.db"),
        DAILY_TASK_COUNT="3",
        IMAGES_ENABLED="false",
    )
    bot = RecordingBot()
    application = await build(settings, bot=bot)
    yield application, bot
    await application.database.close()
    await bot.session.close()


async def test_start_greets_and_offers_to_begin(app):
    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/start"))

    assert any("тренажёр арабского" in text for text in bot.texts())
    markup = bot.last_markup()
    assert markup.inline_keyboard[0][0].callback_data == keyboards.START_SESSION


async def test_stranger_is_turned_away(app):
    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/start", user_id=STRANGER_ID))
    assert any("бот личный" in text for text in bot.texts())


async def test_go_sends_a_question(app):
    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/go"))

    assert any("Букв в фокусе сегодня" in text for text in bot.texts())
    assert any("Вопрос 1 из 3" in text for text in bot.texts())


async def test_correct_answer_reports_done_and_moves_on(app):
    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/go"))

    service = application.dispatcher.workflow_data["service"]
    exercise = (await service.active_session(USER_ID)).current_exercise
    bot.clear()

    await application.dispatcher.feed_update(bot, _message(exercise.accepted[0]))

    assert any(text.startswith("Done ✅") for text in bot.texts())
    assert any("Вопрос 2 из 3" in text for text in bot.texts())


async def test_wrong_answer_offers_retry_and_reveal(app):
    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/go"))
    bot.clear()

    await application.dispatcher.feed_update(bot, _message("совершенно неверный ответ"))

    assert any("Не верно ❌" in text for text in bot.texts())
    buttons = [button.callback_data for row in bot.last_markup().inline_keyboard for button in row]
    assert keyboards.RETRY in buttons and keyboards.REVEAL in buttons


async def test_reveal_shows_answer_and_waits_for_next(app):
    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/go"))
    await application.dispatcher.feed_update(bot, _message("неверно"))
    bot.clear()

    await application.dispatcher.feed_update(bot, _callback(keyboards.REVEAL))

    assert any("Правильный ответ" in text for text in bot.texts())
    # Следующий вопрос не приходит сам — ждём нажатия «Дальше».
    assert not any("Вопрос 2 из 3" in text for text in bot.texts())

    bot.clear()
    await application.dispatcher.feed_update(bot, _callback(keyboards.NEXT))
    assert any("Вопрос 2 из 3" in text for text in bot.texts())


async def test_session_finishes_with_a_summary(app):
    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/go"))
    service = application.dispatcher.workflow_data["service"]

    for _ in range(3):
        exercise = (await service.active_session(USER_ID)).current_exercise
        await application.dispatcher.feed_update(bot, _message(exercise.accepted[0]))

    assert any("Занятие окончено" in text for text in bot.texts())
    buttons = [button.callback_data for row in bot.last_markup().inline_keyboard for button in row]
    assert keyboards.MORE in buttons


async def test_answer_without_session_suggests_starting(app):
    application, bot = app
    await application.dispatcher.feed_update(bot, _message("ба"))
    assert any("нет активного занятия" in text.lower() for text in bot.texts())


async def test_reference_commands_respond(app):
    application, bot = app
    for command in ("/stats", "/letters", "/digits"):
        await application.dispatcher.feed_update(bot, _message(command))
    joined = "\n".join(bot.texts())
    assert "Прогресс" in joined and "Алфавит" in joined and "Цифры" in joined


async def test_digits_cheatsheet_lists_every_numeral(app):
    """Без шпаргалки задание на названия цифр негде выучить."""
    from arabic_bot.domain.digits import DIGITS

    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/digits"))
    body = "\n".join(bot.texts())
    for digit in DIGITS:
        assert digit.char in body and digit.name_ru in body


async def test_settings_change_is_saved(app):
    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/settings count 12"))

    users = application.dispatcher.workflow_data["users"]
    user = await users.get(USER_ID)
    assert user.tasks_per_day == 12
    assert any("Готово" in text for text in bot.texts())


async def test_settings_rejects_bad_time(app):
    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/settings time 25:99"))
    assert any("ЧЧ:ММ" in text for text in bot.texts())


async def test_stale_button_press_still_works(app):
    """Кнопка, нажатая пока бот был недоступен, приходит с истёкшим query id.

    Раньше на подтверждении такого нажатия падал весь хендлер, и действие
    пользователя терялось.
    """
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import AnswerCallbackQuery

    application, bot = app
    await application.dispatcher.feed_update(bot, _message("/go"))
    bot.clear()

    bot.fail = lambda method: (
        TelegramBadRequest(
            method=method,
            message="Bad Request: query is too old and response timeout expired",
        )
        if isinstance(method, AnswerCallbackQuery)
        else None
    )

    await application.dispatcher.feed_update(bot, _callback(keyboards.SKIP))

    assert any("Правильный ответ" in text for text in bot.texts()), (
        "показ ответа должен состояться, несмотря на устаревшее нажатие"
    )
