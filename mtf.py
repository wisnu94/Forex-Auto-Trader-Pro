# ============================================================
# MTF TREND ENGINE
# ============================================================

DEFAULT_TIMEFRAMES = ("H4", "H1", "M15")


def calculate_ema(series, period):
    return series.ewm(
        span=period,
        adjust=False
    ).mean()


def timeframe_trend(
    df,
    fast_period=20,
    slow_period=50
):
    if df is None or len(df) < slow_period:
        return "HOLD"

    close = df["close"]

    fast = calculate_ema(
        close,
        fast_period
    )

    slow = calculate_ema(
        close,
        slow_period
    )

    last_close = float(
        close.iloc[-1]
    )

    last_fast = float(
        fast.iloc[-1]
    )

    last_slow = float(
        slow.iloc[-1]
    )

    if (
        last_close > last_fast
        and last_fast > last_slow
    ):
        return "BUY"

    if (
        last_close < last_fast
        and last_fast < last_slow
    ):
        return "SELL"

    return "HOLD"


# ============================================================
# MTF SCORE
# ============================================================

def calculate_mtf_score(trends):

    weights = {
        "H4": 40,
        "H1": 35,
        "M15": 25,
    }

    score = 0

    for timeframe, weight in weights.items():

        trend = trends.get(
            timeframe,
            "HOLD"
        )

        if trend == "BUY":
            score += weight

        elif trend == "SELL":
            score -= weight

    return int(score)


# ============================================================
# MTF CONFIRMATION
# ============================================================

def get_mtf_confirmation(
    symbol,
    timeframes=DEFAULT_TIMEFRAMES,
    bars=150
):
    # MT5 is imported only when real market
    # data is actually requested.
    #
    # This keeps the pure MTF calculation
    # testable inside GitHub Actions.

    from data import get_bars

    trends = {}

    for timeframe in timeframes:

        df = get_bars(
            symbol,
            timeframe,
            count=bars
        )

        trends[timeframe] = timeframe_trend(
            df
        )

    score = calculate_mtf_score(
        trends
    )

    requested = list(
        timeframes
    )

    all_buy = all(
        trends.get(tf) == "BUY"
        for tf in requested
    )

    all_sell = all(
        trends.get(tf) == "SELL"
        for tf in requested
    )

    if all_buy:

        status = "STRONG_BUY"

    elif all_sell:

        status = "STRONG_SELL"

    elif score >= 40:

        status = "BUY_BIAS"

    elif score <= -40:

        status = "SELL_BIAS"

    else:

        status = "NEUTRAL"

    return {
        "trends": trends,
        "score": score,
        "status": status,
    }


# ============================================================
# MTF ENTRY FILTER
# ============================================================

def mtf_allows_signal(
    signal,
    confirmation
):

    if signal == "BUY":

        return (
            confirmation["status"]
            == "STRONG_BUY"
        )

    if signal == "SELL":

        return (
            confirmation["status"]
            == "STRONG_SELL"
        )

    return False