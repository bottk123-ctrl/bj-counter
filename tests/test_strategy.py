from blackjack.cards import Card
from blackjack.rules import Rules
from blackjack.strategy import (
    ACTION_DOUBLE,
    ACTION_HIT,
    ACTION_SPLIT,
    ACTION_STAND,
    basic_strategy,
    deviation_action,
    take_insurance,
)

RULES = Rules()


def _hand(ranks):
    return [Card(r, "\u2660") for r in ranks]


def test_hard_16_vs_10_hits():
    assert basic_strategy(_hand(["10", "6"]), "10", RULES) == ACTION_HIT


def test_hard_11_vs_6_doubles():
    assert basic_strategy(_hand(["5", "6"]), "6", RULES) == ACTION_DOUBLE


def test_hard_12_vs_4_stands():
    assert basic_strategy(_hand(["10", "2"]), "4", RULES) == ACTION_STAND


def test_hard_12_vs_2_hits():
    assert basic_strategy(_hand(["10", "2"]), "2", RULES) == ACTION_HIT


def test_soft_18_vs_5_doubles():
    assert basic_strategy(_hand(["A", "7"]), "5", RULES) == ACTION_DOUBLE


def test_soft_18_vs_9_hits():
    assert basic_strategy(_hand(["A", "7"]), "9", RULES) == ACTION_HIT


def test_pair_eights_always_split():
    assert basic_strategy(_hand(["8", "8"]), "10", RULES) == ACTION_SPLIT


def test_pair_fives_never_split_doubles():
    assert basic_strategy(_hand(["5", "5"]), "6", RULES) == ACTION_DOUBLE


def test_double_falls_back_to_hit_when_not_allowed():
    # 11 vs 6: дабл запрещён -> добираем
    assert basic_strategy(_hand(["5", "6"]), "6", RULES, available={ACTION_HIT, ACTION_STAND}) == ACTION_HIT


def test_soft_double_falls_back_to_stand():
    # мягкие 18 vs 5: дабл запрещён -> стоп
    assert basic_strategy(_hand(["A", "7"]), "5", RULES, available={ACTION_HIT, ACTION_STAND}) == ACTION_STAND


def test_deviation_16_vs_10_stands_at_high_count():
    assert deviation_action(_hand(["10", "6"]), "10", 3.0, {ACTION_HIT, ACTION_STAND}, RULES) == ACTION_STAND


def test_deviation_not_triggered_at_low_count():
    # 16 vs 10 по индексу стоит только при true count >= 0
    assert deviation_action(_hand(["10", "6"]), "10", -1.0, {ACTION_HIT, ACTION_STAND}, RULES) is None


def test_take_insurance_at_high_true_count():
    assert take_insurance(3.2, RULES) is True
    assert take_insurance(2.9, RULES) is False
