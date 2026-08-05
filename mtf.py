import pandas as pd
import numpy as np


# ============================================================
# FOREX AUTO TRADER PRO
# MTF ENGINE V2
#
# Architecture:
# H1  = MARKET BIAS
# M15 = SETUP CONFIRMATION
# M1  = ENTRY TRIGGER
# ============================================================


# ============================================================
# EMA
# ============================================================

def calculate_ema(series, period):

    return series.ewm(
        span=period,
        adjust=False
    ).mean()


# ============================================================
# TIMEFRAME TREND
# ============================================================

def timeframe_trend(
    df,
    fast_period=20,
    slow_period=50
):

    if (
        df is None
        or len(df) < slow_period
    ):
        return "HOLD"

    data = df.copy()

    if "close" not in data.columns:
        return "HOLD"

    fast_ema = calculate_ema(
        data["close"],
        fast_period
    )

    slow_ema = calculate_ema(
        data["close"],
        slow_period
    )

    fast = fast_ema.iloc[-1]
    slow = slow_ema.iloc[-1]
    close = data["close"].iloc[-1]

    if (
        pd.isna(fast)
        or pd.isna(slow)
        or pd.isna(close)
    ):
        return "HOLD"

    # ========================================================
    # BULLISH
    # ========================================================

    if (
        fast > slow
        and close > fast
    ):
        return "BUY"

    # ========================================================
    # BEARISH
    # ========================================================

    if (
        fast < slow
        and close < fast
    ):
        return "SELL"

    return "HOLD"


# ============================================================
# MTF SCORE
# ============================================================

def calculate_mtf_score(trends):

    if not isinstance(
        trends,
        dict
    ):
        return 0

    score = 0

    # ========================================================
    # H1 — 40 POINTS
    # ========================================================

    h1 = trends.get(
        "H1",
        "HOLD"
    )

    if h1 == "BUY":
        score += 40

    elif h1 == "SELL":
        score -= 40

    # ========================================================
    # M15 — 30 POINTS
    # ========================================================

    m15 = trends.get(
        "M15",
        "HOLD"
    )

    if m15 == "BUY":
        score += 30

    elif m15 == "SELL":
        score -= 30

    # ========================================================
    # M1 — 30 POINTS
    # ========================================================

    m1 = trends.get(
        "M1",
        "HOLD"
    )

    if m1 == "BUY":
        score += 30

    elif m1 == "SELL":
        score -= 30

    return int(score)


# ============================================================
# MTF STATUS
# ============================================================

def calculate_mtf_status(trends):

    if not isinstance(
        trends,
        dict
    ):
        return "NEUTRAL"

    h1 = trends.get(
        "H1",
        "HOLD"
    )

    m15 = trends.get(
        "M15",
        "HOLD"
    )

    m1 = trends.get(
        "M1",
        "HOLD"
    )

    # ========================================================
    # STRONG BUY
    # ========================================================

    if (
        h1 == "BUY"
        and m15 == "BUY"
        and m1 == "BUY"
    ):
        return "STRONG_BUY"

    # ========================================================
    # STRONG SELL
    # ========================================================

    if (
        h1 == "SELL"
        and m15 == "SELL"
        and m1 == "SELL"
    ):
        return "STRONG_SELL"

    # ========================================================
    # H1 + M15 BUY
    # ========================================================

    if (
        h1 == "BUY"
        and m15 == "BUY"
    ):
        return "BUY_BIAS"

    # ========================================================
    # H1 + M15 SELL
    # ========================================================

    if (
        h1 == "SELL"
        and m15 == "SELL"
    ):
        return "SELL_BIAS"

    # ========================================================
    # H1 ONLY BUY
    # ========================================================

    if h1 == "BUY":
        return "BUY_BIAS"

    # ========================================================
    # H1 ONLY SELL
    # ========================================================

    if h1 == "SELL":
        return "SELL_BIAS"

    return "NEUTRAL"


# ============================================================
# MTF CONFIRMATION BUILDER
# ============================================================

def build_mtf_confirmation(
    h1_df,
    m15_df,
    m1_df
):

    trends = {
        "H1": timeframe_trend(
            h1_df,
            fast_period=20,
            slow_period=50
        ),

        "M15": timeframe_trend(
            m15_df,
            fast_period=20,
            slow_period=50
        ),

        "M1": timeframe_trend(
            m1_df,
            fast_period=20,
            slow_period=50
        ),
    }

    score = calculate_mtf_score(
        trends
    )

    status = calculate_mtf_status(
        trends
    )

    return {
        "trends": trends,

        "score": int(score),

        "status": status,

        "h1_trend": trends["H1"],

        "m15_trend": trends["M15"],

        "m1_trend": trends["M1"],
    }


# ============================================================
# MTF ENTRY PERMISSION
#
# H1 = directional filter
# M15 = setup filter
# M1 = trigger
# ============================================================

def mtf_allows_signal(
    signal,
    mtf_confirmation
):

    if (
        not isinstance(
            mtf_confirmation,
            dict
        )
    ):
        return False

    trends = mtf_confirmation.get(
        "trends",
        {}
    )

    h1 = trends.get(
        "H1",
        "HOLD"
    )

    m15 = trends.get(
        "M15",
        "HOLD"
    )

    m1 = trends.get(
        "M1",
        "HOLD"
    )

    # ========================================================
    # BUY
    #
    # H1 must be BUY
    # M15 must be BUY
    # M1 must be BUY
    # ========================================================

    if signal == "BUY":

        return (
            h1 == "BUY"
            and m15 == "BUY"
            and m1 == "BUY"
        )

    # ========================================================
    # SELL
    # ========================================================

    if signal == "SELL":

        return (
            h1 == "SELL"
            and m15 == "SELL"
            and m1 == "SELL"
        )

    return False


# ============================================================
# MTF BIAS
#
# Used when we only need H1 + M15 direction.
# ============================================================

def mtf_bias(
    h1_df,
    m15_df
):

    h1 = timeframe_trend(
        h1_df,
        fast_period=20,
        slow_period=50
    )

    m15 = timeframe_trend(
        m15_df,
        fast_period=20,
        slow_period=50
    )

    if (
        h1 == "BUY"
        and m15 == "BUY"
    ):
        return "BUY"

    if (
        h1 == "SELL"
        and m15 == "SELL"
    ):
        return "SELL"

    return "NEUTRAL"


# ============================================================
# MTF DIAGNOSTIC
# ============================================================

def mtf_diagnostic(
    mtf_confirmation
):

    if not isinstance(
        mtf_confirmation,
        dict
    ):
        return {
            "h1": "HOLD",
            "m15": "HOLD",
            "m1": "HOLD",
            "score": 0,
            "status": "NEUTRAL",
            "aligned": False,
        }

    trends = mtf_confirmation.get(
        "trends",
        {}
    )

    h1 = trends.get(
        "H1",
        "HOLD"
    )

    m15 = trends.get(
        "M15",
        "HOLD"
    )

    m1 = trends.get(
        "M1",
        "HOLD"
    )

    aligned_buy = (
        h1 == "BUY"
        and m15 == "BUY"
        and m1 == "BUY"
    )

    aligned_sell = (
        h1 == "SELL"
        and m15 == "SELL"
        and m1 == "SELL"
    )

    return {
        "h1": h1,

        "m15": m15,

        "m1": m1,

        "score": int(
            mtf_confirmation.get(
                "score",
                0
            )
        ),

        "status": mtf_confirmation.get(
            "status",
            "NEUTRAL"
        ),

        "aligned": (
            aligned_buy
            or aligned_sell
        ),
    }