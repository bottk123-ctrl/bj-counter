import json

from storage import Store


def test_store_records_and_persists(tmp_path):
    path = tmp_path / "state.json"
    store = Store(path)
    store.record_decision(True)
    store.record_decision(False)
    store.record_count(True)
    store.record_round()
    store.save()

    reloaded = Store(path)
    assert reloaded.data["decisions_total"] == 2
    assert reloaded.data["decisions_correct"] == 1
    assert reloaded.data["count_total"] == 1
    assert reloaded.data["count_correct"] == 1
    assert reloaded.data["rounds_played"] == 1
    assert reloaded.decision_accuracy == 0.5
    assert reloaded.count_accuracy == 1.0


def test_store_simulation_history_capped(tmp_path):
    store = Store(tmp_path / "s.json")
    for i in range(60):
        store.record_simulation({"system": "Hi-Lo", "hands": 100, "net": i,
                                 "edge": 0.01, "ev_per_hand_units": 0.001,
                                 "max_drawdown_units": 5.0, "rules": "test"})
    assert len(store.data["simulations"]) == 50
    assert store.data["hands_simulated"] == 6000
    # последняя записанная — сверху
    assert store.data["simulations"][0]["net"] == 59


def test_store_live_session_roundtrip(tmp_path):
    store = Store(tmp_path / "l.json")
    assert store.load_live_session() is None
    store.save_live_session("Hi-Lo", 6, ["10\u2665", "A\u2660", "5\u2660"])
    data = store.load_live_session()
    assert data["system"] == "Hi-Lo"
    assert data["num_decks"] == 6
    assert data["cards"] == ["10\u2665", "A\u2660", "5\u2660"]
    store.clear_live_session()
    assert store.load_live_session() is None


def test_store_survives_corrupt_file(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ это не json", encoding="utf-8")
    store = Store(path)
    assert store.data["decisions_total"] == 0
    assert store.data["simulations"] == []


def test_store_reset(tmp_path):
    store = Store(tmp_path / "r.json")
    store.record_decision(True)
    store.record_simulation({"system": "KO", "hands": 10, "net": 5})
    store.reset_stats()
    assert store.data["decisions_total"] == 0
    assert store.data["simulations"] == []


def test_store_summary_text(tmp_path):
    store = Store(tmp_path / "t.json")
    store.record_decision(True)
    text = store.summary_text()
    assert "Статистика" in text
    assert "1/1" in text


def test_store_default_path_is_json(tmp_path):
    store = Store(tmp_path / "deep" / "nested" / "state.json")
    store.record_count(True)
    store.save()
    assert store.path.exists()
    json.loads(store.path.read_text(encoding="utf-8"))
