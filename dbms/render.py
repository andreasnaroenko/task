"""Отрисовка данных в виде таблиц из символов.

Модуль отвечает только за внешний вид. Логика команд и хранение данных
находятся в других модулях.
"""

from __future__ import annotations

from .models import Table, format_value

MAX_CELL = 36


def render_table(
    table: Table,
    rows: list[tuple[int, dict[str, object]]],
) -> list[str]:
    """Строки псевдографической таблицы с колонкой id."""
    headers = ["id"] + [f"{field.name} ({field.type})" for field in table.fields]
    data = [
        [str(row_id)] + [format_value(row.get(field.name)) for field in table.fields]
        for row_id, row in rows
    ]
    return render_matrix(headers, data)


def render_matrix(headers: list[str], rows: list[list[str]]) -> list[str]:
    """Рисует таблицу с выравниванием колонок.

    Значения длиннее MAX_CELL символов сокращаются, но в памяти остаются
    полностью.
    """
    clipped_headers = [_clip(item) for item in headers]
    clipped_rows = [[_clip(cell) for cell in row] for row in rows]

    widths = [len(item) for item in clipped_headers]
    for row in clipped_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    border = "+" + "+".join("-" * (width + 2) for width in widths) + "+"

    def make_line(cells: list[str]) -> str:
        parts = [
            " " + cell.ljust(widths[index]) + " "
            for index, cell in enumerate(cells)
        ]
        return "|" + "|".join(parts) + "|"

    lines = [border, make_line(clipped_headers), border]
    lines.extend(make_line(row) for row in clipped_rows)
    lines.append(border)
    return lines


def _clip(text: str) -> str:
    text = str(text)
    if len(text) <= MAX_CELL:
        return text
    return text[: MAX_CELL - 1] + "…"
