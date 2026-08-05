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
    candle_open=None,
    candle_high=None,
    candle_low=None,
    overextension_atr=1.50,
):

    # --------------------------------------------------------
    # BASIC VALIDATION
    # --------------------------------------------------------

    if signal not in {
        "BUY",
        "SELL"
    }:
        return False

    if atr_value is None:
        return False

    if not np.isfinite(
        float(atr_value)
    ):
        return False

    if float(atr_value) <= 0:
        return False

    # --------------------------------------------------------
    # EMA VALIDATION
    # --------------------------------------------------------

    if not np.isfinite(
        float(ema_fast)
    ):
        return False

    if not np.isfinite(
        float(ema_slow)
    ):
        return False

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if signal == "BUY":

        # Trend wajib bullish
        if trend != "BULLISH":
            return False

        # Struktur wajib breakout bullish
        if structure != "BULLISH_BREAK":
            return False

        # Momentum wajib positif
        if momentum <= 0:
            return False

        # Harga wajib di atas EMA fast
        if close <= ema_fast:
            return False

        # EMA fast wajib di atas EMA slow
        if ema_fast <= ema_slow:
            return False

        # ----------------------------------------------------
        # OVEREXTENSION FILTER
        # ----------------------------------------------------

        distance_from_ema = (
            close - ema_fast
        )

        if distance_from_ema > (
            atr_value
            * overextension_atr
        ):
            return False

        # ----------------------------------------------------
        # CANDLE QUALITY
        # ----------------------------------------------------

        if (
            candle_open is not None
            and candle_high is not None
            and candle_low is not None
        ):

            candle_range = (
                candle_high
                - candle_low
            )

            if candle_range > 0:

                candle_body = abs(
                    close
                    - candle_open
                )

                body_ratio = (
                    candle_body
                    / candle_range
                )

                # Breakout candle harus
                # memiliki body yang cukup kuat
                if body_ratio < 0.35:
                    return False

        return True

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    if signal == "SELL":

        # Trend wajib bearish
        if trend != "BEARISH":
            return False

        # Struktur wajib breakout bearish
        if structure != "BEARISH_BREAK":
            return False

        # Momentum wajib negatif
        if momentum >= 0:
            return False

        # Harga wajib di bawah EMA fast
        if close >= ema_fast:
            return False

        # EMA fast wajib di bawah EMA slow
        if ema_fast >= ema_slow:
            return False

        # ----------------------------------------------------
        # OVEREXTENSION FILTER
        # ----------------------------------------------------

        distance_from_ema = (
            ema_fast - close
        )

        if distance_from_ema > (
            atr_value
            * overextension_atr
        ):
            return False

        # ----------------------------------------------------
        # CANDLE QUALITY
        # ----------------------------------------------------

        if (
            candle_open is not None
            and candle_high is not None
            and candle_low is not None
        ):

            candle_range = (
                candle_high
                - candle_low
            )

            if candle_range > 0:

                candle_body = abs(
                    close
                    - candle_open
                )

                body_ratio = (
                    candle_body
                    / candle_range
                )

                if body_ratio < 0.35:
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
):

    score = 0

    # --------------------------------------------------------
    # MTF — 30 POINTS
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
            score += 30

        elif (
            signal == "SELL"
            and mtf_status == "STRONG_SELL"
        ):
            score += 30

    # --------------------------------------------------------
    # TREND — 20 POINTS
    # --------------------------------------------------------

    if (
        signal == "BUY"
        and trend == "BULLISH"
    ):
        score += 20

    elif (
        signal == "SELL"
        and trend == "BEARISH"
    ):
        score += 20

    # --------------------------------------------------------
    # STRUCTURE — 20 POINTS
    # --------------------------------------------------------

    if (
        signal == "BUY"
        and structure == "BULLISH_BREAK"
    ):
        score += 20

    elif (
        signal == "SELL"
        and structure == "BEARISH_BREAK"
    ):
        score += 20

    # --------------------------------------------------------
    # MOMENTUM — 15 POINTS
    # --------------------------------------------------------

    if (
        signal == "BUY"
        and momentum > 0
    ):
        score += 15

    elif (
        signal == "SELL"
        and momentum < 0
    ):
        score += 15

    # --------------------------------------------------------
    # PRICE / EMA — 10 POINTS
    # --------------------------------------------------------

    if (
        signal == "BUY"
        and close > ema_fast
    ):
        score += 10

    elif (
        signal == "SELL"
        and close < ema_fast
    ):
        score += 10

    # --------------------------------------------------------
    # ATR — 5 POINTS
    # --------------------------------------------------------

    if (
        atr_value is not None
        and np.isfinite(
            float(atr_value)
        )
        and atr_value > 0
    ):
        score += 5

    return min(
        score,
        100
    )


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
    precision_pass,
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
    mtf_confirmation=None,
):

    minimum_bars = max(
        ema_slow + 10,
        atr_period + 10
    )

    if len(df) < minimum_bars:

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
            "score": 0,
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

    structure = detect_structure(
        data
    )

    momentum = calculate_momentum(
        data
    )

    atr_value = last["atr"]

    # ========================================================
    # BASE SIGNAL SCORE
    # ========================================================

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

    # ========================================================
    # BASE SIGNAL
    # ========================================================

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

    # ========================================================
    # MTF FILTER
    # ========================================================

    if (
        mtf_confirmation is not None
        and signal != "HOLD"
    ):

        if not mtf_allows_signal(
            signal,
            mtf_confirmation
        ):
            signal = "HOLD"

    # ========================================================
    # PRECISION FILTER V3
    # ========================================================

    atr_numeric = (
        float(atr_value)
        if pd.notna(atr_value)
        else None
    )

    precision_pass = False

    if signal != "HOLD":

        precision_pass = (
            precision_entry_filter(
                signal=signal,
                trend=trend,
                structure=structure,
                momentum=momentum,
                atr_value=atr_numeric,
                close=float(
                    last["close"]
                ),
                ema_fast=float(
                    last["ema_fast"]
                ),
                ema_slow=float(
                    last["ema_slow"]
                ),
                candle_open=float(
                    last["open"]
                )
                if "open" in last
                else None,
                candle_high=float(
                    last["high"]
                )
                if "high" in last
                else None,
                candle_low=float(
                    last["low"]
                )
                if "low" in last
                else None,
                overextension_atr=1.50,
            )
        )

    if (
        signal != "HOLD"
        and not precision_pass
    ):
        signal = "HOLD"

    # ========================================================
    # PRECISION SCORE
    # ========================================================

    precision_score = (
        calculate_precision_score(
            signal=signal,
            trend=trend,
            structure=structure,
            momentum=momentum,
            atr_value=atr_numeric,
            close=float(
                last["close"]
            ),
            ema_fast=float(
                last["ema_fast"]
            ),
            mtf_confirmation=(
                mtf_confirmation
            ),
        )
    )

    # ========================================================
    # RETURN
    # ========================================================

    return {

        "signal": signal,

        "precision_pass": (
            precision_pass
        ),

        "precision_score": (
            precision_score
        ),

        "precision_grade": (
            get_precision_grade(
                precision_score
            )
        ),

        "precision_decision": (
            get_precision_decision(
                signal=signal,
                score=precision_score,
                precision_pass=(
                    precision_pass
                ),
            )
        ),

        "mtf_status": (
            mtf_confirmation[
                "status"
            ]
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
            atr_numeric
        ),

        "buy_score": (
            buy_score
        ),

        "sell_score": (
            sell_score
        ),

        "score": max(
            buy_score,
            sell_score
        ),
    }