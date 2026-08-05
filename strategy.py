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


def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(
        0,
        np.nan
    )

    rsi = 100 - (
        100 / (1 + rs)
    )

    return rsi.fillna(50.0)


def calculate_adx(df, period=14):

    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where(
            (up_move > down_move)
            & (up_move > 0),
            up_move,
            0.0
        ),
        index=df.index
    )

    minus_dm = pd.Series(
        np.where(
            (down_move > up_move)
            & (down_move > 0),
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

    tr = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(axis=1)

    atr = tr.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    plus_di = (
        100
        * plus_dm.ewm(
            alpha=1 / period,
            adjust=False
        ).mean()
        / atr.replace(0, np.nan)
    )

    minus_di = (
        100
        * minus_dm.ewm(
            alpha=1 / period,
            adjust=False
        ).mean()
        / atr.replace(0, np.nan)
    )

    dx = (
        100
        * (plus_di - minus_di).abs()
        / (plus_di + minus_di).replace(
            0,
            np.nan
        )
    )

    adx = dx.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    return (
        adx.fillna(0.0),
        plus_di.fillna(0.0),
        minus_di.fillna(0.0)
    )


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
# EMA SLOPE ENGINE
# ============================================================

def calculate_ema_slope(
    df,
    fast=20,
    lookback=5
):

    ema = calculate_ema(
        df["close"],
        fast
    )

    if len(ema) <= lookback:
        return 0.0

    current = float(
        ema.iloc[-1]
    )

    previous = float(
        ema.iloc[-1 - lookback]
    )

    if previous == 0:
        return 0.0

    return (
        (current - previous)
        / previous
    ) * 100


# ============================================================
# MOMENTUM
# ============================================================

def calculate_momentum(df):

    if len(df) < 5:
        return 0.0

    current = float(
        df["close"].iloc[-1]
    )

    previous = float(
        df["close"].iloc[-5]
    )

    if previous == 0:
        return 0.0

    return (
        (current - previous)
        / previous
    ) * 100


# ============================================================
# CANDLE QUALITY
# ============================================================

def calculate_candle_quality(df):

    candle = df.iloc[-1]

    high = float(candle["high"])
    low = float(candle["low"])
    close = float(candle["close"])
    open_price = float(candle["open"])

    candle_range = high - low

    if candle_range <= 0:
        return 0.0

    body = abs(
        close - open_price
    )

    return body / candle_range


# ============================================================
# BREAKOUT QUALITY
# ============================================================

def calculate_breakout_quality(
    df,
    signal
):

    if len(df) < 6:
        return False

    candle = df.iloc[-1]

    high = float(candle["high"])
    low = float(candle["low"])
    close = float(candle["close"])
    open_price = float(candle["open"])

    candle_range = high - low

    if candle_range <= 0:
        return False

    body = abs(
        close - open_price
    )

    body_ratio = (
        body / candle_range
    )

    recent_high = df["high"].iloc[-5:-1].max()
    recent_low = df["low"].iloc[-5:-1].min()

    if signal == "BUY":

        return (
            close > recent_high
            and close > open_price
            and body_ratio >= 0.55
        )

    if signal == "SELL":

        return (
            close < recent_low
            and close < open_price
            and body_ratio >= 0.55
        )

    return False


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
    rsi,
    adx,
    plus_di,
    minus_di,
    ema_slope,
    candle_quality,
    breakout_quality
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

        if ema_slope <= 0:
            return False

        if rsi < 55 or rsi > 72:
            return False

        if adx < 20:
            return False

        if plus_di <= minus_di:
            return False

        if candle_quality < 0.55:
            return False

        if not breakout_quality:
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

        if ema_slope >= 0:
            return False

        if rsi > 45 or rsi < 28:
            return False

        if adx < 20:
            return False

        if minus_di <= plus_di:
            return False

        if candle_quality < 0.55:
            return False

        if not breakout_quality:
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
    ema_slow,
    rsi,
    adx,
    plus_di,
    minus_di,
    ema_slope,
    candle_quality,
    breakout_quality,
    mtf_confirmation=None
):

    score = 0

    # --------------------------------------------------------
    # MTF — 15 POINTS
    # --------------------------------------------------------

    if mtf_confirmation is not None:

        mtf_status = mtf_confirmation.get(
            "status",
            "UNKNOWN"
        )

        if (
            signal == "BUY"
            and mtf_status == "STRONG_BUY"
        ):
            score += 15

        elif (
            signal == "SELL"
            and mtf_status == "STRONG_SELL"
        ):
            score += 15

    # --------------------------------------------------------
    # TREND — 15 POINTS
    # --------------------------------------------------------

    if (
        signal == "BUY"
        and trend == "BULLISH"
    ):
        score += 15

    elif (
        signal == "SELL"
        and trend == "BEARISH"
    ):
        score += 15

    # --------------------------------------------------------
    # STRUCTURE — 15 POINTS
    # --------------------------------------------------------

    if (
        signal == "BUY"
        and structure == "BULLISH_BREAK"
    ):
        score += 15

    elif (
        signal == "SELL"
        and structure == "BEARISH_BREAK"
    ):
        score += 15

    # --------------------------------------------------------
    # MOMENTUM — 10 POINTS
    # --------------------------------------------------------

    if (
        signal == "BUY"
        and momentum > 0
    ):
        score += 10

    elif (
        signal == "SELL"
        and momentum < 0
    ):
        score += 10

    # --------------------------------------------------------
    # EMA POSITION — 10 POINTS
    # --------------------------------------------------------

    if (
        signal == "BUY"
        and close > ema_fast
        and ema_fast > ema_slow
    ):
        score += 10

    elif (
        signal == "SELL"
        and close < ema_fast
        and ema_fast < ema_slow
    ):
        score += 10

    # --------------------------------------------------------
    # EMA SLOPE — 10 POINTS
    # --------------------------------------------------------

    if (
        signal == "BUY"
        and ema_slope > 0
    ):
        score += 10

    elif (
        signal == "SELL"
        and ema_slope < 0
    ):
        score += 10

    # --------------------------------------------------------
    # RSI — 10 POINTS
    # --------------------------------------------------------

    if signal == "BUY":

        if 55 <= rsi <= 72:
            score += 10

        elif 50 <= rsi < 55:
            score += 5

    elif signal == "SELL":

        if 28 <= rsi <= 45:
            score += 10

        elif 45 < rsi <= 50:
            score += 5

    # --------------------------------------------------------
    # ADX + DI — 10 POINTS
    # --------------------------------------------------------

    if adx >= 25:

        if (
            signal == "BUY"
            and plus_di > minus_di
        ):
            score += 10

        elif (
            signal == "SELL"
            and minus_di > plus_di
        ):
            score += 10

    elif adx >= 20:

        if (
            signal == "BUY"
            and plus_di > minus_di
        ):
            score += 5

        elif (
            signal == "SELL"
            and minus_di > plus_di
        ):
            score += 5

    # --------------------------------------------------------
    # CANDLE QUALITY — 5 POINTS
    # --------------------------------------------------------

    if candle_quality >= 0.70:
        score += 5

    elif candle_quality >= 0.55:
        score += 3

    # --------------------------------------------------------
    # BREAKOUT QUALITY — 5 POINTS
    # --------------------------------------------------------

    if breakout_quality:
        score += 5

    # --------------------------------------------------------
    # ATR — 5 POINTS
    # --------------------------------------------------------

    if (
        atr_value is not None
        and atr_value > 0
    ):
        score += 5

    return min(
        int(score),
        100
    )


# ============================================================
# PRECISION GRADE
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
        ema_slow + 20,
        atr_period + 20,
        80
    )

    if (
        df is None
        or len(df) < minimum_bars
    ):

        return {
            "signal": "HOLD",
            "trend": "UNKNOWN",
            "structure": "UNKNOWN",
            "momentum": 0.0,
            "atr": None,
            "precision_pass": False,
            "precision_score": 0,
            "precision_grade": "D",
            "precision_decision": "NO_TRADE",
            "mtf_status": "NOT_CHECKED",
            "buy_score": 0,
            "sell_score": 0,
            "score": 0
        }

    data = df.copy()

    # --------------------------------------------------------
    # CORE INDICATORS
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

    data["rsi"] = calculate_rsi(
        data["close"],
        14
    )

    (
        data["adx"],
        data["plus_di"],
        data["minus_di"]
    ) = calculate_adx(
        data,
        14
    )

    last = data.iloc[-1]

    # --------------------------------------------------------
    # BASE ANALYSIS
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

    atr_value = (
        float(last["atr"])
        if pd.notna(last["atr"])
        else None
    )

    close = float(
        last["close"]
    )

    ema_fast_value = float(
        last["ema_fast"]
    )

    ema_slow_value = float(
        last["ema_slow"]
    )

    rsi = float(
        last["rsi"]
    )

    adx = float(
        last["adx"]
    )

    plus_di = float(
        last["plus_di"]
    )

    minus_di = float(
        last["minus_di"]
    )

    ema_slope = calculate_ema_slope(
        data,
        ema_fast,
        5
    )

    candle_quality = (
        calculate_candle_quality(
            data
        )
    )

    # --------------------------------------------------------
    # PRELIMINARY SIGNAL
    # --------------------------------------------------------

    buy_score = 0
    sell_score = 0

    # Trend
    if trend == "BULLISH":
        buy_score += 25

    elif trend == "BEARISH":
        sell_score += 25

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

    # Price / EMA
    if close > ema_fast_value:
        buy_score += 15

    elif close < ema_fast_value:
        sell_score += 15

    # ADX direction
    if adx >= 20:

        if plus_di > minus_di:
            buy_score += 10

        elif minus_di > plus_di:
            sell_score += 10

    signal = "HOLD"

    if (
        buy_score >= 70
        and buy_score > sell_score
    ):
        signal = "BUY"

    elif (
        sell_score >= 70
        and sell_score > buy_score
    ):
        signal = "SELL"

    # --------------------------------------------------------
    # BREAKOUT QUALITY
    # --------------------------------------------------------

    breakout_quality = (
        calculate_breakout_quality(
            data,
            signal
        )
    )

    # --------------------------------------------------------
    # MTF FILTER
    # --------------------------------------------------------

    if (
        mtf_confirmation is not None
        and signal != "HOLD"
    ):

        if not mtf_allows_signal(
            signal,
            mtf_confirmation
        ):
            signal = "HOLD"

    # --------------------------------------------------------
    # PRECISION ENTRY FILTER
    # --------------------------------------------------------

    precision_pass = (
        precision_entry_filter(
            signal=signal,
            trend=trend,
            structure=structure,
            momentum=momentum,
            atr_value=atr_value,
            close=close,
            ema_fast=ema_fast_value,
            ema_slow=ema_slow_value,
            rsi=rsi,
            adx=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            ema_slope=ema_slope,
            candle_quality=candle_quality,
            breakout_quality=breakout_quality
        )
    )

    if (
        signal != "HOLD"
        and not precision_pass
    ):
        signal = "HOLD"

    # --------------------------------------------------------
    # PRECISION SCORE
    # --------------------------------------------------------

    precision_score = (
        calculate_precision_score(
            signal=signal,
            trend=trend,
            structure=structure,
            momentum=momentum,
            atr_value=atr_value,
            close=close,
            ema_fast=ema_fast_value,
            ema_slow=ema_slow_value,
            rsi=rsi,
            adx=adx,
            plus_di=plus_di,
            minus_di=minus_di,
            ema_slope=ema_slope,
            candle_quality=candle_quality,
            breakout_quality=breakout_quality,
            mtf_confirmation=mtf_confirmation
        )
    )

    # --------------------------------------------------------
    # FINAL PRECISION PASS
    # --------------------------------------------------------

    if (
        signal != "HOLD"
        and precision_score < 80
    ):
        signal = "HOLD"
        precision_pass = False

    elif signal == "HOLD":
        precision_pass = False

    precision_grade = (
        get_precision_grade(
            precision_score
        )
    )

    precision_decision = (
        get_precision_decision(
            signal=signal,
            score=precision_score,
            precision_pass=precision_pass
        )
    )

    # --------------------------------------------------------
    # RETURN
    # --------------------------------------------------------

    return {

        "signal": signal,

        "precision_pass": (
            precision_pass
        ),

        "precision_score": (
            precision_score
        ),

        "precision_grade": (
            precision_grade
        ),

        "precision_decision": (
            precision_decision
        ),

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

        "atr": atr_value,

        "rsi": round(
            rsi,
            2
        ),

        "adx": round(
            adx,
            2
        ),

        "plus_di": round(
            plus_di,
            2
        ),

        "minus_di": round(
            minus_di,
            2
        ),

        "ema_slope": round(
            ema_slope,
            5
        ),

        "candle_quality": round(
            candle_quality,
            4
        ),

        "breakout_quality": (
            breakout_quality
        ),

        "buy_score": buy_score,

        "sell_score": sell_score,

        "score": max(
            buy_score,
            sell_score
        )
    }