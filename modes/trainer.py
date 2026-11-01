"""Тренажёр: подсчёт карт и игра против дилера."""

from __future__ import annotations

from blackjack.cards import Shoe, cards_to_str
from blackjack.counting import CardCounter
from blackjack.engine import BlackjackGame
from blackjack.rules import Rules
from blackjack.strategy import basic_strategy

LETTER_TO_ACTION = {"h": "hit", "s": "stand", "d": "double", "p": "split", "r": "surrender"}
ACTION_TO_LETTER = {v: k for k, v in LETTER_TO_ACTION.items()}
ACTION_RU = {
    "hit": "добор",
    "stand": "стоп",
    "double": "дабл",
    "split": "сплит",
    "surrender": "сюррендер",
}


def _ask_int(prompt: str):
    raw = input(prompt).strip()
    if raw in ("", "q", "quit", "выход"):
        return None
    try:
        return int(raw)
    except ValueError:
        print("  ! Введите целое число.")
        return _ask_int(prompt)


class TrainerSession:
    def __init__(self, system, rules: Rules, seed: int | None = None, store=None):
        self.system = system
        self.rules = rules
        self.game = BlackjackGame(rules, seed)
        self.counter = CardCounter(system, rules.num_decks)
        self.store = store
        self.stats = {
            "rounds": 0,
            "actions_total": 0,
            "actions_correct": 0,
            "count_checks": 0,
            "count_correct": 0,
        }

    # --- учёт статистики (если подключено хранилище) -----------------------
    def _store_decision(self, correct: bool) -> None:
        if self.store is not None:
            self.store.record_decision(correct, save=False)

    def _store_count(self, correct: bool) -> None:
        if self.store is not None:
            self.store.record_count(correct, save=False)

    def _store_round(self) -> None:
        if self.store is not None:
            self.store.record_round(save=False)

    def _flush(self) -> None:
        if self.store is not None:
            self.store.save()

    # --- тренировка счёта ---------------------------------------------------
    def run_count_drill(self, ask_every: int = 5, with_true_count: bool = True) -> None:
        print("\n--- Тренажёр счёта ---")
        print("Показываю карты. Каждые", ask_every, "карт(ы) спрашиваю running count.")
        if with_true_count and self.system.balanced:
            print("Дополнительно спрашиваю true count (округлённо).")
        print("В любой момент для выхода введите 'q'.\n")

        shoe = Shoe(self.rules.num_decks, penetration=0.85)
        counter = CardCounter(self.system, self.rules.num_decks)
        dealt = 0
        try:
            while not shoe.needs_shuffle() and shoe.remaining > 0:
                batch = []
                for _ in range(ask_every):
                    if shoe.remaining == 0:
                        break
                    card = shoe.deal()
                    counter.observe(card)
                    batch.append(card)
                dealt += len(batch)
                print("Карты:", cards_to_str(batch))

                answer = _ask_int("  Running count? ")
                if answer is None:
                    print("  Выход из тренажёра счёта.")
                    return
                correct = answer == round(counter.running_count)
                self.stats["count_checks"] += 1
                if correct:
                    self.stats["count_correct"] += 1
                    print("  Верно! RC =", round(counter.running_count))
                else:
                    print(f"  Неверно. Правильно RC = {round(counter.running_count)}")
                self._store_count(correct)

                if with_true_count and self.system.balanced:
                    tc_answer = _ask_int("  True count? ")
                    if tc_answer is None:
                        print("  Выход из тренажёра счёта.")
                        return
                    real_tc = round(counter.true_count)
                    correct_tc = tc_answer == real_tc
                    self.stats["count_checks"] += 1
                    if correct_tc:
                        self.stats["count_correct"] += 1
                        print(f"  Верно! TC = {real_tc}")
                    else:
                        print(f"  Неверно. Правильно TC = {real_tc:.1f} "
                              f"(колод осталось {counter.decks_remaining:.1f})")
                    self._store_count(correct_tc)
                print(f"  [подсказка] {counter.summary()}")
        except (EOFError, KeyboardInterrupt):
            print("\nПрервано.")
            return
        print("\nШуз закончился. Итог:", self._count_stats())

    # --- тренировка игры ----------------------------------------------------
    def run_play_drill(self, base_bet: float = 10.0, ask_count_every_round: bool = True) -> None:
        print("\n--- Игра против дилера ---")
        print("Действия: h=hit  s=stand  d=double  p=split  r=surrender  q=выход")
        print("После руки спрашиваю счёт, чтобы тренировать и стратегию, и подсчёт.\n")
        try:
            while True:
                if self.game.shoe.needs_shuffle():
                    self.game.shoe.shuffle()
                    self.counter.reset()
                    print(">> Новый шуз, счёт сброшен.\n")

                rnd = self.game.start_round(base_bet)
                seen: set[int] = set()

                def see(card) -> None:
                    if id(card) not in seen:
                        seen.add(id(card))
                        self.counter.observe(card)

                def see_player() -> None:
                    for h in rnd.player:
                        for c in h.cards:
                            see(c)

                def see_dealer_revealed() -> None:
                    for c in rnd.dealer[1:]:
                        see(c)

                see_player()
                see(rnd.dealer[0])
                print(f"Дилер: {rnd.dealer[0]}  [скрытая]")
                print(f"Ваша рука: {cards_to_str(rnd.player[0].cards)}  (сумма {rnd.player[0].total})")

                if rnd.dealer_has_ace and self.rules.insurance:
                    ans = input("  Страховка? (y/n) ").strip().lower()
                    if ans == "q":
                        print("Выход.")
                        return
                    if ans == "y":
                        rnd.take_insurance(base_bet / 2)

                early_done = False
                if self.rules.dealer_peeks and (rnd.dealer_has_ace or rnd.dealer_has_ten_up):
                    if rnd.dealer_blackjack:
                        see(rnd.dealer[1])  # блэкджек вскрывается — учитываем карту
                        print("  Дилер проверяет — блэкджек!")
                        early_done = True

                if not early_done:
                    i = 0
                    quit_flag = False
                    while i < len(rnd.player):
                        while True:
                            acts = rnd.available_actions(i)
                            if not acts:
                                break
                            hand = rnd.player[i]
                            tag = f"[рука {i + 1}] " if len(rnd.player) > 1 else ""
                            correct = basic_strategy(hand.cards, rnd.dealer_upcard.rank, self.rules, acts)
                            letters = "/".join(ACTION_TO_LETTER[a] for a in
                                               ["hit", "stand", "double", "split", "surrender"] if a in acts)
                            raw = input(f"  {tag}{cards_to_str(hand.cards)} (сумма {hand.total}) "
                                        f"[{letters}]: ").strip().lower()
                            if raw in ("q", "quit", "выход"):
                                print("Выход.")
                                return
                            if raw not in LETTER_TO_ACTION or LETTER_TO_ACTION[raw] not in acts:
                                print("  ! Недопустимое действие.")
                                continue
                            action = LETTER_TO_ACTION[raw]
                            self.stats["actions_total"] += 1
                            action_ok = action == correct
                            if action_ok:
                                self.stats["actions_correct"] += 1
                                print("  Верно.")
                            else:
                                print(f"  По базовой стратегии лучше: "
                                      f"{ACTION_RU[correct]} ({ACTION_TO_LETTER[correct]})")
                            self._store_decision(action_ok)
                            rnd.apply(action, i)
                            see_player()
                        i += 1

                rnd.play_dealer()
                see_dealer_revealed()
                results = rnd.settle()
                self.stats["rounds"] += 1
                self._store_round()

                print(f"  Дилер набрал: {cards_to_str(rnd.dealer)} (сумма {rnd.dealer_total})")
                for j, r in enumerate(results):
                    print(f"    {r.result}: ставка {r.bet:.0f}, итог {r.net:+.2f}")

                if ask_count_every_round:
                    self._check_count()
                print()
        except (EOFError, KeyboardInterrupt):
            print("\nПрервано.")
            return

    def _check_count(self) -> None:
        answer = _ask_int("  Running count за столом? ")
        if answer is None:
            return
        self.stats["count_checks"] += 1
        rc_ok = answer == round(self.counter.running_count)
        if rc_ok:
            self.stats["count_correct"] += 1
            print("    Счёт верный!")
        else:
            print(f"    Неверно: RC = {round(self.counter.running_count)}")
        self._store_count(rc_ok)
        if self.system.balanced:
            tc_answer = _ask_int("  True count? ")
            if tc_answer is None:
                return
            self.stats["count_checks"] += 1
            real_tc = round(self.counter.true_count)
            tc_ok = tc_answer == real_tc
            if tc_ok:
                self.stats["count_correct"] += 1
                print("    True count верный!")
            else:
                print(f"    Неверно: TC = {real_tc} (колод осталось {self.counter.decks_remaining:.1f})")
            self._store_count(tc_ok)
        print(f"    [подсказка] {self.counter.summary()}")

    def _count_stats(self) -> str:
        s = self.stats
        if s["count_checks"]:
            acc = 100 * s["count_correct"] / s["count_checks"]
            return f"проверок счёта {s['count_checks']}, верно {acc:.0f}%"
        return "нет проверок"

    def summary(self) -> str:
        s = self.stats
        parts = []
        if s["actions_total"]:
            acc = 100 * s["actions_correct"] / s["actions_total"]
            parts.append(f"решения: {s['actions_correct']}/{s['actions_total']} ({acc:.0f}%)")
        if s["count_checks"]:
            acc = 100 * s["count_correct"] / s["count_checks"]
            parts.append(f"счёт: {s['count_correct']}/{s['count_checks']} ({acc:.0f}%)")
        return "; ".join(parts) if parts else "пока нет статистики"
