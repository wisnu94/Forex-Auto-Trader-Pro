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

    data = df.copy()

    data["ema_fast"] = calculate_ema(
        data["close"],
        fast
    )

    data["ema_slow"] = calculate_ema(
        data["close"],
        slow
    )

    last = data.iloc[-1]

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

    current = float(df["close"].iloc[-1])
    previous = float(df["close"].iloc[-5])

    if previous == 0:
        return 0.0

    momentum = (
        (current - previous)
        / previous
    ) * 100

    return float(momentum)


# ============================================================
# PRECISION ENTRY FILTER V2
# ============================================================

def precision_entry_filter(
    signal,
    trend,
    structure,
    momentum,
    atr_value,
    close,
    ema_fast,
    ema_slow,
    breakout_strength=0.0,
    ema_separation=0.0
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

        if ema_fast <= ema_slow:
            return False

        if atr_value is None or atr_value <= 0:
            return False

        # Breakout harus cukup kuat dibanding ATR
        if breakout_strength < 0.15:
            return False

        # EMA harus memiliki separation minimum
        if ema_separation < 0.05:
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

        if ema_fast >= ema_slow:
            return False

        if atr_value is None or atr_value <= 0:
            return False

        # SELL dibuat lebih ketat
        if breakout_strength < 0.20:
            return False

        if ema_separation < 0.08:
            return False

        return True

    return False


# ============================================================
# PRECISION SCORE ENGINE V2
# ============================================================

def calculate_precision_score(
    signal,
    trend,
    structure,
    momentum,
    atr_value,
    close,
    ema_fast,
    ema_slow,
    breakout_strength=0.0,
    ema_separation=0.0,
    mtf_confirmation=None
):

    score = 0

    # --------------------------------------------------------
    # MTF — 25 POINTS
    # --------------------------------------------------------

    if mtf_confirmation is not None:

        mtf_status = mtf_confirmation.get(
            "status",
            "UNKNOWN"
        )

        if signal == "BUY" and mtf_status == "STRONG_BUY":
            score += 25

        elif signal == "SELL" and mtf_status == "STRONG_SELL":
            score += 25

    # --------------------------------------------------------
    # TREND — 20 POINTS
    # --------------------------------------------------------

    if signal == "BUY" and trend == "BULLISH":
        score += 20

    elif signal == "SELL" and trend == "BEARISH":
        score += 20

    # --------------------------------------------------------
    # STRUCTURE — 20 POINTS
    # --------------------------------------------------------

    if signal == "BUY" and structure == "BULLISH_BREAK":
        score += 20

    elif signal == "SELL" and structure == "BEARISH_BREAK":
        score += 20

    # --------------------------------------------------------
    # MOMENTUM — 15 POINTS
    # --------------------------------------------------------

    if signal == "BUY" and momentum > 0:
        score += 15

    elif signal == "SELL" and momentum < 0:
        score += 15

    # --------------------------------------------------------
    # PRICE / EMA — 10 POINTS
    # --------------------------------------------------------

    if signal == "BUY" and close > ema_fast:
        score += 10

    elif signal == "SELL" and close < ema_fast:
        score += 10

    # --------------------------------------------------------
    # BREAKOUT STRENGTH — 5 POINTS
    # --------------------------------------------------------

    if breakout_strength >= 0.20:
        score += 5

    # --------------------------------------------------------
    # EMA SEPARATION — 5 POINTS
    # --------------------------------------------------------

    if ema_separation >= 0.10:
        score += 5

    # --------------------------------------------------------
    # ATR VALIDITY
    # --------------------------------------------------------

    # ATR tetap wajib valid, tetapi tidak menjadi poin utama.
    # Ini mencegah score tinggi hanya karena ATR tersedia.

    if atr_value is None or atr_value <= 0:
        return 0

    return min(score, 100)


# ============================================================
# PRECISION GRADE ENGINE V2
# ============================================================

def get_precision_grade(score):

    if score >= 90:
        return "A+"

    if score >= 80:
        return "A"

    if score >= 70:
        return "B"

    if score >= 60:
        return "C"

    return "D"


# ============================================================
# PRECISION DECISION
# ============================================================

def get_precision_decision(
    signal,
    score,
    precision_pass
):

    if not precision_pass:
        return "NO_TRADE"

    if score >= 90:

        if signal == "BUY":
            return "STRONG_BUY"

        if signal == "SELL":
            return "STRONG_SELL"

    if score >= 80:

        if signal == "BUY":
            return "BUY"

        if signal == "SELL":
            return "SELL"

    if score >= 70:

        if signal == "BUY":
            return "VALID_BUY"

        if signal == "SELL":
            return "VALID_SELL"

    return "NO_TRADE"


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

    if df is None or len(df) < minimum_bars:

        return {
            "signal": "HOLD",
            "precision_pass": False,
            "precision_score": 0,
            "precision_grade": "D",
            "precision_decision": "NO_TRADE",
            "mtf_status": "NOT_CHECKED",
            "trend": "UNKNOWN",
            "structure": "UNKNOWN",
            "momentum": 0.0,
            "atr": None,
            "buy_score": 0,
            "sell_score": 0,
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

    atr_value = (
        float(last["atr"])
        if pd.notna(last["atr"])
        else None
    )

    close = float(last["close"])
    ema_fast_value = float(last["ema_fast"])
    ema_slow_value = float(last["ema_slow"])

    # ========================================================
    # BREAKOUT STRENGTH
    # ========================================================

    if atr_value is not None and atr_value > 0:

        if structure == "BULLISH_BREAK":

            previous_high = data["high"].iloc[-5:-1].max()

            breakout_distance = (
                close - previous_high
            )

            breakout_strength = (
                breakout_distance / atr_value
            )

        elif structure == "BEARISH_BREAK":

            previous_low = data["low"].iloc[-5:-1].min()

            breakout_distance = (
                previous_low - close
            )

            breakout_strength = (
                breakout_distance / atr_value
            )

        else:

            breakout_strength = 0.0

    else:

        breakout_strength = 0.0

    # ========================================================
    # EMA SEPARATION
    # ========================================================

    if atr_value is not None and atr_value > 0:

        ema_separation = (
            abs(
                ema_fast_value
                - ema_slow_value
            )
            / atr_value
        )

    else:

        ema_separation = 0.0

    # ========================================================
    # BASE SIGNAL SCORE
    # ========================================================

    buy_score = 0
    sell_score = 0

    if trend == "BULLISH":
        buy_score += 30

    elif trend == "BEARISH":
        sell_score += 30

    if structure == "BULLISH_BREAK":
        buy_score += 30

    elif structure == "BEARISH_BREAK":
        sell_score += 30

    if momentum > 0:
        buy_score += 20

    elif momentum < 0:
        sell_score += 20

    if close > ema_fast_value:
        buy_score += 20

    elif close < ema_fast_value:
        sell_score += 20

    # ========================================================
    # INITIAL SIGNAL
    # ========================================================

    signal = "HOLD"

    if buy_score >= 70 and buy_score > sell_score:
        signal = "BUY"

    elif sell_score >= 70 and sell_score > buy_score:
        signal = "SELL"

    # ========================================================
    # MTF FILTER
    # ========================================================

    if (
        signal != "HOLD"
        and mtf_confirmation is not None
    ):

        if not mtf_allows_signal(
            signal,
            mtf_confirmation
        ):

            signal = "HOLD"

    # ========================================================
    # PRECISION FILTER
    # ========================================================

    precision_pass = False

    if signal != "HOLD":

        precision_pass = precision_entry_filter(
            signal=signal,
            trend=trend,
            structure=structure,
            momentum=momentum,
            atr_value=atr_value,
            close=close,
            ema_fast=ema_fast_value,
            ema_slow=ema_slow_value,
            breakout_strength=breakout_strength,
            ema_separation=ema_separation
        )

        if not precision_pass:
            signal = "HOLD"

    # ========================================================
    # PRECISION SCORE
    # ========================================================

    precision_score = calculate_precision_score(
        signal=signal,
        trend=trend,
        structure=structure,
        momentum=momentum,
        atr_value=atr_value,
        close=close,
        ema_fast=ema_fast_value,
        ema_slow=ema_slow_value,
        breakout_strength=breakout_strength,
        ema_separation=ema_separation,
        mtf_confirmation=mtf_confirmation
    )

    precision_grade = get_precision_grade(
        precision_score
    )

    precision_decision = get_precision_decision(
        signal=signal,
        score=precision_score,
        precision_pass=precision_pass
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return {
        "signal": signal,

        "precision_pass": precision_pass,

        "precision_score": precision_score,

        "precision_grade": precision_grade,

        "precision_decision": precision_decision,

        "mtf_status": (
            mtf_confirmation.get(
                "status",
                "UNKNOWN"
            )
            if mtf_confirmation is not None
            else "NOT_CHECKED"
        ),

        "trend": trend,

        "structure": structure,

        "momentum": round(
            momentum,
            4
        ),

        "atr": atr_value,

        "breakout_strength": round(
            breakout_strength,
            4
        ),

        "ema_separation": round(
            ema_separation,
            4
        ),

        "buy_score": buy_score,

        "sell_score": sell_score,

        "score": max(
            buy_score,
            sell_score
        )
    }