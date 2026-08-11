"""
GOLD Precision V13 - strategy.py

Purpose:
- High-selectivity XAUUSD M15 signal engine.
- Uses trend, trend slope, RSI, MACD, ADX/DI, ATR regime,
  candle structure and breakout/pullback confirmation.
- No look-ahead and no live order execution.
- Keeps the public generate_signal() contract used by backtest.py.
"""

from __future__ import annotations
from typing import Optional, Dict, Any
import math


def _ema(values, period):
    if len(values) < period:
        return [None] * len(values)
    out = [None] * (period - 1)
    seed = sum(values[:period]) / period
    out.append(seed)
    k = 2.0 / (period + 1)
    prev = seed
    for x in values[period:]:
        prev = x * k + prev * (1.0 - k)
        out.append(prev)
    return out


def _rsi(values, period=14):
    if len(values) <= period:
        return [None] * len(values)
    out = [None] * period
    gains = [max(values[i] - values[i - 1], 0.0) for i in range(1, period + 1)]
    losses = [max(values[i - 1] - values[i], 0.0) for i in range(1, period + 1)]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    out.append(100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss))

    for i in range(period + 1, len(values)):
        gain = max(values[i] - values[i - 1], 0.0)
        loss = max(values[i - 1] - values[i], 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out.append(100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss))
    return out


def _atr(high, low, close, period=14):
    if len(close) <= period:
        return [None] * len(close)

    tr = [high[0] - low[0]]
    for i in range(1, len(close)):
        tr.append(max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        ))

    out = [None] * (period - 1)
    prev = sum(tr[:period]) / period
    out.append(prev)

    for x in tr[period:]:
        prev = (prev * (period - 1) + x) / period
        out.append(prev)
    return out


def _macd(close):
    fast = _ema(close, 12)
    slow = _ema(close, 26)
    macd = [None if a is None or b is None else a - b for a, b in zip(fast, slow)]

    valid = [x for x in macd if x is not None]
    signal_valid = _ema(valid, 9) if valid else []
    signal = [None] * (len(macd) - len(signal_valid)) + signal_valid
    return macd, signal


def _adx_di(high, low, close, period=14):
    """Wilder-style ADX/+DI/-DI using only completed data in the supplied window."""
    n = len(close)
    if n <= period * 2:
        return [None] * n, [None] * n, [None] * n

    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n

    for i in range(1, n):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        plus_dm[i] = up if up > down and up > 0 else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    atr = sum(tr[1:period + 1]) / period
    p_dm = sum(plus_dm[1:period + 1]) / period
    m_dm = sum(minus_dm[1:period + 1]) / period

    plus_di = [None] * n
    minus_di = [None] * n
    dx = [None] * n

    def set_di(i):
        if atr <= 0:
            return
        p = 100.0 * p_dm / atr
        m = 100.0 * m_dm / atr
        plus_di[i] = p
        minus_di[i] = m
        den = p + m
        dx[i] = 100.0 * abs(p - m) / den if den > 0 else 0.0

    set_di(period)

    for i in range(period + 1, n):
        atr = (atr * (period - 1) + tr[i]) / period
        p_dm = (p_dm * (period - 1) + plus_dm[i]) / period
        m_dm = (m_dm * (period - 1) + minus_dm[i]) / period
        set_di(i)

    adx = [None] * n
    first_dx = [x for x in dx[period:period * 2] if x is not None]
    if len(first_dx) < period:
        return adx, plus_di, minus_di

    adx[period * 2 - 1] = sum(first_dx) / period
    for i in range(period * 2, n):
        if dx[i] is not None and adx[i - 1] is not None:
            adx[i] = (adx[i - 1] * (period - 1) + dx[i]) / period

    return adx, plus_di, minus_di


def _compat_atr(df, period=14):
    if len(df) <= period:
        return None
    highs = [float(x) for x in df["high"]]
    lows = [float(x) for x in df["low"]]
    closes = [float(x) for x in df["close"]]

    trs = [highs[0] - lows[0]]
    for j in range(1, len(closes)):
        trs.append(max(
            highs[j] - lows[j],
            abs(highs[j] - closes[j - 1]),
            abs(lows[j] - closes[j - 1]),
        ))

    value = sum(trs[:period]) / period
    for x in trs[period:]:
        value = (value * (period - 1) + x) / period
    return value


def _safe_float(value, default=0.0):
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _v13_generate_signal(df, min_score=78, rr=1.8, atr_mult=1.6) -> Dict[str, Any]:
    if len(df) < 100:
        return {
            "action": "WAIT", "score": 0.0, "confidence": 0.0,
            "entry": None, "stop_loss": None, "take_profit": None,
            "reason": "Insufficient bars",
        }

    close = [_safe_float(x) for x in df["close"]]
    high = [_safe_float(x) for x in df["high"]]
    low = [_safe_float(x) for x in df["low"]]
    volume = (
        [_safe_float(x) for x in df["volume"]]
        if "volume" in df.columns else [1.0] * len(close)
    )

    ema20 = _ema(close, 20)
    ema50 = _ema(close, 50)
    rsi = _rsi(close, 14)
    atr = _atr(high, low, close, 14)
    macd, macd_sig = _macd(close)
    adx, plus_di, minus_di = _adx_di(high, low, close, 14)

    i = len(close) - 1
    needed = (ema20, ema50, rsi, atr, macd, macd_sig, adx, plus_di, minus_di)
    if any(x[i] is None for x in needed):
        return {
            "action": "WAIT", "score": 0.0, "confidence": 0.0,
            "entry": close[i], "stop_loss": None, "take_profit": None,
            "reason": "Indicators not ready",
        }

    e20 = ema20[i]
    e50 = ema50[i]
    r = rsi[i]
    a = atr[i]
    m = macd[i]
    ms = macd_sig[i]
    ax = adx[i]
    pdi = plus_di[i]
    mdi = minus_di[i]

    if a <= 0 or close[i] <= 0:
        return {
            "action": "WAIT", "score": 0.0, "confidence": 0.0,
            "entry": close[i], "stop_loss": None, "take_profit": None,
            "reason": "Invalid volatility data",
        }

    # Trend slope: require direction, not just EMA20 > EMA50.
    slope_lookback = 5
    e20_prev = ema20[i - slope_lookback]
    e50_prev = ema50[i - slope_lookback]
    slope_buy = e20 > e20_prev and e50 >= e50_prev
    slope_sell = e20 < e20_prev and e50 <= e50_prev

    # Trend separation avoids taking signals while EMAs are almost flat.
    separation = abs(e20 - e50) / a
    trend_buy = e20 > e50 and slope_buy
    trend_sell = e20 < e50 and slope_sell

    buy = 0.0
    sell = 0.0
    buy_reasons = []
    sell_reasons = []

    # 1) Trend direction + slope: 25 points.
    if trend_buy:
        buy += 25
        buy_reasons.append("EMA trend+slope bullish")
    elif trend_sell:
        sell += 25
        sell_reasons.append("EMA trend+slope bearish")

    # 2) Trend separation quality: 5 points.
    if separation >= 0.35:
        if e20 > e50:
            buy += 5
            buy_reasons.append("EMA separation")
        elif e20 < e50:
            sell += 5
            sell_reasons.append("EMA separation")

    # 3) RSI regime: favor continuation, reject overextended entries.
    if 53 <= r <= 66:
        buy += 12
        buy_reasons.append("RSI continuation")
    elif 34 <= r <= 47:
        sell += 12
        sell_reasons.append("RSI continuation")

    # 4) MACD direction + histogram expansion.
    hist = m - ms
    macd_prev = macd[i - 1]
    sig_prev = macd_sig[i - 1]
    hist_prev = macd_prev - sig_prev

    if m > ms and hist >= hist_prev:
        buy += 12
        buy_reasons.append("MACD expanding bullish")
    elif m < ms and hist <= hist_prev:
        sell += 12
        sell_reasons.append("MACD expanding bearish")

    # 5) ADX + directional dominance.
    if ax >= 20:
        if pdi > mdi and pdi - mdi >= 3:
            buy += 16
            buy_reasons.append("ADX/+DI trend")
        elif mdi > pdi and mdi - pdi >= 3:
            sell += 16
            sell_reasons.append("ADX/-DI trend")

    # 6) ATR regime: avoid dead markets and extreme volatility spikes.
    atr_pct = a / close[i]
    atr_window = [x for x in atr[max(0, i - 50):i] if x is not None and x > 0]
    atr_med = sorted(atr_window)[len(atr_window) // 2] if atr_window else a
    volatility_ok = (
        atr_pct > 0
        and a >= atr_med * 0.75
        and a <= atr_med * 1.80
    )
    if volatility_ok:
        if e20 > e50:
            buy += 5
            buy_reasons.append("ATR regime")
        elif e20 < e50:
            sell += 5
            sell_reasons.append("ATR regime")

    # 7) Structure confirmation.
    lookback = 20
    prior_high = max(high[i - lookback:i])
    prior_low = min(low[i - lookback:i])
    candle_range = max(high[i] - low[i], 1e-12)
    body = abs(close[i] - float(df.iloc[i]["open"]))
    close_location = (close[i] - low[i]) / candle_range

    breakout_buy = close[i] > prior_high and close_location >= 0.65 and body >= 0.35 * candle_range
    breakout_sell = close[i] < prior_low and close_location <= 0.35 and body >= 0.35 * candle_range

    # Pullback reclaim is preferred when no fresh breakout exists.
    prev_close = close[i - 1]
    pullback_buy = (
        e20 > e50
        and low[i] <= e20 + 0.20 * a
        and close[i] > e20
        and close[i] > prev_close
    )
    pullback_sell = (
        e20 < e50
        and high[i] >= e20 - 0.20 * a
        and close[i] < e20
        and close[i] < prev_close
    )

    if breakout_buy or pullback_buy:
        buy += 15
        buy_reasons.append("structure confirmation")
    if breakout_sell or pullback_sell:
        sell += 15
        sell_reasons.append("structure confirmation")

    # 8) Volume only adds confirmation; never creates a trade by itself.
    if len(volume) >= 20:
        vavg = sum(volume[i - 19:i]) / 19
        if vavg > 0 and volume[i] >= 1.15 * vavg:
            if buy > sell and (breakout_buy or pullback_buy):
                buy += 5
                buy_reasons.append("volume confirmation")
            elif sell > buy and (breakout_sell or pullback_sell):
                sell += 5
                sell_reasons.append("volume confirmation")

    best = max(buy, sell)
    if buy > sell:
        side = "BUY"
    elif sell > buy:
        side = "SELL"
    else:
        side = "WAIT"

    # Require the structural component and trend component.
    structural = breakout_buy or pullback_buy if side == "BUY" else breakout_sell or pullback_sell
    trend_ok = trend_buy if side == "BUY" else trend_sell

    if side == "WAIT" or best < min_score or not structural or not trend_ok:
        return {
            "action": "WAIT",
            "score": round(best, 2),
            "confidence": round(min(100.0, best), 2),
            "entry": close[i],
            "stop_loss": None,
            "take_profit": None,
            "reason": "Precision gate not satisfied",
        }

    entry = close[i]
    risk = max(a * atr_mult, entry * 0.001)
    sl = entry - risk if side == "BUY" else entry + risk
    tp = entry + risk * rr if side == "BUY" else entry - risk * rr

    return {
        "action": side,
        "score": round(best, 2),
        "confidence": round(min(100.0, best), 2),
        "entry": round(entry, 5),
        "stop_loss": round(sl, 5),
        "take_profit": round(tp, 5),
        "reason": "; ".join(buy_reasons if side == "BUY" else sell_reasons),
        "adx": round(ax, 3),
        "plus_di": round(pdi, 3),
        "minus_di": round(mdi, 3),
    }


def generate_signal(
    df,
    ema_fast=20,
    ema_slow=50,
    atr_period=14,
    mtf_confirmation=None,
    min_score=70,
    **kwargs,
):
    """
    Compatibility adapter for the existing backtest.py.

    Important:
    - ema_fast/ema_slow are accepted for API compatibility.
    - V13 currently uses the production 20/50 trend pair.
    - MTF is intentionally NOT added to the score; backtest.py already
      applies the H1/M15 directional gate after this function.
    """
    result = _v13_generate_signal(
        df,
        min_score=min_score,
        rr=kwargs.get("reward_risk", kwargs.get("rr", 1.8)),
        atr_mult=kwargs.get("atr_sl_multiplier", kwargs.get("atr_mult", 1.6)),
    )

    action = result.get("action", "WAIT")
    score = int(result.get("score", 0))
    signal = action if action in ("BUY", "SELL") else "HOLD"

    mtf = mtf_confirmation or {}
    trends = mtf.get("trends", {}) if isinstance(mtf, dict) else {}
    h1 = trends.get("H1")
    m15 = trends.get("M15")
    mtf_aligned = (
        (signal == "BUY" and h1 == "BUY" and m15 == "BUY")
        or (signal == "SELL" and h1 == "SELL" and m15 == "SELL")
    )

    precision_pass = bool(signal in ("BUY", "SELL") and score >= int(min_score))
    atr = _compat_atr(df, atr_period)
    close = float(df.iloc[-1]["close"])

    # Diagnostics for existing CSV/backtest consumers.
    rsi_value = None
    rsi_series = _rsi([float(x) for x in df["close"]], 14)
    if rsi_series and rsi_series[-1] is not None:
        rsi_value = rsi_series[-1]

    adx_series, pdi_series, mdi_series = _adx_di(
        [float(x) for x in df["high"]],
        [float(x) for x in df["low"]],
        [float(x) for x in df["close"]],
        14,
    )

    adx_value = adx_series[-1]
    pdi_value = pdi_series[-1]
    mdi_value = mdi_series[-1]

    return {
        "signal": signal,
        "precision_score": score,
        "precision_pass": precision_pass,
        "precision_grade": (
            "A+" if score >= 95 else
            "A" if score >= 88 else
            "B" if score >= 78 else
            "C" if score >= 70 else
            "D"
        ),
        "reason": result.get("reason", "V13"),
        "atr": atr,
        "rsi": rsi_value,
        "adx": adx_value,
        "momentum": close - float(df.iloc[-4]["close"]) if len(df) >= 4 else 0.0,
        "atr_average": atr,
        "plus_di": pdi_value,
        "minus_di": mdi_value,
        "mtf_score": mtf.get("score", 0) if isinstance(mtf, dict) else 0,
        "mtf_aligned": mtf_aligned,
    }


def backtest_signals(df, min_score=78, rr=1.8, atr_mult=1.6):
    """Simple non-live evaluator. No parameter fitting or trade execution."""
    results = []
    for end in range(100, len(df)):
        window = df.iloc[:end + 1]
        results.append(
            generate_signal(
                window,
                min_score=min_score,
                reward_risk=rr,
                atr_sl_multiplier=atr_mult,
            )
        )
    return results
