import numpy as np
import pandas as pd

# ============================================================
# FOREX AUTO TRADER PRO - GOLD PRECISION V8
# Precision-first. No look-ahead.
# Goal: fewer, higher-quality entries.
# ============================================================


def calculate_ema(series, period):
    return series.astype(float).ewm(span=period, adjust=False).mean()


def calculate_atr(df, period=14):
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev).abs(),
            (low - prev).abs(),
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


def calculate_adx_components(df, period=14):
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

    pdi = (
        100
        * plus_dm.ewm(alpha=1 / period, adjust=False).mean()
        / atr.replace(0, np.nan)
    )

    mdi = (
        100
        * minus_dm.ewm(alpha=1 / period, adjust=False).mean()
        / atr.replace(0, np.nan)
    )

    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    return (
        adx.fillna(0.0),
        pdi.fillna(0.0),
        mdi.fillna(0.0),
    )


def calculate_adx(df, period=14):
    return calculate_adx_components(df, period)[0]


def calculate_momentum(df, lookback=5):
    if len(df) < lookback + 1:
        return 0.0

    old = float(df["close"].iloc[-lookback - 1])
    now = float(df["close"].iloc[-1])

    if old == 0:
        return 0.0

    return ((now - old) / old) * 100.0


def detect_trend(df, fast=20, slow=50):
    if len(df) < slow:
        return "NEUTRAL"

    close = df["close"].astype(float)
    fast_ema = calculate_ema(close, fast)
    slow_ema = calculate_ema(close, slow)

    if fast_ema.iloc[-1] > slow_ema.iloc[-1]:
        return "BULLISH"
    if fast_ema.iloc[-1] < slow_ema.iloc[-1]:
        return "BEARISH"
    return "NEUTRAL"


def detect_structure(df, lookback=8):
    if len(df) < lookback + 2:
        return "UNKNOWN"

    prior = df.iloc[-lookback - 1:-1]
    close = float(df["close"].iloc[-1])

    if close > float(prior["high"].max()):
        return "BULLISH_BREAK"

    if close < float(prior["low"].min()):
        return "BEARISH_BREAK"

    return "RANGE"


def candle_confirmation(df, signal):
    if len(df) < 2:
        return False

    c = df.iloc[-1]
    o, h, l, close = [
        float(c[x]) for x in ("open", "high", "low", "close")
    ]

    rng = h - l
    if rng <= 0:
        return False

    body_ratio = abs(close - o) / rng

    if body_ratio < 0.40:
        return False

    if signal == "BUY":
        return close > o and ((close - l) / rng) >= 0.65

    if signal == "SELL":
        return close < o and ((h - close) / rng) >= 0.65

    return False


def _mtf_permission(signal, mtf):
    if not isinstance(mtf, dict):
        return False

    trends = mtf.get("trends", {})
    h1 = trends.get("H1", "HOLD")
    m15 = trends.get("M15", "HOLD")

    if signal == "BUY":
        return h1 == "BUY" and m15 == "BUY"

    if signal == "SELL":
        return h1 == "SELL" and m15 == "SELL"

    return False


def _direction_ok(signal, pdi, mdi, adx):
    if adx < 20:
        return False

    if signal == "BUY":
        return pdi > mdi and (pdi - mdi) >= 3.0

    if signal == "SELL":
        return mdi > pdi and (mdi - pdi) >= 3.0

    return False


def _volatility_ok(atr, atr_average):
    if not np.isfinite(atr) or not np.isfinite(atr_average):
        return False

    if atr <= 0 or atr_average <= 0:
        return False

    ratio = atr / atr_average
    return 0.75 <= ratio <= 1.80


def _ema_distance_ok(signal, close, ema_fast, atr):
    if atr <= 0:
        return False

    distance = abs(close - ema_fast) / atr

    if distance > 1.20:
        return False

    if signal == "BUY":
        return close > ema_fast

    if signal == "SELL":
        return close < ema_fast

    return False


def _rsi_ok(signal, rsi):
    # Avoid both exhaustion and weak entries.
    if signal == "BUY":
        return 52 <= rsi <= 67

    if signal == "SELL":
        return 33 <= rsi <= 48

    return False


def _slope_ok(signal, ema_series):
    if len(ema_series) < 6:
        return False

    now = float(ema_series.iloc[-1])
    old = float(ema_series.iloc[-6])

    return now > old if signal == "BUY" else now < old


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
    plus_di=None,
    minus_di=None,
    trend_slope_ok=False,
):
    if signal not in {"BUY", "SELL"}:
        return 0

    score = 0
    trends = (mtf_confirmation or {}).get("trends", {})
    h1 = trends.get("H1", "HOLD")
    m15 = trends.get("M15", "HOLD")

    if (signal == "BUY" and h1 == "BUY" and m15 == "BUY") or (
        signal == "SELL" and h1 == "SELL" and m15 == "SELL"
    ):
        score += 30

    if (signal == "BUY" and trend == "BULLISH") or (
        signal == "SELL" and trend == "BEARISH"
    ):
        score += 15

    if plus_di is not None and minus_di is not None:
        if _direction_ok(signal, plus_di, minus_di, adx):
            score += 15

    if (signal == "BUY" and structure == "BULLISH_BREAK") or (
        signal == "SELL" and structure == "BEARISH_BREAK"
    ):
        score += 10
    elif structure == "RANGE":
        score += 5

    directional_momentum = (
        signal == "BUY" and momentum >= 0.05
    ) or (
        signal == "SELL" and momentum <= -0.05
    )

    if directional_momentum:
        score += 10 if abs(momentum) >= 0.15 else 7

    if _rsi_ok(signal, rsi):
        score += 8

    if _volatility_ok(atr_value, atr_average):
        score += 5

    if candle_confirmed:
        score += 5

    if trend_slope_ok:
        score += 2

    return int(max(0, min(100, score)))


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


def generate_signal(
    df,
    ema_fast=20,
    ema_slow=50,
    atr_period=14,
    mtf_confirmation=None,
):
    neutral = {
        "signal": "HOLD",
        "candidate_signal": "HOLD",
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
        "plus_di": 0.0,
        "minus_di": 0.0,
        "ema_fast": None,
        "ema_slow": None,
        "candle_confirmed": False,
        "trend_slope_ok": False,
        "reason": "insufficient_data",
    }

    if df is None or len(df) < max(ema_slow + 60, 120):
        return neutral

    data = df.copy().reset_index(drop=True)
    close = data["close"].astype(float)

    ef_series = calculate_ema(close, ema_fast)
    es_series = calculate_ema(close, ema_slow)
    atr_series = calculate_atr(data, atr_period)
    rsi_series = calculate_rsi(close, 14)
    adx_series, pdi_series, mdi_series = calculate_adx_components(data, 14)

    ef = float(ef_series.iloc[-1])
    es = float(es_series.iloc[-1])
    atr = float(atr_series.iloc[-1])
    atr_average = float(atr_series.rolling(50).mean().iloc[-1])
    rsi = float(rsi_series.iloc[-1])
    adx = float(adx_series.iloc[-1])
    pdi = float(pdi_series.iloc[-1])
    mdi = float(mdi_series.iloc[-1])
    momentum = float(calculate_momentum(data))
    structure = detect_structure(data)
    trend = detect_trend(data, ema_fast, ema_slow)
    last_close = float(close.iloc[-1])

    values = [ef, es, atr, atr_average, rsi, adx, pdi, mdi, momentum]
    if not all(np.isfinite(x) for x in values):
        return neutral

    slope_buy = _slope_ok("BUY", ef_series)
    slope_sell = _slope_ok("SELL", ef_series)

    candle_buy = candle_confirmation(data, "BUY")
    candle_sell = candle_confirmation(data, "SELL")

    buy_candidate = (
        trend == "BULLISH"
        and ef > es
        and momentum >= 0.05
        and _mtf_permission("BUY", mtf_confirmation)
    )

    sell_candidate = (
        trend == "BEARISH"
        and ef < es
        and momentum <= -0.05
        and _mtf_permission("SELL", mtf_confirmation)
    )

    if buy_candidate and _direction_ok("BUY", pdi, mdi, adx) and slope_buy:
        signal = "BUY"
        candle_ok = candle_buy
        slope_ok = slope_buy
    elif sell_candidate and _direction_ok("SELL", pdi, mdi, adx) and slope_sell:
        signal = "SELL"
        candle_ok = candle_sell
        slope_ok = slope_sell
    else:
        return {
            **neutral,
            "trend": trend,
            "structure": structure,
            "momentum": momentum,
            "atr": atr,
            "atr_average": atr_average,
            "rsi": rsi,
            "adx": adx,
            "plus_di": pdi,
            "minus_di": mdi,
            "ema_fast": ef,
            "ema_slow": es,
            "reason": "no_high_quality_candidate",
        }

    score = calculate_precision_score(
        signal,
        trend,
        structure,
        momentum,
        atr,
        last_close,
        ef,
        es,
        rsi,
        adx,
        atr_average,
        candle_ok,
        mtf_confirmation,
        pdi,
        mdi,
        slope_ok,
    )

    precision_pass = (
        score >= 78
        and _rsi_ok(signal, rsi)
        and _volatility_ok(atr, atr_average)
        and _ema_distance_ok(signal, last_close, ef, atr)
        and candle_ok
    )

    return {
        "signal": signal if precision_pass else "HOLD",
        "candidate_signal": signal,
        "trend": trend,
        "structure": structure,
        "momentum": momentum,
        "score": score,
        "precision_score": score,
        "precision_grade": precision_grade(score),
        "precision_pass": bool(precision_pass),
        "atr": atr,
        "atr_average": atr_average,
        "rsi": rsi,
        "adx": adx,
        "plus_di": pdi,
        "minus_di": mdi,
        "ema_fast": ef,
        "ema_slow": es,
        "candle_confirmed": bool(candle_ok),
        "trend_slope_ok": bool(slope_ok),
        "reason": "precision_pass" if precision_pass else "quality_filter_rejected",
    }
