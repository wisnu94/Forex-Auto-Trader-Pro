import time

from config import (
    TRADING_MODE,
    SYMBOL,
    TIMEFRAME,
    RISK_PER_TRADE,
    MAX_OPEN_POSITIONS,
    ATR_PERIOD,
    ATR_SL_MULTIPLIER,
    REWARD_RISK,
)

from data import (
    get_bars,
    get_tick,
)

from strategy import (
    generate_signal,
)

from risk import (
    calculate_sl_tp,
)

from execution import (
    send_market_order,
)

from journal import (
    log_signal,
    log_order,
)


# ============================================================
# BOT SETTINGS
# ============================================================

LOOP_SECONDS = 60


# ============================================================
# ANALYZE MARKET
# ============================================================

def analyze_market():

    # --------------------------------------------------------
    # GET MARKET DATA
    # --------------------------------------------------------

    df = get_bars(
        SYMBOL,
        TIMEFRAME,
        count=300
    )

    # --------------------------------------------------------
    # GENERATE SIGNAL
    # --------------------------------------------------------

    result = generate_signal(
        df,
        ema_fast=20,
        ema_slow=50,
        atr_period=ATR_PERIOD
    )

    signal = result["signal"]

    print()
    print("=" * 60)
    print("FOREX AUTO TRADER PRO")
    print("=" * 60)

    print(
        f"Symbol     : {SYMBOL}"
    )

    print(
        f"Timeframe  : {TIMEFRAME}"
    )

    print(
        f"Mode       : {TRADING_MODE}"
    )

    print(
        f"Signal     : {signal}"
    )

    print(
        f"Trend      : {result['trend']}"
    )

    print(
        f"Structure  : {result['structure']}"
    )

    print(
        f"Momentum   : {result['momentum']}"
    )

    print(
        f"Score      : {result['score']}"
    )

    print(
        f"ATR        : {result['atr']}"
    )

    # --------------------------------------------------------
    # JOURNAL SIGNAL
    # --------------------------------------------------------

    log_signal(

        symbol=SYMBOL,

        signal=signal,

        score=result["score"],

        reason=(
            f"trend={result['trend']}; "
            f"structure={result['structure']}; "
            f"momentum={result['momentum']}"
        ),

        mode=TRADING_MODE
    )

    # --------------------------------------------------------
    # NO TRADE
    # --------------------------------------------------------

    if signal == "HOLD":

        print(
            "Decision   : HOLD"
        )

        return

    # --------------------------------------------------------
    # CURRENT PRICE
    # --------------------------------------------------------

    tick = get_tick(
        SYMBOL
    )

    if signal == "BUY":

        entry = float(
            tick.ask
        )

    else:

        entry = float(
            tick.bid
        )

    # --------------------------------------------------------
    # SL / TP
    # --------------------------------------------------------

    levels = calculate_sl_tp(

        signal=signal,

        entry_price=entry,

        atr_value=result["atr"],

        atr_multiplier=ATR_SL_MULTIPLIER,

        reward_risk=REWARD_RISK
    )

    if levels is None:

        print(
            "Decision   : REJECTED"
        )

        print(
            "Reason     : Invalid SL/TP"
        )

        return

    print(
        f"Entry      : {levels['entry']}"
    )

    print(
        f"SL         : {levels['sl']}"
    )

    print(
        f"TP         : {levels['tp']}"
    )

    print(
        f"R:R        : 1:{REWARD_RISK}"
    )

    # --------------------------------------------------------
    # OPEN POSITION LIMIT
    # --------------------------------------------------------

    from execution import (
        get_open_positions
    )

    positions = get_open_positions(
        SYMBOL
    )

    if len(positions) >= MAX_OPEN_POSITIONS:

        print(
            "Decision   : REJECTED"
        )

        print(
            "Reason     : Max open positions"
        )

        return

    # --------------------------------------------------------
    # V1 POSITION SIZE
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # The exact MT5 tick-value based sizing
    # will be upgraded in the next Risk Engine.
    #
    # For V1 we use a conservative placeholder.
    #

    volume = 0.01

    # --------------------------------------------------------
    # EXECUTION
    # --------------------------------------------------------

    result_order = send_market_order(

        symbol=SYMBOL,

        signal=signal,

        volume=volume,

        stop_loss=levels["sl"],

        take_profit=levels["tp"]
    )

    print(
        f"Execution  : {result_order}"
    )

    # --------------------------------------------------------
    # JOURNAL ORDER
    # --------------------------------------------------------

    log_order(

        symbol=SYMBOL,

        signal=signal,

        volume=volume,

        entry=levels["entry"],

        stop_loss=levels["sl"],

        take_profit=levels["tp"],

        mode=TRADING_MODE,

        reason=(
            f"score={result['score']}"
        )
    )


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    print()
    print(
        "=========================================="
    )

    print(
        " FOREX AUTO TRADER PRO - V1"
    )

    print(
        "=========================================="
    )

    print(
        f"Mode      : {TRADING_MODE}"
    )

    print(
        f"Symbol    : {SYMBOL}"
    )

    print(
        f"Timeframe : {TIMEFRAME}"
    )

    print(
        "LIVE ORDER: LOCKED"
    )

    print()

    while True:

        try:

            analyze_market()

        except Exception as error:

            print()
            print(
                "BOT ERROR:"
            )

            print(
                error
            )

        print()
        print(
            f"Next scan in "
            f"{LOOP_SECONDS} seconds..."
        )

        time.sleep(
            LOOP_SECONDS
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()