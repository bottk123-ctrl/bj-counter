"""Сохранение статистики, истории симуляций и живой сессии в JSON.

Файл по умолчанию: ``%APPDATA%\\blackjack_ai\\state.json`` (или ``~/blackjack_ai``).
Все операции устойчивы к отсутствию/повреждению файла.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

__all__ = ["Store", "default_path"]


def default_path() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(base) / "blackjack_ai" / "state.json"


class Store:
    """Простое JSON-хранилище состояния приложения."""

    DEFAULTS = {
        "decisions_total": 0,
        "decisions_correct": 0,
        "count_total": 0,
        "count_correct": 0,
        "rounds_played": 0,
        "hands_simulated": 0,
        "simulations": [],
        "live_session": {},
    }

    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path) if path else default_path()
        self.data = json.loads(json.dumps(self.DEFAULTS))  # глубокая копия
        self.load()

    # --- ввод/вывод ---------------------------------------------------------
    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as fh:
                loaded = json.load(fh)
        except (OSError, ValueError):
            return
        if not isinstance(loaded, dict):
            return
        for key, default in self.DEFAULTS.items():
            value = loaded.get(key, default)
            if isinstance(default, list) and not isinstance(value, list):
                value = list(default)
            elif isinstance(default, dict) and not isinstance(value, dict):
                value = dict(default)
            elif isinstance(default, int) and not isinstance(value, int):
                value = default
            self.data[key] = value

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            pass

    # --- тренировка ---------------------------------------------------------
    def record_decision(self, correct: bool, rounds: int = 0, save: bool = True) -> None:
        self.data["decisions_total"] += 1
        if correct:
            self.data["decisions_correct"] += 1
        self.data["rounds_played"] += rounds
        if save:
            self.save()

    def record_count(self, correct: bool, save: bool = True) -> None:
        self.data["count_total"] += 1
        if correct:
            self.data["count_correct"] += 1
        if save:
            self.save()

    def record_round(self, save: bool = True) -> None:
        self.data["rounds_played"] += 1
        if save:
            self.save()

    # --- симуляции ----------------------------------------------------------
    def record_simulation(self, report: dict, save: bool = True) -> dict:
        edge = report.get("edge", report.get("mean_edge", 0.0))
        summary = {
            "time": time.strftime("%Y-%m-%d %H:%M"),
            "system": report.get("system"),
            "rules": report.get("rules"),
            "hands": report.get("hands"),
            "net": round(float(report.get("net", 0.0)), 2),
            "edge": float(edge or 0.0),
            "ev_units": float(report.get("ev_per_hand_units", 0.0)),
            "drawdown_units": float(report.get("max_drawdown_units", 0.0)),
            "bet_mode": report.get("bet_mode", "spread"),
            "sessions": int(report.get("sessions", 1) or 1),
            "ruined": bool(report.get("ruined", False)),
            "ruin_rate": float(report.get("ruin_rate", 0.0)),
            "hands_played": int(report.get("hands_played", report.get("hands", 0)) or 0),
            "min_bankroll_units": float(report.get("min_bankroll_units", 0.0)),
        }
        self.data["simulations"].insert(0, summary)
        self.data["simulations"] = self.data["simulations"][:50]
        self.data["hands_simulated"] += int(report.get("hands", 0) or 0)
        if save:
            self.save()
        return summary

    # --- живая сессия -------------------------------------------------------
    def save_live_session(self, system_name: str, num_decks: int,
                          history_tokens: list[str], save: bool = True) -> None:
        self.data["live_session"] = {
            "system": system_name,
            "num_decks": int(num_decks),
            "cards": list(history_tokens),
            "saved_at": time.strftime("%Y-%m-%d %H:%M"),
        }
        if save:
            self.save()

    def load_live_session(self) -> dict | None:
        session = self.data.get("live_session") or {}
        if not session.get("cards"):
            return None
        return session

    def clear_live_session(self, save: bool = True) -> None:
        self.data["live_session"] = {}
        if save:
            self.save()

    # --- показатели ---------------------------------------------------------
    @property
    def decision_accuracy(self) -> float:
        total = self.data["decisions_total"]
        return (self.data["decisions_correct"] / total) if total else 0.0

    @property
    def count_accuracy(self) -> float:
        total = self.data["count_total"]
        return (self.data["count_correct"] / total) if total else 0.0

    def reset_stats(self, save: bool = True) -> None:
        for key in ("decisions_total", "decisions_correct", "count_total",
                    "count_correct", "rounds_played", "hands_simulated"):
            self.data[key] = 0
        self.data["simulations"] = []
        if save:
            self.save()

    def summary_text(self) -> str:
        d = self.data
        lines = [
            "Статистика тренировок:",
            f"  Решения по стратегии: {d['decisions_correct']}/{d['decisions_total']} "
            f"({self.decision_accuracy * 100:.0f}%)",
            f"  Проверки счёта:        {d['count_correct']}/{d['count_total']} "
            f"({self.count_accuracy * 100:.0f}%)",
            f"  Сыграно рук:           {d['rounds_played']}",
            f"  Сыграно рук в симуляциях: {d['hands_simulated']}",
            f"  Сохранено симуляций:   {len(d['simulations'])}",
        ]
        return "\n".join(lines)
