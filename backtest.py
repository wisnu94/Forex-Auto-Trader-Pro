import pandas as pd
import numpy as np

from strategy import generate_signal
from mtf import (
    timeframe_trend,
    calculate_mtf_score,
)


# ============================================================
# FOREX AUTO TRADER PRO
# BACKTEST ENGINE V3
#
# PURPOSE:
# - No overlapping trades
# - Timestamp-aware H1 aggregation
# - No synthetic M1 used as profitability evidence
# - Entry next candle
# - Conservative SL/TP collision handling
#
# MTF ARCHITECTURE:
#
# H1  = MARKET BIAS
# M15 = SETUP CONFIRMATION
# M1  = REAL ENTRY TRIGGER
#
# IMPORTANT:
# Real M1 must be supplied separately.
# This engine does NOT fabricate M1 data.
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
# NORMALIZE OHLC
# ============================================================

def _normalize_ohlc(df):

    if df is None or len(df) == 0:
        return pd.DataFrame()

    data = df.copy()

    # --------------------------------------------------------
    # Normalize column names
    # --------------------------------------------------------

    data.columns = [
        str(col).lower()
        for col in data.columns
    ]

    required = [
        "open",
        "high",
        "low",
        "close",
    ]

    for column in required:

        if column not in data.columns:
            return pd.DataFrame()

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce"
        )

    data = data.dropna(
        subset=required
    )

    # --------------------------------------------------------
    # Preserve timestamp if available
    # --------------------------------------------------------

    if isinstance(
        data.index,
        pd.DatetimeIndex
    ):

        data = data.sort_index()

        # Remove duplicate timestamps.
        data = data[
            ~data.index.duplicated(
                keep="last"
            )
        ]

    else:

        data = data.reset_index(
            drop=True
        )

    return data


# ============================================================
# RESAMPLE TO H1 USING REAL TIMESTAMP
#
# IMPORTANT:
# Jangan gunakan:
#
# np.arange(len(df)) // 4
#
# karena itu hanya menganggap setiap 4 bar
# selalu merupakan satu H1.
# ============================================================

def _resample_to_h1(df):

    data = _normalize_ohlc(
        df
    )

    if len(data) == 0:
        return pd.DataFrame()

    # --------------------------------------------------------
    # Kalau timestamp tersedia
    # --------------------------------------------------------

    if isinstance(
        data.index,
        pd.DatetimeIndex
    ):

        h1 = (
            data[
                [
                    "open",
                    "high",
                    "low",
                    "close",
                ]
            ]
            .resample("1h")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                }
            )
            .dropna(
                subset=[
                    "open",
                    "high",
                    "low",
                    "close",
                ]
            )
        )

        return h1

    # --------------------------------------------------------
    # Fallback kalau tidak ada timestamp.
    #
    # Ini hanya compatibility fallback.
    # --------------------------------------------------------

    group_id = (
        np.arange(len(data))
        // 4
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
# BUILD MTF CONFIRMATION
#
# M1 PROXY SUDAH DIHAPUS.
#
# M1 hanya boleh berasal dari data market asli.
# ============================================================

def _build_mtf_confirmation(
    history,
    m1_history=None
):

    neutral = {
        "H1": "HOLD",
        "M15": "HOLD",
    }

    if (
        history is None
        or len(history) < 50
    ):

        return {
            "trends": neutral,
            "score": 0,
            "status": "NEUTRAL",
            "m1_real": False,
        }

    m15 = _normalize_ohlc(
        history
    )

    h1 = _resample_to_h1(
        m15
    )

    # --------------------------------------------------------
    # H1
    # --------------------------------------------------------

    h1_trend = timeframe_trend(
        h1,
        fast_period=20,
        slow_period=50
    )

    # --------------------------------------------------------
    # M15
    # --------------------------------------------------------

    m15_trend = timeframe_trend(
        m15,
        fast_period=20,
        slow_period=50
    )

    trends = {
        "H1": h1_trend,
        "M15": m15_trend,
    }

    # --------------------------------------------------------
    # REAL M1
    # --------------------------------------------------------

    real_m1_available = (
        m1_history is not None
        and len(m1_history) >= 50
    )

    if real_m1_available:

        m1 = _normalize_ohlc(
            m1_history
        )

        m1_trend = timeframe_trend(
            m1,
            fast_period=20,
            slow_period=50
        )

        trends["M1"] = m1_trend

    # --------------------------------------------------------
    # SCORE
    #
    # MTF V3:
    #
    # H1  = 40
    # M15 = 30
    # M1  = 30
    #
    # Kalau M1 tidak tersedia:
    # score hanya H1/M15 untuk diagnostic.
    # --------------------------------------------------------

    if "M1" in trends:

        score = calculate_mtf_score(
            trends
        )

    else:

        score = 0

        if h1_trend == "BUY":
            score += 40

        elif h1_trend == "SELL":
            score -= 40

        if m15_trend == "BUY":
            score += 30

        elif m15_trend == "SELL":
            score -= 30

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    if "M1" in trends:

        m1_trend = trends["M1"]

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

    else:

        if (
            h1_trend == "BUY"
            and m15_trend == "BUY"
        ):

            status = "BUY_BIAS"

        elif (
            h1_trend == "SELL"
            and m15_trend == "SELL"
        ):

            status = "SELL_BIAS"

        else:

            status = "NEUTRAL"

    return {
        "trends": trends,

        "score": int(score),

        "status": status,

        "m1_real": (
            "M1" in trends
        ),
    }


# ============================================================
# GET TIMESTAMP
# ============================================================

def _get_timestamp(
    df,
    index
):

    try:

        if isinstance(
            df.index,
            pd.DatetimeIndex
        ):

            return df.index[index]

    except Exception:
        pass

    return None


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
    m1_df=None,
):

    trades = []

    if (
        df is None
        or len(df)
        < ema_slow + 20
    ):

        return _empty_backtest_result()

    data = _normalize_ohlc(
        df
    )

    if len(data) < (
        ema_slow + 20
    ):

        return _empty_backtest_result()

    # --------------------------------------------------------
    # Real M1 optional
    # --------------------------------------------------------

    real_m1 = None

    if m1_df is not None:

        real_m1 = _normalize_ohlc(
            m1_df
        )

        if len(real_m1) < 50:
            real_m1 = None

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # next_available_index controls the earliest bar
    # that may be used for a new trade.
    #
    # This prevents overlapping positions.
    # --------------------------------------------------------

    next_available_index = (
        ema_slow + 20
    )

    # ========================================================
    # WALK FORWARD
    # ========================================================

    while (
        next_available_index
        < len(data) - 1
    ):

        i = next_available_index

        # ----------------------------------------------------
        # HISTORICAL DATA ONLY
        # ----------------------------------------------------

        history = (
            data.iloc[:i + 1]
            .copy()
        )

        # ----------------------------------------------------
        # REAL M1 HISTORY
        #
        # Hanya sampai current M15 timestamp.
        # ----------------------------------------------------

        m1_history = None

        if real_m1 is not None:

            current_time = (
                _get_timestamp(
                    data,
                    i
                )
            )

            if current_time is not None:

                m1_history = (
                    real_m1[
                        real_m1.index
                        <= current_time
                    ]
                    .copy()
                )

            else:

                m1_history = (
                    real_m1.copy()
                )

        # ----------------------------------------------------
        # MTF
        # ----------------------------------------------------

        mtf_confirmation = (
            _build_mtf_confirmation(
                history,
                m1_history
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

        signal = str(
            result.get(
                "signal",
                "HOLD"
            )
        ).upper()

        # ----------------------------------------------------
        # PRECISION
        # ----------------------------------------------------

        precision_score = int(
            result.get(
                "precision_score",
                0
            )
        )

        precision_grade = result.get(
            "precision_grade",
            "D"
        )

        precision_pass = bool(
            result.get(
                "precision_pass",
                False
            )
        )

        # ----------------------------------------------------
        # BASIC FILTER
        # ----------------------------------------------------

        if signal == "HOLD":

            next_available_index += 1
            continue

        if not precision_pass:

            next_available_index += 1
            continue

        if precision_score < min_score:

            next_available_index += 1
            continue

        # ----------------------------------------------------
        # MTF
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
            "NOT_AVAILABLE"
        )

        # ----------------------------------------------------
        # IMPORTANT
        #
        # Kalau real M1 tidak tersedia:
        # kita TIDAK menganggap M1 sebagai confirmed trigger.
        #
        # Strategy layer nanti akan kita upgrade agar
        # H1/M15 bias + real M1 trigger dapat dipisahkan.
        # ----------------------------------------------------

        if "M1" in trends:

            if signal == "BUY":

                if not (
                    h1 == "BUY"
                    and m15 == "BUY"
                    and m1 == "BUY"
                ):

                    next_available_index += 1
                    continue

                mtf_status = "STRONG_BUY"

            elif signal == "SELL":

                if not (
                    h1 == "SELL"
                    and m15 == "SELL"
                    and m1 == "SELL"
                ):

                    next_available_index += 1
                    continue

                mtf_status = "STRONG_SELL"

            else:

                next_available_index += 1
                continue

        else:

            # ------------------------------------------------
            # Temporary research mode:
            #
            # H1 + M15 aligned.
            #
            # Ini bukan final M1 execution logic.
            # ------------------------------------------------

            if signal == "BUY":

                if not (
                    h1 == "BUY"
                    and m15 == "BUY"
                ):

                    next_available_index += 1
                    continue

                mtf_status = "BUY_BIAS"

            elif signal == "SELL":

                if not (
                    h1 == "SELL"
                    and m15 == "SELL"
                ):

                    next_available_index += 1
                    continue

                mtf_status = "SELL_BIAS"

            else:

                next_available_index += 1
                continue

        # ----------------------------------------------------
        # ATR
        # ----------------------------------------------------

        atr = result.get(
            "atr"
        )

        if atr is None:

            next_available_index += 1
            continue

        try:

            atr = float(atr)

        except (
            TypeError,
            ValueError
        ):

            next_available_index += 1
            continue

        if not np.isfinite(
            atr
        ):

            next_available_index += 1
            continue

        if atr <= 0:

            next_available_index += 1
            continue

        # ----------------------------------------------------
        # ENTRY
        #
        # Entry ALWAYS next candle open.
        # ----------------------------------------------------

        entry_index = i + 1

        if entry_index >= len(data):

            break

        entry = float(
            data.iloc[
                entry_index
            ]["open"]
        )

        entry_time = (
            _get_timestamp(
                data,
                entry_index
            )
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
                # if both are touched on same candle,
                # SL wins.
                if (
                    hit_sl
                    and hit_tp
                ):

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

            elif signal == "SELL":

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

            break

        # ----------------------------------------------------
        # R MULTIPLE
        # ----------------------------------------------------

        if outcome == "WIN":

            r_multiple = float(
                reward_risk
            )

        else:

            r_multiple = -1.0

        exit_time = (
            _get_timestamp(
                data,
                exit_index
            )
        )

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

                "entry_time":
                    entry_time,

                "exit_time":
                    exit_time,

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
                # INDICATORS
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
                    mtf_confirmation.get(
                        "score",
                        0
                    ),

                "mtf_status":
                    mtf_status,

                "mtf_h1":
                    h1,

                "mtf_m15":
                    m15,

                "mtf_m1":
                    m1,

                "m1_real":
                    mtf_confirmation.get(
                        "m1_real",
                        False
                    ),
            }
        )

        # ----------------------------------------------------
        # CRITICAL:
        #
        # Next scan begins AFTER the exit candle.
        #
        # This prevents overlapping trades.
        # ----------------------------------------------------

        next_available_index = (
            exit_index + 1
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

        profit_factor = float(
            "inf"
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
            if trade["outcome"] == "WIN"
        )

        losses = total - wins

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
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(
                win_rate,
                2
            ),
            "net_r": round(
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
            if trade["outcome"] == "WIN"
        )

        losses = total - wins

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
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(
                win_rate,
                2
            ),
            "net_r": round(
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
            if trade["outcome"] == "WIN"
        )

        losses = total - wins

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
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(
                win_rate,
                2
            ),
            "net_r": round(
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

        if 70 <= score < 80:

            buckets[
                "70-79"
            ].append(
                trade
            )

        elif 80 <= score < 90:

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
            if trade["outcome"] == "WIN"
        )

        losses = total - wins

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
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(
                win_rate,
                2
            ),
            "net_r": round(
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
            if trade["outcome"] == "WIN"
        )

        losses = total - wins

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
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(
                win_rate,
                2
            ),
            "net_r": round(
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
            if trade["outcome"] == "WIN"
        )

        losses = total - wins

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
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(
                win_rate,
                2
            ),
            "net_r": round(
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

        if trade["outcome"] == "LOSS":

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
        if trade["outcome"] == "WIN"
    )

    losses = total - wins

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
        "total_trades": total,

        "wins": wins,

        "losses": losses,

        "win_rate": round(
            (
                wins / total * 100
                if total > 0
                else 0.0
            ),
            2
        ),

        "net_r": round(
            net_r,
            3
        ),

        "average_r": round(
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