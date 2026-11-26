"""GUI-терминал приложения «РЕЕСТР».

Интерфейс оформлен как консоль: область вывода, строка ввода, история
команд и строка состояния. Используется только tkinter из стандартной
библиотеки Python.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from .engine import Engine
from .human import greeting

# --- палитра -----------------------------------------------------------
BG = "#070d19"
BG_PANEL = "#0d1729"
BG_INPUT = "#101d33"
BG_HOVER = "#172741"
BORDER = "#1e3352"
TEXT = "#dbe7f5"
MUTED = "#7f95b3"
ACCENT = "#38bdf8"
ACCENT_DARK = "#082f49"
GREEN = "#86efac"
RED = "#fca5a5"
YELLOW = "#fcd34d"
PURPLE = "#c4b5fd"
TABLE = "#cbd5e1"

FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI Semibold", 10)
FONT_TERM = ("Consolas", 10)
FONT_TERM_BOLD = ("Consolas", 10, "bold")
FONT_TERM_BIG = ("Consolas", 12, "bold")


class TerminalGUI:
    """Главное окно терминала."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.engine = Engine()
        self.history: list[str] = []
        self.history_index = 0

        self.root.title("РЕЕСТР — мини-СУБД · GUI Terminal")
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        width = max(860, min(1180, screen_width - 80))
        height = max(560, min(760, screen_height - 220))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(860, 560)
        self.root.configure(bg=BG)

        self._build_menu()
        self._build_header()
        self._build_output()
        self._build_input()
        self._build_status()
        self._print_banner()

        self.entry.focus_set()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root, tearoff=0)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Очистить экран\tCtrl+L", command=self._clear_screen)
        file_menu.add_command(label="Сбросить все данные", command=self._reset_data)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.on_close)
        menubar.add_cascade(label="Файл", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Интерактивный урок", command=lambda: self._run("TUTORIAL"))
        tools_menu.add_command(label="Демонстрационные данные", command=lambda: self._run("DEMO"))
        tools_menu.add_command(label="Состояние системы", command=lambda: self._run("STATUS"))
        menubar.add_cascade(label="Инструменты", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Все команды\tF1", command=lambda: self._run("HELP"))
        help_menu.add_command(label="Типы данных", command=lambda: self._run("HELP TYPES"))
        help_menu.add_command(label="Ошибки и решения", command=lambda: self._run("HELP ERRORS"))
        help_menu.add_separator()
        help_menu.add_command(label="О программе", command=self._about)
        menubar.add_cascade(label="Справка", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=BG, padx=20, pady=14)
        header.pack(fill="x")

        title_block = tk.Frame(header, bg=BG)
        title_block.pack(side="left")

        logo = tk.Frame(title_block, bg=BG)
        logo.pack(anchor="w")
        tk.Label(
            logo,
            text="РЕЕСТР",
            bg=BG,
            fg=ACCENT,
            font=("Segoe UI Semibold", 20),
        ).pack(side="left")
        tk.Label(
            logo,
            text="  мини-СУБД",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 11),
        ).pack(side="left", pady=(6, 0))
        tk.Label(
            title_block,
            text="Ваш помощник для небольших баз данных · всё хранится только в памяти",
            bg=BG,
            fg=MUTED,
            font=FONT_UI,
        ).pack(anchor="w", pady=(2, 0))

        buttons = tk.Frame(header, bg=BG)
        buttons.pack(side="right")
        self._header_button(buttons, "Обучение", lambda: self._run("TUTORIAL")).pack(
            side="left", padx=4
        )
        self._header_button(buttons, "Команды", lambda: self._run("HELP")).pack(
            side="left", padx=4
        )
        self._header_button(buttons, "Демо", lambda: self._run("DEMO")).pack(
            side="left", padx=4
        )
        self._header_button(buttons, "Очистить", self._clear_screen).pack(
            side="left", padx=4
        )

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

    def _header_button(self, parent: tk.Widget, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=BG_PANEL,
            fg=TEXT,
            activebackground=BG_HOVER,
            activeforeground=ACCENT,
            font=FONT_UI,
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
        )

    def _build_output(self) -> None:
        frame = tk.Frame(self.root, bg=BG, padx=16, pady=12)
        frame.pack(fill="both", expand=True)

        panel = tk.Frame(frame, bg=BG_PANEL, highlightthickness=1, highlightbackground=BORDER)
        panel.pack(fill="both", expand=True)
        panel.grid_rowconfigure(0, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        self.text = tk.Text(
            panel,
            bg=BG_PANEL,
            fg=TEXT,
            insertbackground=ACCENT,
            selectbackground="#1d4ed8",
            selectforeground="#ffffff",
            font=FONT_TERM,
            relief="flat",
            bd=0,
            padx=16,
            pady=14,
            wrap="none",
            state="disabled",
            cursor="arrow",
            spacing1=1,
            spacing3=1,
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        vbar = tk.Scrollbar(
            panel,
            orient="vertical",
            command=self.text.yview,
            bg=BG_PANEL,
            troughcolor=BG_PANEL,
            activebackground=ACCENT,
            bd=0,
            highlightthickness=0,
            width=12,
        )
        vbar.grid(row=0, column=1, sticky="ns")
        self.text.configure(yscrollcommand=vbar.set)

        hbar = tk.Scrollbar(
            panel,
            orient="horizontal",
            command=self.text.xview,
            bg=BG_PANEL,
            troughcolor=BG_PANEL,
            activebackground=ACCENT,
            bd=0,
            highlightthickness=0,
        )
        hbar.grid(row=1, column=0, sticky="ew")
        self.text.configure(xscrollcommand=hbar.set)

        self.text.tag_configure("banner", foreground=ACCENT, font=FONT_TERM_BIG)
        self.text.tag_configure("tutorial", foreground=PURPLE, font=FONT_TERM_BOLD)
        self.text.tag_configure("info", foreground=TEXT)
        self.text.tag_configure("success", foreground=GREEN)
        self.text.tag_configure("error", foreground=RED)
        self.text.tag_configure("hint", foreground=YELLOW)
        self.text.tag_configure("muted", foreground=MUTED)
        self.text.tag_configure("code", foreground="#93c5fd")
        self.text.tag_configure("table", foreground=TABLE)
        self.text.tag_configure("prompt", foreground=ACCENT, font=FONT_TERM_BOLD)
        self.text.tag_configure("warn", foreground=YELLOW, font=FONT_TERM_BOLD)

        # Контекстное меню для копирования вывода.
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Копировать", command=self._copy_selection)
        self.context_menu.add_command(label="Выделить всё", command=self._select_all)
        self.text.bind("<Button-3>", self._show_context_menu)

    def _build_input(self) -> None:
        wrapper = tk.Frame(self.root, bg=BG, padx=16, pady=0)
        wrapper.pack(fill="x")

        panel = tk.Frame(
            wrapper,
            bg=BG_INPUT,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        panel.pack(fill="x")

        prompt = tk.Label(
            panel,
            text="❯",
            bg=BG_INPUT,
            fg=ACCENT,
            font=("Consolas", 16, "bold"),
            padx=12,
        )
        prompt.pack(side="left")

        self.entry = tk.Entry(
            panel,
            bg=BG_INPUT,
            fg=TEXT,
            insertbackground=ACCENT,
            font=("Consolas", 12),
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=9)
        self.entry.bind("<Return>", self.submit)
        self.entry.bind("<Up>", self._history_up)
        self.entry.bind("<Down>", self._history_down)
        self.entry.bind("<Tab>", self._complete)
        self.entry.bind("<Control-l>", lambda event: self._clear_screen())

        run_button = tk.Button(
            panel,
            text="Выполнить  ⏎",
            command=self.submit,
            bg=ACCENT,
            fg=ACCENT_DARK,
            activebackground="#7dd3fc",
            activeforeground=ACCENT_DARK,
            font=FONT_UI_BOLD,
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
        )
        run_button.pack(side="right", padx=6, pady=6)

        hint = tk.Label(
            wrapper,
            text=(
                "Enter — выполнить   ·   ↑ ↓ — история   ·   "
                "Tab — автодополнение   ·   F1 — помощь"
            ),
            bg=BG,
            fg=MUTED,
            font=FONT_UI,
        )
        hint.pack(anchor="w", pady=(6, 0))

        self.root.bind("<F1>", lambda event: self._run("HELP"))
        self.root.bind("<Control-l>", lambda event: self._clear_screen())

    def _build_status(self) -> None:
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        bar = tk.Frame(self.root, bg=BG, padx=20, pady=8)
        bar.pack(fill="x")

        tk.Label(
            bar,
            text="●",
            bg=BG,
            fg=GREEN,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 6))

        self.status_var = tk.StringVar(value=self.engine.status_line())
        tk.Label(
            bar,
            textvariable=self.status_var,
            bg=BG,
            fg=MUTED,
            font=("Consolas", 9),
        ).pack(side="left")

        tk.Label(
            bar,
            text="Данные только в памяти · без сторонних библиотек",
            bg=BG,
            fg=MUTED,
            font=FONT_UI,
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Вывод
    # ------------------------------------------------------------------
    def _print_banner(self) -> None:
        self.append(f"  {greeting()}! Я РЕЕСТР — ваша мини-СУБД.", "banner")
        self.append(
            "  Помогу создать базу, таблицу и записи. Всё храню только в памяти.",
            "info",
        )
        self.append("  " + "─" * 72, "muted")
        self.append(
            "  Данные не сохраняются на диск и исчезают при закрытии — так требует задание.",
            "muted",
        )
        self.append("", "info")
        self.append("  С чего начнём?", "tutorial")
        self.append("    HELP        расскажу, что умею", "code")
        self.append("    TUTORIAL    проведу урок из 13 шагов", "code")
        self.append("    DEMO        покажу готовый пример", "code")
        self.append("", "info")

    def append(self, text: str, kind: str = "info") -> None:
        """Добавляет строку в область вывода."""
        self.text.configure(state="normal")
        self.text.insert("end", text + "\n", kind)
        self.text.configure(state="disabled")
        self.text.see("end")

    def _clear_screen(self, show_hint: bool = True) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        if show_hint:
            self.append("Экран очищен. HELP — справка, TUTORIAL — обучение.", "muted")

    def _copy_selection(self) -> None:
        try:
            selected = self.text.get("sel.first", "sel.last")
        except tk.TclError:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(selected)

    def _select_all(self) -> None:
        self.text.tag_add("sel", "1.0", "end-1c")

    def _show_context_menu(self, event) -> None:
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    # ------------------------------------------------------------------
    # Выполнение команд
    # ------------------------------------------------------------------
    def submit(self, event=None) -> str:
        raw = self.entry.get()
        if not raw.strip():
            return "break"

        self.entry.delete(0, "end")
        self._remember(raw)
        self.append("❯ " + raw, "prompt")

        result = self.engine.execute(raw)

        if result.clear_requested:
            self._clear_screen(show_hint=False)
        for kind, text in result.lines:
            self.append(text, kind)
        if result.clear_requested:
            self.append("Экран очищен. HELP — справка, TUTORIAL — обучение.", "muted")

        if result.prefill is not None:
            self.entry.delete(0, "end")
            self.entry.insert(0, result.prefill)
            self.entry.icursor("end")

        self._update_status()
        if result.exit_requested:
            self.root.after(120, self.on_close)
        return "break"

    def _run(self, command: str) -> None:
        """Выполняет команду из меню или кнопки."""
        self.entry.delete(0, "end")
        self.entry.insert(0, command)
        self.entry.focus_set()
        self.submit()

    def _remember(self, raw: str) -> None:
        command = raw.strip()
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)
        self.history_index = len(self.history)

    def _history_up(self, event=None) -> str:
        if not self.history:
            return "break"
        if self.history_index > 0:
            self.history_index -= 1
        self.entry.delete(0, "end")
        self.entry.insert(0, self.history[self.history_index])
        self.entry.icursor("end")
        return "break"

    def _history_down(self, event=None) -> str:
        if not self.history:
            return "break"
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            value = self.history[self.history_index]
        else:
            self.history_index = len(self.history)
            value = ""
        self.entry.delete(0, "end")
        self.entry.insert(0, value)
        self.entry.icursor("end")
        return "break"

    def _complete(self, event=None) -> str:
        """Дополняет команду по первому совпадению из списка."""
        completions = [
            "CREATE DATABASE ",
            "SHOW DATABASES",
            "USE ",
            "DROP DATABASE ",
            "CREATE TABLE ",
            "SHOW TABLES",
            "DESCRIBE ",
            "ALTER TABLE ",
            "DROP TABLE ",
            "INSERT INTO ",
            "SELECT * FROM ",
            "UPDATE ",
            "DELETE FROM ",
            "HELP",
            "HELP TYPES",
            "HELP ERRORS",
            "TUTORIAL",
            "TUTORIAL STOP",
            "DEMO",
            "STATUS",
            "CLEAR",
            "ABOUT",
            "EXIT",
        ]
        text = self.entry.get()
        if not text:
            suggestion = "HELP"
        else:
            matches = [
                item
                for item in completions
                if item.upper().startswith(text.upper()) and item != text
            ]
            if not matches:
                self.root.bell()
                return "break"
            suggestion = matches[0]
        self.entry.delete(0, "end")
        self.entry.insert(0, suggestion)
        self.entry.icursor("end")
        return "break"

    def _update_status(self) -> None:
        self.status_var.set(self.engine.status_line())

    # ------------------------------------------------------------------
    # Действия меню
    # ------------------------------------------------------------------
    def _reset_data(self) -> None:
        if not messagebox.askyesno(
            "Сброс данных",
            "Я удалю все базы и таблицы из памяти.\n"
            "Это действие нельзя отменить. Продолжить?",
            parent=self.root,
        ):
            return
        self.engine.reset()
        self._clear_screen(show_hint=False)
        self.append("Готово, память очищена. Начинаем с чистого листа.", "success")
        self.append("Можно начать заново: TUTORIAL или DEMO.", "muted")
        self._update_status()

    def _about(self) -> None:
        messagebox.showinfo(
            "О программе",
            "Привет! Я РЕЕСТР — учебная мини-СУБД.\n"
            "Версия 1.0\n\n"
            "Работаю на Python и tkinter, без сторонних библиотек.\n"
            "Все данные храню только в оперативной памяти.\n\n"
            "Умею создавать базы, таблицы и записи, проверяю типы\n"
            "и подсказываю, если что-то пошло не так.",
            parent=self.root,
        )

    def on_close(self) -> None:
        if messagebox.askyesno(
            "Выход",
            "Завершить работу?\nВсе данные находятся только в оперативной "
            "памяти и будут потеряны.",
            parent=self.root,
        ):
            self.root.destroy()


def run(initial_commands: list[str] | None = None) -> None:
    """Запускает приложение.

    initial_commands позволяет сразу выполнить команды при старте
    (например, python main.py --tutorial для демонстрации).
    """
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    app = TerminalGUI(root)

    mapping = {"--tutorial": "TUTORIAL", "--demo": "DEMO"}
    delay = 300
    for raw in initial_commands or []:
        command = mapping.get(raw.lower(), raw)
        root.after(delay, lambda value=command: app._run(value))
        delay += 450

    root.mainloop()
