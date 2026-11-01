"""Правила стола."""

from __future__ import annotations

from dataclasses import dataclass

from .cards import hand_total


@dataclass
class Rules:
    """Правила конкретного стола.

    Значения по умолчанию — распространённый вариант: 6 колод, дилер стоит
    на мягких 17 (S17), дабл после сплита разрешён, дабл на любые две карты.
    """

    num_decks: int = 6
    penetration: float = 0.75

    # Дилер добирает на soft 17?
    dealer_hits_soft_17: bool = False

    # Дабл после сплита (DAS)?
    double_after_split: bool = True

    # Максимум сплитов (3 => до 4 рук).
    max_splits: int = 3

    # Разрешать ли повторный сплит тузов.
    resplit_aces: bool = False

    # Выплата за блэкджек (1.5 = 3:2, 1.2 = 6:5).
    blackjack_payout: float = 1.5

    # Поздний сюррендер.
    surrender: bool = False

    # На какие суммы разрешён дабл: "any" | "9-11" | "10-11".
    double_on: str = "any"

    # Страховка доступна?
    insurance: bool = True

    # Дилер проверяет блэкджек на A/10 (американские правила).
    dealer_peeks: bool = True

    def can_double_on(self, hand) -> bool:
        """Разрешён ли дабл на текущую сумму руки."""
        if self.double_on == "any":
            return True
        total, _ = hand_total(hand.cards)
        if self.double_on == "9-11":
            return 9 <= total <= 11
        if self.double_on == "10-11":
            return 10 <= total <= 11
        return True

    def describe(self) -> str:
        h17 = "H17 (добирает на soft 17)" if self.dealer_hits_soft_17 else "S17 (стоит на soft 17)"
        return (
            f"{self.num_decks} колод | {h17} | "
            f"DAS: {'да' if self.double_after_split else 'нет'} | "
            f"BJ {self.blackjack_payout:g}:1 | "
            f"сюррендер: {'да' if self.surrender else 'нет'} | "
            f"страховка: {'да' if self.insurance else 'нет'}"
        )
