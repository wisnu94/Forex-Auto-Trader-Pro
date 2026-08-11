import os
import pandas as pd
from backtest import backtest_strategy
from config import EMA_FAST, EMA_SLOW, ATR_PERIOD, ATR_SL_MULTIPLIER, REWARD_RISK, MIN_SCORE
from data import get_bars

BARS = int(os.getenv("ROBUSTNESS_BARS", "4608"))
SYMBOL = os.getenv("ROBUSTNESS_SYMBOL", "XAUUSD")
TIMEFRAME = "M15"
COST_R = float(os.getenv("AUDIT_COST_R", "0.10"))

def run(df, rr=REWARD_RISK):
    return backtest_strategy(
        df=df,
        ema_fast=EMA_FAST,
        ema_slow=EMA_SLOW,
        atr_period=ATR_PERIOD,
        atr_sl_multiplier=ATR_SL_MULTIPLIER,
        reward_risk=rr,
        min_score=MIN_SCORE,
    )

def stats(label, r, cost=COST_R):
    n = r["total_trades"]
    net = float(r["net_r"])
    after = net - cost * n
    print("-" * 72)
    print(label)
    print("-" * 72)
    print(f"Trades            : {n}")
    print(f"Win Rate          : {r['win_rate']}%")
    print(f"Profit Factor     : {r['profit_factor']}")
    print(f"Net R             : {r['net_r']}")
    print(f"Expectancy R      : {r['expectancy_r']}")
    print(f"After cost {cost:.2f}R : {after:.4f}")
    return {
        "label": label,
        "trades": n,
        "win_rate": r["win_rate"],
        "profit_factor": r["profit_factor"],
        "net_r": net,
        "expectancy_r": r["expectancy_r"],
        "after_cost_r": after,
    }

def slice_run(df, start_frac, end_frac):
    start = int(len(df) * start_frac)
    end = int(len(df) * end_frac)
    seg = df.iloc[start:end].reset_index(drop=True)
    if len(seg) < EMA_SLOW + 120:
        return None
    return run(seg)

def rolling_windows(df):
    specs = [
        ("W1 0-50%", 0.00, 0.50),
        ("W2 25-75%", 0.25, 0.75),
        ("W3 50-100%", 0.50, 1.00),
        ("W4 0-60%", 0.00, 0.60),
        ("W5 40-100%", 0.40, 1.00),
    ]
    rows = []
    for label, a, b in specs:
        r = slice_run(df, a, b)
        if r is None:
            continue
        rows.append(stats(label, r))
    return rows

def holdout_sets(df):
    specs = [
        ("HOLDOUT_40_RECENT", 0.60, 1.00),
        ("HOLDOUT_30_RECENT", 0.70, 1.00),
        ("HOLDOUT_25_RECENT", 0.75, 1.00),
        ("HOLDOUT_50_RECENT", 0.50, 1.00),
    ]
    rows = []
    for label, a, b in specs:
        r = slice_run(df, a, b)
        if r is None:
            continue
        rows.append(stats(label, r))
    return rows

def main():
    print("=" * 72)
    print("FOREX AUTO TRADER PRO - GOLD V14 WALK-FORWARD AUDIT")
    print("=" * 72)
    print(f"Symbol            : {SYMBOL}")
    print(f"Timeframe         : {TIMEFRAME}")
    print(f"Bars requested    : {BARS}")
    print(f"Base RR           : {REWARD_RISK}")
    print(f"Cost stress       : {COST_R:.2f}R/trade")
    print("Strategy           : V14 baseline; NO parameter fitting")
    print("Live trading       : NOT ENABLED")
    print()

    df = get_bars(SYMBOL, TIMEFRAME, count=BARS, source="YAHOO")

    required = {"open", "high", "low", "close", "time"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing columns: {sorted(missing)}")

    print("OHLC validation    : PASS")
    print(f"Loaded bars        : {len(df)}")
    print(f"First candle       : {df.iloc[0]['time']}")
    print(f"Last candle        : {df.iloc[-1]['time']}")

    full = run(df)
    full_row = stats("FULL SAMPLE", full)

    print("\n" + "=" * 72)
    print("ROLLING WINDOWS")
    print("=" * 72)
    windows = rolling_windows(df)

    print("\n" + "=" * 72)
    print("MULTIPLE RECENT HOLDOUTS")
    print("=" * 72)
    holds = holdout_sets(df)

    # Stability summary:
    # A window passes only if it remains profitable after 0.10R cost.
    all_rows = windows + holds
    positive_after_cost = [x for x in all_rows if x["after_cost_r"] > 0]

    print("\n" + "=" * 72)
    print("V14 WALK-FORWARD DECISION")
    print("=" * 72)
    print(f"Positive-after-cost windows : {len(positive_after_cost)}/{len(all_rows)}")

    checks = {
        "full_after_cost_positive": full_row["after_cost_r"] > 0,
        "all_windows_majority_positive": (
            len(positive_after_cost) >= max(1, int(len(all_rows) * 0.60))
        ),
        "recent_40_positive": any(
            x["label"] == "HOLDOUT_40_RECENT" and x["after_cost_r"] > 0
            for x in holds
        ),
        "recent_30_positive": any(
            x["label"] == "HOLDOUT_30_RECENT" and x["after_cost_r"] > 0
            for x in holds
        ),
        "recent_25_positive": any(
            x["label"] == "HOLDOUT_25_RECENT" and x["after_cost_r"] > 0
            for x in holds
        ),
    }

    for name, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'} | {name}")

    ready = all(checks.values())
    print(f"\nV14 WALK-FORWARD STATUS : {'PASS' if ready else 'NOT_READY'}")
    print("No live-trading setting is changed by this audit.")

    pd.DataFrame(all_rows).to_csv("gold_v14_walkforward.csv", index=False)
    print("Saved: gold_v14_walkforward.csv")

if __name__ == "__main__":
    main()
