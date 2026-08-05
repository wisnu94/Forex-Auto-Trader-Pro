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

    return rsi.fillna(50)


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

    true_range = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(axis=1)

    atr = true_range.ewm(
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

    denominator = (
        plus_di + minus_di
    ).replace(0, np.nan)

    dx = (
        100
        * (plus_di - minus_di).abs()
        / denominator
    )

    adx = dx.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    return adx.fillna(0)


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
# CANDLE CONFIRMATION
# ============================================================

def candle_confirmation(df, signal):

    if len(df) < 2:
        return False

    candle = df.iloc[-1]

    open_price = float(candle["open"])
    high = float(candle["high"])
    low = float(candle["low"])
    close = float(candle["close"])

    candle_range = high - low

    if candle_range <= 0:
        return False

    body = abs(close - open_price)

    body_ratio = body / candle_range

    # Hindari candle yang terlalu kecil / doji
    if body_ratio < 0.35:
        return False

    if signal == "BUY":

        # Candle bullish
        if close <= open_price:
            return False

        # Close harus berada di bagian atas candle
        close_position = (
            (close - low)
            / candle_range
        )

        if close_position < 0.60:
            return False

        return True

    if signal == "SELL":

        # Candle bearish
        if close >= open_price:
            return False

        # Close harus berada di bagian bawah candle
        close_position = (
            (high - close)
            / candle_range
        )

        if close_position < 0.60:
            return False

        return True

    return False


# ============================================================
# RSI FILTER
# ============================================================

def rsi_confirmation(
    signal,
    rsi
):

    if rsi is None or pd.isna(rsi):
        return False

    if signal == "BUY":

        # Hindari BUY ketika sudah terlalu overbought
        return (
            rsi >= 52
            and rsi <= 70
        )

    if signal == "SELL":

        # Hindari SELL ketika sudah terlalu oversold
        return (
            rsi <= 48
            and rsi >= 30
        )

    return False


# ============================================================
# ADX / TREND STRENGTH
# ============================================================

def adx_confirmation(
    signal,
    adx
):

    if adx is None or pd.isna(adx):
        return False

    # Hindari market terlalu lemah
    if adx < 18:
        return False

    return True


# ============================================================
# VOLATILITY REGIME
# ============================================================

def volatility_confirmation(
    atr,
    atr_average
):

    if (
        atr is None
        or atr_average is None
        or pd.isna(atr)
        or pd.isna(atr_average)
    ):
        return False

    if atr <= 0 or atr_average <= 0:
        return False

    # Hindari kondisi volatility terlalu kecil
    if atr < atr_average * 0.70:
        return False

    # Hindari spike volatility ekstrem
    if atr > atr_average * 2.50:
        return False

    return True


# ============================================================
# EMA DISTANCE / OVEREXTENSION FILTER
# ============================================================

def ema_distance_confirmation(
    signal,
    close,
    ema_fast,
    atr
):

    if (
        atr is None
        or pd.isna(atr)
        or atr <= 0
    ):
        return False

    distance = abs(
        close - ema_fast
    )

    # Harga tidak boleh terlalu jauh dari EMA
    # untuk mencegah entry terlambat.
    max_distance = atr * 1.50

    if distance > max_distance:
        return False

    if signal == "BUY":
        return close > ema_fast

    if signal == "SELL":
        return close < ema_fast

    return False


# ============================================================
# PRECISION ENTRY FILTER V3
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
    atr_average,
    candle_confirmed
):

    if signal == "HOLD":
        return False

    # --------------------------------------------------------
    # 1. TREND
    # --------------------------------------------------------

    if signal == "BUY":

        if trend != "BULLISH":
            return False

        if ema_fast <= ema_slow:
            return False

    elif signal == "SELL":

        if trend != "BEARISH":
            return False

        if ema_fast >= ema_slow:
            return False

    # --------------------------------------------------------
    # 2. STRUCTURE
    # --------------------------------------------------------

    if signal == "BUY":

        if structure != "BULLISH_BREAK":
            return False

    elif signal == "SELL":

        if structure != "BEARISH_BREAK":
            return False

    # --------------------------------------------------------
    # 3. MOMENTUM
    # --------------------------------------------------------

    if signal == "BUY":

        if momentum <= 0:
            return False

    elif signal == "SELL":

        if momentum >= 0:
            return False

    # --------------------------------------------------------
    # 4. ATR
    # --------------------------------------------------------

    if (
        atr_value is None
        or pd.isna(atr_value)
        or atr_value <= 0
    ):
        return False

    # --------------------------------------------------------
    # 5. RSI
    # --------------------------------------------------------

    if not rsi_confirmation(
        signal,
        rsi
    ):
        return False

    # --------------------------------------------------------
    # 6. ADX
    # --------------------------------------------------------

    if not adx_confirmation(
        signal,
        adx
    ):
        return False

    # --------------------------------------------------------
    # 7. VOLATILITY
    # --------------------------------------------------------

    if not volatility_confirmation(
        atr_value,
        atr_average
    ):
        return False

    # --------------------------------------------------------
    # 8. EMA DISTANCE
    # --------------------------------------------------------

    if not ema_distance_confirmation(
        signal,
        close,
        ema_fast,
        atr_value
    ):
        return False

    # --------------------------------------------------------
    # 9. CANDLE CONFIRMATION
    # --------------------------------------------------------

    if not candle_confirmed:
        return False

    return True


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
    rsi,
    adx,
    atr_average,
    candle_confirmed,
    mtf_confirmation=None
):

    if signal == "HOLD":
        return 0

    score = 0

    # --------------------------------------------------------
    # MTF — 20 POINTS
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
            score += 20

        elif (
            signal == "SELL"
            and mtf_status == "STRONG_SELL"
        ):
            score += 20

        elif (
            signal == "BUY"
            and mtf_status == "BUY"
        ):
            score += 15

        elif (
            signal == "SELL"
            and mtf_status == "SELL"
        ):
            score += 15

    # --------------------------------------------------------
    # TREND — 15 POINTS
    # --------------------------------------------------------

    if (
        signal == "BUY"
        and trend == "BULLISH"
        and ema_fast > ema_slow
    ):
        score += 15

    elif (
        signal == "SELL"
        and trend == "BEARISH"
        and ema_fast < ema_slow
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
    # RSI — 10 POINTS
    # --------------------------------------------------------

    if rsi_confirmation(
        signal,
        rsi
    ):
        score += 10

    # --------------------------------------------------------
    # ADX — 10 POINTS
    # --------------------------------------------------------

    if adx_confirmation(
        signal,
        adx
    ):
        score += 10

    # --------------------------------------------------------
    # MOMENTUM — 10 POINTS
    # --------------------------------------------------------

    if signal == "BUY" and momentum > 0:
        score += 10

    elif signal == "SELL" and momentum < 0:
        score += 10

    # --------------------------------------------------------
    # CANDLE — 5 POINTS
    # --------------------------------------------------------

    if candle_confirmed:
        score += 5

    # --------------------------------------------------------
    # EMA LOCATION — 5 POINTS
    # --------------------------------------------------------

    if ema_distance_confirmation(
        signal,
        close,
        ema_fast,
        atr_value
    ):
        score += 5

    # --------------------------------------------------------
    # VOLATILITY — 5 POINTS
    # --------------------------------------------------------

    if volatility_confirmation(
        atr_value,
        atr_average
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
        50
    )

    if (
        df is None
        or len(df) < minimum_bars
    ):
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
            "rsi": None,
            "adx": None,
            "atr": None,
            "buy_score": 0,
            "sell_score": 0,
            "score": 0
        }

    data = df.copy().reset_index(
        drop=True
    )

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

    data["rsi"] = calculate_rsi(
        data["close"],
        14
    )

    data["adx"] = calculate_adx(
        data,
        14
    )

    data["atr_average"] = data["atr"].rolling(
        50
    ).mean()

    # --------------------------------------------------------
    # LAST VALUES
    # --------------------------------------------------------

    last = data.iloc[-1]

    close = float(
        last["close"]
    )

    ema_fast_value = float(
        last["ema_fast"]
    )

    ema_slow_value = float(
        last["ema_slow"]
    )

    atr_value = (
        float(last["atr"])
        if pd.notna(last["atr"])
        else None
    )

    rsi_value = (
        float(last["rsi"])
        if pd.notna(last["rsi"])
        else None
    )

    adx_value = (
        float(last["adx"])
        if pd.notna(last["adx"])
        else None
    )

    atr_average = (
        float(last["atr_average"])
        if pd.notna(last["atr_average"])
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
    # RAW SIGNAL SCORE
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
    if close > ema_fast_value:
        buy_score += 20

    elif close < ema_fast_value:
        sell_score += 20

    # --------------------------------------------------------
    # RAW SIGNAL
    # --------------------------------------------------------

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
    # CANDLE CONFIRMATION
    # --------------------------------------------------------

    candle_confirmed = candle_confirmation(
        data,
        signal
    )

    # --------------------------------------------------------
    # PRECISION FILTER V3
    # --------------------------------------------------------

    precision_pass = precision_entry_filter(
        signal=signal,
        trend=trend,
        structure=structure,
        momentum=momentum,
        atr_value=atr_value,
        close=close,
        ema_fast=ema_fast_value,
        ema_slow=ema_slow_value,
        rsi=rsi_value,
        adx=adx_value,
        atr_average=atr_average,
        candle_confirmed=candle_confirmed
    )

    if (
        signal != "HOLD"
        and not precision_pass
    ):
        signal = "HOLD"

    # --------------------------------------------------------
    # PRECISION SCORE
    # --------------------------------------------------------

    precision_score = calculate_precision_score(
        signal=signal,
        trend=trend,
        structure=structure,
        momentum=momentum,
        atr_value=atr_value,
        close=close,
        ema_fast=ema_fast_value,
        ema_slow=ema_slow_value,
        rsi=rsi_value,
        adx=adx_value,
        atr_average=atr_average,
        candle_confirmed=candle_confirmed,
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

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    return {
        "signal": signal,

        "precision_pass": precision_pass,

        "precision_score": precision_score,

        "precision_grade": precision_grade,

        "precision_decision": precision_decision,

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

        "rsi": (
            round(rsi_value, 2)
            if rsi_value is not None
            else None
        ),

        "adx": (
            round(adx_value, 2)
            if adx_value is not None
            else None
        ),

        "atr": atr_value,

        "atr_average": atr_average,

        "candle_confirmed": candle_confirmed,

        "buy_score": buy_score,

        "sell_score": sell_score,

        "score": max(
            buy_score,
            sell_score
        )
    }