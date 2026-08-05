import pandas as pd
import numpy as np


# ============================================================
# FOREX AUTO TRADER PRO
# MTF ENGINE V4
#
# PRIMARY ARCHITECTURE
#
# H1  = MARKET BIAS        -> REQUIRED
# M15 = SETUP CONFIRMATION -> REQUIRED
# M1  = ENTRY CONFIRMATION -> SUPPLEMENTARY
#
# IMPORTANT:
# M1 TIDAK BOLEH menjadi hard blocker.
#
# H1 + M15 aligned:
#     signal boleh masuk
#
# M1 aligned:
#     confidence tambahan
#
# M1 opposite / HOLD:
#     tidak otomatis membatalkan signal
#
# LEGACY:
#
# H4  = 40
# H1  = 30
# M15 = 30
# ============================================================


# ============================================================
# EMA
# ============================================================

def calculate_ema(series, period):

    if series is None:
        return pd.Series(dtype=float)

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

    close = pd.to_numeric(
        data["close"],
        errors="coerce"
    )

    fast_ema = calculate_ema(
        close,
        fast_period
    )

    slow_ema = calculate_ema(
        close,
        slow_period
    )

    fast = fast_ema.iloc[-1]
    slow = slow_ema.iloc[-1]
    last_close = close.iloc[-1]

    if (
        pd.isna(fast)
        or pd.isna(slow)
        or pd.isna(last_close)
    ):
        return "HOLD"

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if (
        fast > slow
        and last_close > fast
    ):
        return "BUY"

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    if (
        fast < slow
        and last_close < fast
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

    # ========================================================
    # PRIMARY
    #
    # H1  = 40
    # M15 = 30
    # M1  = 30
    #
    # M1 tetap dihitung sebagai confidence.
    # Tetapi M1 tidak menjadi permission blocker.
    # ========================================================

    if "M1" in trends:

        score = 0

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

        if h1 == "BUY":
            score += 40

        elif h1 == "SELL":
            score -= 40

        if m15 == "BUY":
            score += 30

        elif m15 == "SELL":
            score -= 30

        # M1 supplementary score
        if m1 == "BUY":
            score += 30

        elif m1 == "SELL":
            score -= 30

        return int(score)

    # ========================================================
    # LEGACY
    #
    # H4  = 40
    # H1  = 30
    # M15 = 30
    # ========================================================

    if "H4" in trends:

        score = 0

        h4 = trends.get(
            "H4",
            "HOLD"
        )

        h1 = trends.get(
            "H1",
            "HOLD"
        )

        m15 = trends.get(
            "M15",
            "HOLD"
        )

        if h4 == "BUY":
            score += 40

        elif h4 == "SELL":
            score -= 40

        if h1 == "BUY":
            score += 30

        elif h1 == "SELL":
            score -= 30

        if m15 == "BUY":
            score += 30

        elif m15 == "SELL":
            score -= 30

        return int(score)

    return 0


# ============================================================
# MTF STATUS
# ============================================================

def calculate_mtf_status(trends):

    if not isinstance(
        trends,
        dict
    ):
        return "NEUTRAL"

    # ========================================================
    # PRIMARY H1 / M15 / M1
    # ========================================================

    if "M1" in trends:

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

        # ----------------------------------------------------
        # PERFECT ALIGNMENT
        # ----------------------------------------------------

        if (
            h1 == "BUY"
            and m15 == "BUY"
            and m1 == "BUY"
        ):
            return "STRONG_BUY"

        if (
            h1 == "SELL"
            and m15 == "SELL"
            and m1 == "SELL"
        ):
            return "STRONG_SELL"

        # ----------------------------------------------------
        # H1 + M15 CORE ALIGNMENT
        # ----------------------------------------------------

        if (
            h1 == "BUY"
            and m15 == "BUY"
        ):
            return "BUY_BIAS"

        if (
            h1 == "SELL"
            and m15 == "SELL"
        ):
            return "SELL_BIAS"

        # ----------------------------------------------------
        # H1 BIAS ONLY
        # ----------------------------------------------------

        if h1 == "BUY":
            return "BUY_BIAS"

        if h1 == "SELL":
            return "SELL_BIAS"

        return "NEUTRAL"

    # ========================================================
    # LEGACY H4 / H1 / M15
    # ========================================================

    if "H4" in trends:

        h4 = trends.get(
            "H4",
            "HOLD"
        )

        h1 = trends.get(
            "H1",
            "HOLD"
        )

        m15 = trends.get(
            "M15",
            "HOLD"
        )

        if (
            h4 == "BUY"
            and h1 == "BUY"
            and m15 == "BUY"
        ):
            return "STRONG_BUY"

        if (
            h4 == "SELL"
            and h1 == "SELL"
            and m15 == "SELL"
        ):
            return "STRONG_SELL"

        if (
            h4 == "BUY"
            and h1 == "BUY"
        ):
            return "BUY_BIAS"

        if (
            h4 == "SELL"
            and h1 == "SELL"
        ):
            return "SELL_BIAS"

        if (
            h4 == "BUY"
            or h1 == "BUY"
        ):
            return "BUY_BIAS"

        if (
            h4 == "SELL"
            or h1 == "SELL"
        ):
            return "SELL_BIAS"

        return "NEUTRAL"

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

    h1_trend = trends["H1"]
    m15_trend = trends["M15"]
    m1_trend = trends["M1"]

    # ========================================================
    # CORE ALIGNMENT
    #
    # H1 + M15 = CORE
    # M1        = SUPPLEMENTARY
    # ========================================================

    core_buy = (
        h1_trend == "BUY"
        and m15_trend == "BUY"
    )

    core_sell = (
        h1_trend == "SELL"
        and m15_trend == "SELL"
    )

    m1_buy_confirmation = (
        m1_trend == "BUY"
    )

    m1_sell_confirmation = (
        m1_trend == "SELL"
    )

    return {
        "trends": trends,

        "score": int(score),

        "status": status,

        "h1_trend": h1_trend,

        "m15_trend": m15_trend,

        "m1_trend": m1_trend,

        # ----------------------------------------------------
        # CORE
        # ----------------------------------------------------

        "core_buy": core_buy,

        "core_sell": core_sell,

        # ----------------------------------------------------
        # M1 SUPPLEMENTARY
        # ----------------------------------------------------

        "m1_buy_confirmation":
            m1_buy_confirmation,

        "m1_sell_confirmation":
            m1_sell_confirmation,

        "m1_aligned":
            (
                m1_buy_confirmation
                or m1_sell_confirmation
            ),
    }


# ============================================================
# MTF ENTRY PERMISSION
#
# PRIMARY RULE
#
# H1  = REQUIRED
# M15 = REQUIRED
# M1  = SUPPLEMENTARY
#
# M1 TIDAK BOLEH MEMBATALKAN ENTRY.
# ============================================================

def mtf_allows_signal(
    signal,
    mtf_confirmation
):

    if not isinstance(
        mtf_confirmation,
        dict
    ):
        return False

    trends = mtf_confirmation.get(
        "trends",
        {}
    )

    signal = str(
        signal
    ).upper()

    # ========================================================
    # PRIMARY H1 / M15 / M1
    # ========================================================

    if "M1" in trends:

        h1 = trends.get(
            "H1",
            "HOLD"
        )

        m15 = trends.get(
            "M15",
            "HOLD"
        )

        # ----------------------------------------------------
        # BUY
        #
        # H1 + M15 wajib BUY.
        # M1 bebas BUY / HOLD / SELL.
        # ----------------------------------------------------

        if signal == "BUY":

            return (
                h1 == "BUY"
                and m15 == "BUY"
            )

        # ----------------------------------------------------
        # SELL
        #
        # H1 + M15 wajib SELL.
        # M1 bebas BUY / HOLD / SELL.
        # ----------------------------------------------------

        if signal == "SELL":

            return (
                h1 == "SELL"
                and m15 == "SELL"
            )

        return False

    # ========================================================
    # LEGACY H4 / H1 / M15
    # ========================================================

    if "H4" in trends:

        h4 = trends.get(
            "H4",
            "HOLD"
        )

        h1 = trends.get(
            "H1",
            "HOLD"
        )

        m15 = trends.get(
            "M15",
            "HOLD"
        )

        if signal == "BUY":

            return (
                h4 == "BUY"
                and h1 == "BUY"
                and m15 == "BUY"
            )

        if signal == "SELL":

            return (
                h4 == "SELL"
                and h1 == "SELL"
                and m15 == "SELL"
            )

        return False

    return False


# ============================================================
# MTF BIAS
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

            "core_aligned": False,

            "m1_confirmed": False,
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

    # ========================================================
    # CORE ALIGNMENT
    # ========================================================

    aligned_buy = (
        h1 == "BUY"
        and m15 == "BUY"
    )

    aligned_sell = (
        h1 == "SELL"
        and m15 == "SELL"
    )

    core_aligned = (
        aligned_buy
        or aligned_sell
    )

    # ========================================================
    # M1 CONFIRMATION
    # ========================================================

    m1_buy_confirmed = (
        aligned_buy
        and m1 == "BUY"
    )

    m1_sell_confirmed = (
        aligned_sell
        and m1 == "SELL"
    )

    m1_confirmed = (
        m1_buy_confirmed
        or m1_sell_confirmed
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

        "status":
            mtf_confirmation.get(
                "status",
                "NEUTRAL"
            ),

        # H1 + M15
        "aligned":
            core_aligned,

        "core_aligned":
            core_aligned,

        # M1 supplementary
        "m1_confirmed":
            m1_confirmed,

        "m1_buy_confirmed":
            m1_buy_confirmed,

        "m1_sell_confirmed":
            m1_sell_confirmed,
    }