"""Интерактивный урок по всем возможностям системы.

Урок состоит из последовательных шагов. На каждом шаге пользователю
показывается цель, готовая команда и подсказка. Команда подставляется в
поле ввода, поэтому урок можно пройти, просто нажимая Enter.

Состояние шага проверяется по реальным данным, а не только по тексту
команды: это исключает «формальное» прохождение урока.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from .models import DatabaseManager

if TYPE_CHECKING:  # pragma: no cover - только для аннотаций
    from .engine import Engine


TUTORIAL_DB = "tutorial_db"
TUTORIAL_TABLE = "employees"


@dataclass
class Step:
    """Один шаг интерактивного урока."""

    title: str
    task: str
    example: str
    pattern: re.Pattern[str]
    check: Callable[["Tutorial"], bool]
    hint: str


class Tutorial:
    """Машина состояний интерактивного обучения."""

    def __init__(self, manager: DatabaseManager) -> None:
        self.manager = manager
        self.active = False
        self.index = 0
        self.steps: list[Step] = self._build_steps()

    # ------------------------------------------------------------------
    # Проверки состояния
    # ------------------------------------------------------------------
    def _db(self):
        return self.manager.databases.get(TUTORIAL_DB)

    def _table(self):
        database = self._db()
        if database is None:
            return None
        return database.tables.get(TUTORIAL_TABLE)

    def _check_fields(self) -> bool:
        table = self._table()
        if table is None:
            return False
        expected = {
            "name": "string",
            "age": "int",
            "salary": "float",
            "active": "bool",
        }
        actual = {field.name.lower(): field.type for field in table.fields}
        return actual == expected

    def _check_email(self) -> bool:
        table = self._table()
        if table is None:
            return False
        return any(
            field.name.lower() == "email" and field.type == "string"
            for field in table.fields
        )

    def _build_steps(self) -> list[Step]:
        return [
            Step(
                "Создание базы данных",
                "Создайте учебную базу данных с именем tutorial_db.",
                "CREATE DATABASE tutorial_db",
                re.compile(r"^CREATE\s+DATABASE\s+TUTORIAL_DB\s*$", re.I),
                lambda: self._db() is not None,
                "База создаётся командой CREATE DATABASE <имя>.",
            ),
            Step(
                "Выбор базы данных",
                "Сделайте учебную базу текущей.",
                "USE tutorial_db",
                re.compile(r"^USE\s+TUTORIAL_DB\s*$", re.I),
                lambda: self.manager.current == TUTORIAL_DB,
                "Текущая база выбирается командой USE <имя>.",
            ),
            Step(
                "Создание таблицы",
                "Создайте таблицу employees с полями name, age, salary, active.",
                "CREATE TABLE employees (name:string, age:int, salary:float, active:bool)",
                re.compile(r"^CREATE\s+TABLE\s+EMPLOYEES\s*\(.*\)\s*$", re.I | re.S),
                self._check_fields,
                "Поля перечисляются в скобках в формате имя:тип.",
            ),
            Step(
                "Просмотр структуры",
                "Посмотрите структуру созданной таблицы.",
                "DESCRIBE employees",
                re.compile(r"^DESCRIBE\s+EMPLOYEES\s*$", re.I),
                lambda: self._table() is not None,
                "Структура таблицы выводится командой DESCRIBE <таблица>.",
            ),
            Step(
                "Изменение структуры",
                "Добавьте в таблицу новое поле email типа string.",
                "ALTER TABLE employees ADD email:string",
                re.compile(
                    r"^ALTER\s+TABLE\s+EMPLOYEES\s+ADD\s+EMAIL\s*:\s*STRING\s*$",
                    re.I,
                ),
                self._check_email,
                "Поле добавляется командой ALTER TABLE <т> ADD <поле>:<тип>.",
            ),
            Step(
                "Добавление записи",
                "Добавьте первого сотрудника: Иван Петров, 30 лет, оклад 55000.50, активен.",
                "INSERT INTO employees (name, age, salary, active, email) "
                "VALUES ('Иван Петров', 30, 55000.50, true, '')",
                re.compile(r"^INSERT\s+INTO\s+EMPLOYEES\b", re.I | re.S),
                lambda: self._table() is not None and self._table().row_count >= 1,
                "Строка в кавычках может содержать пробелы.",
            ),
            Step(
                "Добавление второй записи",
                "Добавьте второго сотрудника: Анна Смирнова, 27 лет, оклад 62000, не активна.",
                "INSERT INTO employees (name, age, salary, active, email) "
                "VALUES ('Анна Смирнова', 27, 62000, false, '')",
                re.compile(r"^INSERT\s+INTO\s+EMPLOYEES\b", re.I | re.S),
                lambda: self._table() is not None and self._table().row_count >= 2,
                "Значение bool может быть true/false, 1/0 или да/нет.",
            ),
            Step(
                "Просмотр данных",
                "Выведите все записи таблицы employees.",
                "SELECT * FROM employees",
                re.compile(r"^SELECT\s+\*\s+FROM\s+EMPLOYEES\s*$", re.I | re.S),
                lambda: self._table() is not None and self._table().row_count >= 2,
                "Все записи выводятся командой SELECT * FROM <таблица>.",
            ),
            Step(
                "Изменение записи",
                "Измените оклад записи с id = 1 на 60000 и заполните email "
                "значением ivan@example.ru.",
                "UPDATE employees SET salary = 60000, "
                "email = 'ivan@example.ru' WHERE id = 1",
                re.compile(r"^UPDATE\s+EMPLOYEES\b", re.I | re.S),
                lambda: self._table() is not None
                and 1 in self._table().rows
                and self._table().rows[1].get("salary") == 60000.0
                and self._table().rows[1].get("email") == "ivan@example.ru",
                "Поля задаются через запятую: SET salary = 60000, "
                "email = 'ivan@example.ru'.",
            ),
            Step(
                "Удаление записи",
                "Удалите запись с id = 2.",
                "DELETE FROM employees WHERE id = 2",
                re.compile(r"^DELETE\s+FROM\s+EMPLOYEES\b", re.I | re.S),
                lambda: self._table() is not None and 2 not in self._table().rows,
                "Удаление выполняется только по идентификатору записи.",
            ),
            Step(
                "Финальная проверка",
                "Убедитесь, что в таблице осталась одна изменённая запись.",
                "SELECT * FROM employees",
                re.compile(r"^SELECT\s+\*\s+FROM\s+EMPLOYEES\s*$", re.I | re.S),
                lambda: self._table() is not None
                and self._table().row_count == 1
                and 1 in self._table().rows
                and self._table().rows[1].get("email") == "ivan@example.ru",
                "Сравните количество записей, значение salary и поле email.",
            ),
            Step(
                "Удаление таблицы",
                "Удалите учебную таблицу employees.",
                "DROP TABLE employees CONFIRM",
                re.compile(
                    r"^DROP\s+TABLE\s+EMPLOYEES\s+CONFIRM\s*$", re.I
                ),
                lambda: self._table() is None,
                "Удаление таблицы требует подтверждения: DROP TABLE ... CONFIRM.",
            ),
            Step(
                "Удаление базы данных",
                "Удалите учебную базу tutorial_db.",
                "DROP DATABASE tutorial_db CONFIRM",
                re.compile(
                    r"^DROP\s+DATABASE\s+TUTORIAL_DB\s+CONFIRM\s*$", re.I
                ),
                lambda: self._db() is None,
                "Удаление базы требует подтверждения: DROP DATABASE ... CONFIRM.",
            ),
        ]

    # ------------------------------------------------------------------
    # Управление уроком
    # ------------------------------------------------------------------
    def start(self) -> tuple[list[tuple[str, str]], str]:
        """Сбрасывает учебную базу и запускает урок с первого шага."""
        lines: list[tuple[str, str]] = []
        if TUTORIAL_DB in self.manager.databases:
            self.manager.drop_database(TUTORIAL_DB)
            lines.append(
                (
                    "muted",
                    "Предыдущая учебная база удалена, чтобы урок начался с чистого листа.",
                )
            )
        self.active = True
        self.index = 0
        lines.append(
            ("tutorial", f"ИНТЕРАКТИВНЫЙ УРОК · {len(self.steps)} шагов")
        )
        lines.append(
            (
                "info",
                "Привет! Я проведу вас по всем основным возможностям и всё "
                "покажу на примере.",
            )
        )
        lines.append(
            (
                "info",
                "Команду шага я уже подставила в строку ввода — просто "
                "нажмите Enter.",
            )
        )
        lines.append(
            (
                "muted",
                "Если устанете: TUTORIAL STOP. Начать заново: TUTORIAL RESTART.",
            )
        )
        lines.extend(self._step_lines())
        return lines, self.steps[self.index].example

    def stop(self, completed: bool = False) -> list[tuple[str, str]]:
        """Завершает урок."""
        self.active = False
        if completed:
            return [
                ("success", f"Ура! Урок пройден — все {len(self.steps)} шагов позади."),
                (
                    "info",
                    "Вы создали базу и таблицу, добавили, изменили и удалили "
                    "записи, а затем удалили таблицу и базу.",
                ),
                (
                    "muted",
                    "Учебные данные убраны. Теперь можно работать со своими "
                    "базами: CREATE DATABASE <имя>.",
                ),
            ]
        return [
            ("warn", "Хорошо, остановила урок."),
            (
                "muted",
                "Продолжить можно с начала: TUTORIAL. Если нужна подсказка: HELP.",
            ),
        ]

    def restart(self) -> tuple[list[tuple[str, str]], str]:
        lines, prefill = self.start()
        return lines, prefill

    def status(self) -> list[tuple[str, str]]:
        if not self.active:
            return [("muted", "Урок пока не запущен. Начать: TUTORIAL.")]
        return self._step_lines()

    # ------------------------------------------------------------------
    # Проверка команд во время урока
    # ------------------------------------------------------------------
    def is_control(self, raw: str) -> bool:
        """Служебные команды разрешены на любом шаге."""
        first = raw.strip().split(None, 1)[0].upper() if raw.strip() else ""
        return first in ("TUTORIAL", "HELP", "CLEAR", "STATUS", "ABOUT")

    def matches_current(self, raw: str) -> bool:
        if not self.active:
            return True
        return bool(self.steps[self.index].pattern.match(raw.strip()))

    def blocked_result(self) -> tuple[list[tuple[str, str]], str]:
        """Сообщение, если команда не относится к текущему шагу."""
        step = self.steps[self.index]
        lines = [
            (
                "warn",
                f"ОБУЧЕНИЕ · шаг {self.index + 1}/{len(self.steps)}: "
                "давайте сначала закончим его.",
            ),
            ("info", step.task),
            ("code", "Введите: " + step.example),
            ("muted", "Если хотите выйти из урока: TUTORIAL STOP."),
        ]
        return lines, step.example

    def after_command(self, raw: str) -> tuple[list[tuple[str, str]], str | None]:
        """Проверяет результат команды и переводит урок на следующий шаг."""
        if not self.active:
            return [], None

        step = self.steps[self.index]
        if not step.check():
            return [
                (
                    "hint",
                    f"Пока не получилось, шаг {self.index + 1} не засчитан. "
                    f"{step.hint}",
                ),
                (
                    "muted",
                    "Ничего страшного — повторите команду или посмотрите "
                    "подсказку выше.",
                ),
            ], step.example

        if self.index + 1 >= len(self.steps):
            return self.stop(completed=True), None

        self.index += 1
        lines: list[tuple[str, str]] = [
            ("success", f"Отлично! Шаг {self.index}/{len(self.steps)} готов."),
        ]
        lines.extend(self._step_lines())
        return lines, self.steps[self.index].example

    # ------------------------------------------------------------------
    # Оформление
    # ------------------------------------------------------------------
    def _step_lines(self) -> list[tuple[str, str]]:
        step = self.steps[self.index]
        return [
            ("tutorial", f"ШАГ {self.index + 1}/{len(self.steps)} · {step.title}"),
            ("info", "Задание: " + step.task),
            ("code", "Команда: " + step.example),
            ("muted", "Нажмите Enter — я выполню. Выйти: TUTORIAL STOP."),
        ]
