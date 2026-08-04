import time

import MetaTrader5 as mt5

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
from mtf import (
    get_mtf_confirmation,
)

from risk import (
    calculate_sl_tp,
    calculate_position_size_mt5,
)

from execution import (
    send_market_order,
    get_open_positions,
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
# MT5 INITIALIZATION
# ============================================================

def initialize_mt5():

    if not mt5.initialize():

        raise RuntimeError(
            f"MT5 initialize failed: "
            f"{mt5.last_error()}"
        )


# ============================================================
# GET ACCOUNT EQUITY
# ============================================================

def get_equity():

    initialize_mt5()

    account = mt5.account_info()

    if account is None:

        raise RuntimeError(
            f"Unable to read account info: "
            f"{mt5.last_error()}"
        )

    return float(
        account.equity
    )


# ============================================================
# GET BROKER SYMBOL DATA
# ============================================================

def get_symbol_risk_data(symbol):

    initialize_mt5()

    info = mt5.symbol_info(
        symbol
    )

    if info is None:

        raise RuntimeError(
            f"Symbol not found: {symbol}"
        )

    if not info.visible:

        if not mt5.symbol_select(
            symbol,
            True
        ):

            raise RuntimeError(
                f"Cannot activate symbol: {symbol}"
            )

    return {
        "tick_size": float(
            info.trade_tick_size
        ),

        "tick_value": float(
            info.trade_tick_value
        ),

        "volume_min": float(
            info.volume_min
        ),

        "volume_max": float(
            info.volume_max
        ),

        "volume_step": float(
            info.volume_step
        ),

        "digits": int(
            info.digits
        ),
    }


# ============================================================
# ANALYZE MARKET
# ============================================================

def analyze_market():

    print()
    print(
        "=" * 60
    )

    print(
        "FOREX AUTO TRADER PRO"
    )

    print(
        "=" * 60
    )

    print(
        f"Symbol     : {SYMBOL}"
    )

    print(
        f"Timeframe  : {TIMEFRAME}"
    )

    print(
        f"Mode       : {TRADING_MODE}"
    )

    # --------------------------------------------------------
    # MARKET DATA
    # --------------------------------------------------------

    df = get_bars(
        SYMBOL,
        TIMEFRAME,
        count=300
    )
    
    # --------------------------------------------------------
    # MTF CONFIRMATION
    # --------------------------------------------------------

    mtf_confirmation = get_mtf_confirmation(
        SYMBOL,
        timeframes=("H4", "H1", "M15"),
        bars=150
    )

    print()
    print(
        "MTF CONFIRMATION"
    )

    print(
        f"H4         : "
        f"{mtf_confirmation['trends']['H4']}"
    )

    print(
        f"H1         : "
        f"{mtf_confirmation['trends']['H1']}"
    )

    print(
        f"M15        : "
        f"{mtf_confirmation['trends']['M15']}"
    )

    print(
        f"MTF Score  : "
        f"{mtf_confirmation['score']}"
    )

    print(
        f"MTF Status : "
        f"{mtf_confirmation['status']}"
    )

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    signal_result = generate_signal(

    # --------------------------------------------------------
    # SIGNAL
    # --------------------------------------------------------

    signal_result = generate_signal(
        df,
        ema_fast=20,
        ema_slow=50,
        atr_period=ATR_PERIOD,
        mtf_confirmation=mtf_confirmation
    )

    signal = signal_result[
        "signal"
    ]

    print(
        f"Signal     : {signal}"
    )

    print(
        f"Trend      : "
        f"{signal_result['trend']}"
    )

    print(
        f"Structure  : "
        f"{signal_result['structure']}"
    )

    print(
        f"Momentum   : "
        f"{signal_result['momentum']}"
    )

    print(
        f"Score      : "
        f"{signal_result['score']}"
    )

    print(
        f"ATR        : "
        f"{signal_result['atr']}"
    )

    # --------------------------------------------------------
    # LOG SIGNAL
    # --------------------------------------------------------

    log_signal(

        symbol=SYMBOL,

        signal=signal,

        score=signal_result[
            "score"
        ],

        reason=(
            f"trend="
            f"{signal_result['trend']}; "

            f"structure="
            f"{signal_result['structure']}; "

            f"momentum="
            f"{signal_result['momentum']}"
        ),

        mode=TRADING_MODE
    )

    # --------------------------------------------------------
    # HOLD
    # --------------------------------------------------------

    if signal == "HOLD":

        print(
            "Decision   : HOLD"
        )

        return

    # --------------------------------------------------------
    # OPEN POSITION LIMIT
    # --------------------------------------------------------

    positions = get_open_positions(
        SYMBOL
    )

    if len(positions) >= (
        MAX_OPEN_POSITIONS
    ):

        print(
            "Decision   : REJECTED"
        )

        print(
            "Reason     : "
            "Maximum open positions"
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

        atr_value=signal_result[
            "atr"
        ],

        atr_multiplier=(
            ATR_SL_MULTIPLIER
        ),

        reward_risk=(
            REWARD_RISK
        )
    )

    if levels is None:

        print(
            "Decision   : REJECTED"
        )

        print(
            "Reason     : "
            "Invalid SL / TP"
        )

        return

    print(
        f"Entry      : "
        f"{levels['entry']}"
    )

    print(
        f"SL         : "
        f"{levels['sl']}"
    )

    print(
        f"TP         : "
        f"{levels['tp']}"
    )

    print(
        f"R:R        : "
        f"1:{REWARD_RISK}"
    )

    # --------------------------------------------------------
    # ACCOUNT EQUITY
    # --------------------------------------------------------

    equity = get_equity()

    print(
        f"Equity     : "
        f"{equity:.2f}"
    )

    # --------------------------------------------------------
    # BROKER RISK DATA
    # --------------------------------------------------------

    broker = get_symbol_risk_data(
        SYMBOL
    )

    # --------------------------------------------------------
    # POSITION SIZE
    # --------------------------------------------------------

    volume = calculate_position_size_mt5(

        equity=equity,

        risk_percent=(
            RISK_PER_TRADE
        ),

        entry_price=(
            levels["entry"]
        ),

        stop_loss=(
            levels["sl"]
        ),

        tick_size=(
            broker["tick_size"]
        ),

        tick_value=(
            broker["tick_value"]
        ),

        volume_min=(
            broker["volume_min"]
        ),

        volume_max=(
            broker["volume_max"]
        ),

        volume_step=(
            broker["volume_step"]
        )
    )

    if volume <= 0:

        print(
            "Decision   : REJECTED"
        )

        print(
            "Reason     : "
            "Calculated volume below "
            "broker minimum"
        )

        return

    print(
        f"Volume     : "
        f"{volume}"
    )

    print(
        f"Risk/trade : "
        f"{RISK_PER_TRADE * 100:.2f}%"
    )

    # --------------------------------------------------------
    # EXECUTION
    # --------------------------------------------------------

    result_order = send_market_order(

        symbol=SYMBOL,

        signal=signal,

        volume=volume,

        stop_loss=(
            levels["sl"]
        ),

        take_profit=(
            levels["tp"]
        )
    )

    print(
        f"Execution  : "
        f"{result_order}"
    )

    # --------------------------------------------------------
    # JOURNAL
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
            f"score="
            f"{signal_result['score']}"
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