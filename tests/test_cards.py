from blackjack.cards import Card, Shoe, hand_total, is_pair, pair_rank


def test_hand_total_blackjack_is_soft():
    total, soft = hand_total([Card("A", "\u2660"), Card("K", "\u2665")])
    assert total == 21
    assert soft is True


def test_hand_total_soft_17():
    assert hand_total([Card("A", "\u2660"), Card("6", "\u2665")]) == (17, True)


def test_hand_total_multiple_aces():
    assert hand_total([Card("A", "\u2660"), Card("A", "\u2665"), Card("9", "\u2666")]) == (21, True)


def test_hand_total_ace_downgrade():
    assert hand_total([Card("A", "\u2660"), Card("10", "\u2665"), Card("5", "\u2666")]) == (16, False)


def test_hand_total_bust():
    assert hand_total([Card("10", "\u2660"), Card("10", "\u2665"), Card("5", "\u2666")]) == (25, False)


def test_is_pair():
    assert is_pair([Card("8", "\u2660"), Card("8", "\u2665")])
    assert not is_pair([Card("8", "\u2660"), Card("9", "\u2665")])
    assert pair_rank([Card("K", "\u2660"), Card("K", "\u2665")]) == "K"


def test_shoe_size_and_shuffle():
    shoe = Shoe(num_decks=2, penetration=0.5)
    assert shoe.total == 104
    assert shoe.remaining == 104
    for _ in range(10):
        shoe.deal()
    assert shoe.dealt == 10
    assert shoe.remaining == 94
    shoe.shuffle()
    assert shoe.dealt == 0


def test_shoe_needs_shuffle():
    shoe = Shoe(num_decks=1, penetration=0.5)
    assert not shoe.needs_shuffle()
    for _ in range(26):
        shoe.deal()
    assert shoe.needs_shuffle()
