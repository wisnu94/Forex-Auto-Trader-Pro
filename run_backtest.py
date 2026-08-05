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
# BACKTEST SETTINGS
# ============================================================

BARS = 3000

ATR_SL_MULTIPLIER = 1.5
REWARD_RISK = 2.0

MIN_SCORE = 70


# ============================================================
# SYNTHETIC BACKTEST DATA
# ============================================================

def create_backtest_data(bars=3000):

    rng = np.random.default_rng(42)

    returns = rng.normal(
        loc=0.00005,
        scale=0.001,
        size=bars
    )

    close = (
        1.1000
        * np.exp(
            np.cumsum(returns)
        )
    )

    open_price = np.roll(
        close,
        1
    )

    open_price[0] = close[0]

    high = (
        np.maximum(
            open_price,
            close
        )
        + 0.0005
    )

    low = (
        np.minimum(
            open_price,
            close
        )
        - 0.0005
    )

    df = pd.DataFrame(
        {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "tick_volume": np.full(
                bars,
                1000
            ),
            "spread": np.zeros(
                bars
            ),
            "real_volume": np.zeros(
                bars
            ),
        }
    )

    return df


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
        "BACKTEST ENGINE V3"
    )

    print("=" * 60)

    print(
        f"Symbol          : {SYMBOL}"
    )

    # M15 tetap menjadi BASE DATA.
    # MTF engine berjalan H1 -> M15 -> M1.

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

    print(
        "M1 Data          : SYNTHETIC PROXY"
    )

    print(
        f"Bars             : {BARS} M15"
    )

    print()

    # --------------------------------------------------------
    # LOAD BACKTEST DATA
    # --------------------------------------------------------

    df = create_backtest_data(
        bars=BARS
    )

    print(
        f"Generated base bars: {len(df)} M15"
    )

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

        min_score=MIN_SCORE

    )

    # --------------------------------------------------------
    # BACKTEST VALIDATION
    # --------------------------------------------------------

    if result["total_trades"] == 0:

        print()

        print(
            "⚠️ BACKTEST VALIDATION"
        )

        print("-" * 60)

        print(
            "No valid trades were generated."
        )

        print(
            "Do NOT optimize the strategy yet."
        )

        print(
            "Reason: the current backtest "
            "filter may be too restrictive."
        )

    else:

        print()

        print(
            "✅ BACKTEST VALIDATION"
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

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print()

    print("-" * 60)

    print(
        "BACKTEST SUMMARY"
    )

    print("-" * 60)

    print(
        f"Total Trades   : "
        f"{result['total_trades']}"
    )

    print(
        f"Wins           : "
        f"{result['wins']}"
    )

    print(
        f"Losses         : "
        f"{result['losses']}"
    )

    print(
        f"Win Rate       : "
        f"{result['win_rate']}%"
    )

    print(
        f"Profit Factor  : "
        f"{result['profit_factor']}"
    )

    print(
        f"Net R          : "
        f"{result['net_r']}"
    )

    print(
        f"Expectancy R   : "
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