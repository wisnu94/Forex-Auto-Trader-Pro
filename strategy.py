import numpy as np
import pandas as pd

# ============================================================
# FOREX AUTO TRADER PRO - STRATEGY ENGINE V7
# Goal: precision-first, direction-aware, no look-ahead.
# ============================================================

def calculate_ema(series, period):
    return series.astype(float).ewm(span=period, adjust=False).mean()


def calculate_atr(df, period=14):
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev).abs(),
        (low - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def calculate_rsi(series, period=14):
    delta = series.astype(float).diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1 / period, adjust=False).mean()
    al = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def calculate_adx_components(df, period=14):
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    pdi = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    mdi = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    denom = (pdi + mdi).replace(0, np.nan)
    dx = 100 * (pdi - mdi).abs() / denom
    adx = dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0.0)
    return adx, pdi.fillna(0.0), mdi.fillna(0.0)


def calculate_adx(df, period=14):
    return calculate_adx_components(df, period)[0]


def detect_structure(df, lookback=8):
    if len(df) < lookback + 2:
        return "UNKNOWN"
    prior = df.iloc[-lookback-1:-1]
    last = float(df["close"].iloc[-1])
    if last > float(prior["high"].max()):
        return "BULLISH_BREAK"
    if last < float(prior["low"].min()):
        return "BEARISH_BREAK"
    return "RANGE"


def detect_trend(df, fast=20, slow=50):
    if len(df) < slow:
        return "NEUTRAL"
    ef = calculate_ema(df["close"], fast).iloc[-1]
    es = calculate_ema(df["close"], slow).iloc[-1]
    if ef > es:
        return "BULLISH"
    if ef < es:
        return "BEARISH"
    return "NEUTRAL"


def calculate_momentum(df, lookback=5):
    if len(df) < lookback + 1:
        return 0.0
    old = float(df["close"].iloc[-lookback-1])
    now = float(df["close"].iloc[-1])
    return 0.0 if old == 0 else ((now - old) / old) * 100.0


def candle_confirmation(df, signal):
    if len(df) < 2:
        return False
    c = df.iloc[-1]
    o, h, l, close = [float(c[x]) for x in ("open", "high", "low", "close")]
    rng = h - l
    if rng <= 0:
        return False
    body = abs(close - o) / rng
    if body < 0.35:
        return False
    if signal == "BUY":
        return close > o and (close - l) / rng >= 0.60
    if signal == "SELL":
        return close < o and (h - close) / rng >= 0.60
    return False


def _mtf_permission(signal, mtf_confirmation):
    if not mtf_confirmation:
        return True
    trends = mtf_confirmation.get("trends", {})
    h1 = trends.get("H1", "HOLD")
    m15 = trends.get("M15", "HOLD")
    return (h1 == "BUY" and m15 == "BUY") if signal == "BUY" else (
        h1 == "SELL" and m15 == "SELL"
    )


def _direction_ok(signal, pdi, mdi, adx):
    if adx < 18:
        return False
    if signal == "BUY":
        return pdi > mdi and (pdi - mdi) >= 2.0
    return mdi > pdi and (mdi - pdi) >= 2.0


def _trend_slope_ok(signal, ema_fast_series):
    if len(ema_fast_series) < 6:
        return False
    now = float(ema_fast_series.iloc[-1])
    old = float(ema_fast_series.iloc[-6])
    if signal == "BUY":
        return now > old
    return now < old


def _volatility_ok(atr, atr_average):
    if not np.isfinite(atr) or not np.isfinite(atr_average) or atr <= 0 or atr_average <= 0:
        return False
    ratio = atr / atr_average
    return 0.70 <= ratio <= 1.90


def _ema_distance_ok(signal, close, ema_fast, atr):
    if atr <= 0:
        return False
    distance = abs(close - ema_fast) / atr
    if distance > 1.35:
        return False
    return close > ema_fast if signal == "BUY" else close < ema_fast


def _rsi_ok(signal, rsi):
    # Avoid chasing exhausted moves.
    if signal == "BUY":
        return 48 <= rsi <= 68
    return 32 <= rsi <= 52


def calculate_precision_score(
    signal, trend, structure, momentum, atr_value, close,
    ema_fast, ema_slow, rsi, adx, atr_average,
    candle_confirmed, mtf_confirmation=None, plus_di=None, minus_di=None,
    trend_slope_ok=False
):
    if signal not in ("BUY", "SELL"):
        return 0

    score = 0.0
    trends = (mtf_confirmation or {}).get("trends", {})
    h1, m15 = trends.get("H1", "HOLD"), trends.get("M15", "HOLD")

    # MTF = 30
    if (signal == "BUY" and h1 == "BUY" and m15 == "BUY") or (
        signal == "SELL" and h1 == "SELL" and m15 == "SELL"
    ):
        score += 30

    # Local trend = 15
    if (signal == "BUY" and trend == "BULLISH") or (signal == "SELL" and trend == "BEARISH"):
        score += 15

    # Directional DI confirmation = 15
    if plus_di is not None and minus_di is not None and _direction_ok(signal, plus_di, minus_di, adx):
        score += 15

    # Structure = 10
    good_break = (signal == "BUY" and structure == "BULLISH_BREAK") or (
        signal == "SELL" and structure == "BEARISH_BREAK"
    )
    if good_break:
        score += 10
    elif structure == "RANGE":
        score += 5

    # Momentum = 10, direction + strength
    m = abs(float(momentum))
    directional_momentum = (signal == "BUY" and momentum > 0) or (signal == "SELL" and momentum < 0)
    if directional_momentum:
        score += 10 if m >= 0.15 else 7 if m >= 0.05 else 3

    # RSI = 8
    if _rsi_ok(signal, rsi):
        score += 8

    # Volatility = 5
    if _volatility_ok(atr_value, atr_average):
        score += 5

    # Candle = 5
    if candle_confirmed:
        score += 5

    # EMA slope = 2
    if trend_slope_ok:
        score += 2

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


def precision_entry_filter(
    signal, trend, structure, momentum, atr_value, close, ema_fast,
    ema_slow, rsi, adx, atr_average, candle_confirmed,
    mtf_confirmation=None, plus_di=None, minus_di=None, trend_slope_ok=False
):
    if signal not in ("BUY", "SELL"):
        return False
    if not _mtf_permission(signal, mtf_confirmation):
        return False
    if signal == "BUY":
        if not (trend == "BULLISH" and ema_fast > ema_slow and momentum > 0):
            return False
        if structure not in ("BULLISH_BREAK", "RANGE"):
            return False
    else:
        if not (trend == "BEARISH" and ema_fast < ema_slow and momentum < 0):
            return False
        if structure not in ("BEARISH_BREAK", "RANGE"):
            return False

    if not _direction_ok(signal, plus_di, minus_di, adx):
        return False
    if not _trend_slope_ok(signal, pd.Series([0, 0, 0, 0, 0, 1 if trend_slope_ok else 0])):
        return False
    if not _rsi_ok(signal, rsi):
        return False
    if not _volatility_ok(atr_value, atr_average):
        return False
    if not _ema_distance_ok(signal, close, ema_fast, atr_value):
        return False
    if not candle_confirmed:
        return False
    return True


def generate_signal(df, ema_fast=20, ema_slow=50, atr_period=14, mtf_confirmation=None):
    neutral = {
        "signal": "HOLD", "candidate_signal": "HOLD",
        "trend": "NEUTRAL", "structure": "UNKNOWN", "momentum": 0.0,
        "score": 0, "precision_score": 0, "precision_grade": "D",
        "precision_pass": False, "atr": None, "atr_average": None,
        "rsi": 50.0, "adx": 0.0, "plus_di": 0.0, "minus_di": 0.0,
        "ema_fast": None, "ema_slow": None, "candle_confirmed": False,
        "trend_slope_ok": False, "reason": "insufficient_data",
    }

    if df is None or len(df) < max(ema_slow + 60, 120):
        return neutral

    data = df.copy().reset_index(drop=True)
    close_series = data["close"].astype(float)
    ef_series = calculate_ema(close_series, ema_fast)
    es_series = calculate_ema(close_series, ema_slow)
    atr_series = calculate_atr(data, atr_period)
    rsi_series = calculate_rsi(close_series, 14)
    adx_series, pdi_series, mdi_series = calculate_adx_components(data, 14)

    ef, es = float(ef_series.iloc[-1]), float(es_series.iloc[-1])
    atr = float(atr_series.iloc[-1])
    atr_avg = float(atr_series.rolling(50).mean().iloc[-1])
    rsi = float(rsi_series.iloc[-1])
    adx = float(adx_series.iloc[-1])
    pdi, mdi = float(pdi_series.iloc[-1]), float(mdi_series.iloc[-1])
    momentum = float(calculate_momentum(data))
    structure = detect_structure(data)
    trend = detect_trend(data, ema_fast, ema_slow)

    values = [ef, es, atr, atr_avg, rsi, adx, pdi, mdi, momentum]
    if not all(np.isfinite(x) for x in values):
        return neutral

    slope_ok_buy = _trend_slope_ok("BUY", ef_series)
    slope_ok_sell = _trend_slope_ok("SELL", ef_series)
    candle_buy = candle_confirmation(data, "BUY")
    candle_sell = candle_confirmation(data, "SELL")

    buy_candidate = (
        trend == "BULLISH" and ef > es and momentum > 0 and rsi >= 48
        and _mtf_permission("BUY", mtf_confirmation)
    )
    sell_candidate = (
        trend == "BEARISH" and ef < es and momentum < 0 and rsi <= 52
        and _mtf_permission("SELL", mtf_confirmation)
    )

    if buy_candidate and _direction_ok("BUY", pdi, mdi, adx) and slope_ok_buy:
        signal, candle_ok, slope_ok = "BUY", candle_buy, slope_ok_buy
    elif sell_candidate and _direction_ok("SELL", pdi, mdi, adx) and slope_ok_sell:
        signal, candle_ok, slope_ok = "SELL", candle_sell, slope_ok_sell
    else:
        return {
            **neutral, "trend": trend, "structure": structure, "momentum": momentum,
            "atr": atr, "atr_average": atr_avg, "rsi": rsi, "adx": adx,
            "plus_di": pdi, "minus_di": mdi, "ema_fast": ef, "ema_slow": es,
            "reason": "no_high_quality_candidate",
        }

    score = calculate_precision_score(
        signal, trend, structure, momentum, atr, float(close_series.iloc[-1]),
        ef, es, rsi, adx, atr_avg, candle_ok, mtf_confirmation,
        pdi, mdi, slope_ok
    )

    # V7 quality floor. The score is only valid after directional filters pass.
    precision_pass = score >= 75 and precision_entry_filter(
        signal, trend, structure, momentum, atr, float(close_series.iloc[-1]),
        ef, es, rsi, adx, atr_avg, candle_ok, mtf_confirmation,
        pdi, mdi, slope_ok
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
        "atr_average": atr_avg,
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
