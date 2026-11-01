"""Вкладка живого подсчёта: ввод карт реальной раздачи."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from blackjack.counting import list_systems
from modes.live import LiveSession, make_card, suit_symbol

RANK_ORDER = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUIT_ROWS = [("S", "\u2660"), ("H", "\u2665"), ("D", "\u2666"), ("C", "\u2663")]
_RANK_KEYS = {"2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7",
              "8": "8", "9": "9", "0": "10", "t": "10", "j": "J", "q": "Q",
              "k": "K", "a": "A"}


class LiveFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.store = app.store
        self.session = LiveSession(app.system, app.rules.num_decks)
        self.current_suit = "S"
        self._build()
        self.refresh()
        self._restore()

    # --- построение ---------------------------------------------------------
    def _build(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        ttk.Label(bar, text="Система:").pack(side="left")
        self.system_var = tk.StringVar(value=self.app.system.name)
        cb = ttk.Combobox(bar, textvariable=self.system_var, state="readonly",
                          values=[s.name for s in list_systems()], width=14)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", self._on_system)

        ttk.Label(bar, text="Колод:").pack(side="left", padx=(12, 2))
        self.decks_var = tk.IntVar(value=self.app.rules.num_decks)
        sp = ttk.Spinbox(bar, from_=1, to=8, width=3, textvariable=self.decks_var,
                         command=self._on_decks)
        sp.pack(side="left")

        ttk.Button(bar, text="Отменить", command=self.undo).pack(side="left", padx=(12, 2))
        ttk.Button(bar, text="Новый шуз", command=self.new_shoe).pack(side="left", padx=2)
        ttk.Button(bar, text="Сброс", command=self.reset).pack(side="left", padx=2)

        # Панель со счётом.
        stats = ttk.LabelFrame(self, text="Счёт", padding=8)
        stats.pack(fill="x", pady=6)
        self.rc_var = tk.StringVar(value="0")
        self.tc_var = tk.StringVar(value="0.0")
        self.dr_var = tk.StringVar(value=str(self.app.rules.num_decks))
        self.bet_var = tk.StringVar(value="1")
        self.seen_var = tk.StringVar(value="0")
        self._stat(stats, "Running count", self.rc_var, 0)
        self._stat(stats, "True count", self.tc_var, 1)
        self._stat(stats, "Колод осталось", self.dr_var, 2)
        self._stat(stats, "Ставка (юниты)", self.bet_var, 3)
        self._stat(stats, "Карт учтено", self.seen_var, 4)

        # Сетка карт.
        grid = ttk.LabelFrame(self, text="Добавить карту (клик). Хоткеи: 2-9, 0/t, j, q, k, a; s/h/d/c — масть", padding=6)
        grid.pack(fill="x")
        self.suit_buttons = {}
        for row, (key, sym) in enumerate(SUIT_ROWS):
            color = "red" if key in ("H", "D") else "black"
            self.suit_buttons[key] = tk.Button(
                grid, text=sym, fg=color, font=("Segoe UI", 15, "bold"), width=2,
                relief="sunken" if key == self.current_suit else "raised",
                command=lambda k=key: self.set_suit(k))
            self.suit_buttons[key].grid(row=row, column=0, padx=2, pady=1)
            for col, rank in enumerate(RANK_ORDER, start=1):
                b = tk.Button(grid, text=rank, width=3,
                              fg=color, font=("Segoe UI", 10),
                              command=lambda r=rank, k=key: self.add(r, k))
                b.grid(row=row, column=col, padx=1, pady=1)

        self.history_var = tk.StringVar(value="—")
        ttk.Label(self, textvariable=self.history_var, wraplength=900,
                  foreground="#555").pack(fill="x", pady=(6, 0))

        self.app.bind("<Key>", self._on_key, add="+")

    def _stat(self, parent, title, var, col):
        cell = ttk.Frame(parent)
        cell.grid(row=0, column=col, padx=12)
        ttk.Label(cell, text=title, foreground="#666").pack()
        lbl = ttk.Label(cell, textvariable=var, font=("Segoe UI", 20, "bold"))
        lbl.pack()
        if title in ("Running count", "True count"):
            setattr(self, "_" + ("rc" if "Running" in title else "tc") + "_lbl", lbl)

    # --- действия -----------------------------------------------------------
    def add(self, rank: str, suit_key: str) -> None:
        self.session.add(make_card(rank, suit_key))
        self.refresh()
        self._persist()

    def undo(self) -> None:
        self.session.undo()
        self.refresh()
        self._persist()

    def new_shoe(self) -> None:
        self.session.reset()
        self.refresh()
        self._persist()

    def reset(self) -> None:
        if messagebox.askyesno("Сброс", "Сбросить счёт и начать новый шуз?"):
            self.session.reset()
            self.refresh()
            self._persist()

    def set_suit(self, key: str) -> None:
        self.current_suit = key
        for k, b in self.suit_buttons.items():
            b.configure(relief="sunken" if k == key else "raised")

    def _on_system(self, _event=None) -> None:
        from blackjack.counting import get_system
        self.session.set_system(get_system(self.system_var.get()))
        self.refresh()

    def _on_decks(self) -> None:
        try:
            n = int(self.decks_var.get())
        except (tk.TclError, ValueError):
            return
        self.session.set_num_decks(n)
        self.refresh()

    # --- обновление ---------------------------------------------------------
    def refresh(self) -> None:
        s = self.session
        self.rc_var.set(f"{s.running_count:+.0f}")
        if s.true_count is not None:
            self.tc_var.set(f"{s.true_count:+.1f}")
        else:
            self.tc_var.set("н/д")
        self.dr_var.set(f"{s.decks_remaining:.1f}")
        self.bet_var.set(str(s.bet_units))
        self.seen_var.set(str(s.cards_seen))

        rc_color = "#c0392b" if s.running_count > 0 else ("#2471a3" if s.running_count < 0 else "#333333")
        if hasattr(self, "_rc_lbl"):
            self._rc_lbl.configure(foreground=rc_color)
        if hasattr(self, "_tc_lbl") and s.true_count is not None:
            tc = s.true_count
            self._tc_lbl.configure(foreground="#c0392b" if tc >= 2 else ("#2471a3" if tc <= -1 else "#333333"))

        if s.history:
            tail = s.history[-24:]
            self.history_var.set("Последние карты: " + " ".join(str(c) for c in tail))
        else:
            self.history_var.set("Последние карты: —")

    # --- хоткеи -------------------------------------------------------------
    def _on_key(self, event) -> None:
        if not self.app.live_active():
            return
        widget = event.widget
        if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Spinbox, ttk.Spinbox)):
            return
        ch = event.char.lower()
        if not ch:
            return
        if ch in ("s", "h", "d", "c"):
            self.set_suit(ch.upper())
            return
        rank = _RANK_KEYS.get(ch)
        if rank:
            self.add(rank, self.current_suit)

    # --- сохранение сессии --------------------------------------------------
    def _persist(self) -> None:
        try:
            self.store.save_live_session(
                self.session.system.name,
                self.session.num_decks,
                [str(card) for card in self.session.history],
            )
        except Exception:  # pragma: no cover
            pass

    def save_session(self) -> None:
        self._persist()

    def clear_session(self) -> None:
        self.session.reset()
        self.refresh()
        self._persist()

    def _restore(self) -> None:
        data = self.store.load_live_session()
        if not data:
            return
        try:
            from blackjack.counting import get_system
            from modes.live import parse_card

            self.session.set_system(get_system(data.get("system", self.session.system.name)))
            self.session.set_num_decks(int(data.get("num_decks", self.session.num_decks)))
            self.system_var.set(self.session.system.name)
            self.decks_var.set(self.session.num_decks)
            for token in data.get("cards", []):
                try:
                    self.session.add(parse_card(token))
                except ValueError:
                    continue
            self.refresh()
        except Exception:  # pragma: no cover
            pass

    def apply_settings(self) -> None:
        self.system_var.set(self.app.system.name)
        self.decks_var.set(self.app.rules.num_decks)
        self.session.set_system(self.app.system)
        self.session.set_num_decks(self.app.rules.num_decks)
        self.refresh()
