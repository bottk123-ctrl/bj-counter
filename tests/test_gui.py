import pytest

tk = pytest.importorskip("tkinter")

from blackjack.counting import get_system
from blackjack.rules import Rules
from storage import Store


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    from gui.app import App

    path = tmp_path_factory.mktemp("state") / "state.json"
    try:
        application = App(store=Store(path))
    except tk.TclError as exc:  # нет дисплея
        pytest.skip(f"GUI недоступен: {exc}")
    application.withdraw()
    yield application
    application.destroy()


@pytest.fixture(autouse=True)
def _clean(app):
    app.store.reset_stats()
    app.set_settings(get_system("Hi-Lo"), Rules())
    app.live.clear_session()
    app.play.rnd = None
    app.play.feedback_var.set("")
    app.play._render()
    yield


def test_app_builds_and_live_tab_works(app):
    app.update_idletasks()

    app.live.add("10", "H")
    app.live.add("5", "S")
    app.live.refresh()
    assert app.live.session.cards_seen == 2

    app.live.undo()
    assert app.live.session.cards_seen == 1

    app.live.new_shoe()
    assert app.live.session.cards_seen == 0


def test_live_session_is_persisted(app):
    app.live.add("10", "H")
    app.live.add("A", "S")
    saved = Store(app.store.path).load_live_session()
    assert saved is not None
    assert len(saved["cards"]) == 2


def test_settings_propagate_to_frames(app):
    app.set_settings(get_system("KO"), Rules(num_decks=2, insurance=False))
    assert app.live.session.num_decks == 2
    assert app.live.session.system.name == "KO"


def test_play_tab_round_builds(app):
    app.set_settings(app.system, Rules(num_decks=6, insurance=False))
    app.play.new_round()
    app.update_idletasks()
    assert app.play.rnd is not None
    assert len(app.play.rnd.player[0].cards) == 2


def test_play_tab_records_statistics(app):
    app.set_settings(app.system, Rules(num_decks=6, insurance=False))
    cur = None
    for _ in range(20):  # иногда дилер сразу берёт блэкджек — тогда пробуем ещё
        app.play.new_round()
        cur = app.play._current()
        if cur is not None:
            break
    assert cur is not None
    _idx, acts = cur
    action = "stand" if "stand" in acts else next(iter(acts))
    app.play._do(action)
    assert app.store.data["decisions_total"] >= 1


def test_stats_tab_records_and_draws(app):
    app.store.record_simulation({
        "system": "Hi-Lo", "hands": 1000, "net": 42.0, "edge": 0.01,
        "ev_per_hand_units": 0.001, "max_drawdown_units": 30.0,
        "start_bankroll": 1000.0, "final_bankroll": 1042.0,
        "bankroll_curve": [1000, 1010, 1020, 1042],
    })
    assert len(app.store.data["simulations"]) == 1
    app.notify_new_simulation({
        "start_bankroll": 1000.0,
        "bankroll_curve": [1000, 1010, 1020, 1042],
    })
    app.stats.refresh()
    app.stats.update_idletasks()
    assert len(app.stats.tree.get_children()) == 1
