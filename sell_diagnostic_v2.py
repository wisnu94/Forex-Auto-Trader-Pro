from pathlib import Path

content = '''import pandas as pd

import numpy as np

from config import SYMBOL, TIMEFRAME

from data import get_bars

from strategy import (

    calculate_ema, calculate_atr, calculate_rsi, calculate_adx,

    calculate_momentum, detect_trend, detect_structure,

    candle_confirmation, rsi_confirmation, adx_confirmation,

    volatility_confirmation, ema_distance_confirmation,

    sell_quality_gate, calculate_precision_score,

)

from backtest import _build_mtf_confirmation

BARS = 3000

def main():

    print("=" * 70)

    print("FOREX AUTO TRADER PRO - SELL FILTER DIAGNOSTIC V2")

    print("=" * 70)

    print(f"Symbol    : {SYMBOL}")

    print(f"Timeframe : {TIMEFRAME}")

    print(f"Bars      : {BARS}")

    print("Tujuan: mencari FILTER PERTAMA yang membuang SELL.")

    print("Tidak mengubah strategy.py / backtest.py.")

    print()

    df = get_bars(symbol=SYMBOL, timeframe=TIMEFRAME, count=BARS)

    if df is None or len(df) == 0:

        raise RuntimeError("Data kosong.")

    df = df.copy().reset_index(drop=True)

    for col in ["open", "high", "low", "close"]:

        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

    counters = {

        "candidate": 0, "mtf": 0, "rsi": 0, "adx": 0,

        "vol": 0, "ema": 0, "candle": 0, "quality": 0,

        "score70": 0, "score80": 0

    }

    failures = {}

    scores = []

    for i in range(70, len(df) - 1):

        h = df.iloc[:i + 1].copy().reset_index(drop=True)

        close = float(h["close"].iloc[-1])

        ef = float(calculate_ema(h["close"], 20).iloc[-1])

        es = float(calculate_ema(h["close"], 50).iloc[-1])

        atrs = calculate_atr(h, 14)

        atr = atrs.iloc[-1]

        atravg = atrs.rolling(20).mean().iloc[-1]

        if pd.isna(atr) or pd.isna(atravg):

            continue

        atr, atravg = float(atr), float(atravg)

        rsi = float(calculate_rsi(h["close"], 14).iloc[-1])

        adx = float(calculate_adx(h, 14).iloc[-1])

        mom = float(calculate_momentum(h))

        trend = detect_trend(h, 20, 50)

        structure = detect_structure(h)

        if not (trend == "BEARISH" and structure == "BEARISH_BREAK" and mom < 0):

            continue

        counters["candidate"] += 1

        mtf = _build_mtf_confirmation(h)

        t = mtf.get("trends", {})

        if not (t.get("H1") == "SELL" and t.get("M15") == "SELL"):

            failures["H1/M15 permission"] = failures.get("H1/M15 permission", 0) + 1

            continue

        counters["mtf"] += 1

        candle = candle_confirmation(h, "SELL")

        if not rsi_confirmation("SELL", rsi):

            failures["RSI"] = failures.get("RSI", 0) + 1

            continue

        counters["rsi"] += 1

        if not adx_confirmation("SELL", adx):

            failures["ADX"] = failures.get("ADX", 0) + 1

            continue

        counters["adx"] += 1

        if not volatility_confirmation(atr, atravg):

            failures["Volatility"] = failures.get("Volatility", 0) + 1

            continue

        counters["vol"] += 1

        if not ema_distance_confirmation("SELL", close, ef, atr):

            failures["EMA distance"] = failures.get("EMA distance", 0) + 1

            continue

        counters["ema"] += 1

        if not candle:

            failures["Candle confirmation"] = failures.get("Candle confirmation", 0) + 1

            continue

        counters["candle"] += 1

        if not sell_quality_gate(mom, adx, rsi, candle):

            reasons = []

            if mom > -0.08: reasons.append("momentum>-0.08")

            if adx < 22: reasons.append("ADX<22")

            if rsi < 34: reasons.append("RSI<34")

            key = "SELL quality: " + ",".join(reasons)

            failures[key] = failures.get(key, 0) + 1

            continue

        counters["quality"] += 1

        score = calculate_precision_score(

            "SELL", trend, structure, mom, atr, close, ef, es,

            rsi, adx, atravg, candle, mtf

        )

        scores.append(score)

        if score >= 70: counters["score70"] += 1

        if score >= 80: counters["score80"] += 1

    print("-" * 70)

    print("SELL PIPELINE")

    print("-" * 70)

    for label, key in [

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

    ]:

        print(f"{label:<30}: {counters[key]:>5}")

    print()

    print("-" * 70)

    print("MAIN BOTTLENECKS")

    print("-" * 70)

    for reason, count in sorted(failures.items(), key=lambda x: x[1], reverse=True)[:10]:

        print(f"{reason:<45}: {count}")

    print()

    if scores:

        print(f"Post-quality SELL count : {len(scores)}")

        print(f"Min / Max score         : {min(scores)} / {max(scores)}")

        print(f"Average score            : {np.mean(scores):.2f}")

    else:

        print("Tidak ada SELL yang lolos sampai tahap score.")

    print("=" * 70)

    print("DIAGNOSTIC COMPLETE")

    print("=" * 70)

if __name__ == "__main__":

    main()

'''

p = Path("/mnt/data/sell_diagnostic_v2.py")

p.write_text(content, encoding="utf-8")

print(f"Created: {p}")