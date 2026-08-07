import pandas as pd
import numpy as np

from config import SYMBOL, TIMEFRAME
from data import get_bars

from strategy import (
    calculate_ema,
    calculate_atr,
    calculate_rsi,
    calculate_adx,
    calculate_momentum,
    detect_trend,
    detect_structure,
    candle_confirmation,
    rsi_confirmation,
    adx_confirmation,
    volatility_confirmation,
    ema_distance_confirmation,
    sell_quality_gate,
    calculate_precision_score,
)

from backtest import _build_mtf_confirmation


BARS = 3000
MAX_NEAR_MISSES = 20


def main():

    print("=" * 78)
    print("FOREX AUTO TRADER PRO - SELL PIPELINE DIAGNOSTIC V5")
    print("=" * 78)

    print(f"Symbol    : {SYMBOL}")
    print(f"Timeframe : {TIMEFRAME}")
    print(f"Bars      : {BARS}")
    print()

    df = get_bars(
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        count=BARS,
    )

    if df is None or len(df) == 0:
        raise RuntimeError("Data kosong.")

    df = df.copy().reset_index(drop=True)

    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(
        subset=["open", "high", "low", "close"]
    ).reset_index(drop=True)

    counters = {
        "candidate": 0,
        "mtf": 0,
        "rsi": 0,
        "adx": 0,
        "vol": 0,
        "ema": 0,
        "candle": 0,
        "quality": 0,
        "score70": 0,
        "score80": 0,
    }

    failures = {}

    near_misses = []

    def add_failure(name):
        failures[name] = failures.get(name, 0) + 1

    def add_near_miss(row):
        near_misses.append(row)

        near_misses.sort(
            key=lambda x: x["failed_filters"]
        )

        if len(near_misses) > MAX_NEAR_MISSES:
            near_misses.pop()

    for i in range(70, len(df) - 1):

        h = df.iloc[: i + 1].copy().reset_index(drop=True)

        close = float(h["close"].iloc[-1])

        ef = float(
            calculate_ema(h["close"], 20).iloc[-1]
        )

        es = float(
            calculate_ema(h["close"], 50).iloc[-1]
        )

        atrs = calculate_atr(h, 14)

        atr = atrs.iloc[-1]
        atravg = atrs.rolling(20).mean().iloc[-1]

        if pd.isna(atr) or pd.isna(atravg):
            continue

        atr = float(atr)
        atravg = float(atravg)

        if atravg == 0:
            continue

        atr_ratio = atr / atravg

        rsi = float(
            calculate_rsi(h["close"], 14).iloc[-1]
        )

        adx = float(
            calculate_adx(h, 14).iloc[-1]
        )

        mom = float(
            calculate_momentum(h)
        )

        trend = detect_trend(
            h,
            20,
            50,
        )

        structure = detect_structure(h)

        # --------------------------------------------------
        # 1. RAW BEARISH CANDIDATE
        # --------------------------------------------------

        if not (
            trend == "BEARISH"
            and structure == "BEARISH_BREAK"
            and mom < 0
        ):
            continue

        counters["candidate"] += 1

        # --------------------------------------------------
        # 2. MTF
        # --------------------------------------------------

        mtf = _build_mtf_confirmation(h)

        trends = mtf.get("trends", {})

        mtf_ok = (
            trends.get("H1") == "SELL"
            and trends.get("M15") == "SELL"
        )

        # --------------------------------------------------
        # 3. RSI
        # --------------------------------------------------

        rsi_ok = rsi_confirmation(
            "SELL",
            rsi,
        )

        # --------------------------------------------------
        # 4. ADX
        # --------------------------------------------------

        adx_ok = adx_confirmation(
            "SELL",
            adx,
        )

        # --------------------------------------------------
        # 5. VOLATILITY
        # --------------------------------------------------

        vol_ok = volatility_confirmation(
            atr,
            atravg,
        )

        # --------------------------------------------------
        # 6. EMA DISTANCE
        # --------------------------------------------------

        ema_ok = ema_distance_confirmation(
            "SELL",
            close,
            ef,
            atr,
        )

        # --------------------------------------------------
        # 7. CANDLE
        # --------------------------------------------------

        candle_ok = candle_confirmation(
            h,
            "SELL",
        )

        # --------------------------------------------------
        # Record all failed filters
        # --------------------------------------------------

        failed = []

        if not mtf_ok:
            failed.append("MTF")

        if not rsi_ok:
            failed.append("RSI")

        if not adx_ok:
            failed.append("ADX")

        if not vol_ok:
            failed.append("VOL")

        if not ema_ok:
            failed.append("EMA")

        if not candle_ok:
            failed.append("CANDLE")

        # --------------------------------------------------
        # Pipeline counters
        # --------------------------------------------------

        if not mtf_ok:
            add_failure("H1/M15 permission")
            continue

        counters["mtf"] += 1

        if not rsi_ok:
            add_failure("RSI")
            continue

        counters["rsi"] += 1

        if not adx_ok:
            add_failure("ADX")
            continue

        counters["adx"] += 1

        if not vol_ok:
            add_failure("Volatility")
            continue

        counters["vol"] += 1

        if not ema_ok:
            add_failure("EMA distance")
            continue

        counters["ema"] += 1

        if not candle_ok:
            add_failure("Candle confirmation")
            continue

        counters["candle"] += 1

        # --------------------------------------------------
        # SELL QUALITY
        # --------------------------------------------------

        quality_ok = sell_quality_gate(
            mom,
            adx,
            rsi,
            candle_ok,
        )

        quality_reasons = []

        if mom > -0.08:
            quality_reasons.append("MOMENTUM")

        if adx < 22:
            quality_reasons.append("ADX")

        if rsi < 34:
            quality_reasons.append("RSI")

        if not quality_ok:

            if not quality_reasons:
                quality_reasons.append("UNKNOWN")

            reason = (
                "SELL quality: "
                + ",".join(quality_reasons)
            )

            add_failure(reason)

            add_near_miss({
                "index": i,
                "close": close,
                "momentum": mom,
                "adx": adx,
                "rsi": rsi,
                "atr_ratio": atr_ratio,
                "ema_atr": abs(close - ef) / atr if atr > 0 else 0,
                "failed_filters": len(quality_reasons),
                "reason": ",".join(quality_reasons),
            })

            continue

        counters["quality"] += 1

        # --------------------------------------------------
        # PRECISION SCORE
        # --------------------------------------------------

        score = calculate_precision_score(
            "SELL",
            trend,
            structure,
            mom,
            atr,
            close,
            ef,
            es,
            rsi,
            adx,
            atravg,
            candle_ok,
            mtf,
        )

        if score >= 70:
            counters["score70"] += 1

        if score >= 80:
            counters["score80"] += 1

        add_near_miss({
            "index": i,
            "close": close,
            "momentum": mom,
            "adx": adx,
            "rsi": rsi,
            "atr_ratio": atr_ratio,
            "ema_atr": abs(close - ef) / atr if atr > 0 else 0,
            "failed_filters": 0,
            "reason": f"QUALITY PASS / SCORE {score}",
        })

    # ======================================================
    # PIPELINE RESULT
    # ======================================================

    print()
    print("-" * 78)
    print("SELL PIPELINE")
    print("-" * 78)

    labels = [
        ("Raw bearish candidate", "candidate"),
        ("H1 + M15 permission", "mtf"),
        ("RSI filter", "rsi"),
        ("ADX filter", "adx"),
        ("Volatility filter", "vol"),
        ("EMA distance filter", "ema"),
        ("Candle confirmation", "candle"),
        ("SELL quality gate", "quality"),
        ("Score >= 70", "score70"),
        ("Score >= 80 / FINAL", "score80"),
    ]

    for label, key in labels:
        print(
            f"{label:<32}: "
            f"{counters[key]:>5}"
        )

    # ======================================================
    # BOTTLENECKS
    # ======================================================

    print()
    print("-" * 78)
    print("MAIN BOTTLENECKS")
    print("-" * 78)

    if failures:

        for reason, count in sorted(
            failures.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:15]:

            print(
                f"{reason:<48}: "
                f"{count}"
            )

    else:
        print("Tidak ada failure tercatat.")

    # ======================================================
    # NEAR MISS ANALYSIS
    # ======================================================

    print()
    print("-" * 78)
    print("SELL NEAR-MISS ANALYSIS")
    print("-" * 78)

    if near_misses:

        print(
            "Menampilkan kandidat SELL paling dekat "
            "dengan lolos quality gate:"
        )
        print()

        for n, x in enumerate(
            near_misses[:MAX_NEAR_MISSES],
            start=1,
        ):

            print(
                f"#{n:02d} "
                f"bar={x['index']} "
                f"close={x['close']:.5f}"
            )

            print(
                f"    Momentum : {x['momentum']:.5f}"
            )

            print(
                f"    ADX      : {x['adx']:.2f}"
            )

            print(
                f"    RSI      : {x['rsi']:.2f}"
            )

            print(
                f"    ATR ratio: {x['atr_ratio']:.3f}"
            )

            print(
                f"    EMA/ATR  : {x['ema_atr']:.3f}"
            )

            print(
                f"    FAIL     : {x['reason']}"
            )

            print()

    else:
        print("Tidak ada near-miss.")

    # ======================================================
    # FINAL
    # ======================================================

    print("-" * 78)

    if counters["score80"] > 0:

        print(
            f"FINAL SELL SIGNALS : "
            f"{counters['score80']}"
        )

    else:

        print(
            "FINAL SELL SIGNALS : 0"
        )

    print()

    print(
        "CATATAN: Diagnostic V5 tidak mengubah "
        "strategy.py atau threshold trading."
    )

    print()
    print("=" * 78)
    print("SELL DIAGNOSTIC V5 COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()