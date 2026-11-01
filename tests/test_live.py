import pytest

from blackjack.counting import get_system
from modes.live import LiveSession, parse_card, state_line, suit_symbol


def test_parse_card_ascii_suit():
    card = parse_card("10h")
    assert card.rank == "10"
    assert card.is_red


def test_parse_card_ace_and_unicode():
    card = parse_card("a\u2660")
    assert card.rank == "A"
    assert not card.is_red


def test_parse_card_ten_alias():
    assert parse_card("ts").rank == "10"
    assert parse_card("kd").rank == "K"


def test_parse_card_invalid():
    with pytest.raises(ValueError):
        parse_card("xy")
    with pytest.raises(ValueError):
        parse_card("z")


def test_live_session_count_and_undo():
    session = LiveSession(get_system("Hi-Lo"), num_decks=6)
    session.add(parse_card("2s"))
    session.add(parse_card("10h"))
    assert session.running_count == 0
    assert session.cards_seen == 2
    removed = session.undo()
    assert removed is not None
    assert session.cards_seen == 1
    assert session.running_count == 1


def test_live_session_reset():
    session = LiveSession(get_system("Hi-Lo"), num_decks=6)
    session.add(parse_card("5s"))
    session.reset()
    assert session.cards_seen == 0
    assert session.running_count == 0


def test_live_session_change_decks_rebuilds():
    session = LiveSession(get_system("Hi-Lo"), num_decks=6)
    session.add(parse_card("5s"))
    session.add(parse_card("6s"))
    session.set_num_decks(2)
    assert session.num_decks == 2
    assert session.running_count == 2


def test_bet_units_grow_in_live_session():
    session = LiveSession(get_system("Hi-Lo"), num_decks=6)
    for _ in range(26):
        session.add(parse_card("5s"))
    # половина колоды младших -> высокий true count
    assert session.bet_units >= 6


def test_state_line_contains_counts():
    session = LiveSession(get_system("Hi-Lo"), num_decks=6)
    session.add(parse_card("10s"))
    line = state_line(session)
    assert "RC=" in line and "TC=" in line


def test_suit_symbol_roundtrip():
    assert suit_symbol("S") in ("\u2660", "S")
    assert suit_symbol("H") in ("\u2665", "H")
