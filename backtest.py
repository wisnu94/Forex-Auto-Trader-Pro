import pandas as pd
import numpy as np

from strategy import generate_signal
from mtf import (
    timeframe_trend,
    calculate_mtf_score,
)


# ============================================================
# FOREX AUTO TRADER PRO
# BACKTEST ENGINE V2
#
# MTF ARCHITECTURE
#
# H1  = MARKET BIAS
# M15 = SETUP CONFIRMATION
# M1  = ENTRY TRIGGER
# ============================================================


# ============================================================
# EMPTY RESULT
# ============================================================

def _empty_backtest_result():

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


# ============================================================
# RESAMPLE M15 -> HIGHER TIMEFRAME
# ============================================================

def _resample_from_m15(
    df,
    bars_per_candle
):

    if df is None or len(df) == 0:
        return pd.DataFrame()

    data = (
        df.copy()
        .reset_index(drop=True)
    )

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
    ).reset_index(
        drop=True
    )

    return result


# ============================================================
# BUILD M1 PROXY
#
# NOTE:
# Ini bukan M1 market asli.
#
# Digunakan hanya untuk membuat pipeline
# H1 -> M15 -> M1 bisa dites terlebih dahulu.
# ============================================================

def _build_m1_proxy(
    m15
):

    if (
        m15 is None
        or len(m15) == 0
    ):
        return pd.DataFrame()

    rows = []

    for _, candle in m15.iterrows():

        open_price = float(
            candle["open"]
        )

        high_price = float(
            candle["high"]
        )

        low_price = float(
            candle["low"]
        )

        close_price = float(
            candle["close"]
        )

        # ----------------------------------------------------
        # Buat 15 candle M1 deterministik.
        # Tidak menggunakan future candle.
        # ----------------------------------------------------

        path = np.linspace(
            open_price,
            close_price,
            15
        )

        for j in range(15):

            current = float(
                path[j]
            )

            if j == 0:
                previous = open_price
            else:
                previous = float(
                    path[j - 1]
                )

            synthetic_open = previous
            synthetic_close = current

            synthetic_high = max(
                synthetic_open,
                synthetic_close
            )

            synthetic_low = min(
                synthetic_open,
                synthetic_close
            )

            # Distribusi range candle M15
            # secara konservatif.
            if j == 0:
                synthetic_high = max(
                    synthetic_high,
                    open_price
                )

                synthetic_low = min(
                    synthetic_low,
                    open_price
                )

            if j == 14:
                synthetic_high = max(
                    synthetic_high,
                    high_price
                )

                synthetic_low = min(
                    synthetic_low,
                    low_price
                )

            rows.append(
                {
                    "open": synthetic_open,
                    "high": synthetic_high,
                    "low": synthetic_low,
                    "close": synthetic_close,
                }
            )

    return pd.DataFrame(
        rows
    )


# ============================================================
# BUILD MTF CONFIRMATION
#
# H1  = 4 x M15
# M15 = native
# M1  = proxy sementara
# ============================================================

def _build_mtf_confirmation(
    history
):

    neutral = {
        "H1": "HOLD",
        "M15": "HOLD",
        "M1": "HOLD",
    }

    if (
        history is None
        or len(history) < 50
    ):

        return {
            "trends": neutral,
            "score": 0,
            "status": "NEUTRAL",
        }

    m15 = (
        history.copy()
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # H1
    # --------------------------------------------------------

    h1 = _resample_from_m15(
        m15,
        4
    )

    # --------------------------------------------------------
    # M1 PROXY
    # --------------------------------------------------------

    m1 = _build_m1_proxy(
        m15
    )

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    h1_trend = timeframe_trend(
        h1,
        fast_period=20,
        slow_period=50
    )

    m15_trend = timeframe_trend(
        m15,
        fast_period=20,
        slow_period=50
    )

    m1_trend = timeframe_trend(
        m1,
        fast_period=20,
        slow_period=50
    )

    trends = {
        "H1": h1_trend,
        "M15": m15_trend,
        "M1": m1_trend,
    }

    # --------------------------------------------------------
    # SCORE
    #
    # H1  = 40
    # M15 = 30
    # M1  = 30
    # --------------------------------------------------------

    score = calculate_mtf_score(
        trends
    )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if (
        h1_trend == "BUY"
        and m15_trend == "BUY"
        and m1_trend == "BUY"
    ):

        status = "STRONG_BUY"

    elif (
        h1_trend == "SELL"
        and m15_trend == "SELL"
        and m1_trend == "SELL"
    ):

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

    if (
        df is None
        or len(df) < ema_slow + 20
    ):

        return _empty_backtest_result()

    data = (
        df.copy()
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # WALK FORWARD
    # --------------------------------------------------------

    for i in range(
        ema_slow + 20,
        len(data) - 1
    ):

        # ----------------------------------------------------
        # ONLY HISTORICAL DATA
        # ----------------------------------------------------

        history = (
            data.iloc[:i + 1]
            .copy()
            .reset_index(drop=True)
        )

        # ----------------------------------------------------
        # MTF
        # ----------------------------------------------------

        mtf_confirmation = (
            _build_mtf_confirmation(
                history
            )
        )

        # ----------------------------------------------------
        # SIGNAL
        # ----------------------------------------------------

        result = generate_signal(
            history,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            atr_period=atr_period,
            mtf_confirmation=(
                mtf_confirmation
            ),
        )

        signal = result.get(
            "signal",
            "HOLD"
        )

        # ----------------------------------------------------
        # PRECISION
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
        # BASIC FILTER
        # ----------------------------------------------------

        if signal == "HOLD":
            continue

        if not precision_pass:
            continue

        if (
            precision_score
            < min_score
        ):
            continue

        # ----------------------------------------------------
        # MTF SAFETY
        #
        # Semua timeframe harus aligned.
        # ----------------------------------------------------

        trends = (
            mtf_confirmation.get(
                "trends",
                {}
            )
        )

        h1 = trends.get(
            "H1",
            "HOLD"
        )

        m15 = trends.get(
            "M15",
            "HOLD"
        )

        m1 = trends.get(
            "M1",
            "HOLD"
        )

        if signal == "BUY":

            if not (
                h1 == "BUY"
                and m15 == "BUY"
                and m1 == "BUY"
            ):

                continue

            mtf_status = (
                "STRONG_BUY"
            )

        elif signal == "SELL":

            if not (
                h1 == "SELL"
                and m15 == "SELL"
                and m1 == "SELL"
            ):

                continue

            mtf_status = (
                "STRONG_SELL"
            )

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

        try:

            atr = float(atr)

        except (
            TypeError,
            ValueError
        ):

            continue

        if not np.isfinite(
            atr
        ):

            continue

        if atr <= 0:
            continue

        # ----------------------------------------------------
        # ENTRY
        # ----------------------------------------------------

        entry_index = (
            i + 1
        )

        entry = float(
            data.iloc[
                entry_index
            ]["open"]
        )

        sl_distance = (
            atr
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
        # EXIT
        # ----------------------------------------------------

        outcome = None
        exit_price = None
        exit_index = None

        for j in range(
            entry_index,
            len(data)
        ):

            candle = (
                data.iloc[j]
            )

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

                # Conservative:
                # jika SL dan TP tersentuh
                # pada candle yang sama,
                # anggap LOSS.
                if (
                    hit_sl
                    and hit_tp
                ):

                    outcome = "LOSS"
                    exit_price = (
                        stop_loss
                    )
                    exit_index = j
                    break

                if hit_sl:

                    outcome = "LOSS"
                    exit_price = (
                        stop_loss
                    )
                    exit_index = j
                    break

                if hit_tp:

                    outcome = "WIN"
                    exit_price = (
                        take_profit
                    )
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

                if (
                    hit_sl
                    and hit_tp
                ):

                    outcome = "LOSS"
                    exit_price = (
                        stop_loss
                    )
                    exit_index = j
                    break

                if hit_sl:

                    outcome = "LOSS"
                    exit_price = (
                        stop_loss
                    )
                    exit_index = j
                    break

                if hit_tp:

                    outcome = "WIN"
                    exit_price = (
                        take_profit
                    )
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

                "entry_index":
                    entry_index,

                "exit_index":
                    exit_index,

                "signal":
                    signal,

                "entry":
                    entry,

                "stop_loss":
                    stop_loss,

                "take_profit":
                    take_profit,

                "exit":
                    exit_price,

                "outcome":
                    outcome,

                "r_multiple":
                    r_multiple,
                    
                # --------------------------------------------
                # INDICATOR DIAGNOSTIC
                # --------------------------------------------

                "rsi":
                    result.get(
                        "rsi"
                    ),

                "adx":
                    result.get(
                        "adx"
                    ),

                "momentum":
                    result.get(
                        "momentum"
                    ),

                "atr":
                    atr,

                "atr_average":
                    result.get(
                        "atr_average"
                    ),

                # --------------------------------------------
                # PRECISION
                # --------------------------------------------

                "precision_score":
                    precision_score,

                "precision_grade":
                    precision_grade,

                "precision_pass":
                    precision_pass,

                # --------------------------------------------
                # MTF
                # --------------------------------------------

                "mtf_score":
                    mtf_confirmation[
                        "score"
                    ],

                "mtf_status":
                    mtf_status,

                "mtf_h1":
                    h1,

                "mtf_m15":
                    m15,

                "mtf_m1":
                    m1,
            }
        )

    # ========================================================
    # STATISTICS
    # ========================================================

    total = len(
        trades
    )

    wins = sum(
        1
        for trade in trades
        if trade["outcome"]
        == "WIN"
    )

    losses = sum(
        1
        for trade in trades
        if trade["outcome"]
        == "LOSS"
    )

    # --------------------------------------------------------
    # WIN RATE
    # --------------------------------------------------------

    win_rate = (
        wins / total * 100
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

    elif gross_profit > 0:

        profit_factor = (
            float("inf")
        )

    else:

        profit_factor = 0.0

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

    return {
        "trades":
            trades,

        "total_trades":
            total,

        "wins":
            wins,

        "losses":
            losses,

        "win_rate":
            round(
                win_rate,
                2
            ),

        "profit_factor":
            (
                round(
                    profit_factor,
                    3
                )
                if profit_factor
                != float("inf")
                else profit_factor
            ),

        "net_r":
            round(
                net_r,
                3
            ),

        "expectancy_r":
            round(
                expectancy_r,
                4
            ),
    }


# ============================================================
# GRADE ANALYSIS
# ============================================================

def analyze_grades(
    trades
):

    result = {}

    for grade in [
        "A+",
        "A",
        "B",
        "C",
        "D",
    ]:

        subset = [
            trade
            for trade in trades
            if trade.get(
                "precision_grade"
            ) == grade
        ]

        total = len(
            subset
        )

        wins = sum(
            1
            for trade in subset
            if trade["outcome"]
            == "WIN"
        )

        losses = (
            total - wins
        )

        net_r = sum(
            trade["r_multiple"]
            for trade in subset
        )

        win_rate = (
            wins / total * 100
            if total > 0
            else 0.0
        )

        result[grade] = {
            "trades":
                total,

            "wins":
                wins,

            "losses":
                losses,

            "win_rate":
                round(
                    win_rate,
                    2
                ),

            "net_r":
                round(
                    net_r,
                    3
                ),
        }

    return result


# ============================================================
# SIGNAL ANALYSIS
# ============================================================

def analyze_signals(
    trades
):

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

        total = len(
            subset
        )

        wins = sum(
            1
            for trade in subset
            if trade["outcome"]
            == "WIN"
        )

        losses = (
            total - wins
        )

        net_r = sum(
            trade["r_multiple"]
            for trade in subset
        )

        win_rate = (
            wins / total * 100
            if total > 0
            else 0.0
        )

        result[signal] = {
            "trades":
                total,

            "wins":
                wins,

            "losses":
                losses,

            "win_rate":
                round(
                    win_rate,
                    2
                ),

            "net_r":
                round(
                    net_r,
                    3
                ),
        }

    return result


# ============================================================
# MTF ANALYSIS
# ============================================================

def analyze_mtf(
    trades
):

    result = {}

    combinations = [
        ("H1", "BUY"),
        ("H1", "SELL"),
        ("M15", "BUY"),
        ("M15", "SELL"),
        ("M1", "BUY"),
        ("M1", "SELL"),
    ]

    for timeframe, direction in combinations:

        subset = [
            trade
            for trade in trades
            if trade.get(
                "signal"
            ) == direction
            and trade.get(
                f"mtf_{timeframe.lower()}"
            ) == direction
        ]

        total = len(
            subset
        )

        wins = sum(
            1
            for trade in subset
            if trade["outcome"]
            == "WIN"
        )

        losses = (
            total - wins
        )

        net_r = sum(
            trade["r_multiple"]
            for trade in subset
        )

        win_rate = (
            wins / total * 100
            if total > 0
            else 0.0
        )

        result[
            f"{timeframe}_{direction}"
        ] = {
            "trades":
                total,

            "wins":
                wins,

            "losses":
                losses,

            "win_rate":
                round(
                    win_rate,
                    2
                ),

            "net_r":
                round(
                    net_r,
                    3
                ),
        }

    return result


# ============================================================
# SCORE BUCKETS
# ============================================================

def analyze_score_buckets(
    trades
):

    buckets = {
        "70-79": [],
        "80-89": [],
        "90-100": [],
    }

    for trade in trades:

        score = float(
            trade.get(
                "precision_score",
                0
            )
        )

        if (
            70 <= score < 80
        ):

            buckets[
                "70-79"
            ].append(
                trade
            )

        elif (
            80 <= score < 90
        ):

            buckets[
                "80-89"
            ].append(
                trade
            )

        elif score >= 90:

            buckets[
                "90-100"
            ].append(
                trade
            )

    result = {}

    for bucket, subset in buckets.items():

        total = len(
            subset
        )

        wins = sum(
            1
            for trade in subset
            if trade["outcome"]
            == "WIN"
        )

        losses = (
            total - wins
        )

        net_r = sum(
            trade["r_multiple"]
            for trade in subset
        )

        win_rate = (
            wins / total * 100
            if total > 0
            else 0.0
        )

        result[bucket] = {
            "trades":
                total,

            "wins":
                wins,

            "losses":
                losses,

            "win_rate":
                round(
                    win_rate,
                    2
                ),

            "net_r":
                round(
                    net_r,
                    3
                ),
        }

    return result


# ============================================================
# MTF STATUS ANALYSIS
# ============================================================

def analyze_mtf_status(
    trades
):

    statuses = [
        "STRONG_BUY",
        "STRONG_SELL",
        "BUY_BIAS",
        "SELL_BIAS",
        "NEUTRAL",
    ]

    result = {}

    for status in statuses:

        subset = [
            trade
            for trade in trades
            if trade.get(
                "mtf_status"
            ) == status
        ]

        total = len(
            subset
        )

        wins = sum(
            1
            for trade in subset
            if trade["outcome"]
            == "WIN"
        )

        losses = (
            total - wins
        )

        net_r = sum(
            trade["r_multiple"]
            for trade in subset
        )

        win_rate = (
            wins / total * 100
            if total > 0
            else 0.0
        )

        result[status] = {
            "trades":
                total,

            "wins":
                wins,

            "losses":
                losses,

            "win_rate":
                round(
                    win_rate,
                    2
                ),

            "net_r":
                round(
                    net_r,
                    3
                ),
        }

    return result


# ============================================================
# MTF SCORE ANALYSIS
# ============================================================

def analyze_mtf_scores(
    trades
):

    buckets = {
        "60_to_100": [],
        "40_to_59": [],
        "20_to_39": [],
        "0_to_19": [],
        "-19_to_-1": [],
        "-39_to_-20": [],
        "-59_to_-40": [],
        "-100_to_-60": [],
    }

    for trade in trades:

        score = int(
            trade.get(
                "mtf_score",
                0
            )
        )

        if score >= 60:

            buckets[
                "60_to_100"
            ].append(
                trade
            )

        elif score >= 40:

            buckets[
                "40_to_59"
            ].append(
                trade
            )

        elif score >= 20:

            buckets[
                "20_to_39"
            ].append(
                trade
            )

        elif score >= 0:

            buckets[
                "0_to_19"
            ].append(
                trade
            )

        elif score >= -19:

            buckets[
                "-19_to_-1"
            ].append(
                trade
            )

        elif score >= -39:

            buckets[
                "-39_to_-20"
            ].append(
                trade
            )

        elif score >= -59:

            buckets[
                "-59_to_-40"
            ].append(
                trade
            )

        else:

            buckets[
                "-100_to_-60"
            ].append(
                trade
            )

    result = {}

    for bucket, subset in buckets.items():

        total = len(
            subset
        )

        wins = sum(
            1
            for trade in subset
            if trade["outcome"]
            == "WIN"
        )

        losses = (
            total - wins
        )

        net_r = sum(
            trade["r_multiple"]
            for trade in subset
        )

        win_rate = (
            wins / total * 100
            if total > 0
            else 0.0
        )

        result[bucket] = {
            "trades":
                total,

            "wins":
                wins,

            "losses":
                losses,

            "win_rate":
                round(
                    win_rate,
                    2
                ),

            "net_r":
                round(
                    net_r,
                    3
                ),
        }

    return result


# ============================================================
# MAX CONSECUTIVE LOSSES
# ============================================================

def calculate_max_consecutive_losses(
    trades
):

    current = 0
    maximum = 0

    for trade in trades:

        if (
            trade["outcome"]
            == "LOSS"
        ):

            current += 1

            maximum = max(
                maximum,
                current
            )

        else:

            current = 0

    return maximum


# ============================================================
# GENERAL DIAGNOSTIC REPORT
# ============================================================

def analyze_diagnostics(
    trades
):

    total = len(
        trades
    )

    wins = sum(
        1
        for trade in trades
        if trade["outcome"]
        == "WIN"
    )

    losses = (
        total - wins
    )

    net_r = sum(
        trade["r_multiple"]
        for trade in trades
    )

    average_r = (
        net_r / total
        if total > 0
        else 0.0
    )

    return {
        "total_trades":
            total,

        "wins":
            wins,

        "losses":
            losses,

        "win_rate":
            round(
                (
                    wins
                    / total
                    * 100
                    if total > 0
                    else 0.0
                ),
                2
            ),

        "net_r":
            round(
                net_r,
                3
            ),

        "average_r":
            round(
                average_r,
                4
            ),

        "max_consecutive_losses":
            calculate_max_consecutive_losses(
                trades
            ),

        "grades":
            analyze_grades(
                trades
            ),

        "signals":
            analyze_signals(
                trades
            ),

        "mtf":
            analyze_mtf(
                trades
            ),

        "score_buckets":
            analyze_score_buckets(
                trades
            ),

        "mtf_status":
            analyze_mtf_status(
                trades
            ),

        "mtf_scores":
            analyze_mtf_scores(
                trades
            ),
    }