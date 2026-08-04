import MetaTrader5 as mt5

from config import (
    TRADING_MODE,
    ALLOW_LIVE_TRADING,
    MAX_SPREAD_POINTS,
)


# ============================================================
# MT5 INITIALIZATION
# ============================================================

def initialize_mt5():

    if not mt5.initialize():

        raise RuntimeError(
            f"MT5 initialize failed: "
            f"{mt5.last_error()}"
        )

    return True


# ============================================================
# SYMBOL INFORMATION
# ============================================================

def get_symbol_info(symbol):

    initialize_mt5()

    info = mt5.symbol_info(symbol)

    if info is None:

        raise RuntimeError(
            f"Symbol tidak ditemukan: {symbol}"
        )

    if not info.visible:

        if not mt5.symbol_select(
            symbol,
            True
        ):

            raise RuntimeError(
                f"Gagal mengaktifkan symbol: {symbol}"
            )

    return info


# ============================================================
# CURRENT PRICE
# ============================================================

def get_current_price(
    symbol,
    signal
):

    initialize_mt5()

    tick = mt5.symbol_info_tick(
        symbol
    )

    if tick is None:

        raise RuntimeError(
            f"Tidak mendapatkan tick: {symbol}"
        )

    if signal == "BUY":

        return float(tick.ask)

    if signal == "SELL":

        return float(tick.bid)

    raise ValueError(
        "Signal harus BUY atau SELL"
    )


# ============================================================
# SPREAD PROTECTION
# ============================================================

def check_spread(symbol):

    info = get_symbol_info(symbol)

    tick = mt5.symbol_info_tick(
        symbol
    )

    if tick is None:

        return False, 0.0

    spread_points = (
        tick.ask - tick.bid
    ) / info.point

    if spread_points > MAX_SPREAD_POINTS:

        return (
            False,
            float(spread_points)
        )

    return (
        True,
        float(spread_points)
    )


# ============================================================
# VOLUME NORMALIZATION
# ============================================================

def normalize_volume(
    symbol,
    volume
):

    info = get_symbol_info(symbol)

    volume_min = info.volume_min
    volume_max = info.volume_max
    volume_step = info.volume_step

    if volume <= 0:

        return 0.0

    volume = min(
        volume,
        volume_max
    )

    # Round DOWN to broker step
    steps = int(
        volume / volume_step
    )

    normalized = (
        steps * volume_step
    )

    if normalized < volume_min:

        return 0.0

    return float(
        round(normalized, 8)
    )


# ============================================================
# PRICE NORMALIZATION
# ============================================================

def normalize_price(
    symbol,
    price
):

    info = get_symbol_info(symbol)

    return float(
        round(
            price,
            info.digits
        )
    )


# ============================================================
# OPEN POSITION COUNT
# ============================================================

def get_open_positions(
    symbol=None
):

    initialize_mt5()

    if symbol:

        positions = mt5.positions_get(
            symbol=symbol
        )

    else:

        positions = mt5.positions_get()

    if positions is None:

        return []

    return list(positions)


# ============================================================
# PAPER EXECUTION
# ============================================================

def paper_order(
    symbol,
    signal,
    volume,
    entry,
    stop_loss,
    take_profit
):

    return {
        "status": "PAPER",
        "symbol": symbol,
        "signal": signal,
        "volume": volume,
        "entry": entry,
        "sl": stop_loss,
        "tp": take_profit,
        "message": "Order simulated. No broker order sent."
    }


# ============================================================
# LIVE ORDER
# ============================================================

def send_market_order(
    symbol,
    signal,
    volume,
    stop_loss,
    take_profit,
    magic=260805
):

    # --------------------------------------------------------
    # HARD SAFETY LOCK
    # --------------------------------------------------------

    if TRADING_MODE == "LIVE":

        if not ALLOW_LIVE_TRADING:

            raise RuntimeError(
                "LIVE TRADING masih DIKUNCI."
            )

    # --------------------------------------------------------
    # PAPER MODE
    # --------------------------------------------------------

    if TRADING_MODE == "PAPER":

        entry = get_current_price(
            symbol,
            signal
        )

        return paper_order(
            symbol,
            signal,
            volume,
            entry,
            stop_loss,
            take_profit
        )

    # --------------------------------------------------------
    # DEMO / LIVE
    # --------------------------------------------------------

    initialize_mt5()

    allowed, spread = check_spread(
        symbol
    )

    if not allowed:

        return {
            "status": "REJECTED",
            "reason": (
                f"Spread terlalu besar: "
                f"{spread:.1f} points"
            )
        }

    volume = normalize_volume(
        symbol,
        volume
    )

    if volume <= 0:

        return {
            "status": "REJECTED",
            "reason": "Invalid volume"
        }

    entry = get_current_price(
        symbol,
        signal
    )

    info = get_symbol_info(
        symbol
    )

    stop_loss = normalize_price(
        symbol,
        stop_loss
    )

    take_profit = normalize_price(
        symbol,
        take_profit
    )

    if signal == "BUY":

        order_type = mt5.ORDER_TYPE_BUY

    elif signal == "SELL":

        order_type = mt5.ORDER_TYPE_SELL

    else:

        return {
            "status": "REJECTED",
            "reason": "Invalid signal"
        }

    request = {

        "action":
            mt5.TRADE_ACTION_DEAL,

        "symbol":
            symbol,

        "volume":
            volume,

        "type":
            order_type,

        "price":
            entry,

        "sl":
            stop_loss,

        "tp":
            take_profit,

        "deviation":
            20,

        "magic":
            magic,

        "comment":
            "ForexAutoTraderPro",

        "type_time":
            mt5.ORDER_TIME_GTC,

        "type_filling":
            mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(
        request
    )

    if result is None:

        return {
            "status": "ERROR",
            "reason": str(
                mt5.last_error()
            )
        }

    if result.retcode != mt5.TRADE_RETCODE_DONE:

        return {
            "status": "REJECTED",
            "retcode": result.retcode,
            "comment": result.comment
        }

    return {
        "status": "EXECUTED",
        "ticket": result.order,
        "symbol": symbol,
        "signal": signal,
        "volume": volume,
        "entry": entry,
        "sl": stop_loss,
        "tp": take_profit
    }