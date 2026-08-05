import pandas as pd
import numpy as np

# ============================================================
# FOREX AUTO TRADER PRO
# STRATEGY ENGINE V5.1
#
# IMPORTANT:
# - This file is a normal Python module.
# - It MUST NOT write files during import.
# - H1 + M15 are the required MTF permission.
# - M1 is supplementary and is handled by backtest.py.
# - SELL quality is stricter because the last real-data test
#   produced 7 SELL / 0 WIN.
# ============================================================


def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calculate_atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()

    true_range = pd.concat(
        [high_low, high_close, low_close],
        axis=1,
    ).max(axis=1)

    return true_range.rolling(period).mean()


def calculate_rsi(series, period=14):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return rsi.fillna(50)


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
            0.0,
        ),
        index=df.index,
    )

    minus_dm = pd.Series(
        np.where(
            (down_move > up_move) & (down_move > 0),
            down_move,
            0.0,
        ),
        index=df.index,
    )

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1,
    ).max(axis=1)

    atr = true_range.ewm(
        alpha=1 / period,
        adjust=False,
    ).mean()

    plus_di = (
        100
        * plus_dm.ewm(
            alpha=1 / period,
            adjust=False,
        ).mean()
        / atr.replace(0, np.nan)
    )

    minus_di = (
        100
        * minus_dm.ewm(
            alpha=1 / period,
            adjust=False,
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
        adjust=False,
    ).mean()

    return adx.fillna(0)


def detect_structure(df):
    if len(df) < 10:
        return "UNKNOWN"

    recent_high = df["high"].iloc[-5:-1].max()
    recent_low = df["low"].iloc[-5:-1].min()
    last_close = float(df["close"].iloc[-1])

    if last_close > recent_high:
        return "BULLISH_BREAK"

    if last_close < recent_low:
        return "BEARISH_BREAK"

    return "RANGE"


def detect_trend(df, fast=20, slow=50):
    if len(df) < slow:
        return "NEUTRAL"

    fast_ema = calculate_ema(
        df["close"],
        fast,
    ).iloc[-1]

    slow_ema = calculate_ema(
        df["close"],
        slow,
    ).iloc[-1]

    if fast_ema > slow_ema:
        return "BULLISH"

    if fast_ema < slow_ema:
        return "BEARISH"

    return "NEUTRAL"


def calculate_momentum(df):
    if len(df) < 5:
        return 0.0

    current = float(df["close"].iloc[-1])
    previous = float(df["close"].iloc[-5])

    if previous == 0:
        return 0.0

    return float(
        ((current - previous) / previous) * 100
    )


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

    body_ratio = (
        abs(close - open_price)
        / candle_range
    )

    if body_ratio < 0.35:
        return False

    if signal == "BUY":
        if close <= open_price:
            return False

        close_position = (
            (close - low)
            / candle_range
        )

        return close_position >= 0.60

    if signal == "SELL":
        if close >= open_price:
            return False

        close_position = (
            (high - close)
            / candle_range
        )

        return close_position >= 0.60

    return False


def rsi_confirmation(signal, rsi):
    if rsi is None or pd.isna(rsi):
        return False

    if signal == "BUY":
        return 52 <= rsi <= 70

    if signal == "SELL":
        return 30 <= rsi <= 48

    return False


def adx_confirmation(signal, adx):
    if adx is None or pd.isna(adx):
        return False

    # Signal-specific quality is handled below.
    # This base filter keeps the strategy compatible
    # with the previous V5 architecture.
    return adx >= 18


def volatility_confirmation(atr, atr_average):
    if (
        atr is None
        or atr_average is None
        or pd.isna(atr)
        or pd.isna(atr_average)
    ):
        return False

    if atr <= 0 or atr_average <= 0:
        return False

    if atr < atr_average * 0.70:
        return False

    if atr > atr_average * 2.50:
        return False

    return True


def ema_distance_confirmation(
    signal,
    close,
    ema_fast,
    atr,
):
    if (
        atr is None
        or pd.isna(atr)
        or atr <= 0
    ):
        return False

    distance = abs(close - ema_fast)

    if distance > atr * 1.50:
        return False

    if signal == "BUY":
        return close > ema_fast

    if signal == "SELL":
        return close < ema_fast

    return False


def sell_quality_gate(
    momentum,
    adx,
    rsi,
    candle_confirmed,
):
    """
    SELL gate based on the real-data diagnostic:
    previous run = 7 SELL / 0 WIN.

    Weak bearish conditions are rejected instead of
    forcing more trades.
    """
    if momentum is None or pd.isna(momentum):
        return False

    if adx is None or pd.isna(adx):
        return False

    if rsi is None or pd.isna(rsi):
        return False

    # Stronger bearish impulse than the previous
    # -0.045 .. -0.057 weak SELL cluster.
    if momentum > -0.08:
        return False

    # ADX below 22 was mostly associated with weak
    # SELL attempts in the previous diagnostic.
    if adx < 22:
        return False

    # Do not short an already deeply oversold market.
    if rsi < 34:
        return False

    if not candle_confirmed:
        return False

    return True


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
    candle_confirmed,
):
    if signal == "HOLD":
        return False

    if signal == "BUY":
        if trend != "BULLISH":
            return False

        if ema_fast <= ema_slow:
            return False

        if structure != "BULLISH_BREAK":
            return False

        if momentum <= 0:
            return False

    elif signal == "SELL":
        if trend != "BEARISH":
            return False

        if ema_fast >= ema_slow:
            return False

        if structure != "BEARISH_BREAK":
            return False

        if momentum >= 0:
            return False

    else:
        return False

    if (
        atr_value is None
        or pd.isna(atr_value)
        or atr_value <= 0
    ):
        return False

    if not rsi_confirmation(signal, rsi):
        return False

    if not adx_confirmation(signal, adx):
        return False

    if not volatility_confirmation(
        atr_value,
        atr_average,
    ):
        return False

    if not ema_distance_confirmation(
        signal,
        close,
        ema_fast,
        atr_value,
    ):
        return False

    if not candle_confirmed:
        return False

    if signal == "SELL":
        if not sell_quality_gate(
            momentum,
            adx,
            rsi,
            candle_confirmed,
        ):
            return False

    return True


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
    mtf_confirmation=None,
):
    if signal == "HOLD":
        return 0

    score = 0.0

    # --------------------------------------------------------
    # MTF — 20
    # --------------------------------------------------------
    if mtf_confirmation is not None:
        status = mtf_confirmation.get(
            "status",
            "UNKNOWN",
        )

        if signal == "BUY":
            if status == "STRONG_BUY":
                score += 20
            elif status in (
                "BUY_BIAS",
                "BUY_CONFIRMED_H1_M15",
                "BUY_H1_M15",
            ):
                score += 16

        elif signal == "SELL":
            if status == "STRONG_SELL":
                score += 20
            elif status in (
                "SELL_BIAS",
                "SELL_CONFIRMED_H1_M15",
                "SELL_H1_M15",
            ):
                score += 16

    # --------------------------------------------------------
    # TREND — 15
    # --------------------------------------------------------
    if ema_slow > 0:
        if (
            signal == "BUY"
            and trend == "BULLISH"
        ):
            spread = (
                ema_fast - ema_slow
            ) / ema_slow

            if spread >= 0.003:
                score += 15
            elif spread >= 0.0015:
                score += 12
            elif spread > 0:
                score += 9

        elif (
            signal == "SELL"
            and trend == "BEARISH"
        ):
            spread = (
                ema_slow - ema_fast
            ) / ema_slow

            if spread >= 0.003:
                score += 15
            elif spread >= 0.0015:
                score += 12
            elif spread > 0:
                score += 9

    # --------------------------------------------------------
    # STRUCTURE — 15
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
    # RSI — 10
    # --------------------------------------------------------
    if rsi is not None and not pd.isna(rsi):
        if signal == "BUY":
            if 55 <= rsi <= 65:
                score += 10
            elif 52 <= rsi < 55:
                score += 8
            elif 65 < rsi <= 70:
                score += 6

        elif signal == "SELL":
            if 38 <= rsi <= 45:
                score += 10
            elif 45 < rsi <= 48:
                score += 8
            elif 34 <= rsi < 38:
                score += 6

    # --------------------------------------------------------
    # ADX — 10
    # --------------------------------------------------------
    if adx is not None and not pd.isna(adx):
        if adx >= 30:
            score += 10
        elif adx >= 25:
            score += 8
        elif adx >= 22:
            score += 6
        elif adx >= 18:
            score += 4

    # --------------------------------------------------------
    # MOMENTUM — 10
    # --------------------------------------------------------
    momentum_strength = abs(
        float(momentum)
    )

    if signal == "BUY" and momentum > 0:
        if momentum_strength >= 0.30:
            score += 10
        elif momentum_strength >= 0.15:
            score += 8
        elif momentum_strength >= 0.05:
            score += 6
        else:
            score += 3

    elif signal == "SELL" and momentum < 0:
        if momentum_strength >= 0.30:
            score += 10
        elif momentum_strength >= 0.15:
            score += 8
        elif momentum_strength >= 0.08:
            score += 6
        else:
            score += 3

    # --------------------------------------------------------
    # VOLATILITY — 5
    # --------------------------------------------------------
    if volatility_confirmation(
        atr_value,
        atr_average,
    ):
        score += 5

    # --------------------------------------------------------
    # CANDLE — 5
    # --------------------------------------------------------
    if candle_confirmed:
        score += 5

    return int(
        max(0, min(100, round(score)))
    )


def precision_grade(score):
    if score >= 90:
        return "A+"

    if score >= 80:
        return "A"

    if score >= 70:
        return "B"

    if score >= 60:
        return "C"

    return "D"


def _extract_mtf_permission(
    signal,
    mtf_confirmation,
):
    """
    H1 + M15 are hard permission.
    M1 remains supplementary.
    """
    if not mtf_confirmation:
        return False

    trends = mtf_confirmation.get(
        "trends",
        {},
    )

    h1 = trends.get(
        "H1",
        "HOLD",
    )

    m15 = trends.get(
        "M15",
        "HOLD",
    )

    if signal == "BUY":
        return (
            h1 == "BUY"
            and m15 == "BUY"
        )

    if signal == "SELL":
        return (
            h1 == "SELL"
            and m15 == "SELL"
        )

    return False


def generate_signal(
    df,
    ema_fast=20,
    ema_slow=50,
    atr_period=14,
    mtf_confirmation=None,
):
    """
    Main strategy API consumed by backtest.py.

    Returns all diagnostic fields expected by the
    existing V5 backtest engine.
    """
    neutral = {
        "signal": "HOLD",
        "score": 0,
        "precision_score": 0,
        "precision_grade": "D",
        "precision_pass": False,
        "trend": "NEUTRAL",
        "structure": "UNKNOWN",
        "momentum": 0.0,
        "atr": None,
        "rsi": 50.0,
        "adx": 0.0,
        "atr_average": None,
        "ema_fast": None,
        "ema_slow": None,
        "candle_confirmed": False,
        "mtf_score": 0,
        "mtf_status": "NEUTRAL",
    }

    if df is None:
        return neutral

    if len(df) < max(
        ema_slow + 10,
        atr_period + 10,
        60,
    ):
        return neutral

    data = (
        df.copy()
        .reset_index(drop=True)
    )

    required = [
        "open",
        "high",
        "low",
        "close",
    ]

    if any(
        column not in data.columns
        for column in required
    ):
        return neutral

    for column in required:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    data = data.dropna(
        subset=required
    ).reset_index(drop=True)

    if len(data) < 60:
        return neutral

    close = float(
        data["close"].iloc[-1]
    )

    ema_fast_series = calculate_ema(
        data["close"],
        ema_fast,
    )

    ema_slow_series = calculate_ema(
        data["close"],
        ema_slow,
    )

    ema_fast_value = float(
        ema_fast_series.iloc[-1]
    )

    ema_slow_value = float(
        ema_slow_series.iloc[-1]
    )

    atr_series = calculate_atr(
        data,
        atr_period,
    )

    atr_value = atr_series.iloc[-1]

    atr_average_series = (
        atr_series.rolling(20).mean()
    )

    atr_average = (
        atr_average_series.iloc[-1]
    )

    rsi = float(
        calculate_rsi(
            data["close"]
        ).iloc[-1]
    )

    adx = float(
        calculate_adx(
            data,
            period=14,
        ).iloc[-1]
    )

    momentum = calculate_momentum(
        data
    )

    trend = detect_trend(
        data,
        fast=ema_fast,
        slow=ema_slow,
    )

    structure = detect_structure(
        data
    )

    # Candidate direction comes from the
    # current trend + structure + momentum.
    if (
        trend == "BULLISH"
        and structure == "BULLISH_BREAK"
        and momentum > 0
    ):
        signal = "BUY"

    elif (
        trend == "BEARISH"
        and structure == "BEARISH_BREAK"
        and momentum < 0
    ):
        signal = "SELL"

    else:
        signal = "HOLD"

    candle_confirmed = (
        candle_confirmation(
            data,
            signal,
        )
        if signal != "HOLD"
        else False
    )

    if (
        atr_value is None
        or pd.isna(atr_value)
    ):
        atr_float = None
    else:
        atr_float = float(atr_value)

    if (
        atr_average is None
        or pd.isna(atr_average)
    ):
        atr_average_float = None
    else:
        atr_average_float = float(
            atr_average
        )

    mtf_score = int(
        mtf_confirmation.get(
            "score",
            0,
        )
        if mtf_confirmation
        else 0
    )

    mtf_status = (
        mtf_confirmation.get(
            "status",
            "NEUTRAL",
        )
        if mtf_confirmation
        else "NEUTRAL"
    )

    # H1 + M15 are hard permission.
    mtf_allowed = _extract_mtf_permission(
        signal,
        mtf_confirmation,
    )

    # A real MTF confirmation is required for
    # both directions in the production backtest.
    if signal != "HOLD" and not mtf_allowed:
        precision_score = 0
        precision_pass = False

    else:
        filter_pass = precision_entry_filter(
            signal=signal,
            trend=trend,
            structure=structure,
            momentum=momentum,
            atr_value=atr_float,
            close=close,
            ema_fast=ema_fast_value,
            ema_slow=ema_slow_value,
            rsi=rsi,
            adx=adx,
            atr_average=atr_average_float,
            candle_confirmed=candle_confirmed,
        )

        precision_score = calculate_precision_score(
            signal=signal,
            trend=trend,
            structure=structure,
            momentum=momentum,
            atr_value=atr_float,
            close=close,
            ema_fast=ema_fast_value,
            ema_slow=ema_slow_value,
            rsi=rsi,
            adx=adx,
            atr_average=atr_average_float,
            candle_confirmed=candle_confirmed,
            mtf_confirmation=mtf_confirmation,
        )

        # BUY threshold remains 70.
        # SELL has a higher threshold to prevent
        # the previous low-quality SELL cluster.
        required_score = (
            80
            if signal == "SELL"
            else 70
        )

        precision_pass = (
            filter_pass
            and precision_score >= required_score
        )

    grade = precision_grade(
        precision_score
    )

    return {
        "signal": signal,
        "score": precision_score,
        "precision_score": precision_score,
        "precision_grade": grade,
        "precision_pass": precision_pass,
        "trend": trend,
        "structure": structure,
        "momentum": float(momentum),
        "atr": atr_float,
        "rsi": float(rsi),
        "adx": float(adx),
        "atr_average": atr_average_float,
        "ema_fast": ema_fast_value,
        "ema_slow": ema_slow_value,
        "candle_confirmed": bool(
            candle_confirmed
        ),
        "mtf_score": mtf_score,
        "mtf_status": mtf_status,
    }


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    print("strategy.py import/test OK")
