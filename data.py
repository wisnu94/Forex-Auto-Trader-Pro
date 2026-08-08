import os
from types import SimpleNamespace

import pandas as pd

from config import (
    DATA_SOURCE,
    MT5_PATH,
    MT5_LOGIN,
    MT5_PASSWORD,
    MT5_SERVER,
)

# ============================================================
# MARKET DATA V8
# MT5 = production/live.
# Yahoo = CI/backtest compatibility only.
# ============================================================

YAHOO_SYMBOL_MAP = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "USDCHF": "CHF=X",
    "NZDUSD": "NZDUSD=X",
    # Yahoo proxy only. This is gold futures, not broker spot XAUUSD.
    "XAUUSD": "GC=F",
}


def _load_mt5():
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise RuntimeError(
            "MetaTrader5 belum terinstall. Untuk bot MT5 gunakan Windows/VPS: "
            "pip install MetaTrader5"
        ) from exc
    return mt5


def initialize_mt5():
    mt5 = _load_mt5()

    if mt5.terminal_info() is not None:
        return mt5

    kwargs = {}
    if MT5_LOGIN:
        kwargs["login"] = int(MT5_LOGIN)
    if MT5_PASSWORD:
        kwargs["password"] = MT5_PASSWORD
    if MT5_SERVER:
        kwargs["server"] = MT5_SERVER

    ok = (
        mt5.initialize(MT5_PATH, **kwargs)
        if MT5_PATH
        else mt5.initialize(**kwargs)
    )

    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    return mt5


def _mt5_timeframe(mt5, timeframe):
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    name = str(timeframe).upper().strip()
    if name not in mapping:
        raise ValueError(f"Unsupported MT5 timeframe: {name}")
    return mapping[name]


def _normalize(df):
    if df is None or len(df) == 0:
        raise RuntimeError("Market data kosong.")

    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]

    required = ["time", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Kolom market data hilang: {missing}")

    for col in ["open", "high", "low", "close", "tick_volume", "real_volume", "spread"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "tick_volume" not in df.columns:
        df["tick_volume"] = 0
    if "real_volume" not in df.columns:
        df["real_volume"] = 0
    if "spread" not in df.columns:
        df["spread"] = 0

    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
    df = df.dropna(subset=required)
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)

    invalid = (
        (df["high"] < df["low"])
        | (df["high"] < df["open"])
        | (df["high"] < df["close"])
        | (df["low"] > df["open"])
        | (df["low"] > df["close"])
    )

    if bool(invalid.any()):
        raise RuntimeError(f"Invalid OHLC rows: {int(invalid.sum())}")

    return df[
        [
            "time",
            "open",
            "high",
            "low",
            "close",
            "tick_volume",
            "real_volume",
            "spread",
        ]
    ]


def _get_bars_mt5(symbol, timeframe, count):
    mt5 = initialize_mt5()
    symbol = str(symbol).upper().strip()

    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(
            f"MT5 symbol '{symbol}' tidak ditemukan. "
            "Gunakan nama symbol persis dari broker, misalnya XAUUSD/XAUUSDm."
        )

    if not info.visible and not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Gagal mengaktifkan symbol MT5: {symbol}")

    rates = mt5.copy_rates_from_pos(
        symbol,
        _mt5_timeframe(mt5, timeframe),
        0,
        int(count),
    )

    if rates is None or len(rates) == 0:
        raise RuntimeError(
            f"MT5 tidak mengembalikan bar: {symbol} {timeframe}; "
            f"error={mt5.last_error()}"
        )

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)

    return _normalize(df)


def _get_bars_yahoo(symbol, timeframe, count):
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance belum terinstall.") from exc

    symbol = str(symbol).upper().strip()
    timeframe = str(timeframe).upper().strip()

    yahoo_symbol = YAHOO_SYMBOL_MAP.get(symbol, symbol)

    interval_map = {
        "M1": "1m",
        "M5": "5m",
        "M15": "15m",
        "M30": "30m",
        "H1": "1h",
        "H4": "1h",
        "D1": "1d",
    }

    period_map = {
        "M1": "7d",
        "M5": "60d",
        "M15": "60d",
        "M30": "60d",
        "H1": "730d",
        "H4": "730d",
        "D1": "10y",
    }

    if timeframe not in interval_map:
        raise ValueError(f"Unsupported Yahoo timeframe: {timeframe}")

    df = yf.download(
        tickers=yahoo_symbol,
        period=period_map[timeframe],
        interval=interval_map[timeframe],
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df is None or len(df) == 0:
        raise RuntimeError(f"Yahoo Finance tidak mengembalikan data: {yahoo_symbol}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    df = df.reset_index()

    if "Datetime" in df.columns:
        df = df.rename(columns={"Datetime": "time"})
    elif "Date" in df.columns:
        df = df.rename(columns={"Date": "time"})

    df.columns = [str(c).lower() for c in df.columns]

    if "volume" in df.columns:
        df = df.rename(columns={"volume": "tick_volume"})

    df["real_volume"] = 0
    df["spread"] = 0

    df = _normalize(df)

    if count > 0 and len(df) > count:
        df = df.tail(int(count)).reset_index(drop=True)

    return df


def get_bars(symbol, timeframe, count=3000, source=None):
    source = str(source or DATA_SOURCE).upper().strip()

    if source == "MT5":
        return _get_bars_mt5(symbol, timeframe, count)

    if source == "YAHOO":
        return _get_bars_yahoo(symbol, timeframe, count)

    raise ValueError("DATA_SOURCE harus MT5 atau YAHOO")


def get_tick(symbol):
    mt5 = initialize_mt5()
    symbol = str(symbol).upper().strip()

    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Gagal mengaktifkan symbol: {symbol}")

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Tidak mendapatkan tick MT5: {symbol}")

    return tick


def get_spread_points(symbol):
    mt5 = initialize_mt5()
    symbol = str(symbol).upper().strip()

    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if info is None or tick is None or info.point <= 0:
        return 0.0

    return float((tick.ask - tick.bid) / info.point)


def shutdown():
    try:
        mt5 = _load_mt5()
        mt5.shutdown()
    except Exception:
        pass
