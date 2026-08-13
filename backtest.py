import pandas as pd
import numpy as np

from strategy import generate_signal
from mtf import timeframe_trend, calculate_mtf_score


def _empty_backtest_result():
    return {
        "trades": [], "total_trades": 0, "wins": 0, "losses": 0,
        "win_rate": 0.0, "profit_factor": 0.0, "net_r": 0.0,
        "expectancy_r": 0.0,
    }


def _resample_from_m15(df, bars_per_candle):
    if df is None or len(df) == 0:
        return pd.DataFrame()
    data = df.copy().reset_index(drop=True)
    if "time" in data.columns:
        data["time"] = pd.to_datetime(data["time"], errors="coerce")
        data = data.dropna(subset=["time"])
        if len(data) == 0:
            return pd.DataFrame()
        data["_hour"] = data["time"].dt.floor("h")
        grouped = data.groupby("_hour", sort=True)
        counts = grouped.size()
        complete = counts[counts >= bars_per_candle].index
        if len(complete) == 0:
            return pd.DataFrame()
        return grouped.agg({
            "open": "first", "high": "max", "low": "min", "close": "last"
        }).loc[complete].reset_index(drop=True)
    gid = np.arange(len(data)) // bars_per_candle
    return data.groupby(gid, sort=True).agg({
        "open": "first", "high": "max", "low": "min", "close": "last"
    }).reset_index(drop=True)


def _build_m1_proxy(m15):
    if m15 is None or len(m15) == 0:
        return pd.DataFrame()
    rows = []
    for _, c in m15.iterrows():
        o, h, l, cl = map(float, (c["open"], c["high"], c["low"], c["close"]))
        path = np.linspace(o, cl, 15)
        for j, current in enumerate(path):
            previous = o if j == 0 else float(path[j - 1])
            rows.append({
                "open": previous,
                "high": max(previous, float(current), h if j == 14 else previous),
                "low": min(previous, float(current), l if j == 14 else previous),
                "close": float(current),
            })
    return pd.DataFrame(rows)


def _build_mtf_confirmation(history):
    neutral = {"H1": "HOLD", "M15": "HOLD", "M1": "HOLD"}
    if history is None or len(history) < 120:
        return {"trends": neutral, "score": 0, "status": "NEUTRAL"}

    m15 = history.copy().reset_index(drop=True)
    h1 = _resample_from_m15(m15, 4)

    # Performance optimization: only build the synthetic M1 proxy from
    # a recent window. The old version rebuilt M1 from the full history
    # on every backtest candle, causing unnecessary CI workload.
    m1_source = m15.tail(160).reset_index(drop=True)
    m1 = _build_m1_proxy(m1_source)

    trends = {
        "H1": timeframe_trend(h1, fast_period=20, slow_period=50),
        "M15": timeframe_trend(m15, fast_period=20, slow_period=50),
        "M1": timeframe_trend(m1, fast_period=20, slow_period=50),
    }
    score = calculate_mtf_score(trends)

    if trends["H1"] == trends["M15"] == trends["M1"] == "BUY":
        status = "STRONG_BUY"
    elif trends["H1"] == trends["M15"] == trends["M1"] == "SELL":
        status = "STRONG_SELL"
    elif trends["H1"] == trends["M15"] == "BUY":
        status = "BUY_CONFIRMED_H1_M15"
    elif trends["H1"] == trends["M15"] == "SELL":
        status = "SELL_CONFIRMED_H1_M15"
    else:
        status = "NEUTRAL"
    return {"trends": trends, "score": int(score), "status": status}


def _trade_outcome(data, entry_index, signal, entry, sl, tp):
    for j in range(entry_index, len(data)):
        c = data.iloc[j]
        high, low = float(c["high"]), float(c["low"])
        if signal == "BUY":
            hit_sl, hit_tp = low <= sl, high >= tp
        else:
            hit_sl, hit_tp = high >= sl, low <= tp
        if hit_sl and hit_tp:
            return "LOSS", sl, j
        if hit_sl:
            return "LOSS", sl, j
        if hit_tp:
            return "WIN", tp, j
    return None, None, None


def backtest_strategy(
    df, ema_fast=20, ema_slow=50, atr_period=14,
    atr_sl_multiplier=1.5, reward_risk=2.0, min_score=70
):
    if df is None or len(df) < ema_slow + 100:
        return _empty_backtest_result()

    data = df.copy().reset_index(drop=True)
    trades = []
    next_available = ema_slow + 100

    # V7: non-overlapping trades. A new trade cannot open while the prior one is active.
    for i in range(ema_slow + 100, len(data) - 1):
        if i < next_available:
            continue

        history = data.iloc[:i + 1].copy().reset_index(drop=True)
        mtf = _build_mtf_confirmation(history)
        result = generate_signal(
            history, ema_fast=ema_fast, ema_slow=ema_slow,
            atr_period=atr_period, mtf_confirmation=mtf,
            # IMPORTANT: propagate the backtest candidate's score gate into
            # the canonical signal engine. Without this, candidate runs such
            # as S79/S80 were scored after signal generation, while the engine
            # itself still evaluated the default min_score=70 gate.
            min_score=min_score,
        )

        signal = result.get("signal", "HOLD")
        score = int(result.get("precision_score", 0))
        if signal == "HOLD" or not result.get("precision_pass", False) or score < min_score:
            continue

        trends = mtf.get("trends", {})
        h1, m15, m1 = trends.get("H1"), trends.get("M15"), trends.get("M1")
        if signal == "BUY" and not (h1 == "BUY" and m15 == "BUY"):
            continue
        if signal == "SELL" and not (h1 == "SELL" and m15 == "SELL"):
            continue

        atr = result.get("atr")
        if atr is None or not np.isfinite(float(atr)) or float(atr) <= 0:
            continue

        entry_index = i + 1
        entry = float(data.iloc[entry_index]["open"])
        sl_distance = float(atr) * atr_sl_multiplier

        if signal == "BUY":
            sl, tp = entry - sl_distance, entry + sl_distance * reward_risk
            mtf_status = "STRONG_BUY" if m1 == "BUY" else "BUY_CONFIRMED_H1_M15"
        else:
            sl, tp = entry + sl_distance, entry - sl_distance * reward_risk
            mtf_status = "STRONG_SELL" if m1 == "SELL" else "SELL_CONFIRMED_H1_M15"

        outcome, exit_price, exit_index = _trade_outcome(
            data, entry_index, signal, entry, sl, tp
        )
        if outcome is None:
            continue

        r = reward_risk if outcome == "WIN" else -1.0
        trades.append({
            "index": i, "entry_index": entry_index, "exit_index": exit_index,
            "signal": signal, "entry": entry, "stop_loss": sl,
            "take_profit": tp, "exit": exit_price, "outcome": outcome,
            "r_multiple": r, "rsi": result.get("rsi"), "adx": result.get("adx"),
            "momentum": result.get("momentum"), "atr": float(atr),
            "atr_average": result.get("atr_average"),
            "precision_score": score, "precision_grade": result.get("precision_grade"),
            "precision_pass": True, "mtf_score": mtf.get("score", 0),
            "mtf_status": mtf_status, "mtf_h1": h1, "mtf_m15": m15, "mtf_m1": m1,
            "plus_di": result.get("plus_di"), "minus_di": result.get("minus_di"),
        })
        next_available = exit_index + 1

    total = len(trades)
    wins = sum(t["outcome"] == "WIN" for t in trades)
    losses = total - wins
    gross_profit = sum(t["r_multiple"] for t in trades if t["r_multiple"] > 0)
    gross_loss = abs(sum(t["r_multiple"] for t in trades if t["r_multiple"] < 0))
    net_r = sum(t["r_multiple"] for t in trades)
    pf = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit else 0.0)

    return {
        "trades": trades, "total_trades": total, "wins": wins, "losses": losses,
        "win_rate": round((wins / total) * 100, 2) if total else 0.0,
        "profit_factor": round(pf, 3) if np.isfinite(pf) else pf,
        "net_r": round(net_r, 4),
        "expectancy_r": round(net_r / total, 4) if total else 0.0,
    }


def analyze_grades(trades):
    result = {}
    for grade in ("A+", "A", "B", "C", "D"):
        subset = [t for t in trades if t.get("precision_grade") == grade]
        wins = sum(t.get("outcome") == "WIN" for t in subset)
        result[grade] = {
            "trades": len(subset), "wins": wins,
            "win_rate": (wins / len(subset) * 100) if subset else 0.0
        }
    return result


def analyze_signals(trades):
    result = {}
    for signal in ("BUY", "SELL"):
        subset = [t for t in trades if t.get("signal") == signal]
        wins = sum(t.get("outcome") == "WIN" for t in subset)
        result[signal] = {
            "trades": len(subset), "wins": wins,
            "win_rate": (wins / len(subset) * 100) if subset else 0.0
        }
    return result
