"""
FOREX AUTO TRADER PRO
SELL QUALITY CALIBRATION V1

Purpose:
- Diagnose SELL candidates on real Yahoo Finance M15 data.
- Compare a small, fixed grid of SELL quality thresholds.
- DOES NOT modify strategy.py, config.py, or trading thresholds.
- Does not use MetaTrader5.
- Designed to run safely in GitHub Actions.
"""

import numpy as np
import pandas as pd
import yfinance as yf

from strategy import (
    calculate_adx,
    calculate_atr,
    calculate_rsi,
    calculate_momentum,
    candle_confirmation,
    calculate_ema,
)


SYMBOL = "EURUSD=X"
INTERVAL = "15m"
PERIOD = "60d"


def download_data():
    df = yf.download(
        SYMBOL,
        interval=INTERVAL,
        period=PERIOD,
        progress=False,
        auto_adjust=False,
    )

    if df is None or df.empty:
        raise RuntimeError("Yahoo Finance returned no data.")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.rename(columns=str.lower)
    required = {"open", "high", "low", "close"}

    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing OHLC columns: {sorted(missing)}")

    df = df[list(required)].copy()
    df = df.dropna().reset_index(drop=False)

    if "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "time"})
    elif "Date" in df.columns:
        df = df.rename(columns={"Date": "time"})

    return df


def build_candidates(df):
    rows = []

    for i in range(80, len(df)):
        hist = df.iloc[: i + 1].copy().reset_index(drop=True)

        close = hist["close"].astype(float)
        ema_fast = float(calculate_ema(close, 20).iloc[-1])
        ema_slow = float(calculate_ema(close, 50).iloc[-1])
        atr_series = calculate_atr(hist, 14)
        atr = float(atr_series.iloc[-1])
        atr_avg = float(atr_series.rolling(50).mean().iloc[-1])
        rsi = float(calculate_rsi(close, 14).iloc[-1])
        adx = float(calculate_adx(hist, 14).iloc[-1])
        momentum = float(calculate_momentum(hist))
        candle_ok = candle_confirmation(hist, "SELL")

        if not all(np.isfinite(x) for x in (ema_fast, ema_slow, atr, atr_avg, rsi, adx, momentum)):
            continue

        bearish_context = (
            ema_fast < ema_slow
            and momentum < 0
            and rsi <= 50
        )

        if not bearish_context:
            continue

        # Forward outcome is measured only after the candidate candle.
        entry = float(df.iloc[i + 1]["open"]) if i + 1 < len(df) else np.nan
        future = df.iloc[i + 1 : min(i + 1 + 16, len(df))]

        if future.empty or not np.isfinite(entry):
            continue

        # Normalized forward return after 4 M15 bars (~1 hour).
        end_close = float(future.iloc[min(3, len(future) - 1)]["close"])
        forward_r = (entry - end_close) / atr if atr > 0 else 0.0

        rows.append(
            {
                "index": i,
                "momentum": momentum,
                "adx": adx,
                "rsi": rsi,
                "atr_ratio": atr / atr_avg if atr_avg > 0 else np.nan,
                "ema_distance_atr": abs(float(hist["close"].iloc[-1]) - ema_fast) / atr,
                "candle": candle_ok,
                "forward_r": forward_r,
            }
        )

    return pd.DataFrame(rows)


def evaluate(candidates, min_momentum, min_adx):
    if candidates.empty:
        return 0, 0, 0.0

    mask = (
        (candidates["momentum"] <= -min_momentum)
        & (candidates["adx"] >= min_adx)
        & (candidates["rsi"] >= 30)
        & (candidates["rsi"] <= 50)
        & (candidates["atr_ratio"] >= 0.65)
        & (candidates["atr_ratio"] <= 2.25)
        & candidates["candle"]
    )

    selected = candidates.loc[mask]
    n = len(selected)

    if n == 0:
        return 0, 0, 0.0

    wins = int((selected["forward_r"] > 0).sum())
    win_rate = wins / n * 100
    expectancy = float(selected["forward_r"].mean())

    return n, wins, expectancy


def main():
    print("=" * 70)
    print("FOREX AUTO TRADER PRO - SELL QUALITY CALIBRATION V1")
    print("=" * 70)
    print("Symbol    :", SYMBOL)
    print("Timeframe :", INTERVAL)
    print("Period    :", PERIOD)
    print()
    print("Downloading real market data...")

    df = download_data()
    print("Bars      :", len(df))

    candidates = build_candidates(df)
    print("Bearish candidates with usable indicators:", len(candidates))
    print()

    print("-" * 70)
    print("FIXED THRESHOLD COMPARISON")
    print("-" * 70)
    print("Momentum is absolute % decline over 5 M15 bars.")
    print()

    grid = [
        (0.02, 18),
        (0.03, 18),
        (0.05, 18),
        (0.08, 22),
        (0.10, 22),
        (0.12, 24),
    ]

    results = []

    for momentum, adx in grid:
        n, wins, expectancy = evaluate(candidates, momentum, adx)
        wr = wins / n * 100 if n else 0.0
        results.append((expectancy, n, momentum, adx, wr))
        print(
            f"momentum >= {momentum:0.02f}% | "
            f"ADX >= {adx:2d} | "
            f"signals={n:3d} | "
            f"wins={wins:3d} | "
            f"win_rate={wr:6.2f}% | "
            f"forward_expectancy_R={expectancy: .4f}"
        )

    print()
    print("-" * 70)
    print("CALIBRATION RESULT")
    print("-" * 70)

    viable = [x for x in results if x[1] >= 5]

    if not viable:
        print("No threshold produced at least 5 candidates.")
        print("Result: KEEP CURRENT CONSERVATIVE SELL FILTER.")
    else:
        best = max(viable, key=lambda x: x[0])
        print(
            "Best observed fixed grid (diagnostic only): "
            f"momentum >= {best[2]:.02f}%, "
            f"ADX >= {best[3]}, "
            f"signals={best[1]}, "
            f"win_rate={best[4]:.2f}%, "
            f"expectancy={best[0]:.4f}R"
        )
        print(
            "IMPORTANT: This script does not automatically change strategy "
            "thresholds. Use it as evidence before changing production rules."
        )

    print()
    print("SELL QUALITY CALIBRATION: PASS")


if __name__ == "__main__":
    main()
