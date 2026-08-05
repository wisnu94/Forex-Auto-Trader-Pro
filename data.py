import pandas as pd
import numpy as np

# ============================================================
# FOREX AUTO TRADER PRO
# REAL MARKET DATA ENGINE
#
# PRIMARY SOURCE:
# Yahoo Finance
#
# SYMBOL:
# EURUSD=X
#
# GitHub Actions compatible
# Tidak membutuhkan MetaTrader 5
# ============================================================


# ============================================================
# SYMBOL MAP
# ============================================================

SYMBOL_MAP = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "JPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "CAD=X",
    "USDCHF": "CHF=X",
    "NZDUSD": "NZDUSD=X",
}


# ============================================================
# TIMEFRAME MAP
# ============================================================

TIMEFRAME_MAP = {
    "M1": "1m",
    "M5": "5m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "1h",
    "D1": "1d",
}


# ============================================================
# YAHOO RANGE LIMIT
# ============================================================

def _get_period(timeframe):

    if timeframe == "M1":
        return "7d"

    if timeframe in ["M5", "M15", "M30"]:
        return "60d"

    if timeframe == "H1":
        return "730d"

    if timeframe == "H4":
        return "730d"

    if timeframe == "D1":
        return "10y"

    return "60d"


# ============================================================
# NORMALIZE SYMBOL
# ============================================================

def normalize_symbol(symbol):

    symbol = str(symbol).upper().strip()

    return SYMBOL_MAP.get(
        symbol,
        symbol
    )


# ============================================================
# GET MARKET DATA
# ============================================================

def get_bars(
    symbol: str,
    timeframe: str,
    count: int = 3000
) -> pd.DataFrame:

    symbol = normalize_symbol(symbol)

    timeframe = str(
        timeframe
    ).upper().strip()

    if timeframe not in TIMEFRAME_MAP:

        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    try:

        import yfinance as yf

    except ImportError:

        raise RuntimeError(
            "yfinance belum terinstall. "
            "Tambahkan yfinance ke requirements.txt"
        )

    interval = TIMEFRAME_MAP[
        timeframe
    ]

    period = _get_period(
        timeframe
    )

    print(
        f"Downloading real market data: "
        f"{symbol} {timeframe}"
    )

    print(
        f"Yahoo interval: {interval}"
    )

    print(
        f"Yahoo period  : {period}"
    )

    # --------------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------------

    df = yf.download(
        tickers=symbol,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )

    if df is None or len(df) == 0:

        raise RuntimeError(
            f"Yahoo Finance tidak mengembalikan "
            f"data untuk {symbol} {timeframe}"
        )

    # --------------------------------------------------------
    # NORMALIZE MULTIINDEX
    # --------------------------------------------------------

    if isinstance(
        df.columns,
        pd.MultiIndex
    ):

        df.columns = [
            column[0]
            for column in df.columns
        ]

    # --------------------------------------------------------
    # RESET INDEX
    # --------------------------------------------------------

    df = df.reset_index()

    # --------------------------------------------------------
    # NORMALIZE TIME
    # --------------------------------------------------------

    if "Datetime" in df.columns:

        df = df.rename(
            columns={
                "Datetime": "time"
            }
        )

    elif "Date" in df.columns:

        df = df.rename(
            columns={
                "Date": "time"
            }
        )

    # --------------------------------------------------------
    # REQUIRED COLUMNS
    # --------------------------------------------------------

    required = [
        "open",
        "high",
        "low",
        "close",
    ]

    df.columns = [
        str(column).lower()
        for column in df.columns
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:

        raise RuntimeError(
            f"Data market tidak lengkap. "
            f"Missing columns: {missing}"
        )

    # --------------------------------------------------------
    # KEEP REQUIRED DATA
    # --------------------------------------------------------

    columns = [
        "time",
        "open",
        "high",
        "low",
        "close",
    ]

    optional_columns = [
        "volume"
    ]

    for column in optional_columns:

        if column in df.columns:

            columns.append(
                column
            )

    df = df[
        columns
    ].copy()

    # --------------------------------------------------------
    # RENAME VOLUME
    # --------------------------------------------------------

    if "volume" in df.columns:

        df = df.rename(
            columns={
                "volume":
                    "tick_volume"
            }
        )

    else:

        df["tick_volume"] = 0

    # --------------------------------------------------------
    # REAL VOLUME PLACEHOLDER
    #
    # Forex Yahoo data tidak memiliki
    # centralized real volume.
    # --------------------------------------------------------

    df["real_volume"] = 0

    # --------------------------------------------------------
    # SPREAD PLACEHOLDER
    #
    # Yahoo historical candles tidak
    # menyediakan bid/ask spread.
    # --------------------------------------------------------

    df["spread"] = 0

    # --------------------------------------------------------
    # NUMERIC
    # --------------------------------------------------------

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        "real_volume",
        "spread",
    ]

    for column in numeric_columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    # --------------------------------------------------------
    # REMOVE INVALID
    # --------------------------------------------------------

    df = df.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close",
        ]
    )

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    df = df.sort_values(
        "time"
    )

    df = df.drop_duplicates(
        subset=["time"]
    )

    df = df.reset_index(
        drop=True
    )

    # --------------------------------------------------------
    # LIMIT COUNT
    #
    # Ambil candle terbaru sebanyak count.
    # --------------------------------------------------------

    if count > 0 and len(df) > count:

        df = df.tail(
            count
        ).reset_index(
            drop=True
        )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if len(df) == 0:

        raise RuntimeError(
            f"Data kosong setelah validasi: "
            f"{symbol} {timeframe}"
        )

    print(
        f"Downloaded real bars: "
        f"{len(df)} {timeframe}"
    )

    print(
        f"First candle: "
        f"{df.iloc[0]['time']}"
    )

    print(
        f"Last candle : "
        f"{df.iloc[-1]['time']}"
    )

    return df


# ============================================================
# GET CURRENT PRICE
#
# Digunakan oleh live engine.
# ============================================================

def get_tick(symbol):

    symbol = normalize_symbol(
        symbol
    )

    try:

        import yfinance as yf

    except ImportError:

        raise RuntimeError(
            "yfinance belum terinstall."
        )

    ticker = yf.Ticker(
        symbol
    )

    data = ticker.history(
        period="1d",
        interval="1m"
    )

    if data is None or len(data) == 0:

        raise RuntimeError(
            f"Tidak dapat mengambil tick "
            f"{symbol}"
        )

    last = data.iloc[-1]

    price = float(
        last["Close"]
    )

    return {
        "bid": price,
        "ask": price,
        "last": price,
    }


# ============================================================
# GET SPREAD
#
# Yahoo historical data tidak memiliki
# bid/ask spread.
# ============================================================

def get_spread_points(
    symbol: str
) -> float:

    return 0.0


# ============================================================
# CLOSE CONNECTION
#
# Compatibility function.
# Tidak diperlukan untuk Yahoo Finance.
# ============================================================

def shutdown():

    return True