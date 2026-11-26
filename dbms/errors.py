"""Исключения приложения.

Все ожидаемые ошибки пользователя поднимаются как DBError. Для каждой
ошибки можно указать подсказку с решением — она выводится в терминале.
"""


class DBError(Exception):
    """Ожидаемая ошибка ввода или операции с данными."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
