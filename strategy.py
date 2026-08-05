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
# ADX
# ============================================================

def calculate_adx(df, period=14):

    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where(
            (up_move > down_move) & (up_move > 0),
            up_move,
            0.0
        ),
        index=df.index
    )

    minus_dm = pd.Series(
        np.where(
            (down_move > up_move) & (down_move > 0),
            down_move,
            0.0
        ),
        index=df.index
    )

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    true_range = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(axis=1)

    atr = true_range.rolling(
        period
    ).mean()

    plus_di = (
        100
        * plus_dm.rolling(period).mean()
        / atr.replace(0, np.nan)
    )

    minus_di = (
        100
        * minus_dm.rolling(period).mean()
        / atr.replace(0, np.nan)
    )

    denominator = (
        plus_di + minus_di
    ).replace(0, np.nan)

    dx = (
        100
        * (plus_di - minus_di).abs()
        / denominator
    )

    return dx.rolling(
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

def detect_trend(
    df,
    fast=20,
    slow=50
):

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

    current = df["close"].iloc[-1]
    previous = df["close"].iloc[-5]

    if previous == 0:
        return 0.0

    return float(
        ((current - previous) / previous) * 100
    )


# ============================================================
# BREAKOUT STRENGTH
# ============================================================

def calculate_breakout_strength(
    df,
    signal,
    atr_value
):

    if len(df) < 5:
        return 0.0

    previous_high = df["high"].iloc[-5:-1].max()
    previous_low = df["low"].iloc[-5:-1].min()

    close = float(df["close"].iloc[-1])

    if atr_value is None or atr_value <= 0:
        return 0.0

    if signal == "BUY":

        breakout_distance = (
            close - previous_high
        )

    elif signal == "SELL":

        breakout_distance = (
            previous_low - close
        )

    else:
        return 0.0

    if breakout_distance <= 0:
        return 0.0

    return float(
        breakout_distance / atr_value
    )


# ============================================================
# EMA SEPARATION
# ============================================================

def calculate_ema_separation(
    close,
    ema_fast,
    ema_slow
):

    if close == 0:
        return 0.0

    return float(
        abs(ema_fast - ema_slow)
        / close
        * 100
    )


# ============================================================
# PRECISION SCORE V3
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
    adx_value=None,
    breakout_strength=0.0,
    ema_separation=0.0,
    mtf_confirmation=None
):

    if signal == "HOLD":
        return 0

    score = 0

    # ========================================================
    # 1. TREND ALIGNMENT — 20 POINTS
    # ========================================================

    if signal == "BUY" and trend == "BULLISH":
        score += 20

    elif signal == "SELL" and trend == "BEARISH":
        score += 20

    # ========================================================
    # 2. STRUCTURE — 20 POINTS
    # ========================================================

    if signal == "BUY" and structure == "BULLISH_BREAK":
        score += 20

    elif signal == "SELL" and structure == "BEARISH_BREAK":
        score += 20

    # ========================================================
    # 3. ADX STRENGTH — 20 POINTS
    # ========================================================

    if adx_value is not None:

        if adx_value >= 30:
            score += 20

        elif adx_value >= 25:
            score += 15

        elif adx_value >= 20:
            score += 10

    # ========================================================
    # 4. BREAKOUT STRENGTH — 15 POINTS
    # ========================================================

    if breakout_strength >= 1.0:
        score += 15

    elif breakout_strength >= 0.50:
        score += 10

    elif breakout_strength > 0:
        score += 5

    # ========================================================
    # 5. MOMENTUM STRENGTH — 10 POINTS
    # ========================================================

    if signal == "BUY" and momentum > 0.05:
        score += 10

    elif signal == "SELL" and momentum < -0.05:
        score += 10

    elif (
        signal == "BUY"
        and momentum > 0
    ):
        score += 5

    elif (
        signal == "SELL"
        and momentum < 0
    ):
        score += 5

    # ========================================================
    # 6. EMA SEPARATION — 10 POINTS
    # ========================================================

    if ema_separation >= 0.20:
        score += 10

    elif ema_separation >= 0.10:
        score += 7

    elif ema_separation >= 0.05:
        score += 4

    # ========================================================
    # 7. MTF CONFIRMATION — 5 POINTS
    # ========================================================

    if mtf_confirmation is not None:

        mtf_status = mtf_confirmation.get(
            "status",
            "UNKNOWN"
        )

        if (
            signal == "BUY"
            and mtf_status == "STRONG_BUY"
        ):
            score += 5

        elif (
            signal == "SELL"
            and mtf_status == "STRONG_SELL"
        ):
            score += 5

    return min(score, 100)


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
    ema_fast,
    ema_slow,
    precision_score
):

    if signal == "HOLD":
        return False

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

    elif signal == "SELL":

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

    else:
        return False

    if atr_value is None or atr_value <= 0:
        return False

    # ========================================================
    # IMPORTANT:
    # Minimum precision threshold
    # ========================================================

    if precision_score < 70:
        return False

    return True


# ============================================================
# GRADE
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
# DECISION
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
        atr_period * 2 + 10,
        50
    )

    if len(df) < minimum_bars:

        return {
            "signal": "HOLD",
            "trend": "UNKNOWN",
            "structure": "UNKNOWN",
            "momentum": 0.0,
            "atr": None,
            "adx": None,
            "breakout_strength": 0.0,
            "ema_separation": 0.0,
            "precision_score": 0,
            "precision_grade": "D",
            "precision_pass": False,
            "precision_decision": "NO_TRADE",
            "score": 0
        }

    data = df.copy()

    # --------------------------------------------------------
    # INDICATORS
    # --------------------------------------------------------

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

    data["adx"] = calculate_adx(
        data,
        atr_period
    )

    last = data.iloc[-1]

    atr_value = (
        float(last["atr"])
        if pd.notna(last["atr"])
        else None
    )

    adx_value = (
        float(last["adx"])
        if pd.notna(last["adx"])
        else None
    )

    # --------------------------------------------------------
    # CORE ENGINES
    # --------------------------------------------------------

    trend = detect_trend(
        data,
        ema_fast,
        ema_slow
    )

    structure = detect_structure(
        data
    )

    momentum = calculate_momentum(
        data
    )

    # --------------------------------------------------------
    # BASE SIGNAL
    # --------------------------------------------------------

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

    if last["close"] > last["ema_fast"]:
        buy_score += 20

    elif last["close"] < last["ema_fast"]:
        sell_score += 20

    signal = "HOLD"

    if buy_score >= 70 and buy_score > sell_score:
        signal = "BUY"

    elif sell_score >= 70 and sell_score > buy_score:
        signal = "SELL"

    # --------------------------------------------------------
    # MTF FILTER
    # --------------------------------------------------------

    if (
        signal != "HOLD"
        and mtf_confirmation is not None
    ):

        if not mtf_allows_signal(
            signal,
            mtf_confirmation
        ):
            signal = "HOLD"

    # --------------------------------------------------------
    # ADVANCED MEASUREMENTS
    # --------------------------------------------------------

    breakout_strength = calculate_breakout_strength(
        data,
        signal,
        atr_value
    )

    ema_separation = calculate_ema_separation(
        close=float(last["close"]),
        ema_fast=float(last["ema_fast"]),
        ema_slow=float(last["ema_slow"])
    )

    # --------------------------------------------------------
    # PRECISION SCORE V3
    # --------------------------------------------------------

    precision_score = calculate_precision_score(
        signal=signal,
        trend=trend,
        structure=structure,
        momentum=momentum,
        atr_value=atr_value,
        close=float(last["close"]),
        ema_fast=float(last["ema_fast"]),
        ema_slow=float(last["ema_slow"]),
        adx_value=adx_value,
        breakout_strength=breakout_strength,
        ema_separation=ema_separation,
        mtf_confirmation=mtf_confirmation
    )

    # --------------------------------------------------------
    # PRECISION FILTER
    # --------------------------------------------------------

    precision_pass = precision_entry_filter(
        signal=signal,
        trend=trend,
        structure=structure,
        momentum=momentum,
        atr_value=atr_value,
        close=float(last["close"]),
        ema_fast=float(last["ema_fast"]),
        ema_slow=float(last["ema_slow"]),
        precision_score=precision_score
    )

    if signal != "HOLD" and not precision_pass:
        signal = "HOLD"

    # --------------------------------------------------------
    # FINAL GRADE
    # --------------------------------------------------------

    precision_grade = get_precision_grade(
        precision_score
    )

    precision_decision = get_precision_decision(
        signal=signal,
        score=precision_score,
        precision_pass=precision_pass
    )

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {
        "signal": signal,

        "precision_pass": precision_pass,

        "precision_score": precision_score,

        "precision_grade": precision_grade,

        "precision_decision": precision_decision,

        "trend": trend,

        "structure": structure,

        "momentum": round(
            momentum,
            4
        ),

        "atr": atr_value,

        "adx": adx_value,

        "breakout_strength": round(
            breakout_strength,
            4
        ),

        "ema_separation": round(
            ema_separation,
            4
        ),

        "mtf_status": (
            mtf_confirmation["status"]
            if mtf_confirmation is not None
            else "NOT_CHECKED"
        ),

        "buy_score": buy_score,

        "sell_score": sell_score,

        "score": max(
            buy_score,
            sell_score
        )
    }