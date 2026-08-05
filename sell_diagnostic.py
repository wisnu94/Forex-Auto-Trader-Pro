from pathlib import Path

content = r'''import pandas as pd

import numpy as np

from config import SYMBOL, TIMEFRAME

from data import get_bars

from backtest import _build_mtf_confirmation

from strategy import (

    calculate_ema,

    calculate_atr,

    calculate_rsi,

    calculate_adx,

    detect_trend,

    detect_structure,

    calculate_momentum,

    candle_confirmation,

    rsi_confirmation,

    adx_confirmation,

    volatility_confirmation,

    ema_distance_confirmation,

    sell_quality_gate,

    calculate_precision_score,

)

# ============================================================

# FOREX AUTO TRADER PRO

# SELL CANDIDATE DIAGNOSTIC V5.1

#

# IMPORTANT:

# - Tidak mengubah strategy.py.

# - Tidak mengubah hasil backtest.

# - Hanya mencari FILTER mana yang membuat SELL = 0.

# - Menggunakan data dan MTF architecture yang sama.

# ============================================================

BARS = 3000

EMA_FAST = 20

EMA_SLOW = 50

ATR_PERIOD = 14

MIN_SELL_SCORE = 80

def load_data():

    print()

    print("=" * 60)

    print("FOREX AUTO TRADER PRO")

    print("SELL CANDIDATE DIAGNOSTIC V5.1")

    print("=" * 60)

    print(f"Symbol     : {SYMBOL}")

    print(f"Timeframe  : {TIMEFRAME}")

    print(f"Bars       : {BARS}")

    print()

    df = get_bars(

        symbol=SYMBOL,

        timeframe=TIMEFRAME,

        count=BARS,

    )

    if df is None or len(df) == 0:

        raise RuntimeError("Market data kosong.")

    required = ["open", "high", "low", "close"]

    missing = [

        col for col in required

        if col not in df.columns

    ]

    if missing:

        raise RuntimeError(

            f"Kolom market data hilang: {missing}"

        )

    data = df.copy()

    for col in required:

        data[col] = pd.to_numeric(

            data[col],

            errors="coerce",

        )

    data = data.dropna(

        subset=required

    ).reset_index(drop=True)

    if len(data) < 150:

        raise RuntimeError(

            f"Data terlalu sedikit: {len(data)}"

        )

    return data

def diagnose(data):

    counts = {

        "raw_bearish_candidate": 0,

        "mtf_h1_m15_aligned": 0,

        "rsi_pass": 0,

        "adx_pass": 0,

        "volatility_pass": 0,

        "ema_distance_pass": 0,

        "candle_pass": 0,

        "sell_quality_pass": 0,

        "score_80_pass": 0,

        "final_sell": 0,

    }

    candidates = []

    start = EMA_SLOW + 20

    for i in range(start, len(data) - 1):

        history = (

            data.iloc[:i + 1]

            .copy()

            .reset_index(drop=True)

        )

        close_series = history["close"]

        ema_fast_series = calculate_ema(

            close_series,

            EMA_FAST,

        )

        ema_slow_series = calculate_ema(

            close_series,

            EMA_SLOW,

        )

        ema_fast = float(

            ema_fast_series.iloc[-1]

        )

        ema_slow = float(

            ema_slow_series.iloc[-1]

        )

        atr_series = calculate_atr(

            history,

            ATR_PERIOD,

        )

        atr = atr_series.iloc[-1]

        atr_average = (

            atr_series

            .rolling(20)

            .mean()

            .iloc[-1]

        )

        if pd.isna(atr) or pd.isna(atr_average):

            continue

        atr = float(atr)

        atr_average = float(atr_average)

        rsi = float(

            calculate_rsi(

                close_series

            ).iloc[-1]

        )

        adx = float(

            calculate_adx(

                history,

                period=14,

            ).iloc[-1]

        )

        momentum = calculate_momentum(

            history

        )

        trend = detect_trend(

            history,

            fast=EMA_FAST,

            slow=EMA_SLOW,

        )

        structure = detect_structure(

            history

        )

        # ----------------------------------------------------

        # STAGE 1: RAW SELL CANDIDATE

        # Sama dengan generate_signal()

        # ----------------------------------------------------

        raw_sell = (

            trend == "BEARISH"

            and structure == "BEARISH_BREAK"

            and momentum < 0

        )

        if not raw_sell:

            continue

        counts["raw_bearish_candidate"] += 1

        mtf = _build_mtf_confirmation(

            history

        )

        trends = mtf.get(

            "trends",

            {},

        )

        h1 = trends.get("H1", "HOLD")

        m15 = trends.get("M15", "HOLD")

        m1 = trends.get("M1", "HOLD")

        mtf_pass = (

            h1 == "SELL"

            and m15 == "SELL"

        )

        if mtf_pass:

            counts["mtf_h1_m15_aligned"] += 1

        rsi_pass = rsi_confirmation(

            "SELL",

            rsi,

        )

        if rsi_pass:

            counts["rsi_pass"] += 1

        adx_pass = adx_confirmation(

            "SELL",

            adx,

        )

        if adx_pass:

            counts["adx_pass"] += 1

        volatility_pass = volatility_confirmation(

            atr,

            atr_average,

        )

        if volatility_pass:

            counts["volatility_pass"] += 1

        ema_distance_pass = (

            ema_distance_confirmation(

                "SELL",

                close=float(

                    history["close"].iloc[-1]

                ),

                ema_fast=ema_fast,

                atr=atr,

            )

        )

        if ema_distance_pass:

            counts["ema_distance_pass"] += 1

        candle_pass = candle_confirmation(

            history,

            "SELL",

        )

        if candle_pass:

            counts["candle_pass"] += 1

        sell_quality_pass = sell_quality_gate(

            momentum=momentum,

            adx=adx,

            rsi=rsi,

            candle_confirmed=candle_pass,

        )

        if sell_quality_pass:

            counts["sell_quality_pass"] += 1

        score = calculate_precision_score(

            signal="SELL",

            trend=trend,

            structure=structure,

            momentum=momentum,

            atr_value=atr,

            close=float(

                history["close"].iloc[-1]

            ),

            ema_fast=ema_fast,

            ema_slow=ema_slow,

            rsi=rsi,

            adx=adx,

            atr_average=atr_average,

            candle_confirmed=candle_pass,

            mtf_confirmation=mtf,

        )

        score_pass = (

            score >= MIN_SELL_SCORE

        )

        if score_pass:

            counts["score_80_pass"] += 1

        final_pass = (

            mtf_pass

            and rsi_pass

            and adx_pass

            and volatility_pass

            and ema_distance_pass

            and candle_pass

            and sell_quality_pass

            and score_pass

        )

        if final_pass:

            counts["final_sell"] += 1

        # Simpan kandidat yang sudah lolos

        # raw bearish + H1/M15 supaya mudah dianalisis.

        if mtf_pass:

            candidates.append(

                {

                    "index": i,

                    "h1": h1,

                    "m15": m15,

                    "m1": m1,

                    "rsi": round(rsi, 2),

                    "adx": round(adx, 2),

                    "momentum": round(

                        momentum,

                        6,

                    ),

                    "trend": trend,

                    "structure": structure,

                    "candle": candle_pass,

                    "quality": sell_quality_pass,

                    "score": score,

                }

            )

    return counts, candidates

def print_report(counts, candidates):

    print()

    print("-" * 60)

    print("SELL FILTER DIAGNOSTIC")

    print("-" * 60)

    labels = [

        (

            "Raw bearish candidate",

            "raw_bearish_candidate",

        ),

        (

            "H1 + M15 aligned",

            "mtf_h1_m15_aligned",

        ),

        (

            "RSI pass",

            "rsi_pass",

        ),

        (

            "ADX pass",

            "adx_pass",

        ),

        (

            "Volatility pass",

            "volatility_pass",

        ),

        (

            "EMA distance pass",

            "ema_distance_pass",

        ),

        (

            "Candle pass",

            "candle_pass",

        ),

        (

            "SELL quality pass",

            "sell_quality_pass",

        ),

        (

            "Score >= 80",

            "score_80_pass",

        ),

        (

            "FINAL SELL",

            "final_sell",

        ),

    ]

    for label, key in labels:

        print(

            f"{label:<25}: "

            f"{counts[key]}"

        )

    print()

    print("-" * 60)

    print("SELL CANDIDATES AFTER H1 + M15")

    print("-" * 60)

    if not candidates:

        print("Tidak ada kandidat SELL dengan H1 + M15 aligned.")

    else:

        for n, item in enumerate(

            candidates[-20:],

            start=1,

        ):

            print(

                f"{n:>2}. "

                f"RSI={item['rsi']:<6} | "

                f"ADX={item['adx']:<6} | "

                f"Mom={item['momentum']:<10} | "

                f"M1={item['m1']:<4} | "

                f"Candle={str(item['candle']):<5} | "

                f"Quality={str(item['quality']):<5} | "

                f"Score={item['score']}"

            )

    print()

    print("=" * 60)

    print("DIAGNOSTIC COMPLETE")

    print("=" * 60)

def main():

    data = load_data()

    counts, candidates = diagnose(

        data

    )

    print_report(

        counts,

        candidates,

    )

if __name__ == "__main__":

    main()

'''

path = Path("/mnt/data/sell_diagnostic.py")

path.write_text(content, encoding="utf-8")

print(f"Created: {path}")