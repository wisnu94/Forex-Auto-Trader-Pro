import os
import numpy as np
import pandas as pd

from backtest import backtest_strategy
from data import get_bars

BARS = int(os.getenv("ROBUSTNESS_BARS", "4608"))
SYMBOL = os.getenv("ROBUSTNESS_SYMBOL", "XAUUSD")
TIMEFRAME = "M15"
COST = float(os.getenv("AUDIT_COST_R", "0.10"))

CANDIDATES = [
    {"name": "V15_BASE", "score": 78, "atr_sl": 1.6, "rr": 1.6},
    {"name": "V15_S80", "score": 80, "atr_sl": 1.6, "rr": 1.6},
    {"name": "S80_RR15", "score": 80, "atr_sl": 1.6, "rr": 1.5},
    {"name": "S80_RR14", "score": 80, "atr_sl": 1.6, "rr": 1.4},
    {"name": "S80_SL15", "score": 80, "atr_sl": 1.5, "rr": 1.6},
    {"name": "S80_SL17", "score": 80, "atr_sl": 1.7, "rr": 1.6},
]

WINDOWS = [
    ("W1_0_50", 0.00, 0.50),
    ("W2_25_75", 0.25, 0.75),
    ("W3_50_100", 0.50, 1.00),
    ("W4_0_60", 0.00, 0.60),
    ("W5_40_100", 0.40, 1.00),
    ("HOLDOUT_40", 0.60, 1.00),
    ("HOLDOUT_30", 0.70, 1.00),
    ("HOLDOUT_25", 0.75, 1.00),
    ("HOLDOUT_50", 0.50, 1.00),
]

def run(df, candidate):
    return backtest_strategy(
        df=df, ema_fast=20, ema_slow=50, atr_period=14,
        atr_sl_multiplier=candidate["atr_sl"],
        reward_risk=candidate["rr"],
        min_score=candidate["score"],
    )

def row(label, candidate, result):
    n = int(result["total_trades"])
    net = float(result["net_r"])
    return {
        "candidate": candidate["name"], "label": label,
        "score": candidate["score"], "atr_sl": candidate["atr_sl"],
        "rr": candidate["rr"], "trades": n,
        "win_rate": float(result["win_rate"]),
        "profit_factor": float(result["profit_factor"]),
        "net_r": net, "expectancy_r": float(result["expectancy_r"]),
        "after_cost_r": round(net - COST * n, 4),
    }

def segment(df, a, b):
    x = df.iloc[int(len(df)*a):int(len(df)*b)].reset_index(drop=True)
    return x if len(x) >= 250 else None

def evaluate_candidate(df, candidate):
    rows = [row("FULL", candidate, run(df, candidate))]
    for label, a, b in WINDOWS:
        x = segment(df, a, b)
        if x is not None:
            rows.append(row(label, candidate, run(x, candidate)))
    return rows

def bootstrap_final_r(trades, cost, runs=5000, seed=1501):
    values = np.asarray([float(t["r_multiple"]) - cost for t in trades], dtype=float)
    if len(values) == 0:
        return {"p05": 0.0, "p50": 0.0, "prob_le_zero": 1.0}
    rng = np.random.default_rng(seed)
    sample = rng.choice(values, size=(runs, len(values)), replace=True).sum(axis=1)
    return {
        "p05": float(np.percentile(sample, 5)),
        "p50": float(np.percentile(sample, 50)),
        "prob_le_zero": float(np.mean(sample <= 0)),
    }

def main():
    print("=" * 76)
    print("FOREX AUTO TRADER PRO - GOLD V15 ROBUSTNESS V2")
    print("=" * 76)
    print(f"Symbol          : {SYMBOL}")
    print(f"Timeframe       : {TIMEFRAME}")
    print(f"Bars requested  : {BARS}")
    print(f"Cost            : {COST:.2f}R/trade")
    print("Candidate fitting: NONE")
    print("Live trading     : NOT ENABLED")
    print()

    df = get_bars(SYMBOL, TIMEFRAME, count=BARS, source="YAHOO")
    if len(df) < 1000:
        raise RuntimeError(f"Insufficient bars: {len(df)}")

    all_rows, summaries = [], []
    for candidate in CANDIDATES:
        rows = evaluate_candidate(df, candidate)
        all_rows.extend(rows)
        by_label = {r["label"]: r for r in rows}
        window_rows = [r for r in rows if r["label"] != "FULL"]
        positives = sum(r["after_cost_r"] > 0 for r in window_rows)
        holdouts = [by_label.get(x) for x in
                    ("HOLDOUT_40","HOLDOUT_30","HOLDOUT_25","HOLDOUT_50")]
        summaries.append({
            "candidate": candidate["name"], "score": candidate["score"],
            "atr_sl": candidate["atr_sl"], "rr": candidate["rr"],
            "full_trades": by_label["FULL"]["trades"],
            "full_after_cost": by_label["FULL"]["after_cost_r"],
            "positive_windows": positives, "windows": len(window_rows),
            "holdout_positive": sum(x is not None and x["after_cost_r"] > 0 for x in holdouts),
            "holdouts": 4,
        })

    print("CANDIDATE MATRIX")
    print("-" * 76)
    for s in summaries:
        print(f'{s["candidate"]:10s} trades={s["full_trades"]:3d} '
              f'full_after={s["full_after_cost"]:7.3f} '
              f'windows={s["positive_windows"]}/{s["windows"]} '
              f'holdouts={s["holdout_positive"]}/{s["holdouts"]}')

    ready = [
        s["candidate"] for s in summaries
        if s["full_trades"] >= 30
        and s["full_after_cost"] > 0
        and s["positive_windows"] >= 6
        and s["holdout_positive"] >= 3
    ]

    print("\nROBUSTNESS GATE")
    print("-" * 76)
    print("Rules: full trades >=30; full after-cost >0; >=6/9 windows positive; >=3/4 holdouts positive")
    print(f"READY candidates: {ready if ready else 'NONE'}")

    ranked = sorted(summaries,
                    key=lambda x: (x["holdout_positive"],
                                   x["positive_windows"],
                                   x["full_after_cost"]),
                    reverse=True)
    best_name = ranked[0]["candidate"]
    best = next(c for c in CANDIDATES if c["name"] == best_name)
    mc = bootstrap_final_r(run(df, best)["trades"], COST)

    print("\nBOOTSTRAP CHECK - BEST CANDIDATE")
    print("-" * 76)
    print(f"Candidate       : {best_name}")
    print(f"Final R P05     : {mc['p05']:.3f}")
    print(f"Final R P50     : {mc['p50']:.3f}")
    print(f"Probability <=0 : {mc['prob_le_zero']*100:.2f}%")
    print("Bootstrap is diagnostic only and cannot override the gate.")

    pd.DataFrame(all_rows).to_csv("gold_v15_robustness_v2_windows.csv", index=False)
    pd.DataFrame(summaries).to_csv("gold_v15_robustness_v2_candidates.csv", index=False)

    status = "READY" if ready else "NOT_READY"
    print(f"\nV15 ROBUSTNESS V2 STATUS : {status}")
    print("No live-trading setting is changed by this audit.")

if __name__ == "__main__":
    main()
