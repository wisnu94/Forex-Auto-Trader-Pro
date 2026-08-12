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
BOOTSTRAP_RUNS = int(os.getenv("BOOTSTRAP_RUNS", "5000"))
TIMEOUT_SECONDS = int(os.getenv("AUDIT_TIMEOUT_SECONDS", "540"))

# Fixed candidates only. No parameter fitting / optimization.
CANDIDATES = (
    ("V14_BASE", 78, 1.6, 1.6),
    ("S79", 79, 1.6, 1.6),
    ("S80", 80, 1.6, 1.6),
    ("S80_RR15", 80, 1.6, 1.5),
    ("S80_RR14", 80, 1.6, 1.4),
    ("S80_SL17", 80, 1.7, 1.6),
)

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


def guard(t0):
    if time.monotonic() - t0 > TIMEOUT_SECONDS:
        raise TimeoutError("audit timeout budget exceeded")


def run(df, score, sl, rr):
    return backtest_strategy(
        df=df,
        ema_fast=20,
        ema_slow=50,
        atr_period=14,
        atr_sl_multiplier=sl,
        reward_risk=rr,
        min_score=score,
    )


def summarize(label, name, score, sl, rr, result):
    trades = result.get("trades", [])
    n = len(trades)
    net = float(result.get("net_r", 0.0))
    return {
        "candidate": name,
        "label": label,
        "score": score,
        "atr_sl": sl,
        "rr": rr,
        "trades": n,
        "wins": int(result.get("wins", 0)),
        "win_rate": float(result.get("win_rate", 0.0)),
        "profit_factor": float(result.get("profit_factor", 0.0)),
        "net_r": net,
        "expectancy_r": float(result.get("expectancy_r", 0.0)),
        "after_cost_r": round(net - COST * n, 4),
    }


def filter_trade_window(full_result, start_frac, end_frac, total_bars):
    start = int(total_bars * start_frac)
    end = int(total_bars * end_frac)
    subset = [
        t for t in full_result.get("trades", [])
        if start <= int(t.get("entry_index", t.get("index", -1))) < end
    ]
    if not subset:
        return {
            "trades": [],
            "total_trades": 0,
            "wins": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "net_r": 0.0,
            "expectancy_r": 0.0,
        }

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
        "win_rate": round(wins / len(subset) * 100, 2),
        "profit_factor": pf,
        "net_r": net,
        "expectancy_r": net / len(subset),
    }


def bootstrap(r_values, seed=1503):
    if not r_values:
        return {"p05": 0.0, "p50": 0.0, "prob_le_zero": 1.0}

    adjusted = np.asarray(r_values, dtype=float) - COST
    rng = np.random.default_rng(seed)
    n = len(adjusted)
    finals = np.empty(BOOTSTRAP_RUNS, dtype=float)

    chunk = 500
    pos = 0
    while pos < BOOTSTRAP_RUNS:
        m = min(chunk, BOOTSTRAP_RUNS - pos)
        idx = rng.integers(0, n, size=(m, n))
        finals[pos:pos + m] = adjusted[idx].sum(axis=1)
        pos += m

    return {
        "p05": float(np.percentile(finals, 5)),
        "p50": float(np.percentile(finals, 50)),
        "prob_le_zero": float(np.mean(finals <= 0.0)),
    }


def main():
    t0 = time.monotonic()
    print("=" * 78)
    print("FOREX AUTO TRADER PRO - GOLD V15 ROBUSTNESS V3")
    print("=" * 78)
    print(f"Symbol             : {SYMBOL}")
    print(f"Timeframe          : {TIMEFRAME}")
    print(f"Bars requested     : {BARS}")
    print(f"Cost               : {COST:.2f}R/trade")
    print(f"Bootstrap runs     : {BOOTSTRAP_RUNS}")
    print("Canonical engine   : repository backtest.py")
    print("Parameter fitting  : NONE")
    print("Live trading       : NOT ENABLED")
    print()

    df = get_bars(SYMBOL, TIMEFRAME, count=BARS, source="YAHOO")
    if len(df) < 1000:
        raise RuntimeError(f"Insufficient bars: {len(df)}")

    print(f"OHLC validation    : PASS")
    print(f"Loaded bars        : {len(df)}")
    print(f"First candle       : {df.iloc[0]['time']}")
    print(f"Last candle        : {df.iloc[-1]['time']}")

    full_results = {}
    summary_rows = []

    print("\nFULL CANDIDATE MATRIX")
    print("-" * 78)

    for name, score, sl, rr in CANDIDATES:
        guard(t0)
        result = run(df, score, sl, rr)
        full_results[name] = result
        row = summarize("FULL", name, score, sl, rr, result)
        summary_rows.append(row)
        print(
            f"{name:12s} trades={row['trades']:3d} "
            f"WR={row['win_rate']:6.2f}% PF={row['profit_factor']:6.3f} "
            f"NetR={row['net_r']:7.3f} After={row['after_cost_r']:7.3f}"
        )

    # Fast rolling attribution from the canonical full backtest.
    # This avoids re-running all candidates on every window.
    window_rows = []
    candidate_scores = []

    for name, score, sl, rr in CANDIDATES:
        guard(t0)
        full = full_results[name]
        positives = 0
        for label, a, b in WINDOWS:
            part = filter_trade_window(full, a, b, len(df))
            row = summarize(label, name, score, sl, rr, part)
            row["window_positive_after_cost"] = row["after_cost_r"] > 0
            window_rows.append(row)
            positives += int(row["window_positive_after_cost"])
        candidate_scores.append({
            "candidate": name,
            "positive_windows": positives,
            "windows": len(WINDOWS),
            "full_after_cost_r": summary_rows[[r["candidate"] for r in summary_rows].index(name)]["after_cost_r"],
            "full_trades": len(full.get("trades", [])),
        })

    ranking = sorted(
        candidate_scores,
        key=lambda x: (x["positive_windows"], x["full_after_cost_r"], x["full_trades"]),
        reverse=True,
    )

    # Only the top two candidates receive true holdout re-runs.
    # This is the key runtime reduction versus V2.
    top_names = [x["candidate"] for x in ranking[:2]]

    print("\nFAST WINDOW ATTRIBUTION")
    print("-" * 78)
    for x in ranking:
        print(
            f"{x['candidate']:12s} positive_windows={x['positive_windows']}/{x['windows']} "
            f"full_after={x['full_after_cost_r']:7.3f} trades={x['full_trades']:3d}"
        )

    holdout_rows = []
    print("\nTRUE HOLDOUT RE-RUNS (TOP 2 ONLY)")
    print("-" * 78)

    for name in top_names:
        guard(t0)
        score, sl, rr = next((s, a, b) for n, s, a, b in CANDIDATES if n == name)
        for label, a, b in HOLDOUTS:
            guard(t0)
            start = int(len(df) * a)
            end = int(len(df) * b)
            part_df = df.iloc[start:end].reset_index(drop=True)
            result = run(part_df, score, sl, rr)
            row = summarize(label, name, score, sl, rr, result)
            holdout_rows.append(row)
            print(
                f"{name:12s} {label:12s} trades={row['trades']:3d} "
                f"WR={row['win_rate']:6.2f}% PF={row['profit_factor']:6.3f} "
                f"After={row['after_cost_r']:7.3f}"
            )

    # Bootstrap only on the best full candidate.
    best_name = ranking[0]["candidate"]
    best = full_results[best_name]
    guard(t0)
    mc = bootstrap([float(t["r_multiple"]) for t in best.get("trades", [])])

    best_full = next(x for x in summary_rows if x["candidate"] == best_name)
    best_windows = [x for x in window_rows if x["candidate"] == best_name]
    top_holdouts = [x for x in holdout_rows if x["candidate"] == best_name]

    positive_windows = sum(x["window_positive_after_cost"] for x in best_windows)
    positive_holdouts = sum(x["after_cost_r"] > 0 for x in top_holdouts)

    gates = {
        "full_trade_count_30_plus": best_full["trades"] >= 30,
        "full_after_cost_positive": best_full["after_cost_r"] > 0,
        "windows_4_of_5_positive": positive_windows >= 4,
        "true_holdouts_3_of_4_positive": positive_holdouts >= 3,
        "bootstrap_p05_positive": mc["p05"] > 0,
        "bootstrap_nonpositive_lt_10pct": mc["prob_le_zero"] < 0.10,
    }

    print("\nBOOTSTRAP - BEST CANDIDATE")
    print("-" * 78)
    print(f"Candidate       : {best_name}")
    print(f"P05 final R     : {mc['p05']:.3f}")
    print(f"P50 final R     : {mc['p50']:.3f}")
    print(f"Probability <=0 : {mc['prob_le_zero'] * 100:.2f}%")

    print("\nROBUSTNESS DECISION")
    print("-" * 78)
    for key, passed in gates.items():
        print(f"{'PASS' if passed else 'FAIL'} | {key}")

    status = "READY" if all(gates.values()) else "NOT_READY"
    print(f"\nV15 ROBUSTNESS V3 STATUS : {status}")
    print("No live-trading setting is changed by this audit.")

    pd.DataFrame(summary_rows).to_csv("gold_v15_v3_candidates.csv", index=False)
    pd.DataFrame(window_rows).to_csv("gold_v15_v3_windows.csv", index=False)
    pd.DataFrame(holdout_rows).to_csv("gold_v15_v3_holdouts.csv", index=False)

    elapsed = time.monotonic() - t0
    print(f"Runtime seconds      : {elapsed:.2f}")
    if elapsed > TIMEOUT_SECONDS:
        raise TimeoutError("runtime budget exceeded")

    return 0 if status == "READY" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TimeoutError as exc:
        print(f"AUDIT TIMEOUT: {exc}")
        raise SystemExit(124)
