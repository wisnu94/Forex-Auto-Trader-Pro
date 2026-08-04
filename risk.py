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

    risk_distance = atr_value * atr_multiplier

    if signal == "BUY":
        stop_loss = entry_price - risk_distance
        take_profit = (
            entry_price
            + risk_distance * reward_risk
        )

    else:
        stop_loss = entry_price + risk_distance
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
        ),
    }


# ============================================================
# RISK MONEY
# ============================================================

def calculate_risk_money(
    equity,
    risk_percent
):
    if equity <= 0 or risk_percent <= 0:
        return 0.0

    return float(
        equity * risk_percent
    )


# ============================================================
# MT5 POSITION SIZE
# ============================================================

def calculate_position_size_mt5(
    equity,
    risk_percent,
    entry_price,
    stop_loss,
    tick_size,
    tick_value,
    volume_min,
    volume_max,
    volume_step,
):
    """
    Calculates volume using the broker's MT5
    tick size and tick value.

    Maximum planned loss is approximately:

        equity × risk_percent

    The volume is rounded DOWN to the broker's
    volume step so intended risk is not increased.
    """

    if equity <= 0:
        return 0.0

    if risk_percent <= 0:
        return 0.0

    if entry_price <= 0:
        return 0.0

    if stop_loss <= 0:
        return 0.0

    if tick_size <= 0:
        return 0.0

    if tick_value <= 0:
        return 0.0

    if volume_min <= 0:
        return 0.0

    if volume_max <= 0:
        return 0.0

    if volume_step <= 0:
        return 0.0

    risk_money = calculate_risk_money(
        equity,
        risk_percent
    )

    price_distance = abs(
        entry_price - stop_loss
    )

    if price_distance <= 0:
        return 0.0

    loss_per_lot = (
        price_distance / tick_size
    ) * tick_value

    if loss_per_lot <= 0:
        return 0.0

    raw_volume = (
        risk_money / loss_per_lot
    )

    raw_volume = min(
        raw_volume,
        volume_max
    )

    steps = math.floor(
        raw_volume / volume_step
    )

    volume = (
        steps * volume_step
    )

    if volume < volume_min:
        return 0.0

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

    if current_daily_loss >= max_daily_loss:
        return False, "MAX DAILY LOSS reached"

    return True, "RISK OK"