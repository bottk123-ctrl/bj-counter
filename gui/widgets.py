"""Мелкие помощники для GUI: цвета и отрисовка карт."""

from __future__ import annotations

import tkinter as tk

CARD_RED = "#c0392b"
CARD_BLACK = "#1b1b1b"
CARD_BG = "#fdfdfd"
CARD_BACK = "#2c3e50"

RED_SUITS = {"\u2665", "\u2666", "H", "D"}


def suit_is_red(suit: str) -> bool:
    return suit in RED_SUITS


def card_face(parent, card, font=("Consolas", 16, "bold")) -> tk.Label:
    """Метка с лицом карты."""
    return tk.Label(
        parent,
        text=str(card),
        fg=CARD_RED if suit_is_red(card.suit) else CARD_BLACK,
        bg=CARD_BG,
        relief="ridge",
        bd=2,
        width=3,
        font=font,
    )


def card_back(parent, font=("Consolas", 16, "bold")) -> tk.Label:
    """Рубашка карты (скрытая карта дилера)."""
    return tk.Label(
        parent,
        text="\u2b1b",
        fg=CARD_BG,
        bg=CARD_BACK,
        relief="ridge",
        bd=2,
        width=3,
        font=font,
    )
