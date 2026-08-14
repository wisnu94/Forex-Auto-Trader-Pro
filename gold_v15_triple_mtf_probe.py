"""V15 structural probe: require H1 + M15 + M1 alignment for S80.

This is an experiment only. It does not modify live trading configuration.
It reuses the canonical backtest and tightens entry confirmation by rejecting
signals whose synthetic M1 trend does not agree with H1/M15.
"""
from __future__ import annotations

import os
import time
import numpy as np
import pandas as pd

import backtest as bt
from data import get_bars

BARS = int(os.getenv("ROBUSTNESS_BARS", "4608"))
SYMBOL = os.getenv("ROBUSTNESS_SYMBOL", "XAUUSD")
COST = float(os.getenv("AUDIT_COST_R", "0.10"))
BOOTSTRAP_RUNS = min(int(os.getenv("BOOTSTRAP_RUNS", "1500")), 1500)
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


def summarize(label, result):
    trades = result.get("trades", [])
    n = len(trades)
    net = float(result.get("net_r", 0.0))
    return {
        "candidate": "S80_M1_CONFIRM",
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


def filter_trades(full, a, b, total_bars):
    start, end = int(total_bars * a), int(total_bars * b)
    subset = [t for t in full.get("trades", []) if start <= int(t.get("entry_index", t.get("index", -1))) < end]
    r = [float(t["r_multiple"]) for t in subset]
    wins = sum(x > 0 for x in r)
    gp = sum(x for x in r if x > 0)
    gl = abs(sum(x for x in r if x < 0))
    pf = gp / gl if gl else (float("inf") if gp else 0.0)
    net = sum(r)
    return {"trades": subset, "wins": wins, "win_rate": wins / len(subset) * 100 if subset else 0.0,
            "profit_factor": pf, "net_r": net, "expectancy_r": net / len(subset) if subset else 0.0}


def bootstrap(values, seed=1604):
    if not values:
        return 0.0, 0.0, 1.0
    x = np.asarray(values, dtype=float) - COST
    rng = np.random.default_rng(seed)
    n = len(x)
    finals = np.empty(BOOTSTRAP_RUNS)
    for start in range(0, BOOTSTRAP_RUNS, 500):
        m = min(500, BOOTSTRAP_RUNS - start)
        idx = rng.integers(0, n, size=(m, n))
        finals[start:start + m] = x[idx].sum(axis=1)
    return float(np.percentile(finals, 5)), float(np.percentile(finals, 50)), float(np.mean(finals <= 0))


def main():
    print("=" * 78)
    print("FOREX AUTO TRADER PRO - GOLD V15 TRIPLE MTF PROBE")
    print("=" * 78)
    print(f"Symbol : {SYMBOL} | M15 | bars={BARS} | S80 | SL={SL} | RR={RR}")
    print("Experiment: require H1 + M15 + M1 trend alignment")
    print("Live trading: NOT ENABLED")

    df = get_bars(SYMBOL, "M15", count=BARS, source="YAHOO")
    if len(df) < 1000:
        raise RuntimeError(f"Insufficient bars: {len(df)}")

    original = bt.generate_signal

    def triple_mtf_signal(*args, **kwargs):
        result = original(*args, **kwargs)
        if result.get("signal") in ("BUY", "SELL"):
            mtf = kwargs.get("mtf_confirmation") or {}
            trends = mtf.get("trends", {}) if isinstance(mtf, dict) else {}
            side = result["signal"]
            if trends.get("H1") != side or trends.get("M15") != side or trends.get("M1") != side:
                result = dict(result)
                result["signal"] = "HOLD"
                result["precision_pass"] = False
        return result

    bt.generate_signal = triple_mtf_signal
    t0 = time.monotonic()
    full = bt.backtest_strategy(df=df, ema_fast=20, ema_slow=50, atr_period=14,
                                atr_sl_multiplier=SL, reward_risk=RR, min_score=SCORE)
    row = summarize("FULL", full)
    print("\nFULL SAMPLE")
    print(f"Trades={row['trades']} WR={row['win_rate']:.2f}% PF={row['profit_factor']:.3f} NetR={row['net_r']:.3f} After={row['after_cost_r']:.3f}")

    windows, holdouts = [], []
    print("\nWINDOWS")
    for label, a, b in WINDOWS:
        x = summarize(label, filter_trades(full, a, b, len(df)))
        x["positive"] = x["after_cost_r"] > 0
        windows.append(x)
        print(f"{label:14s} trades={x['trades']:3d} WR={x['win_rate']:6.2f}% PF={x['profit_factor']:.3f} After={x['after_cost_r']:7.3f}")

    print("\nHOLDOUTS")
    for label, a, b in HOLDOUTS:
        x = summarize(label, filter_trades(full, a, b, len(df)))
        x["positive"] = x["after_cost_r"] > 0
        holdouts.append(x)
        print(f"{label:14s} trades={x['trades']:3d} WR={x['win_rate']:6.2f}% PF={x['profit_factor']:.3f} After={x['after_cost_r']:7.3f}")

    p05, p50, prob = bootstrap([float(t["r_multiple"]) for t in full.get("trades", [])])
    print("\nBOOTSTRAP")
    print(f"P05={p05:.3f} P50={p50:.3f} Prob<=0={prob*100:.2f}%")

    print("\nPROBE DECISION")
    print(f"Trades >= 20       : {'PASS' if row['trades'] >= 20 else 'FAIL'}")
    print(f"After cost positive: {'PASS' if row['after_cost_r'] > 0 else 'FAIL'}")
    print(f"Windows 4/5        : {'PASS' if sum(x['positive'] for x in windows) >= 4 else 'FAIL'}")
    print(f"Holdouts 3/4        : {'PASS' if sum(x['positive'] for x in holdouts) >= 3 else 'FAIL'}")
    print(f"Bootstrap P05 > 0  : {'PASS' if p05 > 0 else 'FAIL'}")
    print(f"Prob <=0 < 10%     : {'PASS' if prob < 0.10 else 'FAIL'}")
    print("STATUS: PASS_CANDIDATE" if row['after_cost_r'] > 0 and sum(x['positive'] for x in holdouts) >= 3 else "STATUS: REJECT_CANDIDATE")
    print(f"Runtime seconds={time.monotonic()-t0:.2f}")

    pd.DataFrame([row]).to_csv("gold_v15_triple_mtf_full.csv", index=False)
    pd.DataFrame(windows).to_csv("gold_v15_triple_mtf_windows.csv", index=False)
    pd.DataFrame(holdouts).to_csv("gold_v15_triple_mtf_holdouts.csv", index=False)


if __name__ == "__main__":
    main()
