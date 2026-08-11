import os
import random
import numpy as np
import pandas as pd

from backtest import backtest_strategy
from config import EMA_FAST, EMA_SLOW, ATR_PERIOD, ATR_SL_MULTIPLIER, REWARD_RISK, MIN_SCORE
from data import get_bars

BARS = int(os.getenv("ROBUSTNESS_BARS", "4608"))
SYMBOL = os.getenv("ROBUSTNESS_SYMBOL", "XAUUSD")
TIMEFRAME = "M15"
MC_RUNS = int(os.getenv("MC_RUNS", "5000"))
SEED = int(os.getenv("MC_SEED", "1402"))

COSTS = (0.10, 0.15, 0.20)
SCORE_LEVELS = (76, 78, 80, 82)


def run(df, score=MIN_SCORE, rr=REWARD_RISK):
    return backtest_strategy(
        df=df,
        ema_fast=EMA_FAST,
        ema_slow=EMA_SLOW,
        atr_period=ATR_PERIOD,
        atr_sl_multiplier=ATR_SL_MULTIPLIER,
        reward_risk=rr,
        min_score=score,
    )


def path_metrics(sample):
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    current_loss_run = 0
    max_loss_run = 0

    for r in sample:
        equity += float(r)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

        if r < 0:
            current_loss_run += 1
            max_loss_run = max(max_loss_run, current_loss_run)
        else:
            current_loss_run = 0

    return equity, max_dd, max_loss_run


def bootstrap(trades, cost, runs, seed):
    raw = [float(t["r_multiple"]) for t in trades]
    n = len(raw)
    if n == 0:
        return None

    net_after_cost = [r - cost for r in raw]
    rng = np.random.default_rng(seed)

    finals = np.empty(runs, dtype=float)
    dds = np.empty(runs, dtype=float)
    loss_runs = np.empty(runs, dtype=float)

    for k in range(runs):
        # Resampling WITH replacement changes the terminal distribution,
        # unlike a simple permutation which preserves total R exactly.
        sample = rng.choice(net_after_cost, size=n, replace=True)
        final, max_dd, max_loss_run = path_metrics(sample)
        finals[k] = final
        dds[k] = max_dd
        loss_runs[k] = max_loss_run

    return {
        "p01": float(np.percentile(finals, 1)),
        "p05": float(np.percentile(finals, 5)),
        "p50": float(np.percentile(finals, 50)),
        "p95": float(np.percentile(finals, 95)),
        "prob_nonpositive_pct": float(np.mean(finals <= 0) * 100),
        "dd_p50": float(np.percentile(dds, 50)),
        "dd_p95": float(np.percentile(dds, 95)),
        "lossrun_p95": float(np.percentile(loss_runs, 95)),
    }


def summarize_direction(trades):
    rows = []
    for side in ("BUY", "SELL"):
        xs = [t for t in trades if t.get("signal") == side]
        n = len(xs)
        wins = sum(t.get("outcome") == "WIN" for t in xs)
        gross_p = sum(float(t["r_multiple"]) for t in xs if float(t["r_multiple"]) > 0)
        gross_l = abs(sum(float(t["r_multiple"]) for t in xs if float(t["r_multiple"]) < 0))
        pf = gross_p / gross_l if gross_l else (float("inf") if gross_p else 0.0)
        net = sum(float(t["r_multiple"]) for t in xs)
        rows.append({
            "side": side,
            "trades": n,
            "wins": wins,
            "win_rate": (wins / n * 100) if n else 0.0,
            "pf": pf,
            "net_r": net,
        })
    return rows


def main():
    print("=" * 76)
    print("FOREX AUTO TRADER PRO - GOLD V14 STRESS TEST V2")
    print("=" * 76)
    print(f"Symbol          : {SYMBOL}")
    print(f"Timeframe       : {TIMEFRAME}")
    print(f"Bars requested  : {BARS}")
    print(f"Bootstrap runs  : {MC_RUNS}")
    print(f"Seed            : {SEED}")
    print("Live trading    : NOT ENABLED")
    print()

    df = get_bars(SYMBOL, TIMEFRAME, count=BARS, source="YAHOO")
    base = run(df)

    trades = base["trades"]
    n = len(trades)

    if n < 20:
        print(f"NOT_READY | only {n} trades available")
        raise SystemExit(2)

    print("BASELINE")
    print("-" * 76)
    print(f"Trades       : {n}")
    print(f"Win Rate     : {base['win_rate']}%")
    print(f"Profit Factor: {base['profit_factor']}")
    print(f"Net R        : {base['net_r']}")
    print(f"Expectancy R : {base['expectancy_r']}")

    print("\nDIRECTION")
    direction_rows = summarize_direction(trades)
    for row in direction_rows:
        print(
            f"{row['side']:5} trades={row['trades']:>3} "
            f"wins={row['wins']:>3} WR={row['win_rate']:>6.2f}% "
            f"PF={row['pf']} netR={row['net_r']:>7.3f}"
        )

    print("\nBOOTSTRAP COST STRESS")
    print("-" * 76)

    stress_rows = []
    for cost in COSTS:
        raw_after = base["net_r"] - cost * n
        boot = bootstrap(trades, cost, MC_RUNS, SEED + int(cost * 100))

        print(f"cost={cost:.2f}R | deterministic_after_cost={raw_after:.3f}")
        print(
            f"  P01={boot['p01']:.3f} P05={boot['p05']:.3f} "
            f"P50={boot['p50']:.3f} P95={boot['p95']:.3f}"
        )
        print(
            f"  prob(final<=0)={boot['prob_nonpositive_pct']:.2f}% "
            f"DD_P50={boot['dd_p50']:.3f} DD_P95={boot['dd_p95']:.3f} "
            f"lossrun_P95={boot['lossrun_p95']:.0f}"
        )

        stress_rows.append({
            "cost_r": cost,
            "deterministic_after_cost_r": raw_after,
            **boot,
        })

    print("\nSCORE SENSITIVITY")
    print("-" * 76)
    sensitivity_rows = []

    for score in SCORE_LEVELS:
        r = run(df, score=score)
        after = r["net_r"] - 0.10 * r["total_trades"]
        print(
            f"score={score:>2} trades={r['total_trades']:>3} "
            f"WR={r['win_rate']:>6.2f}% PF={r['profit_factor']:>6} "
            f"netR={r['net_r']:>7.3f} after0.10R={after:>7.3f}"
        )
        sensitivity_rows.append({
            "score": score,
            "trades": r["total_trades"],
            "win_rate": r["win_rate"],
            "profit_factor": r["profit_factor"],
            "net_r": r["net_r"],
            "after_cost_010_r": after,
        })

    print("\nDECISION")
    print("-" * 76)

    c10 = next(x for x in stress_rows if x["cost_r"] == 0.10)
    c15 = next(x for x in stress_rows if x["cost_r"] == 0.15)
    c20 = next(x for x in stress_rows if x["cost_r"] == 0.20)

    checks = {
        "deterministic_010_positive": c10["deterministic_after_cost_r"] > 0,
        "bootstrap_010_p05_positive": c10["p05"] > 0,
        "bootstrap_010_nonpositive_lt_10pct": c10["prob_nonpositive_pct"] < 10.0,
        "deterministic_015_positive": c15["deterministic_after_cost_r"] > 0,
        "deterministic_020_positive": c20["deterministic_after_cost_r"] > 0,
    }

    for k, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'} | {k}")

    status = "PASS" if all(checks.values()) else "NOT_READY"
    print(f"\nV14 STRESS V2 STATUS : {status}")
    print("No live-trading setting is changed by this audit.")

    pd.DataFrame(stress_rows).to_csv("gold_v14_bootstrap_stress.csv", index=False)
    pd.DataFrame(direction_rows).to_csv("gold_v14_direction_stress.csv", index=False)
    pd.DataFrame(sensitivity_rows).to_csv("gold_v14_score_sensitivity.csv", index=False)


if __name__ == "__main__":
    main()
