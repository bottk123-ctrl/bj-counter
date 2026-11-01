"""Счётчик карт: running count, true count и решение о ставке."""

from __future__ import annotations

from collections import Counter

from ..cards import Card
from .systems import CountingSystem

# Приблизительные константы для оценки преимущества и ставки по Kelly.
# На каждую единицу true count преимущество растёт примерно на 0.5%.
EDGE_PER_TRUE_COUNT = 0.005
# Дисперсия результата на один юнит ставки в блэкджеке (~1.3).
VARIANCE_PER_UNIT = 1.3


class CardCounter:
    """Ведёт счёт по выбранной системе.

    Счётчик «видит» каждую открытую карту через :meth:`observe`.
    """

    def __init__(self, system: CountingSystem, num_decks: int, resolution: float = 0.5):
        self.system = system
        self.num_decks = num_decks
        # Нижняя граница «колод осталось», чтобы true count не разлетался в конце шуза.
        self.resolution = resolution
        self.reset()

    def reset(self) -> None:
        self.running_count: float = self.system.initial_count(self.num_decks)
        self.cards_seen = 0
        self.seen: list[Card] = []
        self.by_rank: Counter = Counter()

    def observe(self, card: Card) -> float:
        """Учесть открытую карту и вернуть новый running count."""
        self.running_count += self.system.value(card)
        self.cards_seen += 1
        self.seen.append(card)
        self.by_rank[card.rank] += 1
        return self.running_count

    def observe_many(self, cards) -> float:
        for card in cards:
            self.observe(card)
        return self.running_count

    @property
    def decks_seen(self) -> float:
        return self.cards_seen / 52.0

    @property
    def decks_remaining(self) -> float:
        return max(self.num_decks - self.decks_seen, self.resolution)

    @property
    def true_count(self) -> float | None:
        """True count для balanced-систем; для unbalanced — None."""
        if not self.system.balanced:
            return None
        return self.running_count / self.decks_remaining

    @property
    def metric(self) -> float:
        """Величина, по которой принимается решение о ставке."""
        if self.system.balanced:
            return self.true_count
        return self.running_count - self.system.initial_count(self.num_decks)

    def bet_units(self) -> int:
        """Число юнитов ставки по текущему счёту (bet spread)."""
        metric = self.metric
        units = 1
        for threshold, u in self.system.bet_ramp:
            if metric >= threshold:
                units = u
        return units

    def advantage(self, edge_per_tc: float = EDGE_PER_TRUE_COUNT,
                  pivot: float = 1.0) -> float:
        """Оценка преимущества игрока (доля от ставки) по текущему счёту.

        ``pivot`` — точка, где преимущество равно нулю (обычно true count ≈ 1).
        """
        return edge_per_tc * (self.metric - pivot)

    def kelly_units(self, bankroll: float, unit: float, fraction: float = 0.5,
                    variance: float = VARIANCE_PER_UNIT,
                    edge_per_tc: float = EDGE_PER_TRUE_COUNT, pivot: float = 1.0,
                    min_units: int = 1) -> int:
        """Дробный Kelly: ставка пропорциональна банку и преимуществу.

        Оптимальная доля банка ``f = преимущество / дисперсия``; при
        ``fraction < 1`` используется дробный Kelly (например, 0.5 — half Kelly).
        При неблагоприятном счёте ставка равна ``min_units``.
        """
        if unit <= 0:
            return min_units
        adv = self.advantage(edge_per_tc, pivot)
        if adv <= 0 or bankroll <= 0:
            return min_units
        f = fraction * adv / variance
        units = int((bankroll * f) / unit)
        return max(min_units, units)

    def summary(self) -> str:
        if self.system.balanced:
            return (
                f"RC={self.running_count:+.0f}  TC={self.true_count:+.1f}  "
                f"(колод ост. {self.decks_remaining:.1f}, ставка {self.bet_units()}u)"
            )
        return (
            f"RC={self.running_count:+.0f}  метрика={self.metric:+.0f}  "
            f"(ставка {self.bet_units()}u)"
        )
