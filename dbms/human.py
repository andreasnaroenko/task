"""Человеческие фразы: приветствие и правильные формы слов.

Этот модуль делает сообщения программы живыми, но не влияет на логику.
Его удобно объяснять отдельно: здесь только текст и склонения.
"""

from __future__ import annotations

from datetime import datetime


def greeting(moment: datetime | None = None) -> str:
    """Возвращает приветствие по времени суток."""
    hour = (moment or datetime.now()).hour
    if 5 <= hour < 12:
        return "Доброе утро"
    if 12 <= hour < 18:
        return "Добрый день"
    if 18 <= hour < 23:
        return "Добрый вечер"
    return "Доброй ночи"


def plural(number: int, one: str, few: str, many: str) -> str:
    """Выбирает правильную форму слова для числа.

    Пример: plural(1, "таблица", "таблицы", "таблиц") -> "таблица".
    """
    number = abs(number) % 100
    if 11 <= number <= 14:
        return many
    last = number % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many
