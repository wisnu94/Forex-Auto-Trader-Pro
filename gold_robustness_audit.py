import os
import pandas as pd
from backtest import backtest_strategy
from config import EMA_FAST, EMA_SLOW, ATR_PERIOD, ATR_SL_MULTIPLIER, REWARD_RISK, MIN_SCORE
from data import get_bars

BARS = int(os.getenv("ROBUSTNESS_BARS", "3000"))
SYMBOL = os.getenv("ROBUSTNESS_SYMBOL", "XAUUSD")
COST_LEVELS_R = (0.00, 0.05, 0.10, 0.15, 0.20)
MIN_TRADES_WARNING = 20

def validate_ohlc(df):
    invalid = ((df["high"] < df["low"]) | (df["high"] < df["open"]) |
               (df["high"] < df["close"]) | (df["low"] > df["open"]) |
               (df["low"] > df["close"]))
    if bool(invalid.any()):
        raise RuntimeError(f"Invalid OHLC rows: {int(invalid.sum())}")

def run(df):
    return backtest_strategy(
        df=df, ema_fast=EMA_FAST, ema_slow=EMA_SLOW,
        atr_period=ATR_PERIOD, atr_sl_multiplier=ATR_SL_MULTIPLIER,
        reward_risk=REWARD_RISK, min_score=MIN_SCORE)

def summarize(name, result):
    print("-" * 70)
    print(name)
    print("-" * 70)
    print(f"Trades       : {result['total_trades']}")
    print(f"Win Rate     : {result['win_rate']}%")
    print(f"Profit Factor: {result['profit_factor']}")
    print(f"Net R        : {result['net_r']}")
    print(f"Expectancy R : {result['expectancy_r']}")

def cost_stress(trades):
    print("\nCOST STRESS TEST")
    print("Cost is modeled as R deducted per completed trade.")
    print("-" * 70)
    if not trades:
        print("No trades available.")
        return
    base = sum(float(t["r_multiple"]) for t in trades)
    n = len(trades)
    for cost in COST_LEVELS_R:
        net = base - cost * n
        print(f"cost={cost:>4.2f}R | net_R={net:>8.3f} | "
              f"expectancy_R={net/n:>8.4f} | status={'PASS' if net > 0 else 'FAIL'}")

def segment_result(df, start, end):
    segment = df.iloc[start:end].reset_index(drop=True)
    if len(segment) < max(EMA_SLOW + 120, 300):
        return None, len(segment)
    return run(segment), len(segment)

def main():
    print("=" * 70)
    print("FOREX AUTO TRADER PRO - GOLD ROBUSTNESS AUDIT V1")
    print("=" * 70)
    print(f"Live symbol       : {SYMBOL} (MT5)")
    print("CI proxy          : GC=F (Yahoo gold futures)")
    print("Timeframe         : M15")
    print(f"Bars requested    : {BARS}")
    print(f"Parameters        : EMA {EMA_FAST}/{EMA_SLOW}, ATR {ATR_PERIOD}, "
          f"SL {ATR_SL_MULTIPLIER}x, RR {REWARD_RISK}, score {MIN_SCORE}")
    print("Parameter fitting : NONE\n")

    df = get_bars(SYMBOL, "M15", count=BARS, source="YAHOO")
    validate_ohlc(df)
    print("OHLC validation    : PASS")
    print(f"Loaded bars        : {len(df)}")
    print(f"First candle       : {df.iloc[0]['time']}")
    print(f"Last candle        : {df.iloc[-1]['time']}\n")

    full = run(df)
    summarize("FULL SAMPLE", full)
    cost_stress(full["trades"])

    split = int(len(df) * 0.60)
    train_result, train_len = segment_result(df, 0, split)
    holdout_result, holdout_len = segment_result(df, split, len(df))

    if train_result is None or holdout_result is None:
        print("HOLDOUT CHECK : INSUFFICIENT DATA")
        raise SystemExit(2)

    summarize("CHRONOLOGICAL 60% SAMPLE", train_result)
    summarize("CHRONOLOGICAL 40% HOLDOUT", holdout_result)

    print("\nROBUSTNESS DECISION")
    print("-" * 70)
    checks = {
        "full_positive_expectancy": full["expectancy_r"] > 0,
        "holdout_positive_expectancy": holdout_result["expectancy_r"] > 0,
        "full_pf_above_1": full["profit_factor"] > 1.0,
        "holdout_pf_above_1": holdout_result["profit_factor"] > 1.0,
        "holdout_has_trades": holdout_result["total_trades"] > 0,
    }
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} | {name}")

    if full["total_trades"] < MIN_TRADES_WARNING:
        print(f"WARNING | full sample has only {full['total_trades']} trades; statistical confidence is low.")
    if holdout_result["total_trades"] < MIN_TRADES_WARNING:
        print(f"WARNING | holdout has only {holdout_result['total_trades']} trades; statistical confidence is low.")

    robust_pass = all(checks.values()) and holdout_result["total_trades"] >= MIN_TRADES_WARNING
    print(f"\nROBUSTNESS STATUS : {'PASS' if robust_pass else 'NOT_READY'}")
    if not robust_pass:
        print("No live-trading setting is changed by this audit.")

    rows = []
    for label, result in (("FULL", full), ("TRAIN_60", train_result), ("HOLDOUT_40", holdout_result)):
        for trade in result["trades"]:
            row = dict(trade)
            row["sample"] = label
            rows.append(row)
    if rows:
        pd.DataFrame(rows).to_csv("gold_robustness_trades.csv", index=False)
        print("Saved: gold_robustness_trades.csv")

if __name__ == "__main__":
    main()
