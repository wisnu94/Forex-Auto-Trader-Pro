import pandas as pd
import numpy as np

from mtf import mtf_allows_signal

# ============================================================
# INDICATORS
# ============================================================

def calculate_ema(series, period):
    return series.ewm(
        span=period,
        adjust=False
    ).mean()


def calculate_atr(df, period=14):

    high_low = df["high"] - df["low"]

    high_close = (
        df["high"] - df["close"].shift(1)
    ).abs()

    low_close = (
        df["low"] - df["close"].shift(1)
    ).abs()

    true_range = pd.concat(
        [
            high_low,
            high_close,
            low_close
        ],
        axis=1
    ).max(axis=1)

    return true_range.rolling(
        period
    ).mean()


# ============================================================
# MARKET STRUCTURE
# ============================================================

def detect_structure(df):

    if len(df) < 10:
        return "UNKNOWN"

    recent_high = df["high"].iloc[-5:-1].max()
    recent_low = df["low"].iloc[-5:-1].min()

    last_close = df["close"].iloc[-1]

    if last_close > recent_high:
        return "BULLISH_BREAK"

    if last_close < recent_low:
        return "BEARISH_BREAK"

    return "RANGE"


# ============================================================
# TREND ENGINE
# ============================================================

def detect_trend(df, fast=20, slow=50):

    df = df.copy()

    df["ema_fast"] = calculate_ema(
        df["close"],
        fast
    )

    df["ema_slow"] = calculate_ema(
        df["close"],
        slow
    )

    last = df.iloc[-1]

    if last["ema_fast"] > last["ema_slow"]:
        return "BULLISH"

    if last["ema_fast"] < last["ema_slow"]:
        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# MOMENTUM
# ============================================================

def calculate_momentum(df):

    if len(df) < 5:
        return 0.0

    current = df["close"].iloc[-1]
    previous = df["close"].iloc[-5]

    if previous == 0:
        return 0.0

    momentum = (
        (current - previous)
        / previous
    ) * 100

    return float(momentum)

# ============================================================
# PRECISION ENTRY FILTER
# ============================================================

def precision_entry_filter(
    signal,
    trend,
    structure,
    momentum,
    atr_value,
    close,
    ema_fast
):
    if signal == "BUY":

        if trend != "BULLISH":
            return False

        if structure != "BULLISH_BREAK":
            return False

        if momentum <= 0:
            return False

        if close <= ema_fast:
            return False

        if atr_value is None or atr_value <= 0:
            return False

        return True

    if signal == "SELL":

        if trend != "BEARISH":
            return False

        if structure != "BEARISH_BREAK":
            return False

        if momentum >= 0:
            return False

        if close >= ema_fast:
            return False

        if atr_value is None or atr_value <= 0:
            return False

        return True

    return False

# ============================================================
# SIGNAL ENGINE
# ============================================================

def generate_signal(
    df,
    ema_fast=20,
    ema_slow=50,
    atr_period=14,
    mtf_confirmation=None
):

    minimum_bars = max(
        ema_slow + 10,
        atr_period + 10
    )

    if len(df) < minimum_bars:
        return {
            "signal": "HOLD",
            "trend": "UNKNOWN",
            "structure": "UNKNOWN",
            "momentum": 0.0,
            "atr": None,
            "score": 0
        }

    data = df.copy()

    data["ema_fast"] = calculate_ema(
        data["close"],
        ema_fast
    )

    data["ema_slow"] = calculate_ema(
        data["close"],
        ema_slow
    )

    data["atr"] = calculate_atr(
        data,
        atr_period
    )

    last = data.iloc[-1]

    trend = detect_trend(
        data,
        ema_fast,
        ema_slow
    )

    structure = detect_structure(data)

    momentum = calculate_momentum(data)

    atr_value = last["atr"]

    # --------------------------------------------------------
    # SIGNAL SCORE
    # --------------------------------------------------------

    buy_score = 0
    sell_score = 0

    # Trend
    if trend == "BULLISH":
        buy_score += 30

    elif trend == "BEARISH":
        sell_score += 30

    # Structure
    if structure == "BULLISH_BREAK":
        buy_score += 30

    elif structure == "BEARISH_BREAK":
        sell_score += 30

    # Momentum
    if momentum > 0:
        buy_score += 20

    elif momentum < 0:
        sell_score += 20

    # Price location
    if last["close"] > last["ema_fast"]:
        buy_score += 20

    elif last["close"] < last["ema_fast"]:
        sell_score += 20

    # --------------------------------------------------------
    # FINAL SIGNAL
    # --------------------------------------------------------

    signal = "HOLD"

    if buy_score >= 70 and buy_score > sell_score:
        signal = "BUY"

    elif sell_score >= 70 and sell_score > buy_score:
        signal = "SELL"
        
    # --------------------------------------------------------
    # MTF CONFIRMATION FILTER
    # --------------------------------------------------------
    
    if mtf_confirmation is not None:
    
        if signal != "HOLD":
    
            if not mtf_allows_signal(
                signal,
                mtf_confirmation
            ):
                signal = "HOLD"
                
    # --------------------------------------------------------
    # PRECISION ENTRY FILTER
    # --------------------------------------------------------

    precision_pass = precision_entry_filter(
        signal=signal,
        trend=trend,
        structure=structure,
        momentum=momentum,
        atr_value=(
            float(atr_value)
            if pd.notna(atr_value)
            else None
        ),
        close=float(last["close"]),
        ema_fast=float(last["ema_fast"])
    )

    if signal != "HOLD" and not precision_pass:
        signal = "HOLD"

    return {
        "signal": signal,
        "precision_pass": precision_pass,
        "mtf_status": (
            mtf_confirmation["status"]
            if mtf_confirmation is not None
            else "NOT_CHECKED"
        ),
        "trend": trend,
        "structure": structure,
        "momentum": round(momentum, 4),
        "atr": (
            float(atr_value)
            if pd.notna(atr_value)
            else None
        ),
        "buy_score": buy_score,
        "sell_score": sell_score,
        "score": max(
            buy_score,
            sell_score
        )
    }