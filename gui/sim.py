"""Вкладка симулятора: бот играет N рук, показываем статистику."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

from modes.simulator import (
    SimConfig,
    format_many,
    format_report,
    run_many,
    run_simulation,
)

MODE_CHOICES = [
    ("Флэт (1 юнит)", "flat"),
    ("Спред по счёту", "spread"),
    ("Kelly (доля банка)", "kelly"),
]


class SimFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._build()

    def _build(self) -> None:
        form = ttk.LabelFrame(self, text="Параметры", padding=8)
        form.pack(fill="x")

        self.hands_var = tk.IntVar(value=20000)
        self.bank_var = tk.DoubleVar(value=1000.0)
        self.unit_var = tk.DoubleVar(value=10.0)
        self.dev_var = tk.BooleanVar(value=True)
        self.seed_var = tk.StringVar(value="")

        row = ttk.Frame(form)
        row.pack(fill="x")
        ttk.Label(row, text="Рук:").pack(side="left")
        ttk.Spinbox(row, from_=100, to=5_000_000, increment=1000, width=10,
                    textvariable=self.hands_var).pack(side="left", padx=4)
        ttk.Label(row, text="Банкролл:").pack(side="left", padx=(12, 0))
        ttk.Spinbox(row, from_=0, to=10_000_000, increment=100, width=10,
                    textvariable=self.bank_var).pack(side="left", padx=4)
        ttk.Label(row, text="Юнит:").pack(side="left", padx=(12, 0))
        ttk.Spinbox(row, from_=1, to=10000, increment=5, width=8,
                    textvariable=self.unit_var).pack(side="left", padx=4)
        ttk.Checkbutton(row, text="Индексные отклонения (I18)",
                        variable=self.dev_var).pack(side="left", padx=12)

        row2 = ttk.Frame(form)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="Режим ставок:").pack(side="left")
        self.mode_var = tk.StringVar(value=MODE_CHOICES[1][0])
        ttk.Combobox(row2, textvariable=self.mode_var, state="readonly",
                     values=[label for label, _ in MODE_CHOICES],
                     width=20).pack(side="left", padx=4)
        ttk.Label(row2, text="Доля Kelly:").pack(side="left", padx=(12, 0))
        self.kelly_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(row2, from_=0.05, to=1.0, increment=0.05, width=6,
                    textvariable=self.kelly_var).pack(side="left", padx=4)
        ttk.Label(row2, text="Лимит стола:").pack(side="left", padx=(12, 0))
        self.max_var = tk.DoubleVar(value=0.0)
        ttk.Spinbox(row2, from_=0, to=1_000_000, increment=50, width=10,
                    textvariable=self.max_var).pack(side="left", padx=4)
        ttk.Label(row2, text="(0 = без лимита)", foreground="#666").pack(side="left")

        row3 = ttk.Frame(form)
        row3.pack(fill="x", pady=(6, 0))
        ttk.Label(row3, text="Сессий (для ДИ):").pack(side="left")
        self.sessions_var = tk.IntVar(value=1)
        ttk.Spinbox(row3, from_=1, to=1000, increment=1, width=6,
                    textvariable=self.sessions_var).pack(side="left", padx=4)
        self.ruin_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row3, text="Останавливать на руине",
                        variable=self.ruin_var).pack(side="left", padx=12)
        ttk.Label(row3, text="Seed (пусто = случайно):").pack(side="left", padx=(12, 0))
        ttk.Entry(row3, textvariable=self.seed_var, width=10).pack(side="left", padx=4)

        ttk.Label(form, foreground="#666", wraplength=920,
                  text=("Настройки системы и правил берутся из вкладки «Настройки». "
                        "При числе сессий > 1 считается среднее преимущество с 95% "
                        "доверительным интервалом и риск разорения.")
                  ).pack(anchor="w", pady=(6, 0))

        self.run_btn = ttk.Button(self, text="Запустить симуляцию", command=self.run)
        self.run_btn.pack(anchor="w", pady=8)

        self.output = tk.Text(self, height=22, wrap="word", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True)

    def _selected_mode(self) -> str:
        for label, key in MODE_CHOICES:
            if label == self.mode_var.get():
                return key
        return "spread"

    def run(self) -> None:
        if self._running:
            return
        seed_text = self.seed_var.get().strip()
        seed = int(seed_text) if seed_text.isdigit() or (seed_text.startswith("-") and seed_text[1:].isdigit()) else None
        try:
            sessions = int(self.sessions_var.get())
        except (tk.TclError, ValueError):
            sessions = 1
        cfg = SimConfig(
            hands=int(self.hands_var.get()),
            bankroll=float(self.bank_var.get()),
            unit=float(self.unit_var.get()),
            system_name=self.app.system.name,
            rules=self.app.rules,
            seed=seed,
            use_deviations=bool(self.dev_var.get()),
            bet_mode=self._selected_mode(),
            kelly_fraction=float(self.kelly_var.get()),
            table_max=float(self.max_var.get()),
            stop_at_ruin=bool(self.ruin_var.get()),
            sessions=sessions,
        )
        self._running = True
        self.run_btn.configure(state="disabled")
        self.output.delete("1.0", "end")
        if sessions > 1:
            self.output.insert("end", f"Считаю {sessions} сессий по {cfg.hands} рук "
                                      f"системой {cfg.system_name}...\n")
        else:
            self.output.insert("end", f"Считаю {cfg.hands} рук системой {cfg.system_name}...\n")

        def worker():
            try:
                report = run_many(cfg, sessions) if sessions > 1 else run_simulation(cfg)
                self._queue.put(report)
            except Exception as exc:  # pragma: no cover
                self._queue.put(exc)

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, self._poll)

    def _poll(self) -> None:
        try:
            result = self._queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll)
            return
        self._running = False
        self.run_btn.configure(state="normal")
        self.output.delete("1.0", "end")
        if isinstance(result, Exception):
            self.output.insert("end", f"Ошибка: {result}\n")
        else:
            if result.get("sessions", 1) > 1:
                self.output.insert("end", format_many(result))
            else:
                self.output.insert("end", format_report(result))
            try:
                self.app.store.record_simulation(result)
                self.app.notify_new_simulation(result)
            except Exception:  # pragma: no cover
                pass
