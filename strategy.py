import numpy as np
import pandas as pd

# ============================================================
# FOREX AUTO TRADER PRO
# STRATEGY ENGINE V6
#
# Design:
# - No look-ahead.
# - H1 + M15 remain the required MTF permission when supplied.
# - M1 is supplementary and is NOT used as a hard blocker.
# - SELL is symmetric with BUY; no arbitrary "SELL is bad" bias.
# - Precision score is diagnostic. It does not manufacture trades.
# ============================================================


def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def calculate_atr(df, period=14):
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(alpha=1 / period, adjust=False).mean()


def calculate_rsi(series, period=14):
    delta = series.astype(float).diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def calculate_adx(df, period=14):
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    up = high.diff()
    down = -low.diff()

    plus_dm = pd.Series(
        np.where((up > down) & (up > 0), up, 0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down > up) & (down > 0), down, 0.0),
        index=df.index,
    )

    tr = pd.concat(
        [
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()

    plus_di = (
        100
        * plus_dm.ewm(alpha=1 / period, adjust=False).mean()
        / atr.replace(0, np.nan)
    )
    minus_di = (
        100
        * minus_dm.ewm(alpha=1 / period, adjust=False).mean()
        / atr.replace(0, np.nan)
    )

    denom = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / denom

    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0.0)


def detect_structure(df, lookback=5):
    if len(df) < lookback + 2:
        return "UNKNOWN"

    prior = df.iloc[-lookback-1:-1]
    last = df.iloc[-1]
    close = float(last["close"])

    if close > float(prior["high"].max()):
        return "BULLISH_BREAK"
    if close < float(prior["low"].min()):
        return "BEARISH_BREAK"
    return "RANGE"


def detect_trend(df, fast=20, slow=50):
    if len(df) < slow:
        return "NEUTRAL"

    fast_ema = calculate_ema(df["close"], fast).iloc[-1]
    slow_ema = calculate_ema(df["close"], slow).iloc[-1]

    if fast_ema > slow_ema:
        return "BULLISH"
    if fast_ema < slow_ema:
        return "BEARISH"
    return "NEUTRAL"


def calculate_momentum(df, lookback=5):
    if len(df) < lookback + 1:
        return 0.0

    now = float(df["close"].iloc[-1])
    old = float(df["close"].iloc[-lookback - 1])
    if old == 0:
        return 0.0
    return ((now - old) / old) * 100.0


def candle_confirmation(df, signal):
    if len(df) < 2:
        return False

    c = df.iloc[-1]
    o, h, l, close = map(float, (c["open"], c["high"], c["low"], c["close"]))
    rng = h - l
    if rng <= 0:
        return False

    body = abs(close - o) / rng
    if body < 0.30:
        return False

    if signal == "BUY":
        return close > o and ((close - l) / rng) >= 0.58

    if signal == "SELL":
        return close < o and ((h - close) / rng) >= 0.58

    return False


def rsi_confirmation(signal, rsi):
    if rsi is None or pd.isna(rsi):
        return False
    if signal == "BUY":
        return 50 <= rsi <= 72
    if signal == "SELL":
        return 28 <= rsi <= 50
    return False


def adx_confirmation(signal, adx):
    # ADX measures trend strength, not direction.
    # Direction is supplied by EMA/structure/MTF.
    return adx is not None and np.isfinite(adx) and adx >= 18


def volatility_confirmation(atr, atr_average):
    if atr is None or atr_average is None:
        return False
    if not np.isfinite(atr) or not np.isfinite(atr_average):
        return False
    if atr <= 0 or atr_average <= 0:
        return False

    ratio = atr / atr_average
    return 0.65 <= ratio <= 2.25


def ema_distance_confirmation(signal, close, ema_fast, atr):
    if atr is None or not np.isfinite(atr) or atr <= 0:
        return False

    distance = abs(close - ema_fast)
    if distance > atr * 1.75:
        return False

    if signal == "BUY":
        return close > ema_fast
    if signal == "SELL":
        return close < ema_fast
    return False


def sell_quality_gate(momentum, adx, rsi, candle_confirmed):
    # Symmetric quality gate. The old V5 gate rejected almost every
    # SELL because it demanded momentum < -0.08 and ADX >= 22.
    # Those thresholds were not statistically validated.
    if not candle_confirmed:
        return False
    if momentum is None or adx is None or rsi is None:
        return False
    if not np.isfinite(momentum) or not np.isfinite(adx) or not np.isfinite(rsi):
        return False

    return momentum < -0.02 and adx >= 18 and rsi <= 50


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
    if signal not in ("BUY", "SELL"):
        return False

    if signal == "BUY":
        directional_ok = (
            trend == "BULLISH"
            and ema_fast > ema_slow
            and momentum > 0
            and structure in ("BULLISH_BREAK", "RANGE")
        )
    else:
        directional_ok = (
            trend == "BEARISH"
            and ema_fast < ema_slow
            and momentum < 0
            and structure in ("BEARISH_BREAK", "RANGE")
        )

    if not directional_ok:
        return False

    if not rsi_confirmation(signal, rsi):
        return False
    if not adx_confirmation(signal, adx):
        return False
    if not volatility_confirmation(atr_value, atr_average):
        return False
    if not ema_distance_confirmation(signal, close, ema_fast, atr_value):
        return False
    if not candle_confirmed:
        return False

    if signal == "SELL" and not sell_quality_gate(
        momentum, adx, rsi, candle_confirmed
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
    if signal not in ("BUY", "SELL"):
        return 0

    score = 0.0

    # MTF: 25
    if mtf_confirmation:
        trends = mtf_confirmation.get("trends", {})
        h1 = trends.get("H1", "HOLD")
        m15 = trends.get("M15", "HOLD")

        if signal == "BUY" and h1 == "BUY" and m15 == "BUY":
            score += 25
        elif signal == "SELL" and h1 == "SELL" and m15 == "SELL":
            score += 25
        elif signal == "BUY" and h1 == "BUY":
            score += 12
        elif signal == "SELL" and h1 == "SELL":
            score += 12

    # Trend alignment: 15
    if signal == "BUY" and trend == "BULLISH":
        score += 15
    elif signal == "SELL" and trend == "BEARISH":
        score += 15

    # Structure: 15 for breakout, 8 for orderly range continuation
    if signal == "BUY":
        if structure == "BULLISH_BREAK":
            score += 15
        elif structure == "RANGE":
            score += 8
    else:
        if structure == "BEARISH_BREAK":
            score += 15
        elif structure == "RANGE":
            score += 8

    # RSI: 10
    if rsi is not None and np.isfinite(rsi):
        if signal == "BUY":
            if 54 <= rsi <= 66:
                score += 10
            elif 50 <= rsi <= 72:
                score += 7
        else:
            if 34 <= rsi <= 46:
                score += 10
            elif 28 <= rsi <= 50:
                score += 7

    # ADX: 10
    if adx is not None and np.isfinite(adx):
        if adx >= 30:
            score += 10
        elif adx >= 25:
            score += 8
        elif adx >= 18:
            score += 5

    # Momentum: 10
    m = abs(float(momentum))
    if (signal == "BUY" and momentum > 0) or (signal == "SELL" and momentum < 0):
        if m >= 0.30:
            score += 10
        elif m >= 0.15:
            score += 8
        elif m >= 0.05:
            score += 6
        else:
            score += 3

    # Volatility: 5
    if volatility_confirmation(atr_value, atr_average):
        score += 5

    # Candle: 5
    if candle_confirmed:
        score += 5

    return int(max(0, min(100, round(score))))


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


def _mtf_permission(signal, mtf_confirmation):
    if not mtf_confirmation:
        return True

    trends = mtf_confirmation.get("trends", {})
    h1 = trends.get("H1", "HOLD")
    m15 = trends.get("M15", "HOLD")

    if signal == "BUY":
        return h1 == "BUY" and m15 == "BUY"
    if signal == "SELL":
        return h1 == "SELL" and m15 == "SELL"
    return False


def generate_signal(
    df,
    ema_fast=20,
    ema_slow=50,
    atr_period=14,
    mtf_confirmation=None,
):
    neutral = {
        "signal": "HOLD",
        "trend": "NEUTRAL",
        "structure": "UNKNOWN",
        "momentum": 0.0,
        "score": 0,
        "precision_score": 0,
        "precision_grade": "D",
        "precision_pass": False,
        "atr": None,
        "atr_average": None,
        "rsi": 50.0,
        "adx": 0.0,
        "ema_fast": None,
        "ema_slow": None,
        "candle_confirmed": False,
        "reason": "insufficient_data",
    }

    if df is None or len(df) < max(ema_slow + 10, 80):
        return neutral

    data = df.copy().reset_index(drop=True)

    close = data["close"].astype(float)
    ema_fast_series = calculate_ema(close, ema_fast)
    ema_slow_series = calculate_ema(close, ema_slow)
    atr_series = calculate_atr(data, atr_period)
    rsi_series = calculate_rsi(close, 14)
    adx_series = calculate_adx(data, 14)

    ema_f = float(ema_fast_series.iloc[-1])
    ema_s = float(ema_slow_series.iloc[-1])
    atr = float(atr_series.iloc[-1])
    atr_avg = float(atr_series.rolling(50).mean().iloc[-1])
    rsi = float(rsi_series.iloc[-1])
    adx = float(adx_series.iloc[-1])
    momentum = float(calculate_momentum(data))
    structure = detect_structure(data)
    trend = detect_trend(data, ema_fast, ema_slow)

    if not all(np.isfinite(x) for x in (ema_f, ema_s, atr, atr_avg, rsi, adx, momentum)):
        return neutral

    candle_buy = candle_confirmation(data, "BUY")
    candle_sell = candle_confirmation(data, "SELL")

    # Candidate direction is deliberately broad. Precision filters decide.
    buy_candidate = (
        trend == "BULLISH"
        and ema_f > ema_s
        and momentum > 0
        and rsi >= 50
    )
    sell_candidate = (
        trend == "BEARISH"
        and ema_f < ema_s
        and momentum < 0
        and rsi <= 50
    )

    if buy_candidate and _mtf_permission("BUY", mtf_confirmation):
        signal = "BUY"
        candle_ok = candle_buy
    elif sell_candidate and _mtf_permission("SELL", mtf_confirmation):
        signal = "SELL"
        candle_ok = candle_sell
    else:
        return {
            **neutral,
            "trend": trend,
            "structure": structure,
            "momentum": momentum,
            "atr": atr,
            "atr_average": atr_avg,
            "rsi": rsi,
            "adx": adx,
            "ema_fast": ema_f,
            "ema_slow": ema_s,
            "reason": "no_directional_candidate",
        }

    precision_score = calculate_precision_score(
        signal=signal,
        trend=trend,
        structure=structure,
        momentum=momentum,
        atr_value=atr,
        close=float(close.iloc[-1]),
        ema_fast=ema_f,
        ema_slow=ema_s,
        rsi=rsi,
        adx=adx,
        atr_average=atr_avg,
        candle_confirmed=candle_ok,
        mtf_confirmation=mtf_confirmation,
    )

    precision_pass = precision_entry_filter(
        signal=signal,
        trend=trend,
        structure=structure,
        momentum=momentum,
        atr_value=atr,
        close=float(close.iloc[-1]),
        ema_fast=ema_f,
        ema_slow=ema_s,
        rsi=rsi,
        adx=adx,
        atr_average=atr_avg,
        candle_confirmed=candle_ok,
    )

    # score is retained for compatibility with the existing bot.
    score = precision_score

    return {
        "signal": signal if precision_pass else "HOLD",
        "candidate_signal": signal,
        "trend": trend,
        "structure": structure,
        "momentum": momentum,
        "score": score,
        "precision_score": precision_score,
        "precision_grade": precision_grade(precision_score),
        "precision_pass": bool(precision_pass),
        "atr": atr,
        "atr_average": atr_avg,
        "rsi": rsi,
        "adx": adx,
        "ema_fast": ema_f,
        "ema_slow": ema_s,
        "candle_confirmed": bool(candle_ok),
        "reason": (
            "precision_pass"
            if precision_pass
            else "precision_filter_rejected"
        ),
    }
