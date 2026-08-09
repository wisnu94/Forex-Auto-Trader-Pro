import os
import math
import pandas as pd

from backtest import backtest_strategy
from config import EMA_FAST, EMA_SLOW, ATR_PERIOD, ATR_SL_MULTIPLIER, REWARD_RISK, MIN_SCORE
from data import get_bars

BARS = int(os.getenv("BACKTEST_BARS", "3000"))
SYMBOL = os.getenv("BACKTEST_SYMBOL", "XAUUSD")
MIN_TRADES_TOTAL = int(os.getenv("WF_MIN_TRADES", "20"))
STRESS_COST_R = float(os.getenv("STRESS_COST_R", "0.05"))

def metrics(trades):
    total = len(trades)
    wins = sum(t.get("outcome") == "WIN" for t in trades)
    gp = sum(float(t["r_multiple"]) for t in trades if float(t["r_multiple"]) > 0)
    gl = abs(sum(float(t["r_multiple"]) for t in trades if float(t["r_multiple"]) < 0))
    net = sum(float(t["r_multiple"]) for t in trades)
    pf = gp / gl if gl else (math.inf if gp else 0.0)
    return {
        "trades": total, "wins": wins, "losses": total-wins,
        "win_rate": wins/total*100 if total else 0.0,
        "pf": pf, "net_r": net, "expectancy": net/total if total else 0.0
    }

def show(label, m):
    pf = "INF" if math.isinf(m["pf"]) else f"{m['pf']:.3f}"
    print(f"{label:<12} trades={m['trades']:>3} win={m['win_rate']:>6.2f}% PF={pf:>6} NetR={m['net_r']:>7.2f} ExpR={m['expectancy']:>7.4f}")

def main():
    print("=" * 74)
    print("FOREX AUTO TRADER PRO - GOLD WALK-FORWARD VALIDATION V9")
    print("=" * 74)
    print("Live symbol       : XAUUSD (MT5)")
    print("Backtest proxy    : GC=F (Yahoo Finance)")
    print(f"Bars              : {BARS}")
    print(f"Strategy          : EMA {EMA_FAST}/{EMA_SLOW}, ATR {ATR_PERIOD}, RR {REWARD_RISK}, score {MIN_SCORE}")
    print(f"Stress cost       : {STRESS_COST_R:.3f}R per completed trade")
    print()

    df = get_bars(symbol=SYMBOL, timeframe="M15", count=BARS, source="YAHOO")
    if df is None or len(df) < 1000:
        raise RuntimeError(f"Data terlalu sedikit untuk walk-forward: {0 if df is None else len(df)}")

    df = df.copy().reset_index(drop=True)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.dropna(subset=["time"]).reset_index(drop=True)

    n = len(df)
    edges = [0, n//4, n//2, (3*n)//4, n]
    all_trades = []

    print("WALK-FORWARD SLICES")
    print("-" * 74)
    for k in range(4):
        segment = df.iloc[edges[k]:edges[k+1]].copy().reset_index(drop=True)
        result = backtest_strategy(
            df=segment, ema_fast=EMA_FAST, ema_slow=EMA_SLOW,
            atr_period=ATR_PERIOD, atr_sl_multiplier=ATR_SL_MULTIPLIER,
            reward_risk=REWARD_RISK, min_score=MIN_SCORE
        )
        trades = result.get("trades", [])
        for trade in trades:
            row = dict(trade)
            row["wf_slice"] = k + 1
            all_trades.append(row)
        show(f"Slice {k+1}", metrics(trades))

    overall = metrics(all_trades)
    stressed = dict(overall)
    stressed["net_r"] = overall["net_r"] - overall["trades"] * STRESS_COST_R
    stressed["expectancy"] = stressed["net_r"] / overall["trades"] if overall["trades"] else 0.0

    print()
    print("OVERALL OUT-OF-SAMPLE VALIDATION")
    print("-" * 74)
    show("RAW", overall)
    show("STRESSED", stressed)

    positive_slices = 0
    for k in range(1, 5):
        m = metrics([t for t in all_trades if t.get("wf_slice") == k])
        if m["net_r"] > 0 and m["pf"] > 1.0:
            positive_slices += 1

    print()
    print("ROBUSTNESS CHECK")
    print("-" * 74)
    print(f"Positive slices (NetR>0 and PF>1): {positive_slices}/4")
    print(f"Minimum total trades target       : {MIN_TRADES_TOTAL}")

    passed = (
        overall["trades"] >= MIN_TRADES_TOTAL
        and overall["net_r"] > 0
        and overall["pf"] > 1.0
        and overall["expectancy"] > 0
        and positive_slices >= 3
    )

    print()
    print("V9 GATE")
    print("-" * 74)
    if passed:
        print("PASS: V8 survives the current 4-slice walk-forward gate.")
        print("NEXT: fresh unseen period, then MT5 demo/forward validation.")
    else:
        print("FAIL: V8 is NOT robust enough for live trading yet.")
        print("NEXT: inspect weakest slices before changing thresholds.")

    if all_trades:
        pd.DataFrame(all_trades).to_csv("walk_forward_gold_v9_trades.csv", index=False)
        print("Saved: walk_forward_gold_v9_trades.csv")

    print("=" * 74)
    print("WALK-FORWARD VALIDATION COMPLETE")
    print("=" * 74)
    raise SystemExit(0 if passed else 2)

if __name__ == "__main__":
    main()
