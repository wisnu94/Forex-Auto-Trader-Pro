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
# ADX ENGINE
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

    tr2 = (
        high - close.shift(1)
    ).abs()

    tr3 = (
        low - close.shift(1)
    ).abs()

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

    adx = dx.rolling(
        period
    ).mean()

    return adx


# ============================================================
# MARKET REGIME ENGINE V1
# ============================================================

def detect_market_regime(
    df,
    adx_period=14,
    adx_trend_threshold=20.0
):

    if len(df) < adx_period * 2:
        return "UNKNOWN"

    data = df.copy()

    data["adx"] = calculate_adx(
        data,
        adx_period
    )

    last_adx = data["adx"].iloc[-1]

    if pd.isna(last_adx):
        return "UNKNOWN"

    # Strong enough directional market
    if last_adx >= adx_trend_threshold:
        return "TRENDING"

    # Weak directional movement
    return "RANGING"


# ============================================================
# MARKET REGIME FILTER
# ============================================================

def market_regime_allows_signal(
    signal,
    regime
):

    if signal == "HOLD":
        return False

    # Only trade directional markets
    if regime != "TRENDING":
        return False

    return True


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
    ema_slow
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

        return True

    return False


# ============================================================
# PRECISION SCORE ENGINE
# ============================================================

def calculate_precision_score(
    signal,
    trend,
    structure,
    momentum,
    atr_value,
    close,
    ema_fast,
    mtf_confirmation=None,
    market_regime=None
):

    score = 0

    # --------------------------------------------------------
    # MARKET REGIME — 15 POINTS
    # --------------------------------------------------------

    if market_regime == "TRENDING":
        score += 15

    # --------------------------------------------------------
    # MTF ALIGNMENT — 25 POINTS
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
    # PRICE / EMA — 5 POINTS
    # --------------------------------------------------------

    if signal == "BUY" and close > ema_fast:
        score += 5

    elif signal == "SELL" and close < ema_fast:
        score += 5

    # --------------------------------------------------------
    # ATR VALIDITY
    # --------------------------------------------------------

    if atr_value is not None and atr_value > 0:
        score += 5

    return min(score, 100)


# ============================================================
# PRECISION GRADE ENGINE
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
        atr_period + 10,
        40
    )

    if len(df) < minimum_bars:

        return {
            "signal": "HOLD",
            "trend": "UNKNOWN",
            "structure": "UNKNOWN",
            "market_regime": "UNKNOWN",
            "adx": None,
            "momentum": 0.0,
            "atr": None,
            "score": 0,
            "precision_score": 0,
            "precision_grade": "D",
            "precision_pass": False,
            "precision_decision": "NO_TRADE"
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

    # --------------------------------------------------------
    # ENGINES
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

    market_regime = detect_market_regime(
        data,
        adx_period=atr_period,
        adx_trend_threshold=20.0
    )

    atr_value = last["atr"]

    adx_value = (
        float(last["adx"])
        if pd.notna(last["adx"])
        else None
    )

    # --------------------------------------------------------
    # BASE SIGNAL SCORE
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
    # FINAL BASE SIGNAL
    # --------------------------------------------------------

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
    # MARKET REGIME FILTER
    # --------------------------------------------------------

    if signal != "HOLD":

        if not market_regime_allows_signal(
            signal,
            market_regime
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
        ema_fast=float(last["ema_fast"]),
        ema_slow=float(last["ema_slow"])
    )

    if signal != "HOLD" and not precision_pass:
        signal = "HOLD"

    # --------------------------------------------------------
    # PRECISION SCORE
    # --------------------------------------------------------

    precision_score = calculate_precision_score(
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
        ema_fast=float(last["ema_fast"]),
        mtf_confirmation=mtf_confirmation,
        market_regime=market_regime
    )

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {
        "signal": signal,

        "precision_pass": precision_pass,

        "precision_score": precision_score,

        "precision_grade": get_precision_grade(
            precision_score
        ),

        "precision_decision": get_precision_decision(
            signal=signal,
            score=precision_score,
            precision_pass=precision_pass
        ),

        "market_regime": market_regime,

        "adx": adx_value,

        "mtf_status": (
            mtf_confirmation["status"]
            if mtf_confirmation is not None
            else "NOT_CHECKED"
        ),

        "trend": trend,

        "structure": structure,

        "momentum": round(
            momentum,
            4
        ),

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