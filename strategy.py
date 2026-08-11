"""
FOREX AUTO TRADER PRO - GOLD PRECISION V14

Goal:
- Improve net expectancy and cost robustness after V13 audit.
- Treat BUY and SELL as separate regimes because V13 showed a large
  asymmetry: BUY profitable, SELL negative.
- Keep compatibility with existing backtest.py.
- No live execution, no look-ahead, no parameter fitting in this module.

V14 design:
- BUY: EMA trend + slope + RSI + MACD + ADX/DI + ATR regime +
        structure confirmation.
- SELL: stricter: stronger ADX/DI dominance, stronger EMA separation,
         RSI bearish zone, MACD expansion and BREAKDOWN only.
         A weak SELL pullback is rejected.
"""

from __future__ import annotations
from typing import Dict, Any
import math


def _ema(v, n):
    if len(v) < n:
        return [None] * len(v)
    out = [None] * (n - 1)
    seed = sum(v[:n]) / n
    out.append(seed)
    k = 2.0 / (n + 1)
    p = seed
    for x in v[n:]:
        p = x * k + p * (1.0 - k)
        out.append(p)
    return out


def _rsi(v, n=14):
    if len(v) <= n:
        return [None] * len(v)
    out = [None] * n
    g = [max(v[i] - v[i-1], 0.0) for i in range(1, n + 1)]
    l = [max(v[i-1] - v[i], 0.0) for i in range(1, n + 1)]
    ag = sum(g) / n
    al = sum(l) / n
    out.append(100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al))
    for i in range(n + 1, len(v)):
        gain = max(v[i] - v[i-1], 0.0)
        loss = max(v[i-1] - v[i], 0.0)
        ag = (ag * (n - 1) + gain) / n
        al = (al * (n - 1) + loss) / n
        out.append(100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al))
    return out


def _atr(h, l, c, n=14):
    if len(c) <= n:
        return [None] * len(c)
    tr = [h[0] - l[0]]
    for i in range(1, len(c)):
        tr.append(max(
            h[i] - l[i],
            abs(h[i] - c[i-1]),
            abs(l[i] - c[i-1]),
        ))
    out = [None] * (n - 1)
    p = sum(tr[:n]) / n
    out.append(p)
    for x in tr[n:]:
        p = (p * (n - 1) + x) / n
        out.append(p)
    return out


def _macd(c):
    a = _ema(c, 12)
    b = _ema(c, 26)
    m = [None if x is None or y is None else x - y for x, y in zip(a, b)]
    valid = [x for x in m if x is not None]
    s_valid = _ema(valid, 9) if valid else []
    s = [None] * (len(m) - len(s_valid)) + s_valid
    return m, s


def _adx_di(h, l, c, n=14):
    size = len(c)
    if size <= n * 2:
        return [None] * size, [None] * size, [None] * size

    tr = [0.0] * size
    plus = [0.0] * size
    minus = [0.0] * size

    for i in range(1, size):
        up = h[i] - h[i-1]
        dn = l[i-1] - l[i]
        plus[i] = up if up > dn and up > 0 else 0.0
        minus[i] = dn if dn > up and dn > 0 else 0.0
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))

    atr = sum(tr[1:n+1]) / n
    p_dm = sum(plus[1:n+1]) / n
    m_dm = sum(minus[1:n+1]) / n

    pdi = [None] * size
    mdi = [None] * size
    dx = [None] * size

    def assign(i):
        if atr <= 0:
            return
        p = 100.0 * p_dm / atr
        m = 100.0 * m_dm / atr
        pdi[i], mdi[i] = p, m
        den = p + m
        dx[i] = 100.0 * abs(p - m) / den if den else 0.0

    assign(n)

    for i in range(n + 1, size):
        atr = (atr * (n - 1) + tr[i]) / n
        p_dm = (p_dm * (n - 1) + plus[i]) / n
        m_dm = (m_dm * (n - 1) + minus[i]) / n
        assign(i)

    adx = [None] * size
    first = [x for x in dx[n:n*2] if x is not None]
    if len(first) < n:
        return adx, pdi, mdi

    adx[n*2-1] = sum(first) / n
    for i in range(n*2, size):
        if dx[i] is not None and adx[i-1] is not None:
            adx[i] = (adx[i-1] * (n - 1) + dx[i]) / n

    return adx, pdi, mdi


def _atr_latest(df, period=14):
    h = [float(x) for x in df["high"]]
    l = [float(x) for x in df["low"]]
    c = [float(x) for x in df["close"]]
    a = _atr(h, l, c, period)
    return a[-1] if a and a[-1] is not None else None


def _v14(df, min_score=70, rr=1.8, atr_mult=1.6):
    if len(df) < 120:
        return {"action": "WAIT", "score": 0, "confidence": 0.0,
                "entry": None, "stop_loss": None, "take_profit": None,
                "reason": "Insufficient bars"}

    o = [float(x) for x in df["open"]]
    h = [float(x) for x in df["high"]]
    l = [float(x) for x in df["low"]]
    c = [float(x) for x in df["close"]]
    vol = [float(x) for x in df["volume"]] if "volume" in df.columns else [1.0]*len(c)

    e20 = _ema(c, 20)
    e50 = _ema(c, 50)
    rs = _rsi(c, 14)
    at = _atr(h, l, c, 14)
    mc, ms = _macd(c)
    ax, pdi, mdi = _adx_di(h, l, c, 14)

    i = len(c) - 1
    needed = (e20, e50, rs, at, mc, ms, ax, pdi, mdi)
    if any(x[i] is None for x in needed):
        return {"action": "WAIT", "score": 0, "confidence": 0.0,
                "entry": c[i], "stop_loss": None, "take_profit": None,
                "reason": "Indicators not ready"}

    atr = at[i]
    if atr <= 0 or c[i] <= 0:
        return {"action": "WAIT", "score": 0, "confidence": 0.0,
                "entry": c[i], "stop_loss": None, "take_profit": None,
                "reason": "Invalid ATR"}

    prev_e20 = e20[i-5]
    prev_e50 = e50[i-5]
    sep = abs(e20[i] - e50[i]) / atr
    atr_pct = atr / c[i]

    # Avoid dead and panic-volatility candles.
    atr_hist = [x for x in at[max(0, i-50):i] if x is not None and x > 0]
    atr_med = sorted(atr_hist)[len(atr_hist)//2] if atr_hist else atr
    atr_ok = 0.75 <= atr / atr_med <= 1.70 and 0.00025 <= atr_pct <= 0.02

    trend_buy = e20[i] > e50[i] and e20[i] > prev_e20 and e50[i] >= prev_e50
    trend_sell = e20[i] < e50[i] and e20[i] < prev_e20 and e50[i] <= prev_e50

    prior_hi = max(h[i-20:i])
    prior_lo = min(l[i-20:i])
    rng = max(h[i] - l[i], 1e-12)
    body = abs(c[i] - o[i])
    loc = (c[i] - l[i]) / rng

    buy_break = c[i] > prior_hi and loc >= 0.67 and body >= 0.40 * rng
    sell_break = c[i] < prior_lo and loc <= 0.33 and body >= 0.40 * rng

    buy_pullback = (
        trend_buy and
        l[i] <= e20[i] + 0.15 * atr and
        c[i] > e20[i] and
        c[i] > c[i-1]
    )

    # V14 intentionally does NOT accept weak SELL pullbacks.
    sell_setup = sell_break

    hist = mc[i] - ms[i]
    hist_prev = mc[i-1] - ms[i-1]

    buy = 0
    sell = 0
    buy_reason = []
    sell_reason = []

    if trend_buy:
        buy += 25
        buy_reason.append("trend")
    if trend_sell:
        sell += 25
        sell_reason.append("trend")

    if sep >= 0.35:
        if trend_buy:
            buy += 5
            buy_reason.append("separation")
        if trend_sell:
            sell += 8
            sell_reason.append("strong separation")

    if 53 <= rs[i] <= 67:
        buy += 12
        buy_reason.append("RSI")
    if 33 <= rs[i] <= 46:
        sell += 15
        sell_reason.append("RSI")

    if mc[i] > ms[i] and hist >= hist_prev:
        buy += 12
        buy_reason.append("MACD")
    if mc[i] < ms[i] and hist <= hist_prev:
        sell += 15
        sell_reason.append("MACD")

    if ax[i] >= 20 and pdi[i] - mdi[i] >= 3:
        buy += 16
        buy_reason.append("ADX")
    # SELL requires stronger directional dominance.
    if ax[i] >= 25 and mdi[i] - pdi[i] >= 5:
        sell += 20
        sell_reason.append("ADX")

    if atr_ok:
        if trend_buy:
            buy += 5
            buy_reason.append("ATR")
        if trend_sell:
            sell += 5
            sell_reason.append("ATR")

    if buy_pullback or buy_break:
        buy += 15
        buy_reason.append("structure")

    if sell_setup:
        sell += 18
        sell_reason.append("breakdown")

    if len(vol) >= 20:
        vavg = sum(vol[i-19:i]) / 19
        if vavg > 0 and vol[i] >= 1.10 * vavg:
            if buy > sell and (buy_pullback or buy_break):
                buy += 5
                buy_reason.append("volume")
            elif sell > buy and sell_setup:
                sell += 5
                sell_reason.append("volume")

    side = "BUY" if buy > sell else "SELL" if sell > buy else "WAIT"
    best = max(buy, sell)

    # Side-specific gates.
    buy_pass = (
        side == "BUY"
        and buy >= max(78, min_score)
        and trend_buy
        and atr_ok
        and (buy_pullback or buy_break)
        and rs[i] >= 53
    )

    sell_pass = (
        side == "SELL"
        and sell >= max(86, min_score)
        and trend_sell
        and atr_ok
        and sell_break
        and rs[i] <= 46
        and ax[i] >= 25
        and mdi[i] - pdi[i] >= 5
    )

    if not (buy_pass or sell_pass):
        return {
            "action": "WAIT",
            "score": best,
            "confidence": min(100.0, float(best)),
            "entry": c[i],
            "stop_loss": None,
            "take_profit": None,
            "reason": "V14 side-specific precision gate",
            "adx": ax[i], "plus_di": pdi[i], "minus_di": mdi[i],
        }

    side = "BUY" if buy_pass else "SELL"
    risk = max(atr * atr_mult, c[i] * 0.001)
    sl = c[i] - risk if side == "BUY" else c[i] + risk
    tp = c[i] + risk * rr if side == "BUY" else c[i] - risk * rr

    return {
        "action": side,
        "score": best,
        "confidence": min(100.0, float(best)),
        "entry": round(c[i], 5),
        "stop_loss": round(sl, 5),
        "take_profit": round(tp, 5),
        "reason": "; ".join(buy_reason if side == "BUY" else sell_reason),
        "adx": ax[i], "plus_di": pdi[i], "minus_di": mdi[i],
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
    # Existing backtest.py expects this public signature.
    result = _v14(
        df,
        min_score=min_score,
        rr=kwargs.get("reward_risk", kwargs.get("rr", 1.8)),
        atr_mult=kwargs.get("atr_sl_multiplier", kwargs.get("atr_mult", 1.6)),
    )

    action = result.get("action", "WAIT")
    signal = action if action in ("BUY", "SELL") else "HOLD"
    score = int(result.get("score", 0))

    mtf = mtf_confirmation or {}
    trends = mtf.get("trends", {}) if isinstance(mtf, dict) else {}
    h1 = trends.get("H1")
    m15 = trends.get("M15")

    precision_pass = signal in ("BUY", "SELL") and score >= int(min_score)

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
        "reason": result.get("reason", "V14"),
        "atr": _atr_latest(df, atr_period),
        "rsi": _rsi([float(x) for x in df["close"]], 14)[-1],
        "adx": result.get("adx"),
        "momentum": (
            float(df.iloc[-1]["close"]) - float(df.iloc[-4]["close"])
            if len(df) >= 4 else 0.0
        ),
        "atr_average": _atr_latest(df, atr_period),
        "plus_di": result.get("plus_di"),
        "minus_di": result.get("minus_di"),
        "mtf_score": mtf.get("score", 0) if isinstance(mtf, dict) else 0,
        "mtf_aligned": (
            (signal == "BUY" and h1 == "BUY" and m15 == "BUY")
            or (signal == "SELL" and h1 == "SELL" and m15 == "SELL")
        ),
    }


def backtest_signals(df, min_score=78, rr=1.8, atr_mult=1.6):
    results = []
    for end in range(120, len(df)):
        results.append(
            generate_signal(
                df.iloc[:end+1],
                min_score=min_score,
                reward_risk=rr,
                atr_sl_multiplier=atr_mult,
            )
        )
    return results
