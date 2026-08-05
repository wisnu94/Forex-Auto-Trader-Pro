import pandas as pd
import numpy as np

from strategy import generate_signal
from mtf import (
    timeframe_trend,
    calculate_mtf_score,
)


# ============================================================
# MTF BACKTEST HELPERS
# ============================================================

def _resample_from_m15(df, bars_per_candle):
    """
    Membentuk higher timeframe dari data M15.

    4  M15 candle  = H1
    16 M15 candle  = H4

    Hanya menggunakan data yang sudah tersedia
    sampai titik backtest saat ini.
    """

    if df is None or len(df) == 0:
        return pd.DataFrame()

    data = df.copy().reset_index(drop=True)

    group_id = (
        np.arange(len(data))
        // bars_per_candle
    )

    grouped = data.groupby(
        group_id,
        sort=True
    )

    result = grouped.agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        }
    ).reset_index(drop=True)

    return result


def _build_mtf_confirmation(history):
    """
    Membentuk MTF confirmation secara historis.

    Penting:
    Tidak mengambil candle masa depan.

    H4 = 16 x M15
    H1 = 4 x M15
    M15 = data history langsung
    """

    if history is None or len(history) < 50:
        return {
            "trends": {
                "H4": "HOLD",
                "H1": "HOLD",
                "M15": "HOLD",
            },
            "score": 0,
            "status": "NEUTRAL",
        }

    m15 = history.copy().reset_index(
        drop=True
    )

    h1 = _resample_from_m15(
        m15,
        4
    )

    h4 = _resample_from_m15(
        m15,
        16
    )

    trends = {
        "H4": timeframe_trend(
            h4,
            fast_period=20,
            slow_period=50
        ),

        "H1": timeframe_trend(
            h1,
            fast_period=20,
            slow_period=50
        ),

        "M15": timeframe_trend(
            m15,
            fast_period=20,
            slow_period=50
        ),
    }

    score = calculate_mtf_score(
        trends
    )

    all_buy = all(
        trends.get(tf) == "BUY"
        for tf in ("H4", "H1", "M15")
    )

    all_sell = all(
        trends.get(tf) == "SELL"
        for tf in ("H4", "H1", "M15")
    )

    if all_buy:
        status = "STRONG_BUY"

    elif all_sell:
        status = "STRONG_SELL"

    elif score >= 40:
        status = "BUY_BIAS"

    elif score <= -40:
        status = "SELL_BIAS"

    else:
        status = "NEUTRAL"

    return {
        "trends": trends,
        "score": int(score),
        "status": status,
    }


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

    data = (
        df.copy()
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # WALK-FORWARD BACKTEST
    # --------------------------------------------------------

    for i in range(
        ema_slow + 20,
        len(data) - 1
    ):

        # ----------------------------------------------------
        # HISTORICAL DATA ONLY
        # ----------------------------------------------------

        history = (
            data.iloc[:i + 1]
            .copy()
            .reset_index(drop=True)
        )

        # ----------------------------------------------------
        # BUILD MTF FROM AVAILABLE HISTORY
        # ----------------------------------------------------

        mtf_confirmation = (
            _build_mtf_confirmation(
                history
            )
        )

        # ----------------------------------------------------
        # GENERATE SIGNAL
        # ----------------------------------------------------

        result = generate_signal(
            history,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            atr_period=atr_period,
            mtf_confirmation=mtf_confirmation,
        )

        signal = result.get(
            "signal",
            "HOLD"
        )

        # ----------------------------------------------------
        # PRECISION SCORE
        # ----------------------------------------------------

        precision_score = result.get(
            "precision_score",
            0
        )

        precision_grade = result.get(
            "precision_grade",
            "D"
        )

        precision_pass = result.get(
            "precision_pass",
            False
        )

        # ----------------------------------------------------
        # FILTER
        # ----------------------------------------------------

        if signal == "HOLD":
            continue

        if not precision_pass:
            continue

        if precision_score < min_score:
            continue

        # ----------------------------------------------------
        # MTF SAFETY CHECK
        # ----------------------------------------------------

        mtf_status = mtf_confirmation.get(
            "status",
            "NEUTRAL"
        )

        if signal == "BUY":
            if mtf_status != "STRONG_BUY":
                continue

        elif signal == "SELL":
            if mtf_status != "STRONG_SELL":
                continue

        else:
            continue

        # ----------------------------------------------------
        # ATR
        # ----------------------------------------------------

        atr = result.get(
            "atr"
        )

        if atr is None:
            continue

        if not np.isfinite(
            float(atr)
        ):
            continue

        if float(atr) <= 0:
            continue

        # ----------------------------------------------------
        # ENTRY
        # ----------------------------------------------------

        entry_index = i + 1

        entry = float(
            data.iloc[entry_index]["open"]
        )

        sl_distance = (
            float(atr)
            * atr_sl_multiplier
        )

        # ----------------------------------------------------
        # SL / TP
        # ----------------------------------------------------

        if signal == "BUY":

            stop_loss = (
                entry
                - sl_distance
            )

            take_profit = (
                entry
                + (
                    sl_distance
                    * reward_risk
                )
            )

        else:

            stop_loss = (
                entry
                + sl_distance
            )

            take_profit = (
                entry
                - (
                    sl_distance
                    * reward_risk
                )
            )

        # ----------------------------------------------------
        # FIND EXIT
        # ----------------------------------------------------

        outcome = None
        exit_price = None
        exit_index = None

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

            # ------------------------------------------------
            # BUY
            # ------------------------------------------------

            if signal == "BUY":

                hit_sl = (
                    low <= stop_loss
                )

                hit_tp = (
                    high >= take_profit
                )

                # Conservative assumption:
                # if SL and TP happen in the
                # same candle, count LOSS.
                if hit_sl and hit_tp:

                    outcome = "LOSS"
                    exit_price = stop_loss
                    exit_index = j

                    break

                if hit_sl:

                    outcome = "LOSS"
                    exit_price = stop_loss
                    exit_index = j

                    break

                if hit_tp:

                    outcome = "WIN"
                    exit_price = take_profit
                    exit_index = j

                    break

            # ------------------------------------------------
            # SELL
            # ------------------------------------------------

            else:

                hit_sl = (
                    high >= stop_loss
                )

                hit_tp = (
                    low <= take_profit
                )

                # Conservative assumption:
                # if SL and TP happen in the
                # same candle, count LOSS.
                if hit_sl and hit_tp:

                    outcome = "LOSS"
                    exit_price = stop_loss
                    exit_index = j

                    break

                if hit_sl:

                    outcome = "LOSS"
                    exit_price = stop_loss
                    exit_index = j

                    break

                if hit_tp:

                    outcome = "WIN"
                    exit_price = take_profit
                    exit_index = j

                    break

        # ----------------------------------------------------
        # NO EXIT
        # ----------------------------------------------------

        if outcome is None:
            continue

        # ----------------------------------------------------
        # R MULTIPLE
        # ----------------------------------------------------

        if outcome == "WIN":
            r_multiple = float(
                reward_risk
            )
        else:
            r_multiple = -1.0

        # ----------------------------------------------------
        # SAVE TRADE
        # ----------------------------------------------------

        trades.append(
            {
                "index": i,
                "entry_index": entry_index,
                "exit_index": exit_index,

                "signal": signal,

                "entry": entry,

                "stop_loss": stop_loss,

                "take_profit": take_profit,

                "exit": exit_price,

                "outcome": outcome,

                "r_multiple": r_multiple,

                "precision_score": (
                    precision_score
                ),

                "precision_grade": (
                    precision_grade
                ),

                "precision_pass": (
                    precision_pass
                ),

                # MTF diagnostics
                "mtf_score": (
                    mtf_confirmation[
                        "score"
                    ]
                ),

                "mtf_status": (
                    mtf_status
                ),

                "mtf_h4": (
                    mtf_confirmation[
                        "trends"
                    ].get(
                        "H4",
                        "HOLD"
                    )
                ),

                "mtf_h1": (
                    mtf_confirmation[
                        "trends"
                    ].get(
                        "H1",
                        "HOLD"
                    )
                ),

                "mtf_m15": (
                    mtf_confirmation[
                        "trends"
                    ].get(
                        "M15",
                        "HOLD"
                    )
                ),
            }
        )

    # ========================================================
    # STATISTICS
    # ========================================================

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

    # --------------------------------------------------------
    # WIN RATE
    # --------------------------------------------------------

    win_rate = (
        (
            wins
            / total
        )
        * 100
        if total > 0
        else 0.0
    )

    # --------------------------------------------------------
    # GROSS PROFIT
    # --------------------------------------------------------

    gross_profit = sum(
        trade["r_multiple"]
        for trade in trades
        if trade["r_multiple"] > 0
    )

    # --------------------------------------------------------
    # GROSS LOSS
    # --------------------------------------------------------

    gross_loss = abs(
        sum(
            trade["r_multiple"]
            for trade in trades
            if trade["r_multiple"] < 0
        )
    )

    # --------------------------------------------------------
    # PROFIT FACTOR
    # --------------------------------------------------------

    if gross_loss > 0:

        profit_factor = (
            gross_profit
            / gross_loss
        )

    else:

        profit_factor = (
            float("inf")
            if gross_profit > 0
            else 0.0
        )

    # --------------------------------------------------------
    # NET R
    # --------------------------------------------------------

    net_r = sum(
        trade["r_multiple"]
        for trade in trades
    )

    # --------------------------------------------------------
    # EXPECTANCY
    # --------------------------------------------------------

    expectancy_r = (
        net_r / total
        if total > 0
        else 0.0
    )

    # ========================================================
    # RESULT
    # ========================================================

    return {
        "trades": trades,

        "total_trades": total,

        "wins": wins,

        "losses": losses,

        "win_rate": round(
            win_rate,
            2
        ),

        "profit_factor": (
            round(
                profit_factor,
                3
            )
            if profit_factor
            != float("inf")
            else profit_factor
        ),

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
            if trade.get(
                "precision_grade"
            ) == grade
        ]

        total = len(subset)

        wins = sum(
            1
            for trade in subset
            if trade["outcome"] == "WIN"
        )

        win_rate = (
            (
                wins
                / total
            )
            * 100
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
            if trade.get(
                "signal"
            ) == signal
        ]

        total = len(subset)

        wins = sum(
            1
            for trade in subset
            if trade["outcome"] == "WIN"
        )

        win_rate = (
            (
                wins
                / total
            )
            * 100
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