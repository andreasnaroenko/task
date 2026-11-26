"""Модель данных СУБД: поля, таблицы, базы данных и менеджер баз.

Архитектура:
    DatabaseManager -> Database -> Table -> Field
Каждый уровень отвечает за собственную валидацию и не зависит от GUI,
поэтому модель можно тестировать отдельно от интерфейса.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import DBError

# Поддерживаемые типы данных и их русские псевдонимы.
DATA_TYPES = ("string", "int", "float", "bool")
TYPE_ALIASES = {
    "string": "string",
    "str": "string",
    "строка": "string",
    "стр": "string",
    "int": "int",
    "integer": "int",
    "целое": "int",
    "целый": "int",
    "float": "float",
    "double": "float",
    "вещественное": "float",
    "дробное": "float",
    "bool": "bool",
    "boolean": "bool",
    "логическое": "bool",
    "булево": "bool",
}

NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*$")
INT_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(r"^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?$")

MAX_NAME_LENGTH = 32
MAX_FIELDS = 32


def validate_name(raw: str, kind: str = "имя") -> str:
    """Проверяет имя базы данных, таблицы или поля."""
    name = raw.strip()
    if not name:
        raise DBError(
            f"Пустое {kind}.",
            f"Укажите {kind}: буквы, цифры и символ подчёркивания.",
        )
    if len(name) > MAX_NAME_LENGTH:
        raise DBError(
            f"Слишком длинное {kind} «{name}» ({len(name)} символов).",
            f"Максимальная длина — {MAX_NAME_LENGTH} символов.",
        )
    if not NAME_RE.match(name):
        raise DBError(
            f"Недопустимое {kind} «{name}».",
            "Используйте латинские или русские буквы, цифры и «_»; "
            "имя должно начинаться с буквы или «_».",
        )
    return name


def normalize_type(raw: str) -> str:
    """Приводит название типа к одному из DATA_TYPES."""
    key = raw.strip().lower()
    key = TYPE_ALIASES.get(key, key)
    if key not in DATA_TYPES:
        raise DBError(
            f"Неизвестный тип данных «{raw.strip()}».",
            "Доступные типы: string (строка), int (целое), "
            "float (вещественное), bool (логическое).",
        )
    return key


def convert_value(raw: str, field: "Field") -> object:
    """Проверяет и преобразует введённое значение к типу поля.

    Строки сохраняются как есть, для остальных типов выполняется строгая
    проверка формата, чтобы исключить аварийное завершение программы.
    """
    text = raw.strip()

    if field.type == "string":
        return raw

    if field.type == "int":
        if not INT_RE.match(text):
            raise DBError(
                f"Поле «{field.name}» ожидает целое число (int), "
                f"получено «{raw}».",
                "Пример: 42 или -7. Дробная часть для int недопустима.",
            )
        return int(text, 10)

    if field.type == "float":
        if not FLOAT_RE.match(text):
            raise DBError(
                f"Поле «{field.name}» ожидает число (float), получено «{raw}».",
                "Пример: 55000.50 или 12,5. Можно использовать точку или запятую.",
            )
        return float(text.replace(",", "."))

    if field.type == "bool":
        lowered = text.lower()
        if lowered in ("true", "1", "да", "yes", "y", "истина"):
            return True
        if lowered in ("false", "0", "нет", "no", "n", "ложь"):
            return False
        raise DBError(
            f"Поле «{field.name}» ожидает логическое значение (bool), "
            f"получено «{raw}».",
            "Допустимо: true/false, 1/0, да/нет.",
        )

    # Сюда попасть можно только при повреждении модели.
    raise DBError(
        f"Неподдерживаемый тип поля «{field.type}».",
        "Пересоздайте таблицу с типами string, int, float или bool.",
    )


def format_value(value: object) -> str:
    """Готовит значение для вывода в таблице."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value == "":
        return "''"
    return str(value)


@dataclass
class Field:
    """Поле таблицы: имя и тип данных."""

    name: str
    type: str

    @property
    def label(self) -> str:
        return f"{self.name}:{self.type}"


class Table:
    """Таблица с автоматическим идентификатором записи.

    Идентификатор id создаётся системой, уникален в пределах таблицы и
    никогда не переиспользуется — это упрощает изменение и удаление
    записей по id.
    """

    def __init__(self, name: str) -> None:
        self.name = validate_name(name, "имя таблицы")
        self.fields: list[Field] = []
        self.rows: dict[int, dict[str, object]] = {}
        self._next_id = 1

    # ------------------------------------------------------------------
    # Структура таблицы
    # ------------------------------------------------------------------
    def field(self, name: str) -> Field:
        """Возвращает поле по имени без учёта регистра."""
        key = name.strip().lower()
        for item in self.fields:
            if item.name.lower() == key:
                return item
        raise DBError(
            f"В таблице «{self.name}» нет поля «{name.strip()}».",
            "Посмотрите структуру: DESCRIBE " + self.name + ".",
        )

    def add_field(self, name: str, type_name: str) -> Field:
        """Добавляет поле, проверяя уникальность и зарезервированное id."""
        field_name = validate_name(name, "имя поля")
        if field_name.lower() == "id":
            raise DBError(
                "Имя поля «id» зарезервировано системой.",
                "Идентификатор создаётся автоматически и не требует поля id.",
            )
        if any(item.name.lower() == field_name.lower() for item in self.fields):
            raise DBError(
                f"Поле «{field_name}» уже существует в таблице «{self.name}».",
                "Придумайте другое имя или посмотрите структуру: "
                f"DESCRIBE {self.name}.",
            )
        if len(self.fields) >= MAX_FIELDS:
            raise DBError(
                f"Достигнут лимит полей ({MAX_FIELDS}) в таблице «{self.name}».",
                "Удалите ненужное поле: ALTER TABLE ... DROP ...",
            )
        field = Field(field_name, normalize_type(type_name))
        self.fields.append(field)
        return field

    def drop_field(self, name: str) -> Field:
        """Удаляет поле и его значения из всех записей."""
        field = self.field(name)
        if len(self.fields) == 1:
            raise DBError(
                f"Нельзя удалить последнее поле таблицы «{self.name}».",
                "Сначала добавьте другое поле: ALTER TABLE ... ADD ...",
            )
        self.fields.remove(field)
        for row in self.rows.values():
            row.pop(field.name, None)
        return field

    # ------------------------------------------------------------------
    # Записи
    # ------------------------------------------------------------------
    def insert(self, pairs: list[tuple[str, str]]) -> int:
        """Добавляет запись.

        pairs — список пар (имя поля, значение). Список, а не словарь,
        нужен для обнаружения повторяющихся полей во вводе.
        """
        values: dict[str, object] = {}
        for name, raw_value in pairs:
            field = self.field(name)
            if field.name in values:
                raise DBError(
                    f"Поле «{field.name}» указано в команде дважды.",
                    "Перечислите каждое поле только один раз.",
                )
            values[field.name] = convert_value(raw_value, field)

        missing = [field.name for field in self.fields if field.name not in values]
        if missing:
            raise DBError(
                f"Не заполнены поля: {', '.join(missing)}.",
                "Укажите значения для всех полей таблицы. "
                f"Структура: DESCRIBE {self.name}.",
            )

        row_id = self._next_id
        self._next_id += 1
        self.rows[row_id] = values
        return row_id

    def get_row(self, row_id: int) -> dict[str, object]:
        """Возвращает запись по id или понятную ошибку."""
        if row_id not in self.rows:
            ids = ", ".join(str(item) for item in list(self.rows)[:10])
            if len(self.rows) > 10:
                ids += ", ..."
            hint = (
                f"Существующие id: {ids}. Посмотрите данные: "
                f"SELECT * FROM {self.name}."
                if ids
                else f"Таблица пуста. Добавьте запись: INSERT INTO {self.name} ..."
            )
            raise DBError(
                f"Запись с id={row_id} не найдена в таблице «{self.name}».",
                hint,
            )
        return self.rows[row_id]

    def update(self, row_id: int, pairs: list[tuple[str, str]]) -> dict[str, object]:
        """Изменяет отдельные поля записи по её идентификатору."""
        row = self.get_row(row_id)
        converted: dict[str, object] = {}
        for name, raw_value in pairs:
            field = self.field(name)
            if field.name in converted:
                raise DBError(
                    f"Поле «{field.name}» указано в команде дважды.",
                    "Перечислите каждое поле только один раз.",
                )
            converted[field.name] = convert_value(raw_value, field)
        if not converted:
            raise DBError(
                "Не указаны поля для изменения.",
                "Пример: UPDATE employees SET salary = 60000 WHERE id = 1.",
            )
        row.update(converted)
        return converted

    def delete(self, row_id: int) -> dict[str, object]:
        """Удаляет запись по id и возвращает её данные."""
        row = self.get_row(row_id)
        del self.rows[row_id]
        return row

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def snapshot(self) -> list[tuple[int, dict[str, object]]]:
        """Возвращает записи в порядке возрастания id."""
        return sorted(self.rows.items(), key=lambda item: item[0])


class Database:
    """Именованная база данных, содержащая таблицы."""

    def __init__(self, name: str) -> None:
        self.name = validate_name(name, "имя базы данных")
        self.tables: dict[str, Table] = {}

    def table(self, name: str) -> Table:
        """Возвращает таблицу по имени без учёта регистра."""
        key = name.strip().lower()
        if key in self.tables:
            return self.tables[key]
        raise DBError(
            f"В базе «{self.name}» нет таблицы «{name.strip()}».",
            "Посмотрите список таблиц: SHOW TABLES.",
        )

    def create_table(self, name: str, definitions: list[tuple[str, str]]) -> Table:
        """Атомарно создаёт таблицу: при ошибке в полях она не появится."""
        table_name = validate_name(name, "имя таблицы")
        if table_name.lower() in self.tables:
            raise DBError(
                f"Таблица «{table_name}» уже существует в базе «{self.name}».",
                "Придумайте другое имя или удалите её: "
                f"DROP TABLE {table_name} CONFIRM.",
            )
        if not definitions:
            raise DBError(
                "Не задано ни одного поля таблицы.",
                "Пример: CREATE TABLE employees (name:string, age:int).",
            )
        new_table = Table(table_name)
        for field_name, type_name in definitions:
            new_table.add_field(field_name, type_name)
        self.tables[table_name.lower()] = new_table
        return new_table

    def drop_table(self, name: str) -> Table:
        """Удаляет таблицу по имени."""
        table = self.table(name)
        del self.tables[table.name.lower()]
        return table

    def table_names(self) -> list[Table]:
        return sorted(self.tables.values(), key=lambda item: item.name.lower())

    @property
    def row_count(self) -> int:
        return sum(table.row_count for table in self.tables.values())


class DatabaseManager:
    """Хранилище всех баз данных и указатель на текущую базу."""

    def __init__(self) -> None:
        self.databases: dict[str, Database] = {}
        self.current: str | None = None

    def create_database(self, name: str) -> Database:
        """Создаёт базу с уникальным (без учёта регистра) именем."""
        db_name = validate_name(name, "имя базы данных")
        if db_name.lower() in self.databases:
            raise DBError(
                f"База данных «{db_name}» уже существует.",
                "Придумайте другое имя или выберите её: USE " + db_name + ".",
            )
        database = Database(db_name)
        self.databases[db_name.lower()] = database
        if self.current is None:
            self.current = db_name.lower()
        return database

    def drop_database(self, name: str) -> Database:
        """Удаляет базу и сбрасывает указатель, если она была текущей."""
        database = self.database(name)
        del self.databases[database.name.lower()]
        if self.current == database.name.lower():
            self.current = None
        return database

    def database(self, name: str) -> Database:
        """Возвращает базу по имени без учёта регистра."""
        key = name.strip().lower()
        if key in self.databases:
            return self.databases[key]
        raise DBError(
            f"База данных «{name.strip()}» не найдена.",
            "Посмотрите список: SHOW DATABASES, затем выберите: USE имя.",
        )

    def use(self, name: str) -> Database:
        """Делает базу текущей."""
        database = self.database(name)
        self.current = database.name.lower()
        return database

    def current_database(self) -> Database | None:
        if self.current is None:
            return None
        return self.databases.get(self.current)

    def require_database(self) -> Database:
        """Возвращает текущую базу или подсказывает, как её выбрать."""
        database = self.current_database()
        if database is None:
            raise DBError(
                "Сначала выберите базу данных.",
                "Создайте базу: CREATE DATABASE имя, затем USE имя. "
                "Список баз: SHOW DATABASES.",
            )
        return database

    def database_names(self) -> list[Database]:
        return sorted(self.databases.values(), key=lambda item: item.name.lower())

    def reset(self) -> None:
        """Полностью очищает оперативную память приложения."""
        self.databases.clear()
        self.current = None
