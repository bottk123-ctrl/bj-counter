"""Симулятор: бот играет много рук и показывает статистику.

Поддерживает три режима ставок:

* ``flat``   — всегда 1 юнит (контрольный, «ровный» режим);
* ``spread`` — bet spread по счёту (ставка = юниты × unit);
* ``kelly``  — дробный Kelly: ставка пропорциональна банку и преимуществу.

Также умеет останавливаться при руине, считать минимальный банкролл,
риск разорения (Risk of Ruin) и запускать много сессий для доверительных
интервалов.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from blackjack.counting import CardCounter, get_system
from blackjack.engine import BlackjackGame
from blackjack.rules import Rules
from blackjack.strategy import (
    basic_strategy,
    deviation_action,
    take_insurance,
)

BET_MODES = ("flat", "spread", "kelly")


@dataclass
class SimConfig:
    hands: int = 10000
    bankroll: float = 1000.0
    unit: float = 10.0
    system_name: str = "Hi-Lo"
    rules: Rules = field(default_factory=Rules)
    seed: int | None = None
    use_deviations: bool = True
    bet_mode: str = "spread"       # "flat" | "spread" | "kelly"
    kelly_fraction: float = 0.5    # 0.5 = half Kelly
    table_max: float = 0.0         # 0 = без лимита (в деньгах)
    stop_at_ruin: bool = True
    sessions: int = 1              # >1 — запускать много сессий (см. run_many)


# --- вспомогательные вычисления ---------------------------------------------

def _bet_units(counter: CardCounter, cfg: SimConfig, bankroll: float) -> int:
    """Число юнитов ставки по выбранному режиму."""
    if cfg.bet_mode == "flat":
        return 1
    if cfg.bet_mode == "kelly":
        return counter.kelly_units(bankroll, cfg.unit, fraction=cfg.kelly_fraction)
    return counter.bet_units()


def _cap_units(units: int, cfg: SimConfig) -> int:
    """Ограничить ставку лимитом стола (table max)."""
    units = max(1, int(units))
    if cfg.table_max > 0 and cfg.unit > 0:
        cap = max(1, int(cfg.table_max / cfg.unit))
        units = min(units, cap)
    return units


def analytic_risk_of_ruin(bankroll_units: float, ev_units: float,
                          sd_units: float) -> float:
    """Аналитическая оценка риска разорения (диффузионное приближение).

    ``RoR ≈ exp(-2 · EV · B / σ²)``, где EV и σ — на одну руку в юнитах,
    B — банкролл в юнитах. При неположительном EV риск равен 1.
    """
    if ev_units <= 0:
        return 1.0
    if sd_units <= 0:
        return 0.0
    return min(1.0, math.exp(-2.0 * ev_units * bankroll_units / (sd_units ** 2)))


def _choose_action(rnd, i, counter, cfg) -> str:
    hand = rnd.player[i]
    acts = rnd.available_actions(i)
    if cfg.use_deviations:
        dev = deviation_action(hand.cards, rnd.dealer_upcard.rank, counter.true_count, acts, cfg.rules)
        if dev in acts:
            return dev
    return basic_strategy(hand.cards, rnd.dealer_upcard.rank, cfg.rules, acts)


# --- одна сессия -------------------------------------------------------------

def run_simulation(cfg: SimConfig) -> dict:
    system = get_system(cfg.system_name)
    game = BlackjackGame(cfg.rules, seed=cfg.seed)
    counter = CardCounter(system, cfg.rules.num_decks)

    bankroll = cfg.bankroll
    min_bankroll = bankroll
    peak = bankroll
    max_drawdown = 0.0
    net_total = 0.0
    net_sq = 0.0
    total_wagered = 0.0
    units_wagered = 0.0
    max_bet_units = 0
    hands_played = 0
    ruined = False
    counts = {"win": 0, "lose": 0, "push": 0, "blackjack": 0, "surrender": 0, "insurance": 0}
    shoes = 0
    curve: list[float] = [bankroll]
    sample_every = max(1, cfg.hands // 200)

    for hand_index in range(cfg.hands):
        if game.shoe.needs_shuffle():
            game.shoe.shuffle()
            game.shoe_number += 1
            counter.reset()
            shoes += 1

        units = _cap_units(_bet_units(counter, cfg, bankroll), cfg)
        max_bet_units = max(max_bet_units, units)
        bet = units * cfg.unit

        # Руина: банкролл не покрывает нужную ставку — играть больше нельзя.
        if cfg.stop_at_ruin and (bankroll <= 0 or bankroll < bet):
            ruined = True
            break

        rnd = game.start_round(bet)

        # Видимые карты этого раунда наблюдаем по мере открытия.
        seen: set[int] = set()

        def see(card) -> None:
            if id(card) not in seen:
                seen.add(id(card))
                counter.observe(card)

        def see_player() -> None:
            for h in rnd.player:
                for c in h.cards:
                    see(c)

        def see_dealer_revealed() -> None:
            for c in rnd.dealer[1:]:
                see(c)

        see_player()
        see(rnd.dealer[0])

        if rnd.dealer_has_ace and take_insurance(counter.true_count, cfg.rules):
            rnd.take_insurance(bet / 2)

        # Дилер втайне проверяет блэкджек — карта игроку ещё не видна.
        early_done = False
        if cfg.rules.dealer_peeks and (rnd.dealer_has_ace or rnd.dealer_has_ten_up):
            if rnd.dealer_blackjack:
                see(rnd.dealer[1])  # блэкджек вскрывается — учитываем карту
                early_done = True

        if not early_done:
            i = 0
            while i < len(rnd.player):
                guard = 0
                while True:
                    acts = rnd.available_actions(i)
                    if not acts:
                        break
                    action = _choose_action(rnd, i, counter, cfg)
                    rnd.apply(action, i)
                    see_player()
                    guard += 1
                    if guard > 60:
                        break
                i += 1

        rnd.play_dealer()
        see_dealer_revealed()
        results = rnd.settle()

        hand_net = 0.0
        for r in results:
            bankroll += r.net
            net_total += r.net
            hand_net += r.net
            total_wagered += r.bet
            units_wagered += r.bet / cfg.unit
            counts[r.result] = counts.get(r.result, 0) + 1
        net_sq += hand_net * hand_net
        hands_played += 1

        min_bankroll = min(min_bankroll, bankroll)
        peak = max(peak, bankroll)
        max_drawdown = max(max_drawdown, peak - bankroll)
        if hand_index % sample_every == 0:
            curve.append(bankroll)
    curve.append(bankroll)

    played = max(hands_played, 1)
    mean_units = (net_total / cfg.unit) / played if cfg.unit else 0.0
    var_units = max(net_sq / (cfg.unit ** 2) / played - mean_units ** 2, 0.0) if cfg.unit else 0.0
    sd_units = math.sqrt(var_units)
    bankroll_units = cfg.bankroll / cfg.unit if cfg.unit else 0.0

    report = {
        "system": system.name,
        "rules": cfg.rules.describe(),
        "hands": cfg.hands,
        "hands_played": hands_played,
        "shoes": shoes,
        "bet_mode": cfg.bet_mode,
        "kelly_fraction": cfg.kelly_fraction,
        "table_max": cfg.table_max,
        "start_bankroll": cfg.bankroll,
        "final_bankroll": bankroll,
        "min_bankroll": min_bankroll,
        "min_bankroll_units": min_bankroll / cfg.unit if cfg.unit else 0.0,
        "ruined": ruined,
        "net": net_total,
        "total_wagered": total_wagered,
        "units_wagered": units_wagered,
        "ev_per_hand": net_total / played if played else 0.0,
        "ev_per_hand_units": mean_units,
        "sd_per_hand_units": sd_units,
        "edge": (net_total / total_wagered) if total_wagered else 0.0,
        "max_drawdown": max_drawdown,
        "max_drawdown_units": max_drawdown / cfg.unit if cfg.unit else 0.0,
        "max_bet_units": max_bet_units,
        "ruin_probability_analytic": analytic_risk_of_ruin(bankroll_units, mean_units, sd_units),
        "win_rate": (counts["win"] + counts["blackjack"]) / (counts["win"] + counts["lose"] + counts["push"] + counts["blackjack"]) if (counts["win"] + counts["lose"] + counts["push"] + counts["blackjack"]) else 0.0,
        "counts": counts,
        "bankroll_curve": curve,
    }
    return report


# --- много сессий: доверительные интервалы и риск разорения ------------------

def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    ordered = sorted(xs)
    k = (len(ordered) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return ordered[int(k)]
    return ordered[lo] * (hi - k) + ordered[hi] * (k - lo)


def run_many(cfg: SimConfig, sessions: int | None = None) -> dict:
    """Запустить несколько независимых сессий и собрать статистику.

    Возвращает среднее преимущество с 95% доверительным интервалом,
    распределение итоговых банкроллов, эмпирический риск разорения и
    прочую сводку.
    """
    n = max(1, int(sessions or cfg.sessions or 1))
    finals: list[float] = []
    nets: list[float] = []
    edges: list[float] = []
    wagered: list[float] = []
    mins: list[float] = []
    drawdowns: list[float] = []
    hands_played: list[float] = []
    ruined = 0
    first_curve: list[float] = []

    for i in range(n):
        seed = None if cfg.seed is None else cfg.seed + i
        sub = replace(cfg, sessions=1, seed=seed)
        rep = run_simulation(sub)
        finals.append(rep["final_bankroll"])
        nets.append(rep["net"])
        edges.append(rep["edge"])
        wagered.append(rep["total_wagered"])
        mins.append(rep["min_bankroll_units"])
        drawdowns.append(rep["max_drawdown_units"])
        hands_played.append(rep["hands_played"])
        if rep["ruined"]:
            ruined += 1
        if i == 0:
            first_curve = rep["bankroll_curve"]

    mean_edge = _mean(edges)
    std_edge = _std(edges)
    se_edge = std_edge / math.sqrt(n) if n else 0.0
    margin = 1.96 * se_edge
    mean_net = _mean(nets)
    mean_final = _mean(finals)
    std_final = _std(finals)
    se_final = std_final / math.sqrt(n) if n else 0.0
    final_margin = 1.96 * se_final
    total_wagered = sum(wagered)
    aggregate_edge = (sum(nets) / total_wagered) if total_wagered else 0.0

    return {
        "system": get_system(cfg.system_name).name,
        "rules": cfg.rules.describe(),
        "sessions": n,
        "hands": cfg.hands * n,
        "hands_per_session": cfg.hands,
        "bet_mode": cfg.bet_mode,
        "kelly_fraction": cfg.kelly_fraction,
        "table_max": cfg.table_max,
        "start_bankroll": cfg.bankroll,
        "final_bankroll": mean_final,
        "min_bankroll_units": _mean(mins),
        "ruined": ruined > 0,
        "ruin_rate": ruined / n if n else 0.0,
        "mean_net": mean_net,
        "std_net": _std(nets),
        "net": mean_net,
        "mean_final": mean_final,
        "median_final": _percentile(finals, 0.5),
        "std_final": std_final,
        "ci95_final": (mean_final - final_margin, mean_final + final_margin),
        "mean_edge": mean_edge,
        "std_edge": std_edge,
        "std_err_edge": se_edge,
        "ci95_edge": (mean_edge - margin, mean_edge + margin),
        "aggregate_edge": aggregate_edge,
        "mean_drawdown_units": _mean(drawdowns),
        "max_drawdown_units": _mean(drawdowns),
        "mean_hands_played": _mean(hands_played),
        "ev_per_hand_units": (mean_net / cfg.unit / cfg.hands) if cfg.unit and cfg.hands else 0.0,
        "final_percentiles": {
            "p5": _percentile(finals, 0.05),
            "p25": _percentile(finals, 0.25),
            "p50": _percentile(finals, 0.50),
            "p75": _percentile(finals, 0.75),
            "p95": _percentile(finals, 0.95),
        },
        "final_bankrolls": finals,
        "net_bankrolls": nets,
        "bankroll_curve": first_curve,
    }


# --- вывод -------------------------------------------------------------------

def format_report(r: dict) -> str:
    mode_ru = {"flat": "флэт (1 юнит)", "spread": "спред по счёту",
               "kelly": f"Kelly (доля {r.get('kelly_fraction', 0.5):.2f})"}
    lines = [
        "",
        "=================  РЕЗУЛЬТАТ СИМУЛЯЦИИ  =================",
        f"Система счёта : {r['system']}",
        f"Правила       : {r['rules']}",
        f"Режим ставок  : {mode_ru.get(r.get('bet_mode', 'spread'), r.get('bet_mode'))}",
        f"Рук сыграно   : {r.get('hands_played', r['hands'])} из {r['hands']}  (шушов: {r['shoes']})",
        "",
        f"Банкролл старт: {r['start_bankroll']:.2f}",
        f"Банкролл финал: {r['final_bankroll']:.2f}",
        f"Минимум банка : {r.get('min_bankroll', 0.0):.2f}  ({r.get('min_bankroll_units', 0.0):.1f} юнитов)",
        f"Итог (net)    : {r['net']:+.2f}",
        f"Всего ставок  : {r['total_wagered']:.2f}  ({r['units_wagered']:.0f} юнитов)",
        "",
        f"EV на руку    : {r['ev_per_hand']:+.4f}  ({r['ev_per_hand_units']:+.4f} юнита)",
        f"SD на руку    : {r.get('sd_per_hand_units', 0.0):.3f} юнита",
        f"Преимущество  : {r['edge'] * 100:+.3f}% от оборота",
        f"Win rate      : {r['win_rate'] * 100:.2f}%",
        f"Макс. просадка: {r['max_drawdown']:.2f}  ({r['max_drawdown_units']:.1f} юнитов)",
        f"Макс. ставка  : {r['max_bet_units']} юнитов",
        "",
    ]
    if r.get("ruined"):
        lines.append("!! РУИНА: банкролл закончился, сессия прервана досрочно !!")
    lines.append(
        f"Риск разорения (аналит.): {r.get('ruin_probability_analytic', 0.0) * 100:.2f}%"
    )
    lines += [
        "",
        "Исходы:",
        f"  выигрыш {r['counts']['win']} | блэкджек {r['counts']['blackjack']} | "
        f"проигрыш {r['counts']['lose']} | ничья {r['counts']['push']} | "
        f"сюррендер {r['counts']['surrender']} | страховка {r['counts'].get('insurance', 0)}",
        "=======================================================",
        "",
    ]
    return "\n".join(lines)


def format_many(r: dict) -> str:
    p = r["final_percentiles"]
    lo, hi = r["ci95_edge"]
    flo, fhi = r["ci95_final"]
    mode_ru = {"flat": "флэт (1 юнит)", "spread": "спред по счёту",
               "kelly": f"Kelly (доля {r.get('kelly_fraction', 0.5):.2f})"}
    lines = [
        "",
        "============  РЕЗУЛЬТАТ: МНОГО СЕССИЙ  ============",
        f"Система счёта : {r['system']}",
        f"Правила       : {r['rules']}",
        f"Режим ставок  : {mode_ru.get(r.get('bet_mode', 'spread'), r.get('bet_mode'))}",
        f"Сессий        : {r['sessions']}  по {r['hands_per_session']} рук",
        f"Старт. банк   : {r['start_bankroll']:.2f}",
        "",
        f"Средний итог  : {r['mean_final']:.2f}  (± {r['std_final']:.2f})",
        f"  95% ДИ итога: [{flo:.0f}, {fhi:.0f}]",
        f"Медиана итога : {r['median_final']:.0f}",
        f"Средний net   : {r['mean_net']:+.2f}  (± {r['std_net']:.2f})",
        f"Среднее преим.: {r['mean_edge'] * 100:+.3f}%   "
        f"(совокупное: {r['aggregate_edge'] * 100:+.3f}%)",
        f"  95% ДИ преим: [{lo * 100:+.3f}%, {hi * 100:+.3f}%]",
        f"  (σ преимущ. : {r['std_edge'] * 100:.3f}%, ст.ошибка {r['std_err_edge'] * 100:.3f}%)",
        "",
        f"Риск разорения: {r['ruin_rate'] * 100:.1f}%  "
        f"({int(round(r['ruin_rate'] * r['sessions']))} из {r['sessions']} сессий)",
        f"Средняя просадка: {r['mean_drawdown_units']:.1f} юнитов",
        f"Средне рук сыграно: {r['mean_hands_played']:.0f} из {r['hands_per_session']}",
        "",
        "Распределение финального банкролла:",
        f"  p5  {p['p5']:.0f}   p25 {p['p25']:.0f}   p50 {p['p50']:.0f}   "
        f"p75 {p['p75']:.0f}   p95 {p['p95']:.0f}",
        "==================================================",
        "",
    ]
    return "\n".join(lines)
