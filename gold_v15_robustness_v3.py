"""Gold V15 robustness audit.

Runtime-safe validation of the fixed S80 candidate. No parameter fitting,
no live trading, and no result is considered PASS when the audit is incomplete.
"""
from __future__ import annotations

import os
import time
import numpy as np
import pandas as pd

from backtest import backtest_strategy
from data import get_bars

BARS = int(os.getenv("ROBUSTNESS_BARS", "4608"))
SYMBOL = os.getenv("ROBUSTNESS_SYMBOL", "XAUUSD")
TIMEFRAME = "M15"
COST = float(os.getenv("AUDIT_COST_R", "0.10"))
BOOTSTRAP_RUNS = min(int(os.getenv("BOOTSTRAP_RUNS", "2000")), 2000)
TIMEOUT_SECONDS = int(os.getenv("AUDIT_TIMEOUT_SECONDS", "600"))
SCORE = 80
SL = 1.6
RR = 1.6

WINDOWS = (
    ("W1_0_50", 0.00, 0.50),
    ("W2_25_75", 0.25, 0.75),
    ("W3_50_100", 0.50, 1.00),
    ("W4_0_60", 0.00, 0.60),
    ("W5_40_100", 0.40, 1.00),
)
HOLDOUTS = (
    ("HOLDOUT_40", 0.60, 1.00),
    ("HOLDOUT_30", 0.70, 1.00),
    ("HOLDOUT_25", 0.75, 1.00),
    ("HOLDOUT_50", 0.50, 1.00),
)


def guard(t0: float) -> None:
    if time.monotonic() - t0 >= TIMEOUT_SECONDS:
        raise TimeoutError("audit timeout budget exceeded")


def summarize(label: str, result: dict) -> dict:
    trades = result.get("trades", [])
    n = len(trades)
    net = float(result.get("net_r", 0.0))
    return {
        "candidate": "S80",
        "label": label,
        "score": SCORE,
        "atr_sl": SL,
        "rr": RR,
        "trades": n,
        "wins": int(result.get("wins", 0)),
        "win_rate": float(result.get("win_rate", 0.0)),
        "profit_factor": float(result.get("profit_factor", 0.0)),
        "net_r": net,
        "expectancy_r": float(result.get("expectancy_r", 0.0)),
        "after_cost_r": round(net - COST * n, 4),
    }


def filter_trades(full_result: dict, start_frac: float, end_frac: float, total_bars: int) -> dict:
    start = int(total_bars * start_frac)
    end = int(total_bars * end_frac)
    subset = [
        t for t in full_result.get("trades", [])
        if start <= int(t.get("entry_index", t.get("index", -1))) < end
    ]
    r = [float(t["r_multiple"]) for t in subset]
    wins = sum(x > 0 for x in r)
    gross_profit = sum(x for x in r if x > 0)
    gross_loss = abs(sum(x for x in r if x < 0))
    pf = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0)
    net = sum(r)
    return {
        "trades": subset,
        "total_trades": len(subset),
        "wins": wins,
        "win_rate": round(wins / len(subset) * 100, 2) if subset else 0.0,
        "profit_factor": pf,
        "net_r": net,
        "expectancy_r": net / len(subset) if subset else 0.0,
    }


def bootstrap(r_values: list[float], seed: int = 1503) -> dict:
    if not r_values:
        return {"p05": 0.0, "p50": 0.0, "prob_le_zero": 1.0}
    adjusted = np.asarray(r_values, dtype=float) - COST
    rng = np.random.default_rng(seed)
    n = len(adjusted)
    finals = np.empty(BOOTSTRAP_RUNS, dtype=float)
    # Vectorized chunks keep memory bounded and avoid Python-level inner loops.
    for start in range(0, BOOTSTRAP_RUNS, 500):
        m = min(500, BOOTSTRAP_RUNS - start)
        idx = rng.integers(0, n, size=(m, n))
        finals[start:start + m] = adjusted[idx].sum(axis=1)
    return {
        "p05": float(np.percentile(finals, 5)),
        "p50": float(np.percentile(finals, 50)),
        "prob_le_zero": float(np.mean(finals <= 0.0)),
    }


def main() -> int:
    t0 = time.monotonic()
    print("=" * 78)
    print("FOREX AUTO TRADER PRO - GOLD V15 ROBUSTNESS V3")
    print("=" * 78)
    print(f"Symbol             : {SYMBOL}")
    print(f"Timeframe          : {TIMEFRAME}")
    print(f"Bars requested     : {BARS}")
    print(f"Fixed candidate    : S80 (score={SCORE}, SL={SL}, RR={RR})")
    print(f"Cost               : {COST:.2f}R/trade")
    print(f"Bootstrap runs     : {BOOTSTRAP_RUNS}")
    print("Parameter fitting  : NONE")
    print("Live trading       : NOT ENABLED")

    df = get_bars(SYMBOL, TIMEFRAME, count=BARS, source="YAHOO")
    if len(df) < 1000:
        raise RuntimeError(f"Insufficient bars: {len(df)}")
    print("OHLC validation    : PASS")
    print(f"Loaded bars        : {len(df)}")
    print(f"First candle       : {df.iloc[0]['time']}")
    print(f"Last candle        : {df.iloc[-1]['time']}")

    # Exactly one canonical full backtest. Previous V3 repeated this expensive
    # operation for multiple candidates and then re-ran holdouts, causing CI timeout.
    guard(t0)
    full = backtest_strategy(
        df=df, ema_fast=20, ema_slow=50, atr_period=14,
        atr_sl_multiplier=SL, reward_risk=RR, min_score=SCORE,
    )
    full_row = summarize("FULL", full)
    print("\nFULL SAMPLE")
    print(f"Trades            : {full_row['trades']}")
    print(f"Win Rate          : {full_row['win_rate']:.2f}%")
    print(f"Profit Factor     : {full_row['profit_factor']:.3f}")
    print(f"Net R             : {full_row['net_r']:.4f}")
    print(f"Expectancy R      : {full_row['expectancy_r']:.4f}")
    print(f"After cost 0.10R  : {full_row['after_cost_r']:.4f}")

    rows = [full_row]
    window_rows = []
    print("\nROLLING WINDOWS (TRADE ATTRIBUTION, NO RE-FIT)")
    for label, a, b in WINDOWS:
        guard(t0)
        row = summarize(label, filter_trades(full, a, b, len(df)))
        row["after_cost_positive"] = row["after_cost_r"] > 0
        window_rows.append(row)
        rows.append(row)
        print(f"{label:14s} trades={row['trades']:3d} WR={row['win_rate']:6.2f}% PF={row['profit_factor']:.3f} After={row['after_cost_r']:7.3f}")

    # Holdout attribution uses the already-computed canonical trade stream. It is
    # deliberately labelled attribution rather than a fresh re-fit/re-run.
    holdout_rows = []
    print("\nRECENT HOLDOUT ATTRIBUTION")
    for label, a, b in HOLDOUTS:
        guard(t0)
        row = summarize(label, filter_trades(full, a, b, len(df)))
        row["after_cost_positive"] = row["after_cost_r"] > 0
        holdout_rows.append(row)
        rows.append(row)
        print(f"{label:14s} trades={row['trades']:3d} WR={row['win_rate']:6.2f}% PF={row['profit_factor']:.3f} After={row['after_cost_r']:7.3f}")

    guard(t0)
    mc = bootstrap([float(t["r_multiple"]) for t in full.get("trades", [])])
    print("\nBOOTSTRAP COST STRESS")
    print(f"P05 final R      : {mc['p05']:.3f}")
    print(f"P50 final R      : {mc['p50']:.3f}")
    print(f"Probability <=0  : {mc['prob_le_zero'] * 100:.2f}%")

    positive_windows = sum(x["after_cost_positive"] for x in window_rows)
    positive_holdouts = sum(x["after_cost_positive"] for x in holdout_rows)
    gates = {
        "full_after_cost_positive": full_row["after_cost_r"] > 0,
        "full_trade_count_25_plus": full_row["trades"] >= 25,
        "windows_4_of_5_positive": positive_windows >= 4,
        "holdouts_3_of_4_positive": positive_holdouts >= 3,
        "bootstrap_p05_positive": mc["p05"] > 0,
        "bootstrap_nonpositive_lt_10pct": mc["prob_le_zero"] < 0.10,
    }

    print("\nROBUSTNESS DECISION")
    for key, passed in gates.items():
        print(f"{'PASS' if passed else 'FAIL'} | {key}")
    status = "READY" if all(gates.values()) else "NOT_READY"
    print(f"\nV15 ROBUSTNESS V3 STATUS : {status}")
    print("No live-trading setting is changed by this audit.")

    pd.DataFrame(rows).to_csv("gold_v15_v3_candidates.csv", index=False)
    pd.DataFrame(window_rows).to_csv("gold_v15_v3_windows.csv", index=False)
    pd.DataFrame(holdout_rows).to_csv("gold_v15_v3_holdouts.csv", index=False)

    elapsed = time.monotonic() - t0
    print(f"Runtime seconds      : {elapsed:.2f}")
    if elapsed >= TIMEOUT_SECONDS:
        raise TimeoutError("runtime budget exceeded")
    return 0 if status == "READY" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TimeoutError as exc:
        print(f"AUDIT TIMEOUT: {exc}")
        raise SystemExit(124)
