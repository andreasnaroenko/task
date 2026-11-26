"""Запуск приложения без окна консоли (двойной щелчок по файлу)."""

import sys

from dbms.gui import run


if __name__ == "__main__":
    run(sys.argv[1:])
