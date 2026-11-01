"""Вкладка игры против дилера с проверкой базовой стратегии."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from blackjack.counting import CardCounter
from blackjack.engine import BlackjackGame
from blackjack.strategy import basic_strategy
from gui.widgets import card_back, card_face

ACTION_RU = {
    "hit": "добор",
    "stand": "стоп",
    "double": "дабл",
    "split": "сплит",
    "surrender": "сюррендер",
}
BUTTONS = [
    ("hit", "Добор (H)"),
    ("stand", "Стоп (S)"),
    ("double", "Дабл (D)"),
    ("split", "Сплит (P)"),
    ("surrender", "Сдаться (R)"),
]
KEY_TO_ACTION = {"h": "hit", "s": "stand", "d": "double", "p": "split", "r": "surrender"}

COLOR_OK = "#27ae60"
COLOR_BAD = "#c0392b"
COLOR_HINT = "#8e44ad"


def _beep(ok: bool) -> None:
    try:
        import winsound

        winsound.Beep(900 if ok else 280, 120)
    except Exception:
        pass


class PlayFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.game = BlackjackGame(app.rules)
        self.counter = CardCounter(app.system, app.rules.num_decks)
        self.rnd = None
        self.seen: set[int] = set()
        self._build()
        self._render()

    # --- построение ---------------------------------------------------------
    def _build(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x")
        self.bet_var = tk.DoubleVar(value=10.0)
        ttk.Label(bar, text="Ставка:").pack(side="left")
        ttk.Spinbox(bar, from_=1, to=100000, increment=5, width=8,
                    textvariable=self.bet_var).pack(side="left", padx=4)
        self.show_count = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Показывать счёт", variable=self.show_count,
                        command=self._render).pack(side="left", padx=12)
        self.sound_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Звук", variable=self.sound_var).pack(side="left", padx=6)
        ttk.Button(bar, text="Новая раздача (N)", command=self.new_round).pack(side="left")

        self.count_var = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.count_var, foreground="#555").pack(side="right")

        table = ttk.LabelFrame(self, text="Стол", padding=10)
        table.pack(fill="both", expand=True, pady=8)
        ttk.Label(table, text="Дилер", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.dealer_frame = ttk.Frame(table)
        self.dealer_frame.pack(anchor="w", pady=(2, 10))
        self.dealer_total = tk.StringVar(value="")
        ttk.Label(table, textvariable=self.dealer_total).pack(anchor="w")

        ttk.Label(table, text="Ваши руки", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(8, 0))
        self.player_frame = ttk.Frame(table)
        self.player_frame.pack(anchor="w", pady=2)

        self.result_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.result_var, font=("Segoe UI", 12, "bold")).pack(anchor="w")

        self.feedback_var = tk.StringVar(value="")
        self.feedback_label = ttk.Label(self, textvariable=self.feedback_var,
                                        font=("Segoe UI", 11, "bold"))
        self.feedback_label.pack(anchor="w", pady=4)

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=6)
        self.action_buttons = {}
        for action, label in BUTTONS:
            b = ttk.Button(btns, text=label, state="disabled",
                           command=lambda a=action: self._do(a))
            b.pack(side="left", padx=3)
            self.action_buttons[action] = b

        ttk.Label(self, foreground="#666", wraplength=920,
                  text=("Играйте руку — подсказка покажет, что советует базовая стратегия. "
                        "Горячие клавиши: H/S/D/P/R — действия, N — новая раздача. "
                        "Число рядом с рукой — сумма очков.")).pack(anchor="w")

        self.app.bind("<Key>", self._on_key, add="+")

    # --- обслуживание счётчика ---------------------------------------------
    def _see(self, card) -> None:
        if id(card) not in self.seen:
            self.seen.add(id(card))
            self.counter.observe(card)

    def _see_player(self) -> None:
        for hand in self.rnd.player:
            for card in hand.cards:
                self._see(card)

    def _see_dealer_revealed(self) -> None:
        for card in self.rnd.dealer[1:]:
            self._see(card)

    # --- игровой цикл -------------------------------------------------------
    def new_round(self) -> None:
        if self.game.shoe.needs_shuffle():
            self.game.shoe.shuffle()
            self.game.shoe_number += 1
            self.counter.reset()
        self.rnd = self.game.start_round(float(self.bet_var.get()))
        self.seen = set()
        self.feedback_var.set("")
        self.result_var.set("")
        self._see_player()
        self._see(self.rnd.dealer[0])

        if self.rnd.dealer_has_ace and self.app.rules.insurance:
            from tkinter import messagebox
            if messagebox.askyesno("Страховка", "Дилер показывает туза. Брать страховку?"):
                self.rnd.take_insurance(float(self.bet_var.get()) / 2)

        if self.app.rules.dealer_peeks and (self.rnd.dealer_has_ace or self.rnd.dealer_has_ten_up):
            if self.rnd.dealer_blackjack:
                self._see(self.rnd.dealer[1])
                self._finish()
                return
        self._render()

    def _current(self):
        if self.rnd is None:
            return None
        for i, _hand in enumerate(self.rnd.player):
            acts = self.rnd.available_actions(i)
            if acts:
                return i, acts
        return None

    def _do(self, action: str) -> None:
        cur = self._current()
        if cur is None:
            return
        idx, acts = cur
        if action not in acts:
            return
        hand = self.rnd.player[idx]
        correct = basic_strategy(hand.cards, self.rnd.dealer_upcard.rank, self.app.rules, acts)
        ok = action == correct
        if ok:
            self.feedback_var.set("Верно.")
            self.feedback_label.configure(foreground=COLOR_OK)
        else:
            self.feedback_var.set(f"Базовая стратегия советует: {ACTION_RU[correct]}")
            self.feedback_label.configure(foreground=COLOR_HINT)
        if self.sound_var.get():
            _beep(ok)
        try:
            self.app.store.record_decision(ok, save=True)
        except Exception:  # pragma: no cover
            pass
        self.rnd.apply(action, idx)
        self._see_player()
        if self._current() is None:
            self._finish()
        else:
            self._render()

    def _finish(self) -> None:
        self.rnd.play_dealer()
        self._see_dealer_revealed()
        results = self.rnd.settle()
        try:
            self.app.store.record_round(save=True)
        except Exception:  # pragma: no cover
            pass
        parts = []
        for r in results:
            sign = "+" if r.net >= 0 else ""
            parts.append(f"{r.result} {sign}{r.net:.0f}")
        self.result_var.set("Итог: " + " | ".join(parts))
        self._render()

    # --- отрисовка ----------------------------------------------------------
    def _render(self) -> None:
        for w in self.dealer_frame.winfo_children():
            w.destroy()
        for w in self.player_frame.winfo_children():
            w.destroy()

        if self.rnd is None:
            self.dealer_total.set("")
            self._update_buttons(set())
            self._update_count()
            return

        for card in self.rnd.dealer:
            card_face(self.dealer_frame, card).pack(side="left", padx=2)
        if self.rnd.hole_hidden:
            card_back(self.dealer_frame).pack(side="left", padx=2)
            self.dealer_total.set(f"Открытая карта: {self.rnd.dealer_upcard}")
        else:
            self.dealer_total.set(f"Сумма дилера: {self.rnd.dealer_total}")

        cur = self._current()
        cur_idx = cur[0] if cur else None
        for i, hand in enumerate(self.rnd.player):
            box = tk.Frame(self.player_frame, bd=2,
                           relief="solid" if i == cur_idx else "flat")
            box.pack(side="left", padx=6, pady=2)
            ttk.Label(box, text=f"Рука {i + 1}").pack()
            row = ttk.Frame(box)
            row.pack()
            for card in hand.cards:
                card_face(row, card, font=("Consolas", 12, "bold")).pack(side="left", padx=1)
            ttk.Label(box, text=f"сумма {hand.total}").pack()

        self._update_buttons(cur[1] if cur else set())
        self._update_count()

    def _update_buttons(self, acts: set) -> None:
        for action, button in self.action_buttons.items():
            button.configure(state="normal" if action in acts else "disabled")

    def _update_count(self) -> None:
        if self.show_count.get():
            if self.counter.true_count is not None:
                self.count_var.set(
                    f"RC={self.counter.running_count:+.0f}  TC={self.counter.true_count:+.1f}  "
                    f"ставка {self.counter.bet_units()}u")
            else:
                self.count_var.set(f"RC={self.counter.running_count:+.0f}  "
                                   f"ставка {self.counter.bet_units()}u")
        else:
            self.count_var.set("счёт скрыт")

    # --- хоткеи -------------------------------------------------------------
    def _on_key(self, event) -> None:
        if not self.app.play_active():
            return
        widget = event.widget
        if isinstance(widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Spinbox, ttk.Spinbox)):
            return
        ch = event.char.lower()
        if ch == "n":
            self.new_round()
        elif ch in KEY_TO_ACTION:
            self._do(KEY_TO_ACTION[ch])

    # --- смена настроек -----------------------------------------------------
    def apply_settings(self) -> None:
        self.game = BlackjackGame(self.app.rules)
        self.counter = CardCounter(self.app.system, self.app.rules.num_decks)
        self.rnd = None
        self.seen = set()
        self.feedback_var.set("")
        self.result_var.set("")
        self._render()
