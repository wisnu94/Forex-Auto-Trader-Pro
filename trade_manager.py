import MetaTrader5 as mt5

from config import (
    ATR_SL_MULTIPLIER,
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
# POSITION TYPE
# ============================================================

def is_buy_position(position):

    return (
        position.type
        == mt5.POSITION_TYPE_BUY
    )


def is_sell_position(position):

    return (
        position.type
        == mt5.POSITION_TYPE_SELL
    )


# ============================================================
# GET POSITIONS
# ============================================================

def get_positions(symbol=None):

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
# MODIFY SL / TP
# ============================================================

def modify_position(
    ticket,
    symbol,
    stop_loss=None,
    take_profit=None
):

    initialize_mt5()

    position = None

    positions = mt5.positions_get(
        ticket=ticket
    )

    if positions:

        position = positions[0]

    if position is None:

        return {
            "status": "ERROR",
            "reason": "Position tidak ditemukan"
        }

    current_sl = position.sl
    current_tp = position.tp

    if stop_loss is None:

        stop_loss = current_sl

    if take_profit is None:

        take_profit = current_tp

    request = {

        "action":
            mt5.TRADE_ACTION_SLTP,

        "symbol":
            symbol,

        "position":
            ticket,

        "sl":
            stop_loss,

        "tp":
            take_profit,
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
        "status": "MODIFIED",
        "ticket": ticket,
        "sl": stop_loss,
        "tp": take_profit
    }


# ============================================================
# BREAK-EVEN
# ============================================================

def calculate_break_even(
    position,
    current_price,
    risk_distance,
    trigger_r=1.0,
    buffer=0.0
):

    if risk_distance <= 0:

        return None

    if is_buy_position(position):

        profit_distance = (
            current_price
            - position.price_open
        )

        if profit_distance < (
            risk_distance * trigger_r
        ):

            return None

        return (
            position.price_open
            + buffer
        )

    if is_sell_position(position):

        profit_distance = (
            position.price_open
            - current_price
        )

        if profit_distance < (
            risk_distance * trigger_r
        ):

            return None

        return (
            position.price_open
            - buffer
        )

    return None


# ============================================================
# TRAILING STOP
# ============================================================

def calculate_trailing_stop(
    position,
    current_price,
    atr_value,
    atr_multiplier=1.5
):

    if atr_value is None:

        return None

    if atr_value <= 0:

        return None

    distance = (
        atr_value
        * atr_multiplier
    )

    if is_buy_position(position):

        new_sl = (
            current_price
            - distance
        )

        # Never move SL backwards
        if position.sl > 0:

            new_sl = max(
                new_sl,
                position.sl
            )

        return new_sl

    if is_sell_position(position):

        new_sl = (
            current_price
            + distance
        )

        # Never move SL backwards
        if position.sl > 0:

            new_sl = min(
                new_sl,
                position.sl
            )

        return new_sl

    return None


# ============================================================
# MANAGE POSITION
# ============================================================

def manage_position(
    position,
    current_price,
    atr_value,
    risk_distance,
    break_even_trigger=1.0,
    trailing_multiplier=1.5
):

    if position is None:

        return {
            "status": "ERROR",
            "reason": "Position kosong"
        }

    # --------------------------------------------------------
    # 1. BREAK-EVEN
    # --------------------------------------------------------

    breakeven_sl = calculate_break_even(
        position,
        current_price,
        risk_distance,
        break_even_trigger
    )

    # --------------------------------------------------------
    # 2. TRAILING STOP
    # --------------------------------------------------------

    trailing_sl = calculate_trailing_stop(
        position,
        current_price,
        atr_value,
        trailing_multiplier
    )

    candidates = []

    if breakeven_sl is not None:

        candidates.append(
            breakeven_sl
        )

    if trailing_sl is not None:

        candidates.append(
            trailing_sl
        )

    if not candidates:

        return {
            "status": "NO_CHANGE",
            "ticket": position.ticket
        }

    # --------------------------------------------------------
    # SELECT SAFE SL
    # --------------------------------------------------------

    if is_buy_position(position):

        new_sl = max(
            candidates
        )

        # Never place SL below existing SL
        if position.sl > 0:

            new_sl = max(
                new_sl,
                position.sl
            )

        # SL must remain below current price
        if new_sl >= current_price:

            return {
                "status": "NO_CHANGE",
                "ticket": position.ticket
            }

    elif is_sell_position(position):

        new_sl = min(
            candidates
        )

        # Never place SL above existing SL
        if position.sl > 0:

            new_sl = min(
                new_sl,
                position.sl
            )

        # SL must remain above current price
        if new_sl <= current_price:

            return {
                "status": "NO_CHANGE",
                "ticket": position.ticket
            }

    else:

        return {
            "status": "ERROR",
            "reason": "Unknown position type"
        }

    # --------------------------------------------------------
    # APPLY MODIFICATION
    # --------------------------------------------------------

    return modify_position(
        ticket=position.ticket,
        symbol=position.symbol,
        stop_loss=new_sl,
        take_profit=position.tp
    )