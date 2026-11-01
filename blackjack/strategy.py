"""Базовая стратегия и индексные отклонения (Illustrious 18).

Таблицы записаны строками по 10 символов — по одному на карту дилера
в порядке ``2 3 4 5 6 7 8 9 10 A``.

Коды действий:
  H = hit, S = stand, D = double (если нельзя — откат), P = split.
"""

from __future__ import annotations

from .cards import RANK_VALUE, hand_total, is_pair, pair_rank

DEALER_UPCARDS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]  # 11 = Ace

ACTION_HIT = "hit"
ACTION_STAND = "stand"
ACTION_DOUBLE = "double"
ACTION_SPLIT = "split"
ACTION_SURRENDER = "surrender"

# Игрок не может получить больше 21, поэтому таблица покрывает 5..21.
HARD = {
    5: "HHHHHHHHHH",
    6: "HHHHHHHHHH",
    7: "HHHHHHHHHH",
    8: "HHHHHHHHHH",
    9: "HDDDDHHHHH",
    10: "DDDDDDDDHH",
    11: "DDDDDDDDDD",
    12: "HHSSSHHHHH",
    13: "SSSSSSHHHH",
    14: "SSSSSSHHHH",
    15: "SSSSSSHHHH",
    16: "SSSSSSHHHH",
    17: "SSSSSSSSSS",
    18: "SSSSSSSSSS",
    19: "SSSSSSSSSS",
    20: "SSSSSSSSSS",
    21: "SSSSSSSSSS",
}

# Мягкие руки: ключ — сумма с тузом за 11.
SOFT = {
    13: "HHHDDHHHHH",
    14: "HHHDDHHHHH",
    15: "HHDDDHHHHH",
    16: "HHDDDHHHHH",
    17: "HDDDDHHHHH",
    18: "SDDDDSSHHH",
    19: "SSSSDSSSSS",
    20: "SSSSSSSSSS",
    21: "SSSSSSSSSS",
}

PAIRS = {
    "A": "PPPPPPPPPP",
    "2": "PPPPPPHHHH",
    "3": "PPPPPPHHHH",
    "4": "HHHPPHHHHH",
    "5": None,  # никогда не сплитим — считаем как твёрдые 10
    "6": "PPPPPPHHHH",
    "7": "PPPPPPHHHH",
    "8": "PPPPPPPPPP",
    "9": "PPPPPPSPSS",
    "10": None,  # никогда не сплитим — считаем как твёрдые 20
    "J": None,
    "Q": None,
    "K": None,
}


def up_value(rank: str) -> int:
    """Числовое значение карты дилера (Ace = 11)."""
    return 11 if rank == "A" else RANK_VALUE[rank]


def _resolve(code: str, available: set, fallback: str) -> str:
    if code == "D":
        return ACTION_DOUBLE if ACTION_DOUBLE in available else fallback
    if code == "H":
        return ACTION_HIT
    if code == "S":
        return ACTION_STAND
    return code


def basic_strategy(cards, dealer_rank: str, rules, available=None) -> str:
    """Возвращает оптимальное действие по базовой стратегии.

    ``available`` — множество разрешённых на данном шаге действий
    (hit/stand/double/split/surrender). По умолчанию считаются разрешёнными все.
    """
    if available is None:
        available = {ACTION_HIT, ACTION_STAND, ACTION_DOUBLE, ACTION_SPLIT, ACTION_SURRENDER}

    up = up_value(dealer_rank)
    idx = DEALER_UPCARDS.index(up)
    total, soft = hand_total(cards)

    # Сюррендер (поздний) проверяем самым первым.
    if ACTION_SURRENDER in available and rules.surrender and len(cards) == 2:
        if total == 16 and up in (9, 10, 11):
            return ACTION_SURRENDER
        if total == 15 and up == 10:
            return ACTION_SURRENDER

    # Пары.
    if is_pair(cards) and ACTION_SPLIT in available:
        table = PAIRS.get(pair_rank(cards))
        if table is not None:
            code = table[idx]
            if code == "P":
                return ACTION_SPLIT
            if code in ("H", "S"):
                return _resolve(code, available, ACTION_HIT)

    # Мягкие руки.
    if soft:
        table = SOFT.get(total)
        if table:
            fallback = ACTION_STAND if total >= 18 else ACTION_HIT
            return _resolve(table[idx], available, fallback)

    # Твёрдые руки.
    table = HARD.get(min(total, 21))
    if table:
        return _resolve(table[idx], available, ACTION_HIT)

    return ACTION_STAND


# --- Индексные отклонения (Illustrious 18, сокращённый набор) ---------------
#
# Каждая запись: (условие на руку/карту дилера) -> порог true count и действие.
# Работает только для balanced-систем (где определён true count).

def deviation_action(cards, dealer_rank: str, true_count, available, rules) -> str | None:
    """Действие по индексу или None, если отклонение не срабатывает."""
    if true_count is None:
        return None

    up = up_value(dealer_rank)
    total, soft = hand_total(cards)

    def ok(action: str) -> bool:
        return action in available

    # Сплит десяток против 5/6 при очень высоком счёте.
    if is_pair(cards) and pair_rank(cards) in ("10", "J", "Q", "K"):
        if up == 6 and true_count >= 4 and ok(ACTION_SPLIT):
            return ACTION_SPLIT
        if up == 5 and true_count >= 5 and ok(ACTION_SPLIT):
            return ACTION_SPLIT

    if soft:
        return None

    # Добор/стоп на твёрдых руках.
    if total == 16:
        if up == 10 and true_count >= 0 and ok(ACTION_STAND):
            return ACTION_STAND
        if up == 9 and true_count >= 5 and ok(ACTION_STAND):
            return ACTION_STAND
    if total == 15 and up == 10 and true_count >= 4 and ok(ACTION_STAND):
        return ACTION_STAND
    if total == 12:
        if up == 2 and true_count >= 3 and ok(ACTION_STAND):
            return ACTION_STAND
        if up == 3 and true_count >= 2 and ok(ACTION_STAND):
            return ACTION_STAND
        if up == 4 and true_count < 0 and ok(ACTION_HIT):
            return ACTION_HIT
        if up == 5 and true_count < -2 and ok(ACTION_HIT):
            return ACTION_HIT
        if up == 6 and true_count < -1 and ok(ACTION_HIT):
            return ACTION_HIT
    if total == 13:
        if up == 2 and true_count < -1 and ok(ACTION_HIT):
            return ACTION_HIT
        if up == 3 and true_count < -2 and ok(ACTION_HIT):
            return ACTION_HIT

    # Дабл на высоком счёте.
    if total == 11 and up == 11 and true_count >= 1 and ok(ACTION_DOUBLE):
        return ACTION_DOUBLE
    if total == 10:
        if up == 10 and true_count >= 4 and ok(ACTION_DOUBLE):
            return ACTION_DOUBLE
        if up == 11 and true_count >= 4 and ok(ACTION_DOUBLE):
            return ACTION_DOUBLE
    if total == 9:
        if up == 2 and true_count >= 1 and ok(ACTION_DOUBLE):
            return ACTION_DOUBLE
        if up == 7 and true_count >= 3 and ok(ACTION_DOUBLE):
            return ACTION_DOUBLE

    return None


def take_insurance(true_count, rules) -> bool:
    """Брать ли страховку: да при true count >= 3."""
    if not rules.insurance or true_count is None:
        return False
    return true_count >= 3
