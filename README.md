# Blackjack AI

A blackjack card-counting trainer and bot simulator written in Python.
It ships with a graphical interface (Tkinter) and a console mode.

## Features

- **Multiple counting systems:** Hi-Lo, KO, Hi-Opt I, Hi-Opt II, Zen, Omega II,
  Wong Halves, Red Seven.
- **Graphical interface (GUI):** tabs for Count, Play, Simulator, Stats, Settings.
- **Live counting:** mark cards as they appear (click a 52-card grid or use
  hotkeys) — the running count and recommended bet update in real time.
- **Counting and play drills** (console): check your running/true count and
  basic-strategy decisions.
- **Simulator:** the bot plays N hands with basic strategy and index deviations
  (Illustrious 18). Betting modes: **flat**, **count spread**, and **fractional
  Kelly** (bet proportional to the bankroll). It reports EV, edge, drawdown,
  minimum bankroll, and **risk of ruin**; across many sessions it also reports a
  **95% confidence interval**.
- **Stats tab:** accumulated decision/count accuracy, simulation history, and a
  bankroll-curve chart.
- **State persistence:** training stats and the current live session are saved to
  JSON and restored on the next launch.
- **Play convenience:** hotkeys (H/S/D/P/R, N) plus sound and color feedback.
- The core uses only the standard library. `pytest` is needed for the tests.

## Running

Graphical interface:

```bash
python -m gui
```

or

```bash
python cli.py       # menu option 8
```

Console menu:

```bash
python cli.py
```

Option 7 is live counting straight in the console (enter cards like `10h`, `as`,
`k♦`).

## Live counting (GUI)

The **Count (live deal)** tab:

- Pick a counting system and the number of decks.
- Mark the cards that appear using the grid buttons (row = suit, column = rank) or
  hotkeys: `2-9`, `0`/`t`, `j`, `q`, `k`, `a` for a card, and `s`/`h`/`d`/`c` to
  select the current suit.
- The panel shows the **running count**, **true count**, decks remaining, and the
  recommended bet in units.
- Buttons: Undo (remove the last card), New shoe, Reset.
- The "Show count" checkbox on the Play tab hides the count so it does not give
  hints during practice.

## Simulator: ruin, Kelly, and confidence intervals

The **Simulator** tab:

- **Betting mode:**
  - *flat* — always 1 unit (control mode);
  - *count spread* — the bet grows with the true count (units × unit);
  - *Kelly* — the bet is proportional to the bankroll and edge (fractional Kelly;
    a "Kelly fraction" of 0.5 is half Kelly). The bankroll then grows
    exponentially, so multipliers become meaningful.
- **Table limit** — the maximum bet (0 = no limit).
- **Stop on ruin** — if the bankroll cannot cover the required bet, the session
  ends, and the report flags ruin and the **minimum bankroll** along the way.
- **Sessions > 1** — several independent sessions run with different seeds; the
  report shows the mean edge with a **95% confidence interval**, the distribution
  of the final bankroll (percentiles), and the **empirical risk of ruin**.

Risk of ruin is also estimated analytically with
`RoR ≈ exp(-2·EV·B/σ²)` (EV and σ are per hand in units, B is the bankroll in
units).

## Stats and persistence

The **Stats** tab shows:

- basic-strategy decision and count-check accuracy;
- the number of hands played and hands simulated;
- the history of recent simulations (system, result, edge, EV, drawdown);
- a **bankroll-curve chart** for the last simulation.

Data is stored in `%APPDATA%\blackjack_ai\state.json` (or
`~/blackjack_ai/state.json`):

- the **live session** (system, decks, and entered cards) is saved automatically
  and restored on the next launch — your count is not lost when you close the app;
- training stats and simulation history accumulate across launches;
- buttons on the stats tab let you clear the data.

Console menu option **9) Stats** shows the same accumulated figures.

## Hotkeys

**Play** tab: `H` — hit, `S` — stand, `D` — double, `P` — split, `R` — surrender,
`N` — new round. The "Sound" checkbox toggles a short beep (correct/incorrect),
and the hint color switches between green and purple.

**Count** tab: `2-9`, `0`/`t`, `j`, `q`, `k`, `a` — add a card,
`s`/`h`/`d`/`c` — select the current suit.

## Structure

```
blackjack/
  cards.py            cards, deck, shoe, hand total
  rules.py            table rules (decks, S17/H17, DAS, blackjack payout, ...)
  engine.py           round engine: deal, hit/stand/double/split/insurance, payouts
  strategy.py         basic strategy + index deviations
  counting/
    systems.py        counting-system definitions
    counter.py        running count, true count, bet sizing
modes/
  trainer.py          console counting and play drills
  live.py             live counting from a real deal (shared logic + console)
  simulator.py        bot simulator and statistics
gui/
  app.py              main window and settings tab
  live.py             live-counting tab
  play.py             play-vs-dealer tab
  sim.py              simulator tab (ruin, Kelly, confidence intervals)
  stats.py            stats tab and bankroll chart
  widgets.py          card rendering
storage.py            JSON persistence of stats and the live session
cli.py                console menu
tests/                pytest tests
```

## How counting works

For **balanced** systems the tags of a full deck sum to zero, so:

```
true count = running count / decks remaining
```

The higher the true count, the more tens and aces remain — the better the game
becomes. The bet grows (bet spread) as the true count rises. For **unbalanced**
systems (KO, Red Seven) the running count is used with an initial running count
(IRC) offset.

## Tests

```bash
python -m pytest
```

## License

Released under the [MIT License](LICENSE).

## Note

Card counting is not illegal, but casinos may refuse to let you play. This project
is intended for learning and simulation, not for covert assistance at a real
table.

---

## 📫 Contact

Open to freelance work and collaborations.

- Email: **bottiktik123@gmail.com**
- GitHub: [@bottk123-ctrl](https://github.com/bottk123-ctrl)
- Portfolio: [github.com/bottk123-ctrl/portfolio](https://github.com/bottk123-ctrl/portfolio)
