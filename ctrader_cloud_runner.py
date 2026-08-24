"""Scheduled cTrader strategy runner.

Uses the existing V14 strategy on the last CLOSED Yahoo 15-minute candle set.
Execution is disabled unless CTRADER_EXECUTE=true. DEMO is the only supported
execution mode until live validation is completed.
"""

from __future__ import annotations

import os
import sys
from typing import Final

import pandas as pd
import yfinance as yf

from ctrader_cloud import CTraderConfig, CTraderConfigError, run_one_shot_order
from strategy import generate_signal


YAHOO_SYMBOLS: Final[dict[str, str]] = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "USDCHF": "CHF=X",
    "NZDUSD": "NZDUSD=X",
}


def load_closed_bars(symbol: str) -> pd.DataFrame:
    yahoo_symbol = os.getenv("CTRADER_YAHOO_SYMBOL", YAHOO_SYMBOLS.get(symbol, symbol)).strip()
    if not yahoo_symbol:
        raise ValueError("CTRADER_YAHOO_SYMBOL tidak boleh kosong")

    raw = yf.download(
        tickers=yahoo_symbol,
        period="60d",
        interval="15m",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"Tidak ada data untuk {yahoo_symbol}")

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [str(column[0]).lower() for column in raw.columns]
    else:
        raw.columns = [str(column).lower() for column in raw.columns]

    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(raw.columns)
    if missing:
        raise RuntimeError(f"Kolom market data hilang: {sorted(missing)}")

    frame = raw[["open", "high", "low", "close", "volume"]].copy()
    frame = frame.apply(pd.to_numeric, errors="coerce").dropna()
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    if len(frame) < 140:
        raise RuntimeError(f"Bar valid tidak cukup: {len(frame)}")

    # Never evaluate an unfinished candle.
    return frame.iloc[:-1].copy()


def main() -> int:
    symbol = os.getenv("SYMBOL", "EURUSD").strip().upper()
    if symbol not in YAHOO_SYMBOLS and not os.getenv("CTRADER_YAHOO_SYMBOL", "").strip():
        raise ValueError("SYMBOL harus salah satu pair yang didukung atau CTRADER_YAHOO_SYMBOL harus diisi")

    bars = load_closed_bars(symbol)
    signal = generate_signal(
        bars,
        min_score=int(os.getenv("MIN_SCORE", "78")),
        reward_risk=float(os.getenv("REWARD_RISK", "1.8")),
        atr_sl_multiplier=float(os.getenv("ATR_SL_MULTIPLIER", "1.6")),
    )

    print(
        f"symbol={symbol} bars={len(bars)} signal={signal['signal']} "
        f"score={signal['precision_score']} grade={signal['precision_grade']}"
    )
    print(f"reason={signal['reason']}")

    if signal["signal"] not in {"BUY", "SELL"}:
        return 0

    entry = signal.get("entry")
    stop_loss = signal.get("stop_loss")
    take_profit = signal.get("take_profit")
    if not all(isinstance(value, (int, float)) for value in (entry, stop_loss, take_profit)):
        raise RuntimeError("Signal aktif tetapi entry/SL/TP tidak lengkap")

    if os.getenv("CTRADER_EXECUTE", "false").strip().lower() != "true":
        print("Execution disabled: CTRADER_EXECUTE=false")
        return 0

    config = CTraderConfig.from_env()
    run_one_shot_order(
        config,
        str(signal["signal"]),
        float(entry),
        float(stop_loss),
        float(take_profit),
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CTraderConfigError, RuntimeError, ValueError) as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
