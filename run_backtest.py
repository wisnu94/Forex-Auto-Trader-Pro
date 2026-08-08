import os
import pandas as pd
import numpy as np

from backtest import backtest_strategy, analyze_grades, analyze_signals
from config import EMA_FAST, EMA_SLOW, ATR_PERIOD, ATR_SL_MULTIPLIER, REWARD_RISK, MIN_SCORE
from data import get_bars


# ============================================================
# GOLD BACKTEST V8
# CI/backtest data uses Yahoo GC=F as a proxy.
# Live execution remains MT5 XAUUSD.
# ============================================================

BARS = int(os.getenv("BACKTEST_BARS", "3000"))
BACKTEST_SYMBOL = os.getenv("BACKTEST_SYMBOL", "XAUUSD")


def load_backtest_data():
    print("=" * 70)
    print("FOREX AUTO TRADER PRO - GOLD PRECISION BACKTEST V8")
    print("=" * 70)
    print("Live symbol       : XAUUSD (MT5)")
    print("Backtest source   : Yahoo Finance")
    print("Backtest proxy    : GC=F (gold futures)")
    print("Timeframe         : M15")
    print(f"Bars              : {BARS}")
    print()

    df = get_bars(
        symbol=BACKTEST_SYMBOL,
        timeframe="M15",
        count=BARS,
        source="YAHOO",
    )

    if df is None or len(df) < 300:
        raise RuntimeError(f"Backtest data terlalu sedikit: {0 if df is None else len(df)}")

    return df


def validate_ohlc(df):
    invalid = (
        (df["high"] < df["low"])
        | (df["high"] < df["open"])
        | (df["high"] < df["close"])
        | (df["low"] > df["open"])
        | (df["low"] > df["close"])
    )

    if bool(invalid.any()):
        raise RuntimeError(f"Invalid OHLC rows: {int(invalid.sum())}")


def main():
    df = load_backtest_data()
    validate_ohlc(df)

    print("OHLC validation       : PASS")
    print(f"First candle          : {df.iloc[0]['time']}")
    print(f"Last candle           : {df.iloc[-1]['time']}")
    print()

    result = backtest_strategy(
        df=df,
        ema_fast=EMA_FAST,
        ema_slow=EMA_SLOW,
        atr_period=ATR_PERIOD,
        atr_sl_multiplier=ATR_SL_MULTIPLIER,
        reward_risk=REWARD_RISK,
        min_score=MIN_SCORE,
    )

    print("-" * 70)
    print("BACKTEST RESULT")
    print("-" * 70)
    print(f"Trades       : {result['total_trades']}")
    print(f"Win Rate     : {result['win_rate']}%")
    print(f"Profit Factor: {result['profit_factor']}")
    print(f"Net R        : {result['net_r']}")
    print(f"Expectancy R : {result['expectancy_r']}")
    print()

    print("-" * 70)
    print("GRADE")
    print("-" * 70)
    for grade, row in analyze_grades(result["trades"]).items():
        print(
            f"{grade:>2} | trades={row['trades']:>4} | "
            f"wins={row['wins']:>4} | win_rate={row['win_rate']:>6.2f}%"
        )

    print()
    print("-" * 70)
    print("DIRECTION")
    print("-" * 70)
    for signal, row in analyze_signals(result["trades"]).items():
        print(
            f"{signal:>4} | trades={row['trades']:>4} | "
            f"wins={row['wins']:>4} | win_rate={row['win_rate']:>6.2f}%"
        )

    if result["trades"]:
        pd.DataFrame(result["trades"]).to_csv("backtest_trades.csv", index=False)
        print()
        print("Saved: backtest_trades.csv")

    print()
    print("BACKTEST COMPLETE")


if __name__ == "__main__":
    main()
