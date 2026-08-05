import pandas as pd
import numpy as np

from backtest import (
    backtest_strategy,
    analyze_grades,
    analyze_signals,
)

from config import (
    SYMBOL,
    TIMEFRAME,
)


# ============================================================
# FOREX AUTO TRADER PRO
# REAL-DATA READY BACKTEST ENGINE
# ============================================================

BARS = 3000

ATR_SL_MULTIPLIER = 1.5
REWARD_RISK = 2.0
MIN_SCORE = 70


# ============================================================
# LOAD DATA
# ============================================================

def load_backtest_data():

    # --------------------------------------------------------
    # Prioritas:
    # 1. data.csv
    # 2. backtest_data.csv
    #
    # File harus memiliki:
    # open, high, low, close
    # --------------------------------------------------------

    candidates = [
        "data.csv",
        "backtest_data.csv",
    ]

    for filename in candidates:

        try:

            df = pd.read_csv(
                filename
            )

            required = [
                "open",
                "high",
                "low",
                "close",
            ]

            missing = [
                col
                for col in required
                if col not in df.columns
            ]

            if missing:
                continue

            df = df.copy()

            for col in required:

                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce"
                )

            df = df.dropna(
                subset=required
            )

            if len(df) < 100:

                continue

            df = df.reset_index(
                drop=True
            )

            if len(df) > BARS:

                df = df.iloc[
                    -BARS:
                ].reset_index(
                    drop=True
                )

            return df, filename

        except (
            FileNotFoundError,
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
        ):

            continue

    return (
        pd.DataFrame(),
        None
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
        "REAL-DATA BACKTEST ENGINE"
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
        "M1               : ENTRY TRIGGER"
    )

    print()

    # --------------------------------------------------------
    # LOAD REAL DATA
    # --------------------------------------------------------

    df, source = load_backtest_data()

    if source is None:

        print(
            "❌ BACKTEST STOPPED"
        )

        print("-" * 60)

        print(
            "No real market data file found."
        )

        print()

        print(
            "Expected one of:"
        )

        print(
            "  data.csv"
        )

        print(
            "  backtest_data.csv"
        )

        print()

        print(
            "Required columns:"
        )

        print(
            "  open, high, low, close"
        )

        print()

        print(
            "Synthetic/random data has been"
        )

        print(
            "DISABLED intentionally."
        )

        return

    # --------------------------------------------------------
    # DATA VALIDATION
    # --------------------------------------------------------

    print(
        f"Data Source      : {source}"
    )

    print(
        f"Bars Loaded       : {len(df)}"
    )

    print(
        f"Timeframe         : {TIMEFRAME}"
    )

    print()

    print(
        "OHLC VALIDATION"
    )

    print("-" * 60)

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

        print(
            f"❌ Invalid OHLC rows: "
            f"{invalid_count}"
        )

        return

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
            f"Trades: "
            f"{data['trades']:>4} | "
            f"Wins: "
            f"{data['wins']:>4} | "
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
            f"Trades: "
            f"{data['trades']:>4} | "
            f"Wins: "
            f"{data['wins']:>4} | "
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