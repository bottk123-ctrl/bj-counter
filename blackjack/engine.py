"""Движок блэкджека: раунд, действия игрока, дилер, выплаты."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .cards import Card, Shoe, cards_to_str, hand_total
from .rules import Rules


@dataclass
class Hand:
    """Одна рука игрока."""

    cards: list[Card] = field(default_factory=list)
    bet: float = 0.0
    doubled: bool = False
    from_split: bool = False
    split_aces: bool = False
    surrendered: bool = False
    stood: bool = False
    blackjack: bool = False

    @property
    def total(self) -> int:
        return hand_total(self.cards)[0]

    @property
    def soft(self) -> bool:
        return hand_total(self.cards)[1]

    @property
    def is_bust(self) -> bool:
        return self.total > 21

    @property
    def done(self) -> bool:
        return (
            self.surrendered
            or self.stood
            or self.doubled
            or self.blackjack
            or self.is_bust
            or self.total >= 21
        )

    def __str__(self) -> str:
        return cards_to_str(self.cards)


@dataclass
class RoundResult:
    result: str  # win/lose/push/blackjack/surrender/insurance
    bet: float
    net: float


class Round:
    """Один раунд: раздача, ходы игрока, игра дилера, расчёт."""

    def __init__(self, rules: Rules, shoe, bet: float):
        self.rules = rules
        self.shoe = shoe
        self.player: list[Hand] = [Hand(cards=[shoe.deal(), shoe.deal()], bet=bet)]
        self.dealer: list[Card] = [shoe.deal(), shoe.deal()]
        self.hole_hidden = True
        self.insurance = 0.0
        self.settled = False
        self.results: list[RoundResult] = []
        if self.player[0].total == 21:
            self.player[0].blackjack = True

    # --- свойства -----------------------------------------------------------
    @property
    def dealer_upcard(self) -> Card:
        return self.dealer[0]

    @property
    def dealer_has_ace(self) -> bool:
        return self.dealer[0].is_ace

    @property
    def dealer_has_ten_up(self) -> bool:
        return self.dealer[0].is_ten

    @property
    def dealer_blackjack(self) -> bool:
        return len(self.dealer) == 2 and hand_total(self.dealer)[0] == 21

    @property
    def dealer_total(self) -> int:
        return hand_total(self.dealer)[0]

    @property
    def dealer_soft(self) -> bool:
        return hand_total(self.dealer)[1]

    # --- страховка ----------------------------------------------------------
    def take_insurance(self, amount: float) -> None:
        if not self.rules.insurance:
            raise ValueError("Страховка недоступна по правилам стола")
        self.insurance = amount

    def peek_blackjack(self) -> bool:
        """Если дилер проверяет BJ — вернуть True при блэкджеке дилера."""
        return self.rules.dealer_peeks and self.dealer_blackjack

    # --- действия игрока ----------------------------------------------------
    def available_actions(self, i: int = 0) -> set[str]:
        hand = self.player[i]
        if hand.done:
            return set()
        actions = {"hit", "stand"}

        if len(hand.cards) == 2 and self.rules.can_double_on(hand):
            if not hand.from_split or self.rules.double_after_split:
                actions.add("double")

        if self._can_split(hand):
            actions.add("split")

        if (
            self.rules.surrender
            and len(hand.cards) == 2
            and not hand.from_split
            and len(self.player) == 1
        ):
            actions.add("surrender")

        return actions

    def _can_split(self, hand: Hand) -> bool:
        if len(hand.cards) != 2 or hand.cards[0].rank != hand.cards[1].rank:
            return False
        if hand.cards[0].is_ace and hand.from_split and not self.rules.resplit_aces:
            return False
        splits_done = len(self.player) - 1
        return splits_done < self.rules.max_splits

    def apply(self, action: str, i: int = 0) -> Hand:
        """Выполнить действие и вернуть изменённую руку."""
        hand = self.player[i]
        action = action.lower()
        if action not in self.available_actions(i):
            raise ValueError(f"Недопустимое действие «{action}» для руки {i}")

        if action == "hit":
            hand.cards.append(self.shoe.deal())
            self._auto_done(hand)
        elif action == "stand":
            hand.stood = True
        elif action == "double":
            hand.bet *= 2
            hand.doubled = True
            hand.cards.append(self.shoe.deal())
        elif action == "surrender":
            hand.surrendered = True
        elif action == "split":
            self._split(i)
        return hand

    def _auto_done(self, hand: Hand) -> None:
        if hand.split_aces:
            # Разделённые тузы получают только одну карту (если не разрешён ре-сплит тузов).
            if (
                hand.cards[0].is_ace
                and hand.cards[1].is_ace
                and self.rules.resplit_aces
                and (len(self.player) - 1) < self.rules.max_splits
            ):
                return
            hand.stood = True
            return
        if hand.total >= 21:
            hand.stood = True

    def _split(self, i: int) -> None:
        hand = self.player[i]
        moved = hand.cards.pop()
        new_hand = Hand(cards=[moved, self.shoe.deal()], bet=hand.bet, from_split=True)
        hand.cards.append(self.shoe.deal())
        hand.from_split = True

        splitting_aces = moved.is_ace  # обе карты одного ранга
        if splitting_aces:
            hand.split_aces = True
            new_hand.split_aces = True

        # После сплита 21 — не блэкджек.
        hand.blackjack = False
        self.player.insert(i + 1, new_hand)

        for h in (hand, new_hand):
            self._auto_done(h)

    # --- дилер --------------------------------------------------------------
    def _dealer_should_hit(self) -> bool:
        total, soft = hand_total(self.dealer)
        if total < 17:
            return True
        if total == 17 and soft and self.rules.dealer_hits_soft_17:
            return True
        return False

    def play_dealer(self) -> None:
        """Открыть карту дилера и добрать по правилам."""
        self.hole_hidden = False
        if not any(not h.is_bust and not h.surrendered for h in self.player):
            return  # все руки игрока проиграны — дилер не добирает
        while self._dealer_should_hit():
            self.dealer.append(self.shoe.deal())

    # --- расчёт -------------------------------------------------------------
    def settle(self) -> list[RoundResult]:
        if self.settled:
            return self.results

        dealer_bj = self.dealer_blackjack
        dealer_total = self.dealer_total
        payout = self.rules.blackjack_payout
        results: list[RoundResult] = []

        for hand in self.player:
            bet = hand.bet
            if hand.surrendered:
                results.append(RoundResult("surrender", bet, -bet / 2))
            elif hand.is_bust:
                results.append(RoundResult("lose", bet, -bet))
            elif hand.blackjack and not dealer_bj:
                results.append(RoundResult("blackjack", bet, bet * payout))
            elif dealer_bj and hand.blackjack:
                results.append(RoundResult("push", bet, 0.0))
            elif dealer_bj:
                results.append(RoundResult("lose", bet, -bet))
            elif dealer_total > 21 or hand.total > dealer_total:
                results.append(RoundResult("win", bet, bet))
            elif hand.total < dealer_total:
                results.append(RoundResult("lose", bet, -bet))
            else:
                results.append(RoundResult("push", bet, 0.0))

        if self.insurance:
            net = self.insurance * 2 if dealer_bj else -self.insurance
            results.append(RoundResult("insurance", self.insurance, net))

        self.results = results
        self.settled = True
        return results

    def net(self) -> float:
        return sum(r.net for r in self.results)


class BlackjackGame:
    """Управляет шузом и создаёт раунды."""

    def __init__(self, rules: Rules | None = None, seed: int | None = None):
        self.rules = rules or Rules()
        self.rng = random.Random(seed)
        self.shoe = Shoe(self.rules.num_decks, self.rules.penetration, self.rng)
        self.rounds_played = 0
        self.shoe_number = 0

    def start_round(self, bet: float) -> Round:
        if self.shoe.needs_shuffle():
            self.shoe.shuffle()
            self.shoe_number += 1
        self.rounds_played += 1
        return Round(self.rules, self.shoe, bet)
