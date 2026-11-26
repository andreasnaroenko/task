"""Готовые тексты справки.

Здесь нет логики приложения — только строки, которые видит пользователь.
Это упрощает `engine.py`: в нём остаётся только обработка команд.
"""

from __future__ import annotations

from .errors import DBError


def build_help(topic: str) -> list[tuple[str, str]]:
    """Возвращает строки справки для указанного раздела."""
    key = topic.strip().lower()

    if not key:
        return _general()
    if key in ("db", "database", "databases", "базы", "бд"):
        return _databases()
    if key in ("table", "tables", "таблицы", "таблица"):
        return _tables()
    if key in ("data", "данные", "записи"):
        return _data()
    if key in ("types", "типы", "тип"):
        return _types()
    if key in ("errors", "ошибки", "ошибка"):
        return _errors()
    if key in ("tutorial", "обучение", "урок"):
        return _tutorial()

    raise DBError(
        f"Раздел справки «{topic}» не найден.",
        "Доступно: HELP, HELP DB, HELP TABLES, HELP DATA, "
        "HELP TYPES, HELP ERRORS, HELP TUTORIAL.",
    )


def _general() -> list[tuple[str, str]]:
    return [
        ("banner", "СПРАВКА · ЧТО Я УМЕЮ"),
        (
            "info",
            "Пишите команду в строку ввода — я всё сделаю и подскажу, если "
            "что-то пойдёт не так.",
        ),
        ("muted", "Можно начать с DEMO (готовый пример) или TUTORIAL (урок)."),
        ("tutorial", "БАЗЫ ДАННЫХ"),
        ("code", "  CREATE DATABASE <имя>           создать базу"),
        ("code", "  SHOW DATABASES                 список баз"),
        ("code", "  USE <имя>                      выбрать текущую базу"),
        ("code", "  DROP DATABASE <имя> CONFIRM    удалить базу"),
        ("tutorial", "ТАБЛИЦЫ"),
        ("code", "  CREATE TABLE <имя> (поле:тип, ...)   создать таблицу"),
        ("code", "  SHOW TABLES                    список таблиц"),
        ("code", "  DESCRIBE <таблица>             структура таблицы"),
        ("code", "  ALTER TABLE <т> ADD <поле>:<тип>     добавить поле"),
        ("code", "  ALTER TABLE <т> DROP <поле>         удалить поле"),
        ("code", "  DROP TABLE <имя> CONFIRM       удалить таблицу"),
        ("tutorial", "ДАННЫЕ"),
        ("code", "  INSERT INTO <т> (поля) VALUES (значения)   добавить запись"),
        ("code", "  SELECT * FROM <т> [WHERE id=N]        показать записи"),
        ("code", "  UPDATE <т> SET поле=значение WHERE id=N   изменить"),
        ("code", "  DELETE FROM <т> WHERE id=N            удалить"),
        ("tutorial", "ПРОЧЕЕ"),
        ("code", "  HELP [раздел] · TUTORIAL · DEMO · STATUS · CLEAR · EXIT"),
        ("code", "  ПРИВЕТ · СПАСИБО · ABOUT — просто по-человечески"),
        (
            "muted",
            "Типы: string (строка), int (целое), float (вещественное), "
            "bool (true/false).",
        ),
        (
            "muted",
            "Подробнее: HELP DB, HELP TABLES, HELP DATA, HELP TYPES, "
            "HELP ERRORS.",
        ),
    ]


def _databases() -> list[tuple[str, str]]:
    return [
        ("banner", "СПРАВКА · БАЗЫ ДАННЫХ"),
        ("code", "CREATE DATABASE demo — создать базу demo."),
        ("code", "SHOW DATABASES — показать все базы и их размер."),
        ("code", "USE demo — сделать базу текущей."),
        ("code", "DROP DATABASE demo CONFIRM — удалить базу со всеми данными."),
        (
            "muted",
            "Имена уникальны без учёта регистра: demo и DEMO — одна база.",
        ),
    ]


def _tables() -> list[tuple[str, str]]:
    return [
        ("banner", "СПРАВКА · ТАБЛИЦЫ"),
        ("code", "CREATE TABLE employees (name:string, age:int, active:bool)"),
        ("code", "SHOW TABLES — список таблиц текущей базы."),
        ("code", "DESCRIBE employees — поля, типы и количество записей."),
        ("code", "ALTER TABLE employees ADD email:string — добавить поле."),
        ("code", "ALTER TABLE employees DROP email — удалить поле."),
        ("code", "DROP TABLE employees CONFIRM — удалить таблицу."),
        (
            "muted",
            "Имя id зарезервировано: идентификатор создаётся автоматически.",
        ),
    ]


def _data() -> list[tuple[str, str]]:
    return [
        ("banner", "СПРАВКА · ДАННЫЕ"),
        ("code", "INSERT INTO employees (name, age) VALUES ('Иван', 30)"),
        ("code", "SELECT * FROM employees — все записи."),
        ("code", "SELECT * FROM employees WHERE id = 1 — одна запись."),
        ("code", "UPDATE employees SET age = 31, active = true WHERE id = 1"),
        ("code", "DELETE FROM employees WHERE id = 1"),
        (
            "muted",
            "Строки с пробелами и запятыми заключайте в кавычки: 'Иван Петров'.",
        ),
    ]


def _types() -> list[tuple[str, str]]:
    return [
        ("banner", "СПРАВКА · ТИПЫ ДАННЫХ"),
        ("code", "string — строка: 'Иван Петров', 'Отдел кадров'."),
        ("code", "int — целое число: 42, -7, 0."),
        ("code", "float — вещественное: 55000.50, 12,5, -0.25."),
        ("code", "bool — логическое: true/false, 1/0, да/нет."),
        (
            "muted",
            "При неверном типе запись не добавляется, выводится подсказка.",
        ),
    ]


def _errors() -> list[tuple[str, str]]:
    return [
        ("banner", "СПРАВКА · ОШИБКИ И РЕШЕНИЯ"),
        (
            "info",
            "Дубликат базы/таблицы/поля — выберите другое имя или удалите объект.",
        ),
        (
            "info",
            "Объект не найден — проверьте имя: SHOW DATABASES / SHOW TABLES / "
            "DESCRIBE.",
        ),
        (
            "info",
            "Неверный тип — смотрите HELP TYPES и структуру: DESCRIBE <таблица>.",
        ),
        (
            "info",
            "Запись не найдена — посмотрите id: SELECT * FROM <таблица>.",
        ),
        (
            "muted",
            "После каждой ошибки терминал выводит строку «Решение: ...».",
        ),
    ]


def _tutorial() -> list[tuple[str, str]]:
    return [
        ("banner", "ОБУЧЕНИЕ"),
        ("code", "TUTORIAL — начать интерактивный урок (13 шагов)."),
        ("code", "TUTORIAL STOP — остановить урок."),
        ("code", "TUTORIAL RESTART — начать урок заново."),
        (
            "muted",
            "Во время урока нужная команда подставляется в поле ввода.",
        ),
    ]
