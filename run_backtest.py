import pandas as pd

from backtest import (
    backtest_strategy,
    analyze_grades,
    analyze_signals,
)

from config import (
    SYMBOL,
    TIMEFRAME,
)

from data import get_bars


# ============================================================
# FOREX AUTO TRADER PRO
# REAL-DATA BACKTEST ENGINE V4
#
# REAL DATA SOURCE:
# Yahoo Finance via data.py
#
# MTF ARCHITECTURE:
# H1  = MARKET BIAS
# M15 = SETUP CONFIRMATION
# M1  = ENTRY TRIGGER / MTF CONFIRMATION
# ============================================================

BARS = 3000

ATR_SL_MULTIPLIER = 1.5
REWARD_RISK = 2.0
MIN_SCORE = 70


# ============================================================
# LOAD REAL MARKET DATA
# ============================================================

def load_real_market_data():

    if str(TIMEFRAME).upper() != "M15":

        raise RuntimeError(
            "REAL-DATA BACKTEST V4 membutuhkan "
            "TIMEFRAME=M15 sebagai base timeframe."
        )

    print(
        "Downloading REAL market data..."
    )

    print(
        "Source           : Yahoo Finance"
    )

    print(
        f"Symbol           : {SYMBOL}"
    )

    print(
        f"Base timeframe   : {TIMEFRAME}"
    )

    df = get_bars(
        symbol=SYMBOL,
        timeframe=TIMEFRAME,
        count=BARS,
    )

    if df is None or len(df) == 0:

        raise RuntimeError(
            "Yahoo Finance mengembalikan data kosong."
        )

    required = [
        "open",
        "high",
        "low",
        "close",
    ]

    missing = [
        column
        for column in required
        if column not in df.columns
    ]

    if missing:

        raise RuntimeError(
            f"Kolom market data hilang: {missing}"
        )

    df = df.copy()

    for column in required:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=required
    )

    df = df.reset_index(
        drop=True
    )

    if len(df) < 100:

        raise RuntimeError(
            f"Data real terlalu sedikit: {len(df)} candle."
        )

    return df


# ============================================================
# OHLC VALIDATION
# ============================================================

def validate_ohlc(df):

    invalid = (
        (df["high"] < df["low"])
        |
        (df["high"] < df["open"])
        |
        (df["high"] < df["close"])
        |
        (df["low"] > df["open"])
        |
        (df["low"] > df["close"])
    )

    invalid_count = int(
        invalid.sum()
    )

    if invalid_count > 0:

        raise RuntimeError(
            f"Invalid OHLC rows: {invalid_count}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print("=" * 60)

    print(
        "FOREX AUTO TRADER PRO"
    )

    print(
        "REAL-DATA BACKTEST ENGINE V4"
    )

    print("=" * 60)

    print(
        f"Symbol          : {SYMBOL}"
    )

    print(
        f"Base Timeframe  : {TIMEFRAME}"
    )

    print(
        "MTF Architecture : H1 -> M15 -> M1"
    )

    print(
        "H1               : MARKET BIAS"
    )

    print(
        "M15              : SETUP CONFIRMATION"
    )

    print(
        "M1               : ENTRY TRIGGER / CONFIRMATION"
    )

    print()

    # --------------------------------------------------------
    # LOAD REAL DATA
    # --------------------------------------------------------

    try:

        df = load_real_market_data()

    except Exception as exc:

        print()

        print(
            "❌ BACKTEST STOPPED"
        )

        print("-" * 60)

        print(
            f"Reason: {exc}"
        )

        print()

        print(
            "Synthetic/random data is DISABLED."
        )

        raise

    print()

    print(
        "Data Source      : Yahoo Finance"
    )

    print(
        f"Bars Loaded       : {len(df)}"
    )

    print(
        f"Timeframe         : {TIMEFRAME}"
    )

    if "time" in df.columns:

        print(
            f"First Candle      : {df.iloc[0]['time']}"
        )

        print(
            f"Last Candle       : {df.iloc[-1]['time']}"
        )

    print()

    # --------------------------------------------------------
    # OHLC VALIDATION
    # --------------------------------------------------------

    print(
        "OHLC VALIDATION"
    )

    print("-" * 60)

    try:

        validate_ohlc(df)

    except Exception as exc:

        print(
            f"❌ {exc}"
        )

        raise

    print(
        "✅ OHLC structure valid"
    )

    print()

    # --------------------------------------------------------
    # RUN BACKTEST
    # --------------------------------------------------------

    result = backtest_strategy(

        df=df,

        ema_fast=20,

        ema_slow=50,

        atr_period=14,

        atr_sl_multiplier=(
            ATR_SL_MULTIPLIER
        ),

        reward_risk=(
            REWARD_RISK
        ),

        min_score=MIN_SCORE,

    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    print(
        "BACKTEST VALIDATION"
    )

    print("-" * 60)

    print(
        f"Trades       : "
        f"{result['total_trades']}"
    )

    print(
        f"Win Rate     : "
        f"{result['win_rate']}%"
    )

    print(
        f"Profit Factor: "
        f"{result['profit_factor']}"
    )

    print(
        f"Net R        : "
        f"{result['net_r']}"
    )

    print(
        f"Expectancy R : "
        f"{result['expectancy_r']}"
    )

    trades = result["trades"]

    # --------------------------------------------------------
    # GRADE ANALYSIS
    # --------------------------------------------------------

    grades = analyze_grades(
        trades
    )

    print()

    print("-" * 60)

    print(
        "PRECISION GRADE ANALYSIS"
    )

    print("-" * 60)

    for grade, data in grades.items():

        print(
            f"{grade:>2} | "
            f"Trades: {data['trades']:>4} | "
            f"Wins: {data['wins']:>4} | "
            f"Win Rate: "
            f"{data['win_rate']:>6.2f}%"
        )

    # --------------------------------------------------------
    # SIGNAL ANALYSIS
    # --------------------------------------------------------

    signals = analyze_signals(
        trades
    )

    print()

    print("-" * 60)

    print(
        "SIGNAL ANALYSIS"
    )

    print("-" * 60)

    for signal, data in signals.items():

        print(
            f"{signal:>4} | "
            f"Trades: {data['trades']:>4} | "
            f"Wins: {data['wins']:>4} | "
            f"Win Rate: "
            f"{data['win_rate']:>6.2f}%"
        )

    # --------------------------------------------------------
    # SAVE TRADE LOG
    # --------------------------------------------------------

    if trades:

        trades_df = pd.DataFrame(
            trades
        )

        trades_df.to_csv(
            "backtest_trades.csv",
            index=False
        )

        print()

        print(
            "Saved: backtest_trades.csv"
        )

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print()

    print("=" * 60)

    print(
        "BACKTEST COMPLETE"
    )

    print("=" * 60)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()