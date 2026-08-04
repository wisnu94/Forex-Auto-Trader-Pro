import pandas as pd

from strategy import generate_signal


# ============================================================
# BACKTEST ENGINE
# ============================================================

def backtest_strategy(
    df,
    ema_fast=20,
    ema_slow=50,
    atr_period=14,
    atr_sl_multiplier=1.5,
    reward_risk=2.0,
    min_score=70,
):
    trades = []

    if df is None or len(df) < ema_slow + 20:
        return {
            "trades": [],
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "net_r": 0.0,
            "expectancy_r": 0.0,
        }

    data = df.copy().reset_index(drop=True)

    for i in range(
        ema_slow + 20,
        len(data) - 1
    ):

        history = data.iloc[:i + 1].copy()

        result = generate_signal(
            history,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            atr_period=atr_period,
            mtf_confirmation=None,
        )

        signal = result["signal"]

        precision_score = result.get(
            "precision_score",
            0
        )

        precision_grade = result.get(
            "precision_grade",
            "D"
        )

        if signal == "HOLD":
            continue

        if precision_score < min_score:
            continue

        atr = result.get("atr")

        if atr is None or atr <= 0:
            continue

        entry_index = i + 1

        entry = float(
            data.iloc[entry_index]["open"]
        )

        sl_distance = (
            float(atr)
            * atr_sl_multiplier
        )

        if signal == "BUY":

            stop_loss = (
                entry - sl_distance
            )

            take_profit = (
                entry
                + sl_distance * reward_risk
            )

        else:

            stop_loss = (
                entry + sl_distance
            )

            take_profit = (
                entry
                - sl_distance * reward_risk
            )

        outcome = None
        exit_price = None

        for j in range(
            entry_index,
            len(data)
        ):

            candle = data.iloc[j]

            high = float(
                candle["high"]
            )

            low = float(
                candle["low"]
            )

            if signal == "BUY":

                hit_sl = low <= stop_loss
                hit_tp = high >= take_profit

                if hit_sl and hit_tp:
                    outcome = "LOSS"
                    exit_price = stop_loss
                    break

                if hit_sl:
                    outcome = "LOSS"
                    exit_price = stop_loss
                    break

                if hit_tp:
                    outcome = "WIN"
                    exit_price = take_profit
                    break

            else:

                hit_sl = high >= stop_loss
                hit_tp = low <= take_profit

                if hit_sl and hit_tp:
                    outcome = "LOSS"
                    exit_price = stop_loss
                    break

                if hit_sl:
                    outcome = "LOSS"
                    exit_price = stop_loss
                    break

                if hit_tp:
                    outcome = "WIN"
                    exit_price = take_profit
                    break

        if outcome is None:
            continue

        if outcome == "WIN":
            r_multiple = reward_risk
        else:
            r_multiple = -1.0

        trades.append({
            "index": i,
            "signal": signal,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "exit": exit_price,
            "outcome": outcome,
            "r_multiple": r_multiple,
            "precision_score": precision_score,
            "precision_grade": precision_grade,
        })

    total = len(trades)

    wins = sum(
        1
        for trade in trades
        if trade["outcome"] == "WIN"
    )

    losses = sum(
        1
        for trade in trades
        if trade["outcome"] == "LOSS"
    )

    win_rate = (
        (wins / total) * 100
        if total > 0
        else 0.0
    )

    gross_profit = sum(
        trade["r_multiple"]
        for trade in trades
        if trade["r_multiple"] > 0
    )

    gross_loss = abs(
        sum(
            trade["r_multiple"]
            for trade in trades
            if trade["r_multiple"] < 0
        )
    )

    if gross_loss > 0:
        profit_factor = (
            gross_profit / gross_loss
        )
    else:
        profit_factor = (
            float("inf")
            if gross_profit > 0
            else 0.0
        )

    net_r = sum(
        trade["r_multiple"]
        for trade in trades
    )

    expectancy_r = (
        net_r / total
        if total > 0
        else 0.0
    )

    return {
        "trades": trades,
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(
            win_rate,
            2
        ),
        "profit_factor": round(
            profit_factor,
            3
        )
        if profit_factor != float("inf")
        else profit_factor,
        "net_r": round(
            net_r,
            3
        ),
        "expectancy_r": round(
            expectancy_r,
            4
        ),
    }


# ============================================================
# GRADE ANALYSIS
# ============================================================

def analyze_grades(trades):

    result = {}

    grades = [
        "A+",
        "A",
        "B",
        "C",
        "D",
    ]

    for grade in grades:

        subset = [
            trade
            for trade in trades
            if trade["precision_grade"] == grade
        ]

        total = len(subset)

        wins = sum(
            1
            for trade in subset
            if trade["outcome"] == "WIN"
        )

        win_rate = (
            (wins / total) * 100
            if total > 0
            else 0.0
        )

        result[grade] = {
            "trades": total,
            "wins": wins,
            "win_rate": round(
                win_rate,
                2
            ),
        }

    return result


# ============================================================
# SIGNAL ANALYSIS
# ============================================================

def analyze_signals(trades):

    result = {}

    for signal in [
        "BUY",
        "SELL",
    ]:

        subset = [
            trade
            for trade in trades
            if trade["signal"] == signal
        ]

        total = len(subset)

        wins = sum(
            1
            for trade in subset
            if trade["outcome"] == "WIN"
        )

        win_rate = (
            (wins / total) * 100
            if total > 0
            else 0.0
        )

        result[signal] = {
            "trades": total,
            "wins": wins,
            "win_rate": round(
                win_rate,
                2
            ),
        }

    return result