"""Разбор команд терминала.

Терминал использует SQL-подобный синтаксис, но это не настоящий SQL.
Собственный разбор нужен, чтобы:
* корректно понимать строки с пробелами, запятыми и скобками;
* выдавать пользователю понятные сообщения об ошибках;
* не зависеть от сторонних библиотек.
"""

from __future__ import annotations

from .errors import DBError


def split_top_level(text: str, separator: str = ",") -> list[str]:
    """Делит строку по разделителю вне кавычек и скобок."""
    parts: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    depth = 0
    i = 0

    while i < len(text):
        char = text[i]

        if quote is not None:
            buffer.append(char)
            if char == "\\" and i + 1 < len(text):
                buffer.append(text[i + 1])
                i += 2
                continue
            if char == quote:
                quote = None
        else:
            if char in ("'", '"'):
                quote = char
                buffer.append(char)
            elif char == "(":
                depth += 1
                buffer.append(char)
            elif char == ")":
                depth -= 1
                if depth < 0:
                    raise DBError(
                        "Лишняя закрывающая скобка «)».",
                        "Проверьте парность скобок в команде.",
                    )
                buffer.append(char)
            elif char == separator and depth == 0:
                parts.append("".join(buffer).strip())
                buffer = []
            else:
                buffer.append(char)
        i += 1

    if quote is not None:
        raise DBError(
            "Не закрыта кавычка в команде.",
            "Добавьте закрывающую кавычку того же типа: ' или \".",
        )
    if depth != 0:
        raise DBError(
            "Не закрыта скобка в команде.",
            "Проверьте, что каждой открывающей «(» соответствует «)».",
        )

    parts.append("".join(buffer).strip())
    return parts


def find_keyword(text: str, keyword: str) -> int:
    """Ищет ключевое слово вне кавычек и скобок. Возвращает -1, если нет."""
    upper = text.upper()
    target = keyword.upper()
    quote: str | None = None
    depth = 0
    i = 0
    length = len(target)

    while i <= len(text) - length:
        char = text[i]
        if quote is not None:
            if char == "\\":
                i += 2
                continue
            if char == quote:
                quote = None
            i += 1
            continue

        if char in ("'", '"'):
            quote = char
            i += 1
            continue
        if char == "(":
            depth += 1
            i += 1
            continue
        if char == ")":
            depth -= 1
            i += 1
            continue

        if depth == 0 and upper[i : i + length] == target:
            before_ok = i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")
            after = i + length
            after_ok = after >= len(text) or not (
                text[after].isalnum() or text[after] == "_"
            )
            if before_ok and after_ok:
                return i
        i += 1
    return -1


def extract_parenthesized(text: str, start: int = 0) -> tuple[str, int]:
    """Возвращает содержимое скобок и позицию сразу после закрывающей.

    Позиция start должна указывать на пробелы перед «(» либо на саму «(».
    """
    i = start
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text) or text[i] != "(":
        raise DBError(
            "Ожидалась открывающая скобка «(».",
            "Пример: INSERT INTO employees (name, age) VALUES ('Иван', 30).",
        )

    quote: str | None = None
    depth = 0
    content_start = i + 1
    while i < len(text):
        char = text[i]
        if quote is not None:
            if char == "\\":
                i += 2
                continue
            if char == quote:
                quote = None
        else:
            if char in ("'", '"'):
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return text[content_start:i], i + 1
        i += 1

    raise DBError(
        "Не найдена закрывающая скобка «)».",
        "Проверьте парность скобок в команде.",
    )


def parse_literal(token: str) -> str:
    """Убирает обрамляющие кавычки и раскрывает простые escape-последовательности."""
    text = token.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        quote = text[0]
        inner = text[1:-1]
        inner = inner.replace("\\" + quote, quote)
        inner = inner.replace("\\\\", "\\")
        return inner
    return text


def split_assignment(text: str) -> tuple[str, str]:
    """Делит «поле = значение» по первому знаку равенства вне кавычек."""
    quote: str | None = None
    depth = 0
    i = 0
    while i < len(text):
        char = text[i]
        if quote is not None:
            if char == "\\":
                i += 2
                continue
            if char == quote:
                quote = None
        else:
            if char in ("'", '"'):
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "=" and depth == 0:
                left = text[:i].strip()
                right = text[i + 1 :].strip()
                if not left or not right:
                    break
                return left, right
        i += 1
    raise DBError(
        f"Не удалось разобрать присваивание «{text.strip()}».",
        "Используйте формат поле = значение, например salary = 60000.",
    )
