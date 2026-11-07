"""Карты, колода и шуз (несколько колод)."""

from __future__ import annotations

import random
from dataclasses import dataclass

# Ранги по возрастанию. Ace = "A".
RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
TEN_RANKS = {"10", "J", "Q", "K"}

# Юникод-символы мастей: пики, черви, бубны, трефы.
UNICODE_SUITS = ["\u2660", "\u2665", "\u2666", "\u2663"]
ASCII_SUITS = ["S", "H", "D", "C"]
SUIT_SYMBOLS = list(UNICODE_SUITS)

# Масти, которые считаются «красными» (для Red Seven).
RED_SUITS = {"\u2665", "\u2666", "H", "D"}


def use_ascii_suits() -> None:
    """Переключить вывод мастей на ASCII (для консолей без юникода)."""
    global SUIT_SYMBOLS
    SUIT_SYMBOLS = list(ASCII_SUITS)


RANK_VALUE = {
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 10,
    "Q": 10,
    "K": 10,
    "A": 11,
}


@dataclass(frozen=True)
class Card:
    rank: str
    suit: str

    @property
    def is_ace(self) -> bool:
        return self.rank == "A"

    @property
    def is_ten(self) -> bool:
        return self.rank in TEN_RANKS

    @property
    def is_low(self) -> bool:
        """Младшие карты (в системе Hi-Lo это 2-6)."""
        return self.rank in {"2", "3", "4", "5", "6"}

    @property
    def is_red(self) -> bool:
        return self.suit in RED_SUITS

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return f"Card({self.rank}{self.suit})"


def hand_total(cards) -> tuple[int, bool]:
    """Лучшая сумма руки и признак мягкости (есть туз, считающийся за 11).

    >>> from .cards import Card
    >>> hand_total([Card("A", "\u2660"), Card("K", "\u2665")])
    (21, True)
    """
    total = 0
    aces = 0
    for card in cards:
        if card.rank == "A":
            aces += 1
            total += 11
        else:
            total += RANK_VALUE[card.rank]
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total, aces > 0


def is_pair(cards) -> bool:
    """Пара — две карты одного ранга."""
    return len(cards) == 2 and cards[0].rank == cards[1].rank


def pair_rank(cards):
    """Ранг пары или None, если это не пара."""
    if is_pair(cards):
        return cards[0].rank
    return None


def cards_to_str(cards) -> str:
    """Красивый вывод набора карт: ``A♠ K♥ 7♦``."""
    return " ".join(str(c) for c in cards)


class Shoe:
    """Мультиколодный шуз с точкой проникновения (penetration)."""

    def __init__(
        self,
        num_decks: int = 6,
        penetration: float = 0.75,
        rng: random.Random | None = None,
    ) -> None:
        if num_decks < 1:
            raise ValueError("Колод должно быть хотя бы 1")
        if not 0.0 < penetration <= 1.0:
            raise ValueError("penetration должен быть в диапазоне (0, 1]")
        self.num_decks = num_decks
        self.penetration = penetration
        self.rng = rng or random.Random()
        self._cards: list[Card] = []
        self._dealt = 0
        self.shuffle()

    def shuffle(self) -> None:
        self._cards = [
            Card(rank, suit)
            for _ in range(self.num_decks)
            for suit in SUIT_SYMBOLS
            for rank in RANKS
        ]
        self.rng.shuffle(self._cards)
        self._dealt = 0

    @property
    def total(self) -> int:
        return len(self._cards)

    @property
    def dealt(self) -> int:
        return self._dealt

    @property
    def remaining(self) -> int:
        return len(self._cards) - self._dealt

    @property
    def decks_remaining(self) -> float:
        return self.remaining / 52.0

    def needs_shuffle(self) -> bool:
        """Пора ли тасовать (достигнута точка проникновения)."""
        return self._dealt >= self.penetration * len(self._cards)

    def deal(self) -> Card:
        if self._dealt >= len(self._cards):
            raise IndexError("Шуз пуст — нужно перетасовать")
        card = self._cards[self._dealt]
        self._dealt += 1
        return card

    def __len__(self) -> int:
        return self.remaining
