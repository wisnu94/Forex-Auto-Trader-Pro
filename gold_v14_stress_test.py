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
COSTS = (0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30)
MC_RUNS = int(os.getenv("MC_RUNS", "5000"))
SEED = int(os.getenv("MC_SEED", "1401"))

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

def dd(trades):
    equity = peak = max_dd = 0.0
    for t in trades:
        equity += float(t["r_multiple"])
        peak = max(peak, equity)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd

def direction(trades):
    out = {}
    for s in ("BUY", "SELL"):
        xs = [t for t in trades if t.get("signal") == s]
        wins = sum(t.get("outcome") == "WIN" for t in xs)
        net = sum(float(t.get("r_multiple", 0.0)) for t in xs)
        gross_p = sum(float(t["r_multiple"]) for t in xs if float(t["r_multiple"]) > 0)
        gross_l = abs(sum(float(t["r_multiple"]) for t in xs if float(t["r_multiple"]) < 0))
        pf = gross_p / gross_l if gross_l else (float("inf") if gross_p else 0.0)
        out[s] = (len(xs), wins, net, pf)
    return out

def main():
    print("=" * 72)
    print("FOREX AUTO TRADER PRO - GOLD V14 STRESS TEST")
    print("=" * 72)
    print(f"Symbol          : {SYMBOL}")
    print(f"Timeframe       : {TIMEFRAME}")
    print(f"Bars requested  : {BARS}")
    print(f"Monte Carlo runs: {MC_RUNS}")
    print(f"Seed            : {SEED}")
    print("Live trading    : NOT ENABLED")
    print()

    df = get_bars(SYMBOL, TIMEFRAME, count=BARS, source="YAHOO")
    result = run(df)
    trades = result["trades"]
    n = len(trades)

    if n < 20:
        print(f"FAIL | only {n} trades available for stress test")
        raise SystemExit(2)

    base = float(result["net_r"])
    print(f"Trades          : {n}")
    print(f"Win Rate        : {result['win_rate']}%")
    print(f"Profit Factor   : {result['profit_factor']}")
    print(f"Net R           : {base:.4f}")
    print(f"Expectancy R    : {result['expectancy_r']}")
    print(f"Max Drawdown R  : {dd(trades):.4f}")

    print("\nDIRECTION")
    d = direction(trades)
    for s in ("BUY", "SELL"):
        print(f"{s:5} trades={d[s][0]:>3} wins={d[s][1]:>3} netR={d[s][2]:>7.3f} PF={d[s][3]}")

    print("\nCOST / SLIPPAGE STRESS")
    print("-" * 72)
    cost_rows = []
    for c in COSTS:
        after = base - c * n
        exp = after / n
        ok = after > 0
        print(f"cost={c:>4.2f}R | after_cost_R={after:>8.3f} | expectancy={exp:>8.4f} | {'PASS' if ok else 'FAIL'}")
        cost_rows.append({"cost_r": c, "after_cost_r": after, "expectancy_r": exp, "pass": ok})

    r_values = [float(t["r_multiple"]) for t in trades]

    print("\nMONTE CARLO TRADE-ORDER ROBUSTNESS")
    rng = random.Random(SEED)
    finals = []
    maxdds = []
    lossrun = []

    for _ in range(MC_RUNS):
        sample = r_values[:]
        rng.shuffle(sample)
        equity = peak = mdd = 0.0
        current_losses = max_losses = 0
        for r in sample:
            equity += r
            peak = max(peak, equity)
            mdd = max(mdd, peak - equity)
            if r < 0:
                current_losses += 1
                max_losses = max(max_losses, current_losses)
            else:
                current_losses = 0
        finals.append(equity)
        maxdds.append(mdd)
        lossrun.append(max_losses)

    finals = np.asarray(finals)
    maxdds = np.asarray(maxdds)
    lossrun = np.asarray(lossrun)

    p05 = float(np.percentile(finals, 5))
    p50 = float(np.percentile(finals, 50))
    p95 = float(np.percentile(finals, 95))
    dd50 = float(np.percentile(maxdds, 50))
    dd95 = float(np.percentile(maxdds, 95))
    lose_prob = float(np.mean(finals <= 0) * 100)

    print(f"Final R P05     : {p05:.3f}")
    print(f"Final R P50     : {p50:.3f}")
    print(f"Final R P95     : {p95:.3f}")
    print(f"DD P50          : {dd50:.3f}")
    print(f"DD P95          : {dd95:.3f}")
    print(f"Probability <=0 : {lose_prob:.2f}%")
    print(f"Max loss-run P95: {np.percentile(lossrun, 95):.0f}")

    checks = {
        "base_positive_after_010": base - 0.10 * n > 0,
        "base_positive_after_020": base - 0.20 * n > 0,
        "mc_median_positive": p50 > 0,
        "mc_p05_positive": p05 > 0,
        "mc_zero_probability_below_10pct": lose_prob < 10.0,
    }

    print("\nSTRESS DECISION")
    print("-" * 72)
    for k, ok in checks.items():
        print(f"{'PASS' if ok else 'FAIL'} | {k}")

    status = "PASS" if all(checks.values()) else "NOT_READY"
    print(f"\nV14 STRESS STATUS : {status}")
    print("No live-trading setting is changed by this audit.")

    pd.DataFrame(cost_rows).to_csv("gold_v14_cost_stress.csv", index=False)
    pd.DataFrame([{
        "trades": n,
        "net_r": base,
        "p05_final_r": p05,
        "p50_final_r": p50,
        "p95_final_r": p95,
        "dd_p50": dd50,
        "dd_p95": dd95,
        "prob_final_nonpositive_pct": lose_prob,
        "max_loss_run_p95": float(np.percentile(lossrun, 95)),
        "status": status,
    }]).to_csv("gold_v14_monte_carlo.csv", index=False)

if __name__ == "__main__":
    main()
