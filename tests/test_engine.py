"""Автоматические тесты модели, парсера и команд терминала.

Запуск:
    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest

from dbms.engine import Engine


class EngineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = Engine()

    # ------------------------------------------------------------------
    # Вспомогательные методы
    # ------------------------------------------------------------------
    def run_ok(self, command: str):
        result = self.engine.execute(command)
        self.assertFalse(result.has_errors, msg=self.text(result))
        return result

    def run_error(self, command: str):
        result = self.engine.execute(command)
        self.assertTrue(result.has_errors, msg="Ожидалась ошибка: " + command)
        return result

    @staticmethod
    def text(result) -> str:
        return "\n".join(line for _, line in result.lines)

    def prepare_table(self) -> None:
        self.run_ok("CREATE DATABASE demo")
        self.run_ok(
            "CREATE TABLE employees "
            "(name:string, age:int, salary:float, active:bool)"
        )

    def insert_ivan(self) -> None:
        self.run_ok(
            "INSERT INTO employees (name, age, salary, active) "
            "VALUES ('Иван Петров', 30, 55000.50, true)"
        )

    # ------------------------------------------------------------------
    # Базы данных
    # ------------------------------------------------------------------
    def test_database_create_show_use(self) -> None:
        result = self.run_ok("CREATE DATABASE demo")
        self.assertIn("создана", self.text(result))
        self.run_ok("CREATE DATABASE test")
        self.run_ok("USE demo")
        self.assertEqual(self.engine.manager.current, "demo")
        shown = self.text(self.run_ok("SHOW DATABASES"))
        self.assertIn("demo", shown)
        self.assertIn("test", shown)

    def test_database_duplicate_case_insensitive(self) -> None:
        self.run_ok("CREATE DATABASE Demo")
        result = self.run_error("CREATE DATABASE demo")
        self.assertIn("уже существует", self.text(result))

    def test_database_not_found(self) -> None:
        result = self.run_error("USE missing")
        self.assertIn("не найдена", self.text(result))
        self.assertIn("Решение:", self.text(result))

    def test_database_name_validation(self) -> None:
        self.run_error("CREATE DATABASE 1bad")
        self.run_error("CREATE DATABASE bad-name")
        self.run_error("CREATE DATABASE " + "x" * 40)

    def test_drop_database_requires_confirm(self) -> None:
        self.run_ok("CREATE DATABASE demo")
        result = self.run_error("DROP DATABASE demo")
        self.assertIn("CONFIRM", self.text(result))
        self.run_ok("DROP DATABASE demo CONFIRM")
        self.assertIsNone(self.engine.manager.current)

    # ------------------------------------------------------------------
    # Таблицы и поля
    # ------------------------------------------------------------------
    def test_table_create_describe(self) -> None:
        self.prepare_table()
        result = self.run_ok("DESCRIBE employees")
        text = self.text(result)
        for field in ("name", "age", "salary", "active"):
            self.assertIn(field, text)
        self.assertIn("автоматически", text)

    def test_table_requires_database(self) -> None:
        result = self.run_error("CREATE TABLE t (name:string)")
        self.assertIn("выберите базу", self.text(result))

    def test_duplicate_table(self) -> None:
        self.prepare_table()
        result = self.run_error("CREATE TABLE Employees (name:string)")
        self.assertIn("уже существует", self.text(result))

    def test_duplicate_field(self) -> None:
        self.prepare_table()
        result = self.run_error("ALTER TABLE employees ADD Name:string")
        self.assertIn("уже существует", self.text(result))

    def test_reserved_id_field(self) -> None:
        self.run_ok("CREATE DATABASE demo")
        result = self.run_error("CREATE TABLE t (id:int, name:string)")
        self.assertIn("зарезервировано", self.text(result))
        # Таблица не должна создаваться частично.
        self.assertNotIn("t", self.engine.manager.databases["demo"].tables)

    def test_invalid_type(self) -> None:
        self.run_ok("CREATE DATABASE demo")
        result = self.run_error("CREATE TABLE t (name:text)")
        self.assertIn("Неизвестный тип", self.text(result))

    def test_alter_add_and_drop_field(self) -> None:
        self.prepare_table()
        self.insert_ivan()
        self.run_ok("ALTER TABLE employees ADD email:string")
        text = self.text(self.run_ok("SELECT * FROM employees"))
        self.assertIn("—", text)  # у старой записи новое поле не заполнено
        self.run_ok(
            "UPDATE employees SET email = 'ivan@example.ru' WHERE id = 1"
        )
        self.assertIn(
            "ivan@example.ru",
            self.text(self.run_ok("SELECT * FROM employees")),
        )
        self.run_ok("ALTER TABLE employees DROP email")
        self.assertNotIn(
            "email", self.text(self.run_ok("DESCRIBE employees"))
        )

    def test_cannot_drop_last_field(self) -> None:
        self.run_ok("CREATE DATABASE demo")
        self.run_ok("CREATE TABLE t (name:string)")
        result = self.run_error("ALTER TABLE t DROP name")
        self.assertIn("последнее поле", self.text(result))

    def test_create_table_without_space_before_parenthesis(self) -> None:
        self.run_ok("CREATE DATABASE demo")
        self.run_ok("CREATE TABLE t(name:string, age:int)")
        self.run_ok("INSERT INTO t(name, age) VALUES ('Иван', 20)")
        self.assertIn(
            "Иван",
            self.text(self.run_ok("SELECT * FROM t")),
        )

    def test_drop_table_requires_confirm(self) -> None:
        self.prepare_table()
        self.run_error("DROP TABLE employees")
        self.run_ok("DROP TABLE employees CONFIRM")
        self.assertIn(
            "Таблиц пока нет",
            self.text(self.run_ok("SHOW TABLES")),
        )

    # ------------------------------------------------------------------
    # Записи и типы данных
    # ------------------------------------------------------------------
    def test_insert_select(self) -> None:
        self.prepare_table()
        self.insert_ivan()
        text = self.text(self.run_ok("SELECT * FROM employees"))
        self.assertIn("Иван Петров", text)
        self.assertIn("55000.5", text)

    def test_insert_values_without_columns(self) -> None:
        self.prepare_table()
        self.run_ok(
            "INSERT INTO employees VALUES ('Анна Смирнова', 27, 62000, false)"
        )
        self.assertIn(
            "Анна Смирнова",
            self.text(self.run_ok("SELECT * FROM employees")),
        )

    def test_string_with_comma_and_quotes(self) -> None:
        self.prepare_table()
        self.run_ok(
            "INSERT INTO employees (name, age, salary, active) "
            "VALUES ('Иванов, Иван', 30, 1.5, true)"
        )
        text = self.text(self.run_ok("SELECT * FROM employees"))
        self.assertIn("Иванов, Иван", text)

    def test_duplicate_column_in_insert(self) -> None:
        self.prepare_table()
        result = self.run_error(
            "INSERT INTO employees (name, name, age, salary, active) "
            "VALUES ('a', 'b', 1, 2, true)"
        )
        self.assertIn("дважды", self.text(result))

    def test_unknown_field_in_insert(self) -> None:
        self.prepare_table()
        result = self.run_error(
            "INSERT INTO employees (name, age, salary, active, x) "
            "VALUES ('a', 1, 2, true, 3)"
        )
        self.assertIn("нет поля", self.text(result))

    def test_missing_fields(self) -> None:
        self.prepare_table()
        result = self.run_error(
            "INSERT INTO employees (name) VALUES ('Иван')"
        )
        self.assertIn("Не заполнены поля", self.text(result))

    def test_type_validation(self) -> None:
        self.prepare_table()
        cases = [
            (
                "INSERT INTO employees (name, age, salary, active) "
                "VALUES ('a', 1.5, 2, true)"
            ),
            (
                "INSERT INTO employees (name, age, salary, active) "
                "VALUES ('a', 1, 'много', true)"
            ),
            (
                "INSERT INTO employees (name, age, salary, active) "
                "VALUES ('a', 1, 2, может быть)"
            ),
        ]
        for command in cases:
            with self.subTest(command=command):
                self.run_error(command)
        self.assertIn(
            "Таблица пуста",
            self.text(self.run_ok("SELECT * FROM employees")),
        )

    def test_bool_variants(self) -> None:
        self.prepare_table()
        for value in ("true", "1", "да", "yes", "false", "0", "нет"):
            with self.subTest(value=value):
                self.run_ok(
                    "INSERT INTO employees (name, age, salary, active) "
                    f"VALUES ('a', 1, 1, {value})"
                )
        self.assertEqual(
            self.engine.manager.databases["demo"].tables["employees"].row_count,
            7,
        )

    def test_update_by_id(self) -> None:
        self.prepare_table()
        self.insert_ivan()
        self.run_ok(
            "UPDATE employees SET age = 31, active = false WHERE id = 1"
        )
        text = self.text(self.run_ok("SELECT * FROM employees WHERE id = 1"))
        self.assertIn("31", text)
        self.assertIn("false", text)

    def test_update_requires_where(self) -> None:
        self.prepare_table()
        self.insert_ivan()
        result = self.run_error("UPDATE employees SET age = 31")
        self.assertIn("WHERE", self.text(result))

    def test_update_missing_record(self) -> None:
        self.prepare_table()
        result = self.run_error(
            "UPDATE employees SET age = 31 WHERE id = 99"
        )
        self.assertIn("не найдена", self.text(result))

    def test_delete(self) -> None:
        self.prepare_table()
        self.insert_ivan()
        self.run_ok(
            "INSERT INTO employees (name, age, salary, active) "
            "VALUES ('Анна', 27, 62000, false)"
        )
        self.run_ok("DELETE FROM employees WHERE id = 1")
        text = self.text(self.run_ok("SELECT * FROM employees"))
        self.assertNotIn("Иван Петров", text)
        self.assertIn("Анна", text)

    def test_delete_missing(self) -> None:
        self.prepare_table()
        result = self.run_error("DELETE FROM employees WHERE id = 5")
        self.assertIn("не найдена", self.text(result))

    def test_select_short_format(self) -> None:
        self.prepare_table()
        self.insert_ivan()
        self.assertIn(
            "Иван Петров",
            self.text(self.run_ok("SELECT employees")),
        )

    # ------------------------------------------------------------------
    # Стабильность и интерфейс
    # ------------------------------------------------------------------
    def test_unknown_command(self) -> None:
        result = self.run_error("DROP EVERYTHING")
        self.assertIn("не распознана", self.text(result))
        self.assertIn("HELP", self.text(result))

    def test_empty_command(self) -> None:
        result = self.engine.execute("   ")
        self.assertEqual(result.lines, [])

    def test_semicolon_is_ignored(self) -> None:
        self.run_ok("CREATE DATABASE demo;")
        self.assertEqual(self.engine.manager.current, "demo")

    def test_braces_errors_do_not_crash(self) -> None:
        self.run_error("CREATE TABLE t (name:string")
        self.run_error("INSERT INTO t (name) VALUES ('a'")
        self.run_error("INSERT INTO t (name) VALUES ('a\\')")

    def test_help_sections(self) -> None:
        for command in (
            "HELP",
            "HELP DB",
            "HELP TABLES",
            "HELP DATA",
            "HELP TYPES",
            "HELP ERRORS",
            "HELP TUTORIAL",
        ):
            with self.subTest(command=command):
                self.assertFalse(self.engine.execute(command).has_errors)
        self.run_error("HELP UNKNOWN")

    def test_status_and_demo(self) -> None:
        self.run_ok("DEMO")
        self.assertEqual(self.engine.manager.current, "demo")
        self.assertIn("registry", self.text(self.run_ok("SHOW TABLES")))
        self.assertIn("demo", self.text(self.run_ok("STATUS")))

    def test_human_phrases(self) -> None:
        hello = self.text(self.run_ok("ПРИВЕТ"))
        self.assertIn("РЕЕСТР", hello)
        self.assertIn("TUTORIAL", hello)
        self.assertIn("Пожалуйста", self.text(self.run_ok("СПАСИБО")))
        self.assertIn("отлично", self.text(self.run_ok("КАК ДЕЛА")))

    def test_status_uses_plural_forms(self) -> None:
        self.prepare_table()
        self.insert_ivan()
        text = self.text(self.run_ok("STATUS"))
        self.assertIn("1 таблица", text)
        self.assertIn("1 запись", text)

    def test_reset(self) -> None:
        self.prepare_table()
        self.engine.reset()
        self.assertIsNone(self.engine.manager.current)
        self.assertEqual(self.engine.manager.databases, {})

    # ------------------------------------------------------------------
    # Интерактивный урок
    # ------------------------------------------------------------------
    def test_tutorial_full_pass(self) -> None:
        result = self.engine.execute("TUTORIAL")
        self.assertTrue(self.engine.tutorial.active)
        self.assertEqual(result.prefill, "CREATE DATABASE tutorial_db")
        steps = [step.example for step in self.engine.tutorial.steps]

        # Сначала проходим шаги до удаления таблицы и проверяем данные.
        for command in steps[:-2]:
            result = self.engine.execute(command)
            self.assertFalse(result.has_errors, msg=self.text(result))
        table = self.engine.manager.databases["tutorial_db"].tables["employees"]
        self.assertEqual(table.row_count, 1)
        self.assertEqual(table.rows[1]["salary"], 60000.0)
        self.assertEqual(table.rows[1]["email"], "ivan@example.ru")

        # Последние два шага удаляют таблицу и базу.
        for command in steps[-2:]:
            result = self.engine.execute(command)
            self.assertFalse(result.has_errors, msg=self.text(result))
        self.assertFalse(self.engine.tutorial.active)
        self.assertNotIn("tutorial_db", self.engine.manager.databases)

    def test_tutorial_blocks_foreign_command(self) -> None:
        self.engine.execute("TUTORIAL")
        result = self.engine.execute("CREATE DATABASE another")
        self.assertTrue(result.has_errors is False)
        self.assertIn("ОБУЧЕНИЕ", self.text(result))
        self.assertNotIn("another", self.engine.manager.databases)

    def test_tutorial_stop_and_restart(self) -> None:
        self.engine.execute("TUTORIAL")
        self.engine.execute("TUTORIAL STOP")
        self.assertFalse(self.engine.tutorial.active)
        self.engine.execute("TUTORIAL")
        self.engine.execute("TUTORIAL RESTART")
        self.assertTrue(self.engine.tutorial.active)
        self.assertEqual(self.engine.tutorial.index, 0)

    def test_tutorial_allows_help(self) -> None:
        self.engine.execute("TUTORIAL")
        result = self.engine.execute("HELP")
        self.assertFalse(result.has_errors)
        self.assertIn("СПРАВКА", self.text(result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
