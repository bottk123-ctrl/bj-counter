import pytest

from blackjack.cards import Card
from blackjack.counting import CardCounter, get_system, list_systems


def _cards(ranks, suit="\u2660"):
    return [Card(r, suit) for r in ranks]


def test_hi_lo_values():
    hi_lo = get_system("Hi-Lo")
    assert hi_lo.value(Card("2", "\u2660")) == 1
    assert hi_lo.value(Card("6", "\u2660")) == 1
    assert hi_lo.value(Card("9", "\u2660")) == 0
    assert hi_lo.value(Card("10", "\u2660")) == -1
    assert hi_lo.value(Card("A", "\u2660")) == -1


def test_hi_lo_running_count():
    counter = CardCounter(get_system("Hi-Lo"), num_decks=6)
    counter.observe_many(_cards(["2", "3", "4", "5", "6"]))
    assert counter.running_count == 5
    counter.observe_many(_cards(["10", "J", "Q", "K", "A"]))
    assert counter.running_count == 0


def test_true_count():
    counter = CardCounter(get_system("Hi-Lo"), num_decks=6)
    counter.observe_many(_cards(["2"] * 26))  # половина колоды младших
    assert counter.running_count == 26
    assert counter.decks_remaining == pytest.approx(5.5)
    assert counter.true_count == pytest.approx(26 / 5.5)


def test_true_count_none_for_unbalanced():
    counter = CardCounter(get_system("KO"), num_decks=6)
    assert counter.true_count is None


def test_ko_initial_count():
    assert get_system("KO").initial_count(6) == -20
    assert get_system("KO").initial_count(1) == 0


def test_balanced_systems_sum_to_zero():
    """У balanced-систем сумма тегов полной колоды должна быть равна нулю."""
    ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    for system in list_systems():
        if system.balanced and system.value_fn is None:
            total = sum(system.value(Card(r, "\u2660")) for r in ranks)
            assert total == pytest.approx(0), f"{system.name} не сбалансирована: {total}"


def test_red_seven_color_dependence():
    red_seven = get_system("Red Seven")
    assert red_seven.value(Card("7", "\u2665")) == 1  # красная семёрка
    assert red_seven.value(Card("7", "\u2660")) == 0  # чёрная семёрка
    assert red_seven.value(Card("3", "\u2660")) == 1
    assert red_seven.value(Card("K", "\u2660")) == -1


def test_wong_halves_fractional_values():
    halves = get_system("Wong Halves")
    assert halves.value(Card("5", "\u2660")) == 1.5
    assert halves.value(Card("2", "\u2660")) == 0.5


def test_reset_clears_count():
    counter = CardCounter(get_system("Hi-Lo"), num_decks=6)
    counter.observe_many(_cards(["2", "2", "2"]))
    assert counter.running_count == 3
    counter.reset()
    assert counter.running_count == 0
    assert counter.cards_seen == 0


def test_bet_units_grow_with_count():
    counter = CardCounter(get_system("Hi-Lo"), num_decks=6)
    assert counter.bet_units() == 1
    counter.observe_many(_cards(["2"] * 26))
    # true count около 4.7 -> высокая ставка
    assert counter.bet_units() >= 6
