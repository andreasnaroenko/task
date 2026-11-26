"""Диспетчер команд терминала.

Engine принимает строку команды, разбирает её, вызывает методы модели
данных и формирует CommandResult для GUI. Слой не зависит от tkinter,
поэтому используется и в автоматических тестах.
"""

from __future__ import annotations

import re

from .errors import DBError
from .help_text import build_help
from .human import greeting, plural
from .models import DatabaseManager, format_value
from .parser import (
    extract_parenthesized,
    find_keyword,
    parse_literal,
    split_assignment,
    split_top_level,
)
from .render import render_matrix, render_table
from .result import CommandResult
from .tutorial import Tutorial


class Engine:
    """Исполнитель команд учебной СУБД."""

    def __init__(self) -> None:
        self.manager = DatabaseManager()
        self.tutorial = Tutorial(self.manager)

    # ------------------------------------------------------------------
    # Публичный интерфейс
    # ------------------------------------------------------------------
    def execute(self, raw: str) -> CommandResult:
        """Выполняет одну команду и всегда возвращает результат.

        Любые ошибки пользователя перехватываются и превращаются в
        понятное сообщение, поэтому интерфейс не завершается аварийно.
        """
        result = CommandResult()
        command = raw.strip()
        if command.endswith(";"):
            command = command[:-1].rstrip()
        if not command:
            return result

        is_control = self.tutorial.is_control(command)

        if self.tutorial.active and not is_control:
            if not self.tutorial.matches_current(command):
                lines, prefill = self.tutorial.blocked_result()
                result.extend(lines)
                result.prefill = prefill
                return result

        try:
            self._dispatch(command, result)
        except DBError as error:
            result.add("Ошибка: " + error.message, "error")
            if error.hint:
                result.add("Решение: " + error.hint, "hint")
            result.add(
                "Не переживайте: данные не пострадали. Если нужно, HELP подскажет.",
                "muted",
            )
        except Exception as error:  # защита от непредвиденных ситуаций
            result.add(
                "Непредвиденная ошибка: " + str(error),
                "error",
            )
            result.add(
                "Решение: проверьте команду через HELP или перезапустите приложение. "
                "Данные хранятся только в памяти.",
                "hint",
            )

        if self.tutorial.active and not is_control:
            lines, prefill = self.tutorial.after_command(command)
            result.extend(lines)
            if prefill:
                result.prefill = prefill

        return result

    def reset(self) -> None:
        """Полностью сбрасывает данные и обучение."""
        self.manager.reset()
        self.tutorial.active = False
        self.tutorial.index = 0

    def status_line(self) -> str:
        """Короткая человеческая строка состояния для нижней панели GUI."""
        database = self.manager.current_database()
        if database is None:
            return "Сейчас: база не выбрана · можно создать первую"
        tables = len(database.tables)
        rows = database.row_count
        return (
            f"Сейчас: база «{database.name}» · {tables} "
            f"{plural(tables, 'таблица', 'таблицы', 'таблиц')} · {rows} "
            f"{plural(rows, 'запись', 'записи', 'записей')}"
        )

    # ------------------------------------------------------------------
    # Маршрутизация команд
    # ------------------------------------------------------------------
    def _dispatch(self, command: str, result: CommandResult) -> None:
        """Определяет команду и передаёт её нужному обработчику."""
        upper = command.upper()

        # --- служебные команды -------------------------------------
        if upper in ("EXIT", "QUIT", "ВЫХОД", "ПОКА"):
            result.exit_requested = True
            result.add("До встречи! Все данные останутся только в памяти и исчезнут.", "warn")
            return
        if upper in ("CLEAR", "CLS", "ОЧИСТИТЬ"):
            result.clear_requested = True
            return
        if upper in ("ПРИВЕТ", "ПРИВЕТ!", "ЗДРАВСТВУЙ", "ЗДРАВСТВУЙТЕ", "HELLO", "HI"):
            self._hello(result)
            return
        if upper in ("СПАСИБО", "СПАСИБО!", "БЛАГОДАРЮ", "THANKS"):
            result.add(
                "Пожалуйста! Рада помочь. Если понадоблюсь — просто напишите HELP.",
                "success",
            )
            return
        if upper in ("КАК ДЕЛА", "КАК ДЕЛА?", "КАК ТЫ", "КАК ТЫ?"):
            result.add(
                "Всё отлично: работаю, данные на месте, ничего не потеряно.",
                "info",
            )
            result.add(
                "А у вас как? Если нужна помощь — HELP или TUTORIAL.",
                "muted",
            )
            return
        if upper == "HELP" or upper == "ПОМОЩЬ":
            self._help("", result)
            return
        if upper.startswith("HELP "):
            self._help(command[5:].strip(), result)
            return
        if upper.startswith("ПОМОЩЬ "):
            self._help(command[7:].strip(), result)
            return
        if upper == "ABOUT" or upper == "О ПРОГРАММЕ":
            self._about(result)
            return
        if upper == "STATUS" or upper == "СТАТУС":
            self._status(result)
            return
        if upper == "DEMO" or upper == "ДЕМО":
            self._demo(result)
            return
        if upper == "TUTORIAL" or upper.startswith("TUTORIAL "):
            self._tutorial(command, result)
            return

        # --- базы данных -------------------------------------------
        match = re.match(r"^CREATE\s+DATABASE\s+(.+)$", command, re.I | re.S)
        if match:
            database = self.manager.create_database(match.group(1).strip())
            result.add(f"Готово! База «{database.name}» создана.", "success")
            if self.manager.current == database.name.lower():
                result.add(
                    "Я уже сделала её текущей — можно создавать таблицы.",
                    "muted",
                )
            result.add(
                f"Вернуться к ней позже: USE {database.name}.",
                "muted",
            )
            return

        if upper in ("SHOW DATABASES", "LIST DATABASES", "SHOW DB"):
            self._show_databases(result)
            return

        match = re.match(r"^USE\s+(.+)$", command, re.I | re.S)
        if match:
            database = self.manager.use(match.group(1).strip())
            tables = len(database.tables)
            rows = database.row_count
            result.add(f"Хорошо, теперь работаем с базой «{database.name}».", "success")
            result.add(
                f"Здесь {tables} {plural(tables, 'таблица', 'таблицы', 'таблиц')} "
                f"и {rows} {plural(rows, 'запись', 'записи', 'записей')}.",
                "muted",
            )
            return

        match = re.match(r"^DROP\s+DATABASE\s+(.+)$", command, re.I | re.S)
        if match:
            name, confirmed = self._parse_confirmation(match.group(1))
            if not confirmed:
                raise DBError(
                    f"Удаление базы «{name}» требует подтверждения.",
                    f"Все таблицы и данные будут потеряны. Введите: "
                    f"DROP DATABASE {name} CONFIRM.",
                )
            database = self.manager.drop_database(name)
            result.add(f"Удалила базу «{database.name}» вместе со всеми данными.", "success")
            if self.manager.current is None:
                result.add(
                    "Сейчас база не выбрана. Создайте новую или выберите "
                    "существующую: SHOW DATABASES.",
                    "muted",
                )
            return

        # --- таблицы -----------------------------------------------
        match = re.match(r"^CREATE\s+TABLE\s+([^\s(]+)\s*(.*)$", command, re.I | re.S)
        if match:
            self._create_table(match.group(1), match.group(2).strip(), result)
            return

        if upper in ("SHOW TABLES", "LIST TABLES"):
            self._show_tables(result)
            return

        match = re.match(r"^DESCRIBE\s+(\S+)\s*$", command, re.I)
        if match:
            self._describe(match.group(1), result)
            return

        match = re.match(
            r"^ALTER\s+TABLE\s+(\S+)\s+(ADD|DROP)\s+(.+)$",
            command,
            re.I | re.S,
        )
        if match:
            self._alter_table(
                match.group(1), match.group(2).upper(), match.group(3).strip(), result
            )
            return

        match = re.match(r"^DROP\s+TABLE\s+(.+)$", command, re.I | re.S)
        if match:
            name, confirmed = self._parse_confirmation(match.group(1))
            if not confirmed:
                raise DBError(
                    f"Удаление таблицы «{name}» требует подтверждения.",
                    f"Все записи будут потеряны. Введите: DROP TABLE {name} CONFIRM.",
                )
            table = self.manager.require_database().drop_table(name)
            result.add(
                f"Удалила таблицу «{table.name}» вместе с "
                f"{table.row_count} "
                f"{plural(table.row_count, 'записью', 'записями', 'записями')}.",
                "success",
            )
            return

        # --- данные ------------------------------------------------
        if upper.startswith("INSERT "):
            self._insert(command, result)
            return

        if upper.startswith("SELECT "):
            self._select(command, result)
            return

        if upper.startswith("UPDATE "):
            self._update(command, result)
            return

        if upper.startswith("DELETE "):
            self._delete(command, result)
            return

        raise DBError(
            f"Команда «{command}» не распознана.",
            "Введите HELP — список команд, или TUTORIAL — интерактивный урок.",
        )

    # ------------------------------------------------------------------
    # Базы данных и таблицы
    # ------------------------------------------------------------------
    def _show_databases(self, result: CommandResult) -> None:
        """Выводит список баз и отмечает текущую."""
        databases = self.manager.database_names()
        if not databases:
            result.add("Пока у меня нет ни одной базы — самое время создать первую.", "info")
            result.add("Например: CREATE DATABASE demo.", "muted")
            return
        result.add(f"Вот все базы, которые у меня есть ({len(databases)}):", "info")
        for database in databases:
            marker = "*" if database.name.lower() == self.manager.current else " "
            tables = len(database.tables)
            rows = database.row_count
            result.add(
                f" {marker} {database.name} — {tables} "
                f"{plural(tables, 'таблица', 'таблицы', 'таблиц')}, {rows} "
                f"{plural(rows, 'запись', 'записи', 'записей')}",
                "success" if marker == "*" else "info",
            )
        result.add(
            "Звёздочкой отмечена текущая база. Переключиться: USE <имя>.",
            "muted",
        )

    def _show_tables(self, result: CommandResult) -> None:
        """Выводит список таблиц текущей базы."""
        database = self.manager.require_database()
        tables = database.table_names()
        result.add(
            f"В базе «{database.name}» {len(tables)} "
            f"{plural(len(tables), 'таблица', 'таблицы', 'таблиц')}:",
            "info",
        )
        if not tables:
            result.add(
                "Таблиц пока нет — давайте создадим первую:",
                "muted",
            )
            result.add(
                "CREATE TABLE employees (name:string, age:int).",
                "code",
            )
            return
        for table in tables:
            fields = len(table.fields)
            rows = table.row_count
            result.add(
                f"  {table.name} — {fields} "
                f"{plural(fields, 'поле', 'поля', 'полей')}, {rows} "
                f"{plural(rows, 'запись', 'записи', 'записей')}",
                "success",
            )
        result.add("Посмотреть устройство таблицы: DESCRIBE <имя>.", "muted")

    def _create_table(
        self, name: str, rest: str, result: CommandResult
    ) -> None:
        """Разбирает список полей и создаёт таблицу."""
        database = self.manager.require_database()
        content, position = extract_parenthesized(rest, 0)
        tail = rest[position:].strip()
        if tail:
            raise DBError(
                f"Лишний текст после определения таблицы: «{tail}».",
                "Формат: CREATE TABLE имя (поле:тип, поле:тип).",
            )
        definitions: list[tuple[str, str]] = []
        for item in split_top_level(content):
            if not item:
                raise DBError(
                    "Пустое определение поля в списке.",
                    "Уберите лишнюю запятую: (name:string, age:int).",
                )
            if ":" not in item:
                raise DBError(
                    f"В определении поля «{item}» не указан тип.",
                    "Используйте формат имя:тип, например age:int.",
                )
            field_name, type_name = item.split(":", 1)
            definitions.append((field_name.strip(), type_name.strip()))
        table = database.create_table(name, definitions)
        fields = ", ".join(field.label for field in table.fields)
        result.add(
            f"Готово! Таблица «{table.name}» создана в базе «{database.name}».",
            "success",
        )
        result.add("Вот её поля: " + fields, "muted")
        result.add(
            f"Теперь можно добавлять записи: INSERT INTO {table.name} ...",
            "muted",
        )

    def _describe(self, name: str, result: CommandResult) -> None:
        """Показывает поля, типы и размер таблицы."""
        table = self.manager.require_database().table(name)
        fields = len(table.fields)
        rows_count = table.row_count
        result.add(
            f"Вот как устроена таблица «{table.name}»: {fields} "
            f"{plural(fields, 'поле', 'поля', 'полей')}, {rows_count} "
            f"{plural(rows_count, 'запись', 'записи', 'записей')}.",
            "info",
        )
        rows = [["id", "int", "автоматически"]]
        for field in table.fields:
            rows.append([field.name, field.type, ""])
        for line in render_matrix(["поле", "тип", "примечание"], rows):
            result.add(line, "table")
        result.add(
            f"Если нужно, измените структуру: ALTER TABLE {table.name} ADD|DROP ...",
            "muted",
        )

    def _alter_table(
        self, table_name: str, action: str, payload: str, result: CommandResult
    ) -> None:
        """Добавляет или удаляет поле таблицы."""
        table = self.manager.require_database().table(table_name)
        if action == "ADD":
            if ":" not in payload:
                raise DBError(
                    f"В определении поля «{payload}» не указан тип.",
                    "Формат: ALTER TABLE employees ADD email:string.",
                )
            field_name, type_name = payload.split(":", 1)
            field = table.add_field(field_name.strip(), type_name.strip())
            result.add(
                f"Добавила поле «{field.name}:{field.type}» в таблицу "
                f"«{table.name}».",
                "success",
            )
            if table.row_count:
                result.add(
                    "В старых записях новое поле пока показано как «—». "
                    "Заполнить его: UPDATE ... WHERE id = ...",
                    "muted",
                )
        else:
            field = table.drop_field(payload)
            result.add(
                f"Убрала поле «{field.name}» из таблицы «{table.name}».",
                "success",
            )

    # ------------------------------------------------------------------
    # Работа с данными
    # ------------------------------------------------------------------
    def _insert(self, command: str, result: CommandResult) -> None:
        """Разбирает INSERT, проверяет значения и добавляет запись."""
        match = re.match(r"^INSERT\s+INTO\s+([^\s(]+)\s*(.*)$", command, re.I | re.S)
        if not match:
            raise DBError(
                "Не удалось разобрать команду INSERT.",
                "Пример: INSERT INTO employees (name, age) VALUES ('Иван', 30).",
            )
        table = self.manager.require_database().table(match.group(1))
        rest = match.group(2).strip()
        if not rest:
            raise DBError(
                "Не указаны значения для новой записи.",
                f"Пример: INSERT INTO {table.name} (поле, ...) VALUES (значение, ...).",
            )

        if rest.upper().startswith("VALUES"):
            values_text = rest[6:].strip()
            content, position = extract_parenthesized(values_text, 0)
            self._ensure_end(values_text, position, "VALUES")
            values = [parse_literal(item) for item in split_top_level(content)]
            if len(values) != len(table.fields):
                raise DBError(
                    f"Количество значений ({len(values)}) не совпадает с "
                    f"количеством полей ({len(table.fields)}).",
                    "Перечислите поля явно: INSERT INTO "
                    f"{table.name} (поле, ...) VALUES (значение, ...).",
                )
            pairs = [
                (field.name, value) for field, value in zip(table.fields, values)
            ]
        else:
            content, position = extract_parenthesized(rest, 0)
            fields = [parse_literal(item) for item in split_top_level(content)]
            tail = rest[position:].strip()
            if not tail.upper().startswith("VALUES"):
                raise DBError(
                    "После списка полей ожидается слово VALUES.",
                    "Пример: INSERT INTO employees (name, age) VALUES ('Иван', 30).",
                )
            values_text = tail[6:].strip()
            values_content, values_position = extract_parenthesized(values_text, 0)
            self._ensure_end(values_text, values_position, "VALUES")
            values = [
                parse_literal(item) for item in split_top_level(values_content)
            ]
            if len(fields) != len(values):
                raise DBError(
                    f"Полей указано {len(fields)}, а значений — {len(values)}.",
                    "Количество полей и значений должно совпадать.",
                )
            pairs = list(zip(fields, values))

        row_id = table.insert(pairs)
        result.add(
            f"Записал! Новая запись в «{table.name}» получила id = {row_id}.",
            "success",
        )
        result.add(
            f"Проверить: SELECT * FROM {table.name}. "
            f"Изменить: UPDATE {table.name} SET ... WHERE id = {row_id}.",
            "muted",
        )

    def _select(self, command: str, result: CommandResult) -> None:
        """Показывает все записи или одну запись по id."""
        match = re.match(
            r"^SELECT\s+\*\s+FROM\s+(\S+)"
            r"(?:\s+WHERE\s+ID\s*=\s*(\d+))?\s*$",
            command,
            re.I,
        )
        if not match:
            # Дополнительный короткий формат: SELECT employees
            match = re.match(r"^SELECT\s+(\S+)\s*$", command, re.I)
            if not match:
                raise DBError(
                    "Не удалось разобрать команду SELECT.",
                    "Пример: SELECT * FROM employees "
                    "или SELECT * FROM employees WHERE id = 1.",
                )
        table = self.manager.require_database().table(match.group(1))
        if match.lastindex and match.lastindex >= 2 and match.group(2):
            row_id = int(match.group(2))
            row = table.get_row(row_id)
            rows = [(row_id, row)]
            caption = f"Нашла запись id = {row_id} в таблице «{table.name}»:"
        else:
            rows = table.snapshot()
            rows_count = table.row_count
            caption = (
                f"В таблице «{table.name}» {rows_count} "
                f"{plural(rows_count, 'запись', 'записи', 'записей')}:"
            )

        result.add(caption, "info")
        for line in render_table(table, rows):
            result.add(line, "table")
        if not rows:
            result.add(
                "Таблица пуста. Давайте добавим первую запись: INSERT INTO "
                f"{table.name} ...",
                "muted",
            )

    def _update(self, command: str, result: CommandResult) -> None:
        """Меняет указанные поля записи по id."""
        match = re.match(r"^UPDATE\s+(\S+)\s+(.+)$", command, re.I | re.S)
        if not match:
            raise DBError(
                "Не удалось разобрать команду UPDATE.",
                "Пример: UPDATE employees SET salary = 60000 WHERE id = 1.",
            )
        table = self.manager.require_database().table(match.group(1))
        rest = match.group(2).strip()

        set_position = find_keyword(rest, "SET")
        where_position = find_keyword(rest, "WHERE")
        if set_position != 0:
            raise DBError(
                "После имени таблицы ожидается слово SET.",
                "Пример: UPDATE employees SET salary = 60000 WHERE id = 1.",
            )
        if where_position < 0:
            raise DBError(
                "Не указано условие WHERE id = ...",
                "Изменение выполняется только по идентификатору записи. "
                "Пример: UPDATE employees SET salary = 60000 WHERE id = 1.",
            )
        if where_position < set_position:
            raise DBError(
                "Неверный порядок SET и WHERE.",
                "Сначала SET, затем WHERE: UPDATE employees SET salary = 60000 "
                "WHERE id = 1.",
            )

        assignments_text = rest[set_position + 3 : where_position].strip()
        where_text = rest[where_position + 5 :].strip()
        where_match = re.match(r"^ID\s*=\s*(\d+)$", where_text, re.I)
        if not where_match:
            raise DBError(
                f"Условие «{where_text}» не поддерживается.",
                "Изменять можно только запись по id: WHERE id = 1.",
            )
        if not assignments_text:
            raise DBError(
                "Не указаны поля для изменения.",
                "Пример: UPDATE employees SET salary = 60000 WHERE id = 1.",
            )

        pairs: list[tuple[str, str]] = []
        for item in split_top_level(assignments_text):
            name, raw_value = split_assignment(item)
            pairs.append((name, parse_literal(raw_value)))

        row_id = int(where_match.group(1))
        changed = table.update(row_id, pairs)
        description = ", ".join(
            f"{name} = {format_value(value)}" for name, value in changed.items()
        )
        result.add(
            f"Готово! Обновила запись id = {row_id} в таблице «{table.name}»: "
            f"{description}.",
            "success",
        )
        result.add(
            f"Проверить: SELECT * FROM {table.name} WHERE id = {row_id}.",
            "muted",
        )

    def _delete(self, command: str, result: CommandResult) -> None:
        """Удаляет запись по id."""
        match = re.match(
            r"^DELETE\s+FROM\s+(\S+)\s+WHERE\s+ID\s*=\s*(\d+)\s*$",
            command,
            re.I,
        )
        if not match:
            raise DBError(
                "Не удалось разобрать команду DELETE.",
                "Пример: DELETE FROM employees WHERE id = 1.",
            )
        table = self.manager.require_database().table(match.group(1))
        row_id = int(match.group(2))
        row = table.delete(row_id)
        preview = ", ".join(
            f"{field.name} = {format_value(row.get(field.name))}"
            for field in table.fields[:3]
        )
        result.add(
            f"Удалила запись id = {row_id} из таблицы «{table.name}».",
            "success",
        )
        if preview:
            result.add("Вот что было в записи: " + preview + ".", "muted")
        rows_left = table.row_count
        result.add(
            f"Осталось {rows_left} "
            f"{plural(rows_left, 'запись', 'записи', 'записей')}.",
            "muted",
        )

    # ------------------------------------------------------------------
    # Служебные команды
    # ------------------------------------------------------------------
    def _tutorial(self, command: str, result: CommandResult) -> None:
        """Запускает, останавливает и перезапускает урок."""
        parts = command.split(None, 1)
        action = parts[1].strip().upper() if len(parts) > 1 else ""

        if not action:
            if self.tutorial.active:
                result.extend(self.tutorial.status())
                result.prefill = self.tutorial.steps[self.tutorial.index].example
            else:
                lines, prefill = self.tutorial.start()
                result.extend(lines)
                result.prefill = prefill
            return

        if action in ("STOP", "СТОП"):
            if not self.tutorial.active:
                result.add("Интерактивный урок и так не запущен.", "warn")
                result.add("Начать обучение: TUTORIAL.", "muted")
            else:
                result.extend(self.tutorial.stop())
            return

        if action in ("RESTART", "RESET", "ЗАНОВО"):
            lines, prefill = self.tutorial.restart()
            result.extend(lines)
            result.prefill = prefill
            return

        raise DBError(
            f"Неизвестная команда обучения «{parts[1].strip()}».",
            "Доступно: TUTORIAL, TUTORIAL STOP, TUTORIAL RESTART.",
        )

    def _demo(self, result: CommandResult) -> None:
        """Создаёт демонстрационную базу для быстрого показа возможностей."""
        if "demo" in self.manager.databases:
            database = self.manager.databases["demo"]
            self.manager.use(database.name)
        else:
            database = self.manager.create_database("demo")
            self.manager.use(database.name)

        if "registry" not in database.tables:
            table = database.create_table(
                "registry",
                [
                    ("full_name", "string"),
                    ("department", "string"),
                    ("position", "string"),
                    ("salary", "float"),
                    ("active", "bool"),
                ],
            )
            if table.row_count == 0:
                samples = [
                    (
                        "Иванов Иван Иванович",
                        "Администрация",
                        "Специалист",
                        "55000.50",
                        "true",
                    ),
                    (
                        "Петрова Анна Сергеевна",
                        "Финансовый отдел",
                        "Бухгалтер",
                        "62000",
                        "true",
                    ),
                    (
                        "Сидоров Павел Олегович",
                        "Архив",
                        "Делопроизводитель",
                        "41000",
                        "false",
                    ),
                ]
                for full_name, department, position, salary, active in samples:
                    table.insert(
                        [
                            ("full_name", full_name),
                            ("department", department),
                            ("position", position),
                            ("salary", salary),
                            ("active", active),
                        ]
                    )
        else:
            table = database.tables["registry"]

        result.add(
            f"Смотрите, что я приготовила: база «{database.name}», "
            f"таблица «{table.name}», "
            f"{table.row_count} "
            f"{plural(table.row_count, 'запись', 'записи', 'записей')}.",
            "success",
        )
        result.add(
            "Это пример реестра сотрудников. Посмотрите структуру: "
            "DESCRIBE registry.",
            "muted",
        )
        for line in render_table(table, table.snapshot()):
            result.add(line, "table")

    def _status(self, result: CommandResult) -> None:
        """Показывает текущую базу и количество данных."""
        database = self.manager.current_database()
        if database is None:
            result.add("Сейчас у нас нет выбранной базы.", "warn")
            result.add("Посмотреть список: SHOW DATABASES.", "muted")
        else:
            tables = len(database.tables)
            rows = database.row_count
            result.add(
                f"Сейчас работаем с базой «{database.name}»: {tables} "
                f"{plural(tables, 'таблица', 'таблицы', 'таблиц')} и {rows} "
                f"{plural(rows, 'запись', 'записи', 'записей')}.",
                "info",
            )
            for table in database.table_names():
                fields = len(table.fields)
                result.add(
                    f"  {table.name}: {fields} "
                    f"{plural(fields, 'поле', 'поля', 'полей')}, "
                    f"{table.row_count} "
                    f"{plural(table.row_count, 'запись', 'записи', 'записей')}",
                    "muted",
                )
        result.add(
            "Обучение: "
            + ("идёт прямо сейчас" if self.tutorial.active else "не запущено")
            + ".",
            "muted",
        )

    def _hello(self, result: CommandResult) -> None:
        """Здоровается и предлагает, с чего начать."""
        result.add(f"{greeting()}! Я РЕЕСТР — ваша мини-СУБД.", "banner")
        result.add(
            "Помогу создать базу данных, таблицу и записи. Всё храню только "
            "в оперативной памяти.",
            "info",
        )
        result.add("С чего начнём?", "tutorial")
        result.add("  TUTORIAL — проведу урок из 13 шагов", "code")
        result.add("  DEMO — покажу готовый пример", "code")
        result.add("  HELP — расскажу, что умею", "code")

    def _about(self, result: CommandResult) -> None:
        """Выводит краткие сведения о программе."""
        result.add("Привет! Я РЕЕСТР — учебная мини-СУБД.", "banner")
        result.add(
            "Версия 1.0. Работаю на Python и tkinter, без сторонних библиотек.",
            "info",
        )
        result.add(
            "Все данные храню только в оперативной памяти: при закрытии они "
            "исчезают. Так требует задание.",
            "muted",
        )
        result.add(
            "Умею создавать базы, таблицы и записи, проверяю типы и "
            "подсказываю, если что-то пошло не так.",
            "muted",
        )

    # ------------------------------------------------------------------
    # Справка
    # ------------------------------------------------------------------
    def _help(self, topic: str, result: CommandResult) -> None:
        """Добавляет в вывод готовый текст справки."""
        result.extend(build_help(topic))

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_confirmation(rest: str) -> tuple[str, bool]:
        """Проверяет наличие слова CONFIRM в конце команды."""
        parts = rest.rsplit(None, 1)
        if len(parts) == 2 and parts[1].upper() == "CONFIRM":
            return parts[0].strip(), True
        return rest.strip(), False

    @staticmethod
    def _ensure_end(text: str, position: int, block: str) -> None:
        """Проверяет, что после скобок не осталось лишнего текста."""
        tail = text[position:].strip()
        if tail:
            raise DBError(
                f"Лишний текст после {block}: «{tail}».",
                "Проверьте количество скобок и запятых в команде.",
            )
