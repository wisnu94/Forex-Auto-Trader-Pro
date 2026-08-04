import MetaTrader5 as mt5
import pandas as pd

# ============================================================
# MT5 TIMEFRAME MAP
# ============================================================

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


# ============================================================
# INITIALIZE MT5
# ============================================================

def initialize_mt5():
    """
    Connect to MetaTrader 5.
    """

    if not mt5.initialize():
        raise RuntimeError(
            f"MT5 initialize failed: {mt5.last_error()}"
        )

    return True


# ============================================================
# GET MARKET DATA
# ============================================================

def get_bars(
    symbol: str,
    timeframe: str,
    count: int = 300
) -> pd.DataFrame:

    if timeframe not in TIMEFRAMES:
        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    initialize_mt5()

    # Pastikan symbol tersedia
    symbol_info = mt5.symbol_info(symbol)

    if symbol_info is None:
        raise RuntimeError(
            f"Symbol tidak ditemukan di MT5: {symbol}"
        )

    # Aktifkan symbol jika belum aktif
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(
                f"Gagal mengaktifkan symbol: {symbol}"
            )

    rates = mt5.copy_rates_from_pos(
        symbol,
        TIMEFRAMES[timeframe],
        0,
        count
    )

    if rates is None:
        raise RuntimeError(
            f"Gagal mengambil data {symbol}: "
            f"{mt5.last_error()}"
        )

    if len(rates) == 0:
        raise RuntimeError(
            f"Tidak ada data untuk {symbol}"
        )

    df = pd.DataFrame(rates)

    # Convert Unix timestamp
    df["time"] = pd.to_datetime(
        df["time"],
        unit="s"
    )

    # Pastikan urutan waktu
    df = df.sort_values("time")

    # Reset index
    df = df.reset_index(drop=True)

    return df


# ============================================================
# GET CURRENT PRICE
# ============================================================

def get_tick(symbol: str):

    initialize_mt5()

    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        raise RuntimeError(
            f"Tidak dapat mengambil tick {symbol}: "
            f"{mt5.last_error()}"
        )

    return tick


# ============================================================
# GET SPREAD
# ============================================================

def get_spread_points(symbol: str) -> float:

    initialize_mt5()

    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if info is None or tick is None:
        raise RuntimeError(
            f"Gagal mendapatkan spread {symbol}"
        )

    spread = (
        tick.ask - tick.bid
    ) / info.point

    return float(spread)