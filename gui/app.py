"""Главное окно приложения."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from blackjack.counting import get_system, list_systems
from blackjack.rules import Rules
from gui.live import LiveFrame
from gui.play import PlayFrame
from gui.sim import SimFrame
from gui.stats import StatsFrame
from storage import Store


class SettingsFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self._build()

    def _build(self) -> None:
        rules = self.app.rules

        system_box = ttk.LabelFrame(self, text="Система подсчёта", padding=8)
        system_box.pack(fill="x")
        self.system_var = tk.StringVar(value=self.app.system.name)
        for system in list_systems():
            ttk.Radiobutton(system_box, value=system.name, variable=self.system_var,
                            text=f"{system.name} — {system.description}").pack(anchor="w")

        box = ttk.LabelFrame(self, text="Правила стола", padding=8)
        box.pack(fill="x", pady=8)

        self.decks_var = tk.IntVar(value=rules.num_decks)
        self.pen_var = tk.DoubleVar(value=rules.penetration)
        self.maxsplit_var = tk.IntVar(value=rules.max_splits)
        self.h17_var = tk.BooleanVar(value=rules.dealer_hits_soft_17)
        self.das_var = tk.BooleanVar(value=rules.double_after_split)
        self.sur_var = tk.BooleanVar(value=rules.surrender)
        self.ins_var = tk.BooleanVar(value=rules.insurance)
        self.payout_var = tk.StringVar(value="1.5" if rules.blackjack_payout >= 1.35 else "1.2")

        grid = ttk.Frame(box)
        grid.pack(fill="x")
        ttk.Label(grid, text="Колод:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(grid, from_=1, to=8, width=4, textvariable=self.decks_var).grid(row=0, column=1, padx=4)
        ttk.Label(grid, text="Проникновение:").grid(row=0, column=2, sticky="w", padx=(16, 0))
        ttk.Spinbox(grid, from_=0.3, to=1.0, increment=0.05, width=5,
                    textvariable=self.pen_var).grid(row=0, column=3, padx=4)
        ttk.Label(grid, text="Макс. сплитов:").grid(row=0, column=4, sticky="w", padx=(16, 0))
        ttk.Spinbox(grid, from_=0, to=4, width=4,
                    textvariable=self.maxsplit_var).grid(row=0, column=5, padx=4)

        opts = ttk.Frame(box)
        opts.pack(fill="x", pady=(8, 0))
        ttk.Checkbutton(opts, text="Дилер H17 (добирает на мягких 17)",
                        variable=self.h17_var).pack(anchor="w")
        ttk.Checkbutton(opts, text="Дабл после сплита (DAS)",
                        variable=self.das_var).pack(anchor="w")
        ttk.Checkbutton(opts, text="Разрешён сюррендер", variable=self.sur_var).pack(anchor="w")
        ttk.Checkbutton(opts, text="Разрешена страховка", variable=self.ins_var).pack(anchor="w")

        pay = ttk.Frame(box)
        pay.pack(fill="x", pady=(8, 0))
        ttk.Label(pay, text="Выплата за блэкджек:").pack(side="left")
        ttk.Radiobutton(pay, text="3:2 (1.5)", value="1.5",
                        variable=self.payout_var).pack(side="left", padx=6)
        ttk.Radiobutton(pay, text="6:5 (1.2)", value="1.2",
                        variable=self.payout_var).pack(side="left")

        ttk.Button(self, text="Применить", command=self.apply).pack(anchor="w", pady=10)
        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, foreground="#27ae60").pack(anchor="w")

    def apply(self) -> None:
        try:
            rules = Rules(
                num_decks=int(self.decks_var.get()),
                penetration=float(self.pen_var.get()),
                dealer_hits_soft_17=bool(self.h17_var.get()),
                double_after_split=bool(self.das_var.get()),
                max_splits=int(self.maxsplit_var.get()),
                surrender=bool(self.sur_var.get()),
                insurance=bool(self.ins_var.get()),
                blackjack_payout=float(self.payout_var.get()),
            )
        except Exception as exc:  # pragma: no cover
            messagebox.showerror("Ошибка", str(exc))
            return
        self.app.set_settings(get_system(self.system_var.get()), rules)
        self.status_var.set("Применено: " + rules.describe())


class App(tk.Tk):
    def __init__(self, store=None):
        super().__init__()
        self.title("Blackjack AI")
        self.geometry("1040x780")
        self.minsize(920, 640)

        self.system = list_systems()[0]  # Hi-Lo
        self.rules = Rules()
        self.store = store or Store()

        try:
            ttk.Style(self).theme_use("clam")
        except Exception:  # pragma: no cover
            pass

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.live = LiveFrame(self.nb, self)
        self.play = PlayFrame(self.nb, self)
        self.sim = SimFrame(self.nb, self)
        self.stats = StatsFrame(self.nb, self)
        self.settings = SettingsFrame(self.nb, self)

        self.nb.add(self.live, text="Счёт (реальная раздача)")
        self.nb.add(self.play, text="Игра")
        self.nb.add(self.sim, text="Симулятор")
        self.nb.add(self.stats, text="Статистика")
        self.nb.add(self.settings, text="Настройки")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def live_active(self) -> bool:
        return self._tab_index() == 0

    def play_active(self) -> bool:
        return self._tab_index() == 1

    def _tab_index(self) -> int:
        try:
            return self.nb.index(self.nb.select())
        except Exception:  # pragma: no cover
            return -1

    def set_settings(self, system, rules: Rules) -> None:
        self.system = system
        self.rules = rules
        self.live.apply_settings()
        self.play.apply_settings()

    def notify_new_simulation(self, report: dict) -> None:
        self.stats.set_curve(report.get("bankroll_curve", []),
                             report.get("start_bankroll", 0.0))

    def _on_close(self) -> None:
        try:
            self.live.save_session()
        except Exception:  # pragma: no cover
            pass
        self.store.save()
        self.destroy()


def run() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":  # pragma: no cover
    run()
