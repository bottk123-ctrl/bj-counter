"""Blackjack AI — точка входа.

Запуск:  python cli.py
"""

from __future__ import annotations

import os
import sys

# Корректный вывод юникод-мастей в консоли Windows.
if os.name == "nt":
    os.system("chcp 65001 >nul 2>&1")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

from blackjack.cards import use_ascii_suits
from blackjack.counting import list_systems
from blackjack.rules import Rules
from modes.live import console_live
from modes.simulator import SimConfig, format_report, run_simulation
from modes.trainer import TrainerSession
from storage import Store

if os.environ.get("BJ_ASCII"):
    use_ascii_suits()


HELP = """
=================  СПРАВКА  =================
1) Тренажёр счёта — показывает карты и проверяет running count и true count.
2) Тренажёр игры   — вы играете руку против дилера, бот проверяет ваши
                     решения по базовой стратегии и спрашивает счёт.
3) Симулятор       — бот сам играет N рук по базовой стратегии + индексным
                     отклонениям (Illustrious 18) и меняет ставку по счёту.

Обозначения действий:  h=hit  s=stand  d=double  p=split  r=surrender
True count = running count / колод осталось (для balanced-систем).
Ставки: 1 юнит при низком счёте, растут по мере роста true count.
=============================================
"""


def _ask_int(prompt: str, default: int):
    raw = input(prompt).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("  ! Нужно целое число, беру значение по умолчанию.")
        return default


def _ask_float(prompt: str, default: float):
    raw = input(prompt).strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print("  ! Нужно число, беру значение по умолчанию.")
        return default


def choose_system(current=None):
    systems = list_systems()
    print("\nСистемы подсчёта:")
    for i, s in enumerate(systems, 1):
        mark = " *" if current and s.name == current.name else ""
        print(f"  {i}) {s.name}{mark} — {s.description}")
    raw = input(f"Выберите номер [{systems[0].name}]: ").strip()
    if not raw:
        return systems[0]
    try:
        return systems[int(raw) - 1]
    except (ValueError, IndexError):
        print("  ! Неверный выбор, беру Hi-Lo.")
        return systems[0]


def configure_rules(current: Rules) -> Rules:
    print("\nНастройка правил (Enter — оставить текущее):")
    print("  Текущие:", current.describe())
    rules = Rules(**vars(current))
    rules.num_decks = _ask_int("  Число колод [%d]: " % current.num_decks, current.num_decks)
    ans = input("  Дилер добирает на soft 17? (y/N): ").strip().lower()
    if ans:
        rules.dealer_hits_soft_17 = ans == "y"
    ans = input("  Дабл после сплита? (Y/n): ").strip().lower()
    if ans:
        rules.double_after_split = ans != "n"
    ans = input("  Сюррендер? (y/N): ").strip().lower()
    if ans:
        rules.surrender = ans == "y"
    ans = input("  Выплата за BJ 6:5? (y/N): ").strip().lower()
    if ans == "y":
        rules.blackjack_payout = 1.2
    rules.penetration = _ask_float("  Проникновение 0-1 [%.2f]: " % current.penetration, current.penetration)
    print("  Новые правила:", rules.describe())
    return rules


def run_simulator(system, rules: Rules) -> None:
    print("\n--- Симулятор ---")
    hands = _ask_int("  Сколько рук сыграть? [10000]: ", 10000)
    bankroll = _ask_float("  Стартовый банкролл? [1000]: ", 1000.0)
    unit = _ask_float("  Размер юнита? [10]: ", 10.0)
    ans = input("  Использовать индексные отклонения (Illustrious 18)? (Y/n): ").strip().lower()
    use_dev = ans != "n"
    cfg = SimConfig(
        hands=hands,
        bankroll=bankroll,
        unit=unit,
        system_name=system.name,
        rules=rules,
        use_deviations=use_dev,
    )
    print("\nСчитаю", hands, "рук...")
    report = run_simulation(cfg)
    print(format_report(report))


def launch_gui() -> None:
    """Запустить графический интерфейс."""
    try:
        from gui.app import run as run_gui
    except Exception as exc:
        print("Не удалось загрузить GUI:", exc)
        print("Проверьте, что установлен tkinter (обычно идёт с Python).")
        return
    try:
        run_gui()
    except Exception as exc:  # pragma: no cover
        print("Ошибка GUI:", exc)


def main() -> None:
    system = list_systems()[0]  # Hi-Lo
    rules = Rules()
    store = Store()
    print("=== Blackjack AI ===")

    while True:
        print("\n" + "-" * 50)
        print(f"Система: {system.name} | {rules.describe()}")
        print("-" * 50)
        print("1) Тренажёр счёта")
        print("2) Тренажёр игры")
        print("3) Симулятор бота")
        print("4) Выбрать систему подсчёта")
        print("5) Настроить правила")
        print("6) Справка")
        print("7) Подсчёт по реальной раздаче (консоль)")
        print("8) Графический интерфейс (GUI)")
        print("9) Статистика")
        print("0) Выход")
        choice = input("> ").strip()

        if choice == "1":
            session = TrainerSession(system, rules, store=store)
            ask_every = _ask_int("  Показывать пачку по сколько карт? [5]: ", 5)
            session.run_count_drill(ask_every=ask_every)
            store.save()
            print("\nИтог:", session.summary())
        elif choice == "2":
            session = TrainerSession(system, rules, store=store)
            bet = _ask_float("  Базовая ставка [10]: ", 10.0)
            session.run_play_drill(base_bet=bet)
            store.save()
            print("\nИтог:", session.summary())
        elif choice == "3":
            run_simulator(system, rules)
        elif choice == "4":
            system = choose_system(system)
        elif choice == "5":
            rules = configure_rules(rules)
        elif choice == "6":
            print(HELP)
        elif choice == "7":
            console_live(system, rules.num_decks, store=store)
        elif choice == "8":
            launch_gui()
        elif choice == "9":
            print()
            print(store.summary_text())
            if store.data["simulations"]:
                print("\nПоследние симуляции:")
                for sim in store.data["simulations"][:5]:
                    print(f"  {sim['time']}  {sim['system']}  рук {sim['hands']}  "
                          f"итог {sim['net']:+.0f}  преим. {sim['edge'] * 100:+.3f}%")
            raw = input("\nОчистить статистику? (y/N): ").strip().lower()
            if raw == "y":
                store.reset_stats()
                print("Статистика очищена.")
        elif choice in ("0", "q", "quit", "exit", "выход"):
            print("Пока!")
            return
        else:
            print("Не понял выбор, попробуйте ещё раз.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nПока!")
