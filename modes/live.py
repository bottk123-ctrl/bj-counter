"""Режим подсчёта по реальной раздаче: общая логика для GUI и консоли."""

from __future__ import annotations

import blackjack.cards as cards_module
from blackjack.cards import Card, RANKS
from blackjack.counting import CardCounter, CountingSystem, get_system

# Порядок мастей совпадает с cards.SUIT_SYMBOLS: пики, черви, бубны, трефы.
SUIT_KEYS = ["S", "H", "D", "C"]
_SUIT_BY_INPUT = {
    "s": "S", "h": "H", "d": "D", "c": "C",
    "\u2660": "S", "\u2665": "H", "\u2666": "D", "\u2663": "C",
}
_RANK_ALIASES = {"T": "10"}


def suit_symbol(key: str) -> str:
    """Символ масти для текущего режима (юникод или ASCII)."""
    return cards_module.SUIT_SYMBOLS[SUIT_KEYS.index(key)]


def _setup_console() -> None:
    """Включить UTF-8 в консоли Windows (для символов мастей)."""
    import os
    import sys

    if os.name == "nt":
        os.system("chcp 65001 >nul 2>&1")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass


def make_card(rank: str, suit_key: str) -> Card:
    return Card(rank, suit_symbol(suit_key))


def parse_card(token: str) -> Card:
    """Разобрать карту из строки: '10h', 'as', 'k♦', 'Ts'."""
    token = token.strip()
    if len(token) < 2:
        raise ValueError(f"Не понимаю карту: {token!r}. Пример: 10h, as, k♦")
    suit_key = _SUIT_BY_INPUT.get(token[-1].lower()) or _SUIT_BY_INPUT.get(token[-1])
    if suit_key is None:
        raise ValueError(f"Неизвестная масть в {token!r}. Используйте s/h/d/c.")
    rank_part = token[:-1].upper()
    rank = _RANK_ALIASES.get(rank_part, rank_part)
    if rank not in RANKS:
        raise ValueError(f"Неизвестный ранг в {token!r}. Пример: 10h, as, k♦")
    return make_card(rank, suit_key)


class LiveSession:
    """Живой счёт: добавляем карты, получаем running/true count и ставку."""

    def __init__(self, system: CountingSystem, num_decks: int):
        self.system = system
        self.num_decks = num_decks
        self.counter = CardCounter(system, num_decks)
        self.history: list[Card] = []

    # --- конфигурация -------------------------------------------------------
    def set_system(self, system: CountingSystem) -> None:
        self.system = system
        self._rebuild()

    def set_num_decks(self, num_decks: int) -> None:
        self.num_decks = num_decks
        self._rebuild()

    def _rebuild(self) -> None:
        history = list(self.history)
        self.counter = CardCounter(self.system, self.num_decks)
        self.history = []
        for card in history:
            self.counter.observe(card)
            self.history.append(card)

    # --- изменение состояния ------------------------------------------------
    def add(self, card: Card) -> Card:
        self.counter.observe(card)
        self.history.append(card)
        return card

    def undo(self) -> Card | None:
        if not self.history:
            return None
        removed = self.history.pop()
        history = list(self.history)
        self.counter = CardCounter(self.system, self.num_decks)
        self.history = []
        for card in history:
            self.counter.observe(card)
            self.history.append(card)
        return removed

    def reset(self) -> None:
        """Новый шуз."""
        self.counter.reset()
        self.history = []

    # --- метрики ------------------------------------------------------------
    @property
    def running_count(self) -> float:
        return self.counter.running_count

    @property
    def true_count(self) -> float | None:
        return self.counter.true_count

    @property
    def decks_remaining(self) -> float:
        return self.counter.decks_remaining

    @property
    def bet_units(self) -> int:
        return self.counter.bet_units()

    @property
    def cards_seen(self) -> int:
        return self.counter.cards_seen

    def summary(self) -> str:
        return self.counter.summary()


def state_line(session: LiveSession) -> str:
    if session.true_count is not None:
        return (
            f"RC={session.running_count:+.0f}  TC={session.true_count:+.1f}  "
            f"колод ост. {session.decks_remaining:.1f}  ставка {session.bet_units}u  "
            f"(карт учтено: {session.cards_seen})"
        )
    return (
        f"RC={session.running_count:+.0f}  метрика={session.counter.metric:+.0f}  "
        f"ставка {session.bet_units}u  (карт учтено: {session.cards_seen})"
    )


def console_live(system: CountingSystem, num_decks: int, store=None) -> None:
    """Консольный режим ввода карт по мере раздачи."""
    _setup_console()
    session = LiveSession(system, num_decks)

    def persist() -> None:
        if store is not None:
            store.save_live_session(session.system.name, session.num_decks,
                                    [str(card) for card in session.history])

    if store is not None:
        data = store.load_live_session()
        if data:
            try:
                session.set_system(get_system(data.get("system", system.name)))
                session.set_num_decks(int(data.get("num_decks", num_decks)))
                for token in data.get("cards", []):
                    try:
                        session.add(parse_card(token))
                    except ValueError:
                        continue
                print("Восстановлена сохранённая сессия.")
            except Exception:  # pragma: no cover
                pass

    print("\n--- Подсчёт по реальной раздаче ---")
    print("Вводите карты по мере выхода: например 10h, as, k♦, 7s.")
    print("Команды: u — отменить последнюю, n — новый шуз, q — выход.")
    print("Текущий счёт:", state_line(session))
    while True:
        try:
            raw = input("Карта> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            persist()
            return
        low = raw.lower()
        if low in ("q", "quit", "выход"):
            persist()
            return
        if low in ("u", "undo", "отмена"):
            removed = session.undo()
            print("Убрана:", removed if removed else "(нечего отменять)")
            persist()
        elif low in ("n", "new", "новый"):
            session.reset()
            print("Новый шуз, счёт сброшен.")
            persist()
        elif low == "":
            pass
        else:
            try:
                card = parse_card(raw)
            except ValueError as exc:
                print(" ", exc)
                continue
            session.add(card)
            print(" ", card, "->", state_line(session))
            persist()
