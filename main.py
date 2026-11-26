"""Точка входа приложения «РЕЕСТР».

Запуск:
    python main.py

Требования: Python 3.10+ с tkinter. Сторонние библиотеки не нужны.
"""

from __future__ import annotations

import sys

from dbms.gui import run


if __name__ == "__main__":
    run(sys.argv[1:])
