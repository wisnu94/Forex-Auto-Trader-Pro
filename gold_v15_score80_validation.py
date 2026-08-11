import os
import numpy as np
import pandas as pd

from backtest import backtest_strategy
from config import EMA_FAST, EMA_SLOW, ATR_PERIOD, ATR_SL_MULTIPLIER, REWARD_RISK
from data import get_bars

BARS = int(os.getenv("ROBUSTNESS_BARS", "4608"))
SYMBOL = os.getenv("ROBUSTNESS_SYMBOL", "XAUUSD")
TIMEFRAME = "M15"
SCORE = int(os.getenv("TEST_SCORE", "80"))
COST = float(os.getenv("AUDIT_COST_R", "0.10"))

def run(df):
    return backtest_strategy(
        df=df,
        ema_fast=EMA_FAST,
        ema_slow=EMA_SLOW,
        atr_period=ATR_PERIOD,
        atr_sl_multiplier=ATR_SL_MULTIPLIER,
        reward_risk=REWARD_RISK,
        min_score=SCORE,
    )

def summary(label, r):
    n = r["total_trades"]
    after = float(r["net_r"]) - COST * n
    print("-" * 72)
    print(label)
    print("-" * 72)
    print(f"Trades            : {n}")
    print(f"Win Rate          : {r['win_rate']}%")
    print(f"Profit Factor     : {r['profit_factor']}")
    print(f"Net R             : {r['net_r']}")
    print(f"Expectancy R      : {r['expectancy_r']}")
    print(f"After cost {COST:.2f}R : {after:.4f}")
    return {
        "label": label,
        "trades": n,
        "win_rate": r["win_rate"],
        "profit_factor": r["profit_factor"],
        "net_r": r["net_r"],
        "expectancy_r": r["expectancy_r"],
        "after_cost_r": after,
    }

def seg(df, a, b):
    x = df.iloc[int(len(df)*a):int(len(df)*b)].reset_index(drop=True)
    if len(x) < EMA_SLOW + 120:
        return None
    return run(x)

def main():
    print("=" * 72)
    print("FOREX AUTO TRADER PRO - GOLD V15 SCORE 80 VALIDATION")
    print("=" * 72)
    print(f"Bars        : {BARS}")
    print(f"Score       : {SCORE}")
    print(f"Cost        : {COST:.2f}R")
    print("Parameter fitting: NONE")
    print("Live trading: NOT ENABLED")
    print()

    df = get_bars(SYMBOL, TIMEFRAME, count=BARS, source="YAHOO")

    full = run(df)
    rows = [summary("FULL SAMPLE", full)]

    windows = [
        ("W1 0-50%", 0.00, 0.50),
        ("W2 25-75%", 0.25, 0.75),
        ("W3 50-100%", 0.50, 1.00),
        ("W4 0-60%", 0.00, 0.60),
        ("W5 40-100%", 0.40, 1.00),
        ("HOLDOUT 40%", 0.60, 1.00),
        ("HOLDOUT 30%", 0.70, 1.00),
        ("HOLDOUT 25%", 0.75, 1.00),
        ("HOLDOUT 50%", 0.50, 1.00),
    ]

    for label, a, b in windows:
        r = seg(df, a, b)
        if r is not None:
            rows.append(summary(label, r))

    print("\nDECISION")
    print("-" * 72)

    full_row = rows[0]
    window_rows = rows[1:]

    checks = {
        "full_after_cost_positive": full_row["after_cost_r"] > 0,
        "full_trade_count_30_plus": full_row["trades"] >= 30,
        "holdout_40_positive": any(
            x["label"] == "HOLDOUT 40%" and x["after_cost_r"] > 0
            for x in window_rows
        ),
        "holdout_30_positive": any(
            x["label"] == "HOLDOUT 30%" and x["after_cost_r"] > 0
            for x in window_rows
        ),
        "holdout_25_positive": any(
            x["label"] == "HOLDOUT 25%" and x["after_cost_r"] > 0
            for x in window_rows
        ),
        "majority_windows_positive": (
            sum(x["after_cost_r"] > 0 for x in window_rows)
            >= max(1, int(len(window_rows) * 0.60))
        ),
    }

    for k, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'} | {k}")

    status = "PASS" if all(checks.values()) else "NOT_READY"
    print(f"\nV15 SCORE {SCORE} STATUS : {status}")
    print("No live-trading setting is changed by this audit.")

    pd.DataFrame(rows).to_csv("gold_v15_score80_validation.csv", index=False)

if __name__ == "__main__":
    main()
