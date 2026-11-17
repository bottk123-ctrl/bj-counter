from dataclasses import replace

from blackjack.counting import CardCounter, get_system
from blackjack.rules import Rules
from modes.simulator import (
    SimConfig,
    analytic_risk_of_ruin,
    run_many,
    run_simulation,
)


def test_small_simulation_runs():
    cfg = SimConfig(
        hands=300,
        bankroll=1000.0,
        unit=10.0,
        system_name="Hi-Lo",
        rules=Rules(num_decks=6),
        seed=123,
        use_deviations=True,
    )
    report = run_simulation(cfg)
    assert report["hands"] == 300
    assert report["system"] == "Hi-Lo"
    assert "final_bankroll" in report
    # ставки должны превышать минимальные хотя бы иногда
    assert report["max_bet_units"] >= 1


def test_simulation_is_deterministic_with_seed():
    def run():
        return run_simulation(SimConfig(hands=200, seed=7, system_name="Hi-Lo"))

    assert run()["net"] == run()["net"]


def test_unbalanced_system_simulation():
    report = run_simulation(
        SimConfig(hands=200, seed=5, system_name="KO", rules=Rules(num_decks=6))
    )
    assert report["hands"] == 200


def test_simulation_has_bankroll_curve():
    report = run_simulation(SimConfig(hands=500, seed=11, system_name="Hi-Lo"))
    curve = report["bankroll_curve"]
    assert len(curve) >= 2
    assert curve[0] == report["start_bankroll"]
    assert curve[-1] == report["final_bankroll"]


# --- вариант B: руина, Kelly, доверительные интервалы ------------------------

def test_flat_mode_always_min_bet():
    report = run_simulation(SimConfig(hands=300, seed=3, bet_mode="flat"))
    assert report["max_bet_units"] == 1
    assert report["ruined"] is False


def test_ruin_stops_session_early():
    report = run_simulation(
        SimConfig(hands=100000, bankroll=20.0, unit=10.0, seed=1,
                  bet_mode="spread", stop_at_ruin=True)
    )
    assert report["ruined"] is True
    assert report["hands_played"] < 100000
    assert report["min_bankroll_units"] <= 2.0


def test_no_ruin_stop_when_disabled():
    report = run_simulation(
        SimConfig(hands=500, bankroll=10.0, unit=10.0, seed=2,
                  bet_mode="spread", stop_at_ruin=False)
    )
    assert report["hands_played"] == 500
    assert report["ruined"] is False


def test_table_max_caps_bet():
    report = run_simulation(
        SimConfig(hands=400, bankroll=1000.0, unit=10.0, table_max=20.0,
                  seed=4, bet_mode="spread")
    )
    assert report["max_bet_units"] <= 2


def test_kelly_bet_scales_with_bankroll():
    counter = CardCounter(get_system("Hi-Lo"), 6)
    counter.running_count = 18.0  # true count = 3
    small = counter.kelly_units(1000.0, 10.0, fraction=0.5)
    big = counter.kelly_units(10000.0, 10.0, fraction=0.5)
    assert big > small >= 1


def test_kelly_min_bet_when_no_edge():
    counter = CardCounter(get_system("Hi-Lo"), 6)
    counter.running_count = -12.0  # true count = -2 -> преимущества нет
    assert counter.kelly_units(10000.0, 10.0) == 1


def test_analytic_risk_of_ruin():
    assert analytic_risk_of_ruin(100, 0.0, 1.0) == 1.0
    assert analytic_risk_of_ruin(100, -0.01, 1.0) == 1.0
    risk = analytic_risk_of_ruin(100, 0.01, 1.0)
    assert 0.0 < risk < 1.0
    assert analytic_risk_of_ruin(1_000_000, 0.01, 1.0) < risk


def test_run_many_reports_ci_and_ruin():
    report = run_many(
        SimConfig(hands=300, bankroll=1000.0, seed=10, bet_mode="spread"),
        sessions=8,
    )
    assert report["sessions"] == 8
    assert 0.0 <= report["ruin_rate"] <= 1.0
    lo, hi = report["ci95_edge"]
    assert lo <= report["mean_edge"] <= hi
    assert len(report["final_bankrolls"]) == 8
    assert report["final_percentiles"]["p5"] <= report["final_percentiles"]["p95"]


def test_run_many_max_drawdown_is_maximum_not_mean():
    cfg = SimConfig(hands=500, bankroll=1000.0, seed=21, bet_mode="spread")
    sessions = 5
    reports = [run_simulation(replace(cfg, sessions=1, seed=cfg.seed + i)) for i in range(sessions)]
    per_session = [r["max_drawdown_units"] for r in reports]

    summary = run_many(cfg, sessions=sessions)
    assert summary["max_drawdown_units"] == max(per_session)
    assert summary["max_drawdown_units"] > summary["mean_drawdown_units"]


def test_config_validation_rejects_empty_run():
    import pytest

    with pytest.raises(ValueError):
        run_simulation(SimConfig(hands=0))
    with pytest.raises(ValueError):
        run_simulation(SimConfig(hands=10, unit=0.0))
    with pytest.raises(ValueError):
        run_simulation(SimConfig(hands=10, kelly_fraction=0.0))
    with pytest.raises(ValueError):
        run_many(SimConfig(hands=10, sessions=0))


def test_full_penetration_run_never_crashes_and_reshuffles():
    """1 колода и penetration=1.0: аварийные тасовки не ломают прогон."""
    cfg = SimConfig(hands=5000, bankroll=1000.0, unit=10.0, seed=3,
                    bet_mode="flat", use_deviations=False,
                    rules=Rules(num_decks=1, penetration=1.0),
                    stop_at_ruin=False)
    report = run_simulation(cfg)
    assert report["hands_played"] == 5000
    assert report["shoes"] > 1
    assert report["net"] == report["net"]  # не NaN

