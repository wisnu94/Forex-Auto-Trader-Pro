from pathlib import Path

strategy = r'''import pandas as pd

import numpy as np

from mtf import mtf_allows_signal

# ============================================================

# FOREX AUTO TRADER PRO

# STRATEGY ENGINE V5

#

# Core:

# H1 + M15 = permission

# M1        = supplementary confirmation

#

# SELL QUALITY GATE:

# The previous real-data test showed 7 SELL / 0 WIN.

# Weak SELL setups are rejected when ADX and momentum do not

# support a real bearish impulse.

# ============================================================

def calculate_ema(series, period):

    return series.ewm(

        span=period,

        adjust=False

    ).mean()

def calculate_atr(df, period=14):

    high_low = df["high"] - df["low"]

    high_close = (df["high"] - df["close"].shift(1)).abs()

    low_close = (df["low"] - df["close"].shift(1)).abs()

    true_range = pd.concat(

        [high_low, high_close, low_close],

        axis=1

    ).max(axis=1)

    return true_range.rolling(period).mean()

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

        [tr1, tr2, tr3],

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

# TREND

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

    return float(

        ((current - previous) / previous) * 100

    )

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

    body_ratio = abs(close - open_price) / candle_range

    if body_ratio < 0.35:

        return False

    if signal == "BUY":

        if close <= open_price:

            return False

        close_position = (

            (close - low) / candle_range

        )

        return close_position >= 0.60

    if signal == "SELL":

        if close >= open_price:

            return False

        close_position = (

            (high - close) / candle_range

        )

        return close_position >= 0.60

    return False

# ============================================================

# RSI

# ============================================================

def rsi_confirmation(signal, rsi):

    if rsi is None or pd.isna(rsi):

        return False

    if signal == "BUY":

        return 52 <= rsi <= 70

    if signal == "SELL":

        return 30 <= rsi <= 48

    return False

# ============================================================

# ADX

# ============================================================

def adx_confirmation(signal, adx):

    if adx is None or pd.isna(adx):

        return False

    return adx >= 18

# ============================================================

# VOLATILITY

# ============================================================

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

# ============================================================

# EMA DISTANCE

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

    distance = abs(close - ema_fast)

    if distance > atr * 1.50:

        return False

    if signal == "BUY":

        return close > ema_fast

    if signal == "SELL":

        return close < ema_fast

    return False

# ============================================================

# SELL QUALITY GATE

#

# Important:

# Previous real-data test:

# SELL = 7

# WIN  = 0

#

# Bad SELL examples had:

# ADX mostly ~19-20

# Momentum mostly around -0.045 to -0.057

#

# A bearish trend alone is not enough.

# We require evidence of bearish impulse.

# ============================================================

def sell_quality_gate(

    momentum,

    adx,

    rsi,

    candle_confirmed

):

    if momentum is None or pd.isna(momentum):

        return False

    if adx is None or pd.isna(adx):

        return False

    if rsi is None or pd.isna(rsi):

        return False

    # Bearish momentum must have meaningful strength.

    if momentum > -0.08:

        return False

    # Avoid weak bearish trends.

    if adx < 22:

        return False

    # Avoid entering an already deeply oversold market.

    if rsi < 34:

        return False

    # Require bearish candle confirmation.

    if not candle_confirmed:

        return False

    return True

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

    atr_average,

    candle_confirmed

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

        atr_average

    ):

        return False

    if not ema_distance_confirmation(

        signal,

        close,

        ema_fast,

        atr_value

    ):

        return False

    if not candle_confirmed:

        return False

    # --------------------------------------------------------

    # SELL-SPECIFIC PROTECTION

    # --------------------------------------------------------

    if signal == "SELL":

        if not sell_quality_gate(

            momentum,

            adx,

            rsi,

            candle_confirmed

        ):

            return False

    return True

# ============================================================

# PRECISION SCORE

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

    score = 0.0

    # --------------------------------------------------------

    # MTF — 20

    # --------------------------------------------------------

    if mtf_confirmation is not None:

        status = mtf_confirmation.get(

            "status",

            "UNKNOWN"

        )

        if signal == "BUY":

            if status == "STRONG_BUY":

                score += 20

            elif status == "BUY_BIAS":

                score += 12

        elif signal == "SELL":

            if status == "STRONG_SELL":

                score += 20

            elif status == "SELL_BIAS":

                score += 12

    # --------------------------------------------------------

    # TREND — 15

    # --------------------------------------------------------

    if ema_slow > 0:

        if signal == "BUY" and trend == "BULLISH":

            spread = (

                ema_fast - ema_slow

            ) / ema_slow

            if spread >= 0.003:

                score += 15

            elif spread >= 0.0015:

                score += 12

            elif spread > 0:

                score += 9

        elif signal == "SELL" and trend == "BEARISH":

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

        elif momentum_strength >= 0.08:

            score += 6

        else:

            score += 3

    elif signal == "SELL" and momentum < 0:

        # SELL requires stronger momentum than BUY.

        if momentum <= -0.30:

            score += 10

        elif momentum <= -0.15:

            score += 8

        elif momentum <= -0.08:

            score += 6

        else:

            score += 0

    # --------------------------------------------------------

    # VOLATILITY — 5

    # --------------------------------------------------------

    if (

        atr_value is not None

        and atr_average is not None

        and not pd.isna(atr_value)

        and not pd.isna(atr_average)

        and atr_average > 0

    ):

        ratio = atr_value / atr_average

        if 0.90 <= ratio <= 1.60:

            score += 5

        elif 0.70 <= ratio < 0.90:

            score += 3

        elif 1.60 < ratio <= 2.50:

            score += 2

    # --------------------------------------------------------

    # CANDLE — 5

    # --------------------------------------------------------

    if candle_confirmed:

        score += 5

    # --------------------------------------------------------

    # SELL PENALTY / QUALITY

    #

    # Prevent weak SELL setups from receiving an inflated

    # score just because MTF + structure are bearish.

    # --------------------------------------------------------

    if signal == "SELL":

        if adx < 22:

            score -= 8

        if momentum > -0.08:

            score -= 8

        if (

            rsi is not None

            and not pd.isna(rsi)

            and rsi < 34

        ):

            score -= 5

    return int(

        max(

            0,

            min(

                100,

                round(score)

            )

        )

    )

# ============================================================

# PRECISION GRADE

# ============================================================

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

# ============================================================

# GENERATE SIGNAL

# ============================================================

def generate_signal(

    df,

    ema_fast=20,

    ema_slow=50,

    atr_period=14,

    mtf_confirmation=None

):

    neutral = {

        "signal": "HOLD",

        "precision_score": 0,

        "precision_grade": "D",

        "precision_pass": False,

        "atr": None,

        "atr_average": None,

        "rsi": None,

        "adx": None,

        "momentum": 0.0,

        "trend": "NEUTRAL",

        "structure": "UNKNOWN",

        "candle_confirmed": False,

        "mtf_allowed": False,

        "reason": "INSUFFICIENT_DATA",

    }

    if df is None or len(df) < 80:

        return neutral

    data = df.copy().reset_index(drop=True)

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

            errors="coerce"

        )

    data = data.dropna(

        subset=required

    ).reset_index(drop=True)

    if len(data) < 80:

        return neutral

    close = float(data["close"].iloc[-1])

    ema_fast_series = calculate_ema(

        data["close"],

        ema_fast

    )

    ema_slow_series = calculate_ema(

        data["close"],

        ema_slow

    )

    ema_fast_value = float(

        ema_fast_series.iloc[-1]

    )

    ema_slow_value = float(

        ema_slow_series.iloc[-1]

    )

    atr_series = calculate_atr(

        data,

        atr_period

    )

    atr_value = atr_series.iloc[-1]

    atr_average_series = (

        atr_series.rolling(50).mean()

    )

    atr_average = (

        atr_average_series.iloc[-1]

    )

    rsi_series = calculate_rsi(

        data["close"],

        14

    )

    rsi = float(

        rsi_series.iloc[-1]

    )

    adx_series = calculate_adx(

        data,

        14

    )

    adx = float(

        adx_series.iloc[-1]

    )

    momentum = calculate_momentum(

        data

    )

    trend = detect_trend(

        data,

        ema_fast,

        ema_slow

    )

    structure = detect_structure(

        data

    )

    # --------------------------------------------------------

    # BASE SIGNAL

    # --------------------------------------------------------

    if trend == "BULLISH":

        signal = "BUY"

    elif trend == "BEARISH":

        signal = "SELL"

    else:

        signal = "HOLD"

    candle_confirmed = candle_confirmation(

        data,

        signal

    )

    # --------------------------------------------------------

    # MTF PERMISSION

    # --------------------------------------------------------

    mtf_allowed = False

    if mtf_confirmation is not None:

        try:

            mtf_allowed = mtf_allows_signal(

                signal,

                mtf_confirmation

            )

        except Exception:

            mtf_allowed = False

    if not mtf_allowed:

        return {

            "signal": "HOLD",

            "precision_score": 0,

            "precision_grade": "D",

            "precision_pass": False,

            "atr": (

                float(atr_value)

                if not pd.isna(atr_value)

                else None

            ),

            "atr_average": (

                float(atr_average)

                if not pd.isna(atr_average)

                else None

            ),

            "rsi": rsi,

            "adx": adx,

            "momentum": momentum,

            "trend": trend,

            "structure": structure,

            "candle_confirmed": candle_confirmed,

            "mtf_allowed": False,

            "reason": "MTF_BLOCK",

        }

    # --------------------------------------------------------

    # PRECISION FILTER

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

        rsi=rsi,

        adx=adx,

        atr_average=atr_average,

        candle_confirmed=candle_confirmed

    )

    # --------------------------------------------------------

    # SCORE

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

        rsi=rsi,

        adx=adx,

        atr_average=atr_average,

        candle_confirmed=candle_confirmed,

        mtf_confirmation=mtf_confirmation

    )

    # --------------------------------------------------------

    # SIDE-SPECIFIC SCORE FLOOR

    #

    # BUY remains >=70.

    # SELL requires >=80 because the previous real-data

    # sample showed systematic SELL weakness.

    # --------------------------------------------------------

    score_floor = (

        80

        if signal == "SELL"

        else 70

    )

    final_pass = (

        precision_pass

        and precision_score >= score_floor

    )

    if not final_pass:

        return {

            "signal": "HOLD",

            "precision_score": precision_score,

            "precision_grade":

                precision_grade(

                    precision_score

                ),

            "precision_pass": False,

            "atr": (

                float(atr_value)

                if not pd.isna(atr_value)

                else None

            ),

            "atr_average": (

                float(atr_average)

                if not pd.isna(atr_average)

                else None

            ),

            "rsi": rsi,

            "adx": adx,

            "momentum": momentum,

            "trend": trend,

            "structure": structure,

            "candle_confirmed": candle_confirmed,

            "mtf_allowed": True,

            "reason": "PRECISION_FILTER",

        }

    return {

        "signal": signal,

        "precision_score":

            precision_score,

        "precision_grade":

            precision_grade(

                precision_score

            ),

        "precision_pass":

            True,

        "atr": (

            float(atr_value)

            if not pd.isna(atr_value)

            else None

        ),

        "atr_average": (

            float(atr_average)

            if not pd.isna(atr_average)

            else None

        ),

        "rsi": rsi,

        "adx": adx,

        "momentum": momentum,

        "trend": trend,

        "structure": structure,

        "candle_confirmed":

            candle_confirmed,

        "mtf_allowed":

            True,

        "reason":

            "PRECISION_PASS",

    }

'''

path = Path("/mnt/data/strategy_v5.py")

path.write_text(strategy, encoding="utf-8")

print(f"Created {path} ({len(strategy.splitlines())} lines)")