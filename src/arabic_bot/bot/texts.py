"""Все тексты бота в одном месте — чтобы правились без похода по хендлерам."""

from __future__ import annotations

from ..domain.models import Exercise

START = (
    "Привет! Это тренажёр арабского алфавита. 🕌\n\n"
    "Каждый день — {count} заданий: буквы и их формы, цифры ٠–٩ и распознавание "
    "букв внутри слов. Задания собираются на ходу, поэтому они не кончатся.\n\n"
    "Начнём? Жмите «Поехали» или напишите /go."
)

HELP = (
    "<b>Команды</b>\n"
    "/go — начать занятие\n"
    "/more — ещё 5 заданий\n"
    "/stats — прогресс и трудные буквы\n"
    "/letters — шпаргалка: 28 букв с формами\n"
    "/digits — шпаргалка: цифры ٠–٩ с названиями\n"
    "/settings — время рассылки и число заданий\n"
    "/stop — закончить занятие\n\n"
    "<b>Как отвечать</b>\n"
    "Пишите ответ текстом — по-русски или латиницей: «ба», «baa», «bāʼ» — всё подойдёт.\n"
    "Где нужно выбрать арабский символ, появятся кнопки.\n"
    "В разборе слова называйте буквы через пробел: «кяф та алиф ба» — "
    "или напишите слово целиком: «kitab»."
)

SESSION_START = "Занятие начинается. Букв в фокусе сегодня: {letters}\n"
NO_SESSION = "Сейчас нет активного занятия. Начать — /go"
ALREADY_RUNNING = "Занятие уже идёт — вот текущий вопрос."

CORRECT = "Done ✅"
CORRECT_RETRIED = "Done ✅ — с {attempts}-й попытки, эту букву повторим пораньше."
WRONG = "Не верно ❌"
REVEALED = "Правильный ответ:"

QUESTION_HEADER = "Вопрос {position} из {total}"
HINT = "💡 {text}"

TRY_AGAIN_PROMPT = "Попробуете ещё раз или показать ответ?"
NUDGE = "Пора повторить арабский! 🕌\nЗайдём на пару заданий?"

IMAGE_FAILED = "Не получилось нарисовать картинку, вот текстом:"

NOT_ALLOWED = (
    "Этот бот личный. Если он нужен вам — попросите владельца добавить ваш ID "
    "в ALLOWED_USER_IDS."
)

CHOICE_ONLY = "Здесь нужно выбрать вариант кнопкой 👇"

SESSION_DONE = (
    "Занятие окончено. ✅\n\n"
    "Верных ответов: <b>{correct} из {total}</b> ({percent}%)\n"
    "Круг №{cycle}, букв в нём осталось пройти: {fresh_left}"
)

STATS = (
    "<b>Прогресс</b>\n"
    "Круг №{cycle}, пройдено букв в нём: {seen} из 28\n\n"
    "За 7 дней: {week_total} заданий, верных {week_correct} ({week_percent}%)\n"
    "За всё время: {all_total} заданий, верных {all_correct} ({all_percent}%)"
)
STATS_HARD = "\n\n<b>Труднее всего даются</b>\n{letters}"
STATS_EMPTY = "\n\nПока мало данных — позанимайтесь пару дней, и тут появятся трудные буквы."

SETTINGS = (
    "<b>Настройки</b>\n"
    "Заданий в день: <b>{count}</b>\n"
    "Утренняя рассылка: <b>{time}</b> ({tz})\n"
    "Напоминания: <b>{notifications}</b>\n\n"
    "Изменить:\n"
    "<code>/settings time 09:00</code>\n"
    "<code>/settings count 10</code>\n"
    "<code>/settings notify on</code> или <code>off</code>"
)
SETTINGS_SAVED = "Готово ✅"
SETTINGS_BAD_TIME = "Время нужно в формате ЧЧ:ММ, например 09:00"
SETTINGS_BAD_COUNT = "Число заданий — от 1 до 50"


def question_text(
    exercise: Exercise, position: int, total: int, *, textual_fallback: bool = False
) -> str:
    """Заголовок, задание, крупный арабский символ, подсказка.

    `textual_fallback` — картинку нарисовать не удалось: подставляем формулировку,
    которая не ссылается на цвет и работает обычным текстом.
    """
    prompt = exercise.prompt
    if textual_fallback:
        prompt = exercise.payload.get("prompt_without_image", prompt)

    parts = [f"<i>{QUESTION_HEADER.format(position=position, total=total)}</i>", prompt]

    display = exercise.display
    if textual_fallback and not display and exercise.image is not None:
        display = exercise.image.text
    if display:
        parts.append(f"\n<code>{display}</code>")

    if exercise.hint:
        parts.append(f"\n{HINT.format(text=exercise.hint)}")
    return "\n".join(parts)


def outcome_text(*, correct: bool, attempts: int = 1, comment: str = "") -> str:
    """Отчёт по фактическому числу попыток.

    Раньше здесь была фраза «со второй попытки» вне зависимости от того,
    сколько их было на самом деле.
    """
    if correct:
        return CORRECT if attempts <= 1 else CORRECT_RETRIED.format(attempts=attempts)
    return f"{WRONG}\n{comment}".strip()


def percent(correct: int, total: int) -> int:
    return round(correct * 100 / total) if total else 0
