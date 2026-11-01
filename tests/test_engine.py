from blackjack.cards import Card
from blackjack.engine import BlackjackGame, Round
from blackjack.rules import Rules


class FakeShoe:
    """Шуз, отдающий заранее заданные карты."""

    def __init__(self, cards):
        self.cards = list(cards)
        self.i = 0

    def deal(self):
        card = self.cards[self.i]
        self.i += 1
        return card


def _c(rank, suit="\u2660"):
    return Card(rank, suit)


def test_to_dict_helper_rules_default():
    rules = Rules()
    assert rules.num_decks == 6
    assert rules.dealer_hits_soft_17 is False


def test_player_blackjack_payout():
    # игрок: A,K (21); дилер: 5,9 (14), добирает и перебирает
    shoe = FakeShoe([_c("A"), _c("K"), _c("5"), _c("9"), _c("10"), _c("2")])
    rnd = Round(Rules(), shoe, bet=10)
    assert rnd.player[0].blackjack
    rnd.play_dealer()
    results = rnd.settle()
    assert results[0].result == "blackjack"
    assert results[0].net == 15.0


def test_both_blackjack_push():
    shoe = FakeShoe([_c("A"), _c("K"), _c("A"), _c("Q")])
    rnd = Round(Rules(), shoe, bet=10)
    assert rnd.dealer_blackjack
    results = rnd.settle()
    assert results[0].result == "push"
    assert results[0].net == 0.0


def test_dealer_blackjack_beats_player():
    shoe = FakeShoe([_c("10"), _c("6"), _c("A"), _c("Q")])
    rnd = Round(Rules(), shoe, bet=10)
    rnd.player[0].stood = True
    rnd.play_dealer()
    results = rnd.settle()
    assert results[0].result == "lose"
    assert results[0].net == -10.0


def test_player_bust_loses():
    shoe = FakeShoe([_c("10"), _c("6"), _c("5"), _c("9"), _c("K")])
    rnd = Round(Rules(), shoe, bet=10)
    assert "hit" in rnd.available_actions(0)
    rnd.apply("hit", 0)
    assert rnd.player[0].is_bust
    rnd.play_dealer()
    results = rnd.settle()
    assert results[0].net == -10.0


def test_double_doubles_bet_and_deals_one():
    shoe = FakeShoe([_c("5"), _c("6"), _c("6"), _c("9"), _c("K")])
    rnd = Round(Rules(), shoe, bet=10)
    rnd.apply("double", 0)
    assert rnd.player[0].bet == 20.0
    assert rnd.player[0].doubled
    assert len(rnd.player[0].cards) == 3


def test_split_creates_two_hands():
    shoe = FakeShoe([_c("8"), _c("8"), _c("6"), _c("9"), _c("3"), _c("2")])
    rnd = Round(Rules(), shoe, bet=10)
    assert "split" in rnd.available_actions(0)
    rnd.apply("split", 0)
    assert len(rnd.player) == 2
    assert all(h.from_split for h in rnd.player)
    # после сплита 21 не считается блэкджеком
    assert not any(h.blackjack for h in rnd.player)


def test_dealer_draws_to_17():
    shoe = FakeShoe([_c("2"), _c("3"), _c("5"), _c("6"), _c("10"), _c("4")])
    rnd = Round(Rules(), shoe, bet=10)
    rnd.play_dealer()
    assert rnd.dealer_total == 21


def test_surrender_loses_half():
    rules = Rules(surrender=True)
    shoe = FakeShoe([_c("10"), _c("6"), _c("9"), _c("7")])
    rnd = Round(rules, shoe, bet=10)
    assert "surrender" in rnd.available_actions(0)
    rnd.apply("surrender", 0)
    results = rnd.settle()
    assert results[0].net == -5.0


def test_insurance_pays_on_dealer_blackjack():
    shoe = FakeShoe([_c("10"), _c("6"), _c("A"), _c("Q")])
    rnd = Round(Rules(), shoe, bet=10)
    rnd.take_insurance(5.0)
    results = rnd.settle()
    ins = [r for r in results if r.result == "insurance"][0]
    assert ins.net == 10.0  # выплата 2:1


def test_game_start_round_and_reshuffle():
    game = BlackjackGame(Rules(num_decks=1, penetration=0.2), seed=42)
    rnd = game.start_round(10)
    assert len(rnd.player[0].cards) == 2
    assert len(rnd.dealer) == 2
    assert game.rounds_played == 1
