"""Системы подсчёта карт.

Каждая система — это набор значений (тегов) для рангов, признак
balanced/unbalanced и (для unbalanced) начальный отсчёт (IRC).

* balanced   — сумма тегов полной колоды = 0. True count = running count / колод осталось.
* unbalanced — сумма тегов != 0. Работают с running count напрямую (см. bet_ramp).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

from ..cards import Card

# Ставки по умолчанию: список (порог метрики, юниты). Порядок по возрастанию.
# Всё, что ниже первого порога, — минимальная ставка (1 юнит).
DEFAULT_RAMP: List[Tuple[float, int]] = [(2, 2), (3, 4), (4, 6), (5, 8)]


@dataclass
class CountingSystem:
    name: str
    values: Dict[str, float]
    balanced: bool
    irc: Callable[[int], int] = lambda decks: 0
    bet_ramp: List[Tuple[float, int]] = field(default_factory=lambda: list(DEFAULT_RAMP))
    description: str = ""
    value_fn: Callable[[Card], float] | None = None

    def value(self, card: Card) -> float:
        """Тег карты."""
        if self.value_fn is not None:
            return self.value_fn(card)
        return self.values[card.rank]

    def initial_count(self, num_decks: int) -> int:
        """Начальный running count для данного числа колод."""
        return self.irc(num_decks)


def _tags(**kwargs) -> Dict[str, float]:
    """Хелпер: _tags(a=..., b=...) где ключи — ранги в виде строк."""
    return {str(k): float(v) for k, v in kwargs.items()}


# Значения рангов задаются компактно.

HI_LO = CountingSystem(
    name="Hi-Lo",
    values={
        **{r: 1 for r in "23456"},
        **{r: 0 for r in ("7", "8", "9")},
        **{r: -1 for r in ("10", "J", "Q", "K", "A")},
    },
    balanced=True,
    description="Классика: 2-6 = +1, 7-9 = 0, 10-A = -1.",
)

KO = CountingSystem(
    name="KO",
    values={
        **{r: 1 for r in "234567"},
        **{r: 0 for r in ("8", "9")},
        **{r: -1 for r in ("10", "J", "Q", "K", "A")},
    },
    balanced=False,
    irc=lambda decks: -4 * (decks - 1),
    # Метрика = running_count - IRC, поэтому пороги начинаются с 1.
    bet_ramp=[(1, 2), (2, 4), (3, 6), (4, 8)],
    description="Unbalanced: 2-7 = +1, 8-9 = 0, 10-A = -1, IRC = -4*(колод-1).",
)

HI_OPT_I = CountingSystem(
    name="Hi-Opt I",
    values={
        **{r: 0 for r in ("2", "7", "8", "9", "A")},
        **{r: 1 for r in "3456"},
        **{r: -1 for r in ("10", "J", "Q", "K")},
    },
    balanced=True,
    description="Туз не считается: 3-6 = +1, 10 = -1.",
)

HI_OPT_II = CountingSystem(
    name="Hi-Opt II",
    values={
        "2": 1, "3": 1, "4": 2, "5": 2, "6": 1, "7": 1,
        "8": 0, "9": 0,
        "10": -2, "J": -2, "Q": -2, "K": -2, "A": 0,
    },
    balanced=True,
    bet_ramp=[(1, 2), (2, 4), (3, 6), (4, 8)],
    description="Level 2: 2,3,6,7 = +1; 4,5 = +2; 10 = -2; A,8,9 = 0.",
)

ZEN = CountingSystem(
    name="Zen",
    values={
        "2": 1, "3": 1, "4": 2, "5": 2, "6": 2, "7": 1,
        "8": 0, "9": 0,
        "10": -2, "J": -2, "Q": -2, "K": -2, "A": -1,
    },
    balanced=True,
    bet_ramp=[(1, 2), (2, 4), (3, 6), (4, 8)],
    description="Level 2: 4,5,6 = +2; 10 = -2; A = -1.",
)

OMEGA_II = CountingSystem(
    name="Omega II",
    values={
        "2": 1, "3": 1, "4": 2, "5": 2, "6": 2, "7": 1,
        "8": 0, "9": -1,
        "10": -2, "J": -2, "Q": -2, "K": -2, "A": 0,
    },
    balanced=True,
    bet_ramp=[(1, 2), (2, 4), (3, 6), (4, 8)],
    description="Level 2 (Carlson): 4,5,6 = +2; 9 = -1; 10 = -2; A = 0.",
)

WONG_HALVES = CountingSystem(
    name="Wong Halves",
    values={
        "2": 0.5, "3": 1, "4": 1, "5": 1.5, "6": 1, "7": 0.5,
        "8": 0, "9": -0.5,
        "10": -1, "J": -1, "Q": -1, "K": -1, "A": -1,
    },
    balanced=True,
    bet_ramp=[(1, 2), (2, 4), (3, 6), (4, 8)],
    description="Level 3 с половинками: 2,7 = +0.5; 5 = +1.5; 9 = -0.5.",
)

# Red Seven: значение семёрки зависит от цвета (красная = +1, чёрная = 0).
def _red_seven_value(card: Card) -> float:
    if card.rank == "7":
        return 1 if card.is_red else 0
    if card.rank in {"2", "3", "4", "5", "6"}:
        return 1
    if card.rank in {"8", "9"}:
        return 0
    return -1  # 10/J/Q/K/A


RED_SEVEN = CountingSystem(
    name="Red Seven",
    values={},  # значения задаются через value_fn
    balanced=False,
    irc=lambda decks: -2 * (decks - 1),
    bet_ramp=[(1, 2), (2, 4), (3, 6), (4, 8)],
    description="Red 7 = +1, Black 7 = 0; 2-6 = +1; 8,9 = 0; 10-A = -1.",
    value_fn=_red_seven_value,
)


SYSTEMS: Dict[str, CountingSystem] = {
    s.name: s for s in [HI_LO, KO, HI_OPT_I, HI_OPT_II, ZEN, OMEGA_II, WONG_HALVES, RED_SEVEN]
}


def list_systems() -> List[CountingSystem]:
    return list(SYSTEMS.values())


def get_system(name: str) -> CountingSystem:
    """Получить систему по имени (без учёта регистра)."""
    for key, system in SYSTEMS.items():
        if key.lower() == name.lower():
            return system
    raise KeyError(f"Неизвестная система подсчёта: {name}")


def make_custom_system(name: str, values: Dict[str, float], balanced: bool = True,
                       bet_ramp=None) -> CountingSystem:
    """Создать пользовательскую систему подсчёта."""
    system = CountingSystem(
        name=name,
        values={str(k): float(v) for k, v in values.items()},
        balanced=balanced,
        bet_ramp=bet_ramp or list(DEFAULT_RAMP),
        description="Пользовательская система.",
    )
    return system
