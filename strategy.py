"""
GOLD Precision V12 - strategy.py
Standalone, dependency-light strategy module.

Purpose:
- Generate BUY/SELL/WAIT decisions from OHLCV data.
- Uses EMA trend, RSI, ATR volatility, MACD, ADX, volume and breakout confirmation.
- Designed as a strategy component; it does NOT place live trades.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
import math


@dataclass
class Signal:
    action: str
    score: float
    confidence: float
    entry: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason: str


def _ema(values, period):
    if len(values) < period:
        return [None] * len(values)
    out = [None] * (period - 1)
    seed = sum(values[:period]) / period
    out.append(seed)
    k = 2.0 / (period + 1)
    prev = seed
    for x in values[period:]:
        prev = x * k + prev * (1 - k)
        out.append(prev)
    return out


def _rsi(values, period=14):
    if len(values) <= period:
        return [None] * len(values)
    out = [None] * period
    gains = [max(values[i] - values[i-1], 0.0) for i in range(1, period + 1)]
    losses = [max(values[i-1] - values[i], 0.0) for i in range(1, period + 1)]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    out.append(100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    for i in range(period + 1, len(values)):
        gain = max(values[i] - values[i-1], 0.0)
        loss = max(values[i-1] - values[i], 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out.append(100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss))
    return out


def _atr(high, low, close, period=14):
    if len(close) <= period:
        return [None] * len(close)
    tr = [high[0] - low[0]]
    for i in range(1, len(close)):
        tr.append(max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1])))
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


def _get(row, key, default=0.0):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def generate_signal(df, min_score=78, rr=1.8, atr_mult=1.6) -> Dict[str, Any]:
    """
    Accepts a pandas-like dataframe with columns:
    open, high, low, close and optionally volume.
    Returns a dict with action, score, confidence and trade levels.
    """
    if len(df) < 80:
        return {"action": "WAIT", "score": 0.0, "confidence": 0.0,
                "reason": "Insufficient bars"}

    close = [float(x) for x in df["close"]]
    high = [float(x) for x in df["high"]]
    low = [float(x) for x in df["low"]]
    volume = [float(x) for x in df["volume"]] if "volume" in df.columns else [1.0] * len(close)

    ef = _ema(close, 20)
    es = _ema(close, 50)
    rsi = _rsi(close, 14)
    atr = _atr(high, low, close, 14)
    macd, macd_sig = _macd(close)

    i = len(close) - 1
    if any(x[i] is None for x in (ef, es, rsi, atr, macd, macd_sig)):
        return {"action": "WAIT", "score": 0.0, "confidence": 0.0,
                "reason": "Indicators not ready"}

    score_buy = 0.0
    score_sell = 0.0
    reasons_buy = []
    reasons_sell = []

    # Trend: strongest component.
    if ef[i] > es[i]:
        score_buy += 25
        reasons_buy.append("EMA20>EMA50")
    elif ef[i] < es[i]:
        score_sell += 25
        reasons_sell.append("EMA20<EMA50")

    # Momentum, avoiding extreme chasing.
    if 52 <= rsi[i] <= 68:
        score_buy += 15
        reasons_buy.append("RSI bullish")
    elif 32 <= rsi[i] <= 48:
        score_sell += 15
        reasons_sell.append("RSI bearish")

    # MACD confirmation.
    if macd[i] > macd_sig[i]:
        score_buy += 15
        reasons_buy.append("MACD bullish")
    elif macd[i] < macd_sig[i]:
        score_sell += 15
        reasons_sell.append("MACD bearish")

    # Volatility/tradeability.
    atr_pct = atr[i] / close[i] if close[i] else 0
    if atr_pct > 0:
        if close[i] > ef[i]:
            score_buy += 10
            reasons_buy.append("price above EMA20")
        elif close[i] < ef[i]:
            score_sell += 10
            reasons_sell.append("price below EMA20")

    # Recent breakout confirmation.
    lookback = min(20, i)
    prior_high = max(high[i-lookback:i])
    prior_low = min(low[i-lookback:i])
    if close[i] > prior_high:
        score_buy += 20
        reasons_buy.append("breakout")
    elif close[i] < prior_low:
        score_sell += 20
        reasons_sell.append("breakdown")

    # Volume confirmation, if meaningful.
    if len(volume) >= 20:
        vavg = sum(volume[i-19:i+1]) / 20
        if vavg > 0 and volume[i] >= 1.2 * vavg:
            if score_buy > score_sell:
                score_buy += 10
                reasons_buy.append("volume confirmation")
            elif score_sell > score_buy:
                score_sell += 10
                reasons_sell.append("volume confirmation")

    best = max(score_buy, score_sell)
    side = "BUY" if score_buy > score_sell else "SELL" if score_sell > score_buy else "WAIT"

    if side == "WAIT" or best < min_score:
        return {
            "action": "WAIT",
            "score": round(best, 2),
            "confidence": round(min(100.0, best), 2),
            "entry": close[i],
            "stop_loss": None,
            "take_profit": None,
            "reason": "Confirmation threshold not reached",
        }

    entry = close[i]
    risk = max(atr[i] * atr_mult, entry * 0.001)
    sl = entry - risk if side == "BUY" else entry + risk
    tp = entry + risk * rr if side == "BUY" else entry - risk * rr

    return {
        "action": side,
        "score": round(best, 2),
        "confidence": round(min(100.0, best), 2),
        "entry": round(entry, 5),
        "stop_loss": round(sl, 5),
        "take_profit": round(tp, 5),
        "reason": "; ".join(reasons_buy if side == "BUY" else reasons_sell),
    }


def backtest_signals(df, min_score=78, rr=1.8, atr_mult=1.6):
    """Simple non-live evaluator. No parameter fitting or trade execution."""
    results = []
    for end in range(80, len(df)):
        window = df.iloc[:end + 1]
        results.append(generate_signal(window, min_score=min_score, rr=rr, atr_mult=atr_mult))
    return results


if __name__ == "__main__":
    print("GOLD Precision V12 strategy module loaded.")
    print("Live trading is disabled in this file.")
