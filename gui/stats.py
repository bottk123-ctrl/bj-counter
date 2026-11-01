"""Вкладка статистики: накопленные показатели, история симуляций, график банкролла."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk


class StatsFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self._curve: list[float] = []
        self._start = 0.0
        self._build()
        self.refresh()

    def _build(self) -> None:
        cards = ttk.Frame(self)
        cards.pack(fill="x")
        self.vars = {}
        specs = [
            ("decisions", "Решения (стратегия)"),
            ("count", "Точность счёта"),
            ("rounds", "Сыграно рук"),
            ("hands", "Рук в симуляциях"),
            ("sims", "Симуляций"),
        ]
        for key, title in specs:
            cell = ttk.LabelFrame(cards, text=title, padding=8)
            cell.pack(side="left", padx=4, fill="x", expand=True)
            var = tk.StringVar(value="—")
            self.vars[key] = var
            ttk.Label(cell, textvariable=var, font=("Segoe UI", 16, "bold")).pack()

        chart_box = ttk.LabelFrame(self, text="Кривая банкролла (последняя симуляция)", padding=4)
        chart_box.pack(fill="both", expand=True, pady=8)
        self.canvas = tk.Canvas(chart_box, height=200, bg="#ffffff", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._draw())

        hist_box = ttk.LabelFrame(self, text="История симуляций", padding=4)
        hist_box.pack(fill="both", expand=True)
        columns = ("time", "system", "hands", "net", "edge", "ev", "dd", "ruin")
        headings = {
            "time": "Время", "system": "Система", "hands": "Рук",
            "net": "Итог", "edge": "Преим.", "ev": "EV/юнит", "dd": "Просадка",
            "ruin": "Руина",
        }
        widths = {"time": 120, "system": 110, "hands": 80, "net": 90,
                  "edge": 80, "ev": 90, "dd": 90, "ruin": 70}
        self.tree = ttk.Treeview(hist_box, columns=columns, show="headings", height=8)
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(hist_box, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=6)
        ttk.Button(btns, text="Обновить", command=self.refresh).pack(side="left")
        ttk.Button(btns, text="Очистить статистику", command=self._clear_stats).pack(side="left", padx=6)
        ttk.Button(btns, text="Очистить живую сессию", command=self._clear_session).pack(side="left")

    # --- данные -------------------------------------------------------------
    def set_curve(self, curve: list[float], start_bankroll: float) -> None:
        self._curve = list(curve or [])
        self._start = float(start_bankroll or 0.0)
        self.refresh()

    @staticmethod
    def _ruin_text(sim: dict) -> str:
        sessions = int(sim.get("sessions", 1) or 1)
        if sessions > 1:
            return f"{sim.get('ruin_rate', 0.0) * 100:.0f}%"
        return "да" if sim.get("ruined") else "—"

    def refresh(self) -> None:
        store = self.app.store
        data = store.data
        self.vars["decisions"].set(
            f"{data['decisions_correct']}/{data['decisions_total']}\n"
            f"{store.decision_accuracy * 100:.0f}%")
        self.vars["count"].set(
            f"{data['count_correct']}/{data['count_total']}\n"
            f"{store.count_accuracy * 100:.0f}%")
        self.vars["rounds"].set(str(data["rounds_played"]))
        self.vars["hands"].set(str(data["hands_simulated"]))
        self.vars["sims"].set(str(len(data["simulations"])))

        self.tree.delete(*self.tree.get_children())
        for sim in data["simulations"]:
            self.tree.insert("", "end", values=(
                sim.get("time", ""),
                sim.get("system", ""),
                sim.get("hands", ""),
                f"{sim.get('net', 0):+.0f}",
                f"{sim.get('edge', 0) * 100:+.3f}%",
                f"{sim.get('ev_units', 0):+.4f}",
                f"{sim.get('drawdown_units', 0):.0f}",
                self._ruin_text(sim),
            ))
        self._draw()

    # --- график -------------------------------------------------------------
    def _draw(self) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = canvas.winfo_width() or 600
        height = canvas.winfo_height() or 200
        curve = self._curve
        if len(curve) < 2:
            canvas.create_text(width / 2, height / 2, fill="#888888",
                               text="Запустите симуляцию — здесь появится кривая банкролла")
            return

        lo = min(min(curve), self._start)
        hi = max(max(curve), self._start)
        if hi - lo < 1e-9:
            hi = lo + 1
        pad = 24

        def x_of(i: int) -> float:
            return pad + (width - 2 * pad) * i / (len(curve) - 1)

        def y_of(value: float) -> float:
            return height - pad - (height - 2 * pad) * (value - lo) / (hi - lo)

        canvas.create_line(pad, y_of(self._start), width - pad, y_of(self._start),
                           fill="#bbbbbb", dash=(4, 3))
        canvas.create_text(pad + 2, y_of(self._start) - 8, anchor="w",
                           fill="#888888", text=f"старт {self._start:.0f}")
        points: list[float] = []
        for i, value in enumerate(curve):
            points.extend((x_of(i), y_of(value)))
        color = "#27ae60" if curve[-1] >= self._start else "#c0392b"
        canvas.create_line(*points, fill=color, width=2)
        canvas.create_text(width - pad - 2, y_of(curve[-1]) - 8, anchor="e",
                           fill=color, text=f"финал {curve[-1]:.0f}")

    # --- действия -----------------------------------------------------------
    def _clear_stats(self) -> None:
        if messagebox.askyesno("Очистка", "Сбросить всю накопленную статистику?"):
            self.app.store.reset_stats()
            self.refresh()

    def _clear_session(self) -> None:
        self.app.store.clear_live_session()
        self.app.live.clear_session()
        messagebox.showinfo("Готово", "Живая сессия очищена.")
