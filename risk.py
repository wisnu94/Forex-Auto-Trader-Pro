import math


# ============================================================
# SL / TP ENGINE
# ============================================================

def calculate_sl_tp(
    signal,
    entry_price,
    atr_value,
    atr_multiplier=1.5,
    reward_risk=2.0
):
    """
    Calculate dynamic SL and TP using ATR.

    BUY:
        SL below entry
        TP above entry

    SELL:
        SL above entry
        TP below entry
    """

    if signal not in {"BUY", "SELL"}:
        return None

    if entry_price <= 0:
        return None

    if atr_value is None or atr_value <= 0:
        return None

    if atr_multiplier <= 0:
        return None

    if reward_risk < 1:
        return None

    risk_distance = (
        atr_value * atr_multiplier
    )

    if signal == "BUY":

        stop_loss = (
            entry_price
            - risk_distance
        )

        take_profit = (
            entry_price
            + risk_distance * reward_risk
        )

    else:

        stop_loss = (
            entry_price
            + risk_distance
        )

        take_profit = (
            entry_price
            - risk_distance * reward_risk
        )

    return {
        "entry": float(entry_price),
        "sl": float(stop_loss),
        "tp": float(take_profit),
        "risk_distance": float(risk_distance),
        "reward_distance": float(
            risk_distance * reward_risk
        )
    }


# ============================================================
# RISK MONEY
# ============================================================

def calculate_risk_money(
    equity,
    risk_percent
):
    """
    Example:

    Equity = $10,000
    Risk   = 0.5%

    Maximum planned loss = $50
    """

    if equity <= 0:
        return 0.0

    if risk_percent <= 0:
        return 0.0

    return float(
        equity * risk_percent
    )


# ============================================================
# POSITION SIZE
# ============================================================

def calculate_position_size(
    equity,
    risk_percent,
    stop_distance,
    value_per_price_unit,
    volume_min=0.01,
    volume_max=100.0,
    volume_step=0.01
):
    """
    Calculate position size from monetary risk.

    This function does NOT send an order.

    value_per_price_unit must represent
    the monetary value of a 1.0 price-unit
    movement for 1 lot.
    """

    if equity <= 0:
        return 0.0

    if risk_percent <= 0:
        return 0.0

    if stop_distance <= 0:
        return 0.0

    if value_per_price_unit <= 0:
        return 0.0

    risk_money = calculate_risk_money(
        equity,
        risk_percent
    )

    raw_volume = (
        risk_money
        / (
            stop_distance
            * value_per_price_unit
        )
    )

    # Prevent exceeding broker limits
    raw_volume = min(
        raw_volume,
        volume_max
    )

    # Round DOWN to broker volume step.
    # We never round UP because that could
    # increase the intended risk.
    steps = math.floor(
        raw_volume / volume_step
    )

    volume = (
        steps * volume_step
    )

    volume = max(
        volume,
        volume_min
    )

    return float(
        round(volume, 8)
    )


# ============================================================
# RISK / REWARD
# ============================================================

def calculate_rr(
    entry,
    stop_loss,
    take_profit
):

    risk = abs(
        entry - stop_loss
    )

    reward = abs(
        take_profit - entry
    )

    if risk <= 0:
        return 0.0

    return float(
        reward / risk
    )


# ============================================================
# RISK VALIDATION
# ============================================================

def validate_trade_risk(
    equity,
    risk_percent,
    stop_distance,
    max_daily_loss,
    current_daily_loss
):
    """
    Final safety check before an order
    is allowed to proceed.
    """

    if equity <= 0:
        return False, "Invalid equity"

    if risk_percent <= 0:
        return False, "Invalid risk percentage"

    if stop_distance <= 0:
        return False, "Invalid stop distance"

    if current_daily_loss < 0:
        return False, "Invalid daily loss"

    if max_daily_loss <= 0:
        return False, "Invalid max daily loss"

    # Current daily loss is represented
    # as a fraction of equity.
    if current_daily_loss >= max_daily_loss:
        return False, "MAX DAILY LOSS reached"

    return True, "RISK OK"