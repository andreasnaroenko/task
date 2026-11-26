"""Результат выполнения команды для GUI-терминала."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CommandResult:
    """Набор строк с типами оформления и служебные флаги.

    kinds:
        info, success, error, hint, muted, code, table, tutorial, banner
    """

    lines: list[tuple[str, str]] = field(default_factory=list)
    prefill: str | None = None
    clear_requested: bool = False
    exit_requested: bool = False

    def add(self, text: str, kind: str = "info") -> "CommandResult":
        """Добавляет одну строку вывода."""
        self.lines.append((kind, text))
        return self

    def extend(self, lines: list[tuple[str, str]]) -> "CommandResult":
        self.lines.extend(lines)
        return self

    @property
    def has_errors(self) -> bool:
        return any(kind == "error" for kind, _ in self.lines)
