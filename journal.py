import csv
import os
from datetime import datetime, timezone


# ============================================================
# JOURNAL CONFIG
# ============================================================

JOURNAL_FILE = "trades.csv"


# ============================================================
# CREATE JOURNAL
# ============================================================

def initialize_journal():

    if os.path.exists(JOURNAL_FILE):

        return

    headers = [
        "timestamp",
        "event",
        "symbol",
        "signal",
        "volume",
        "entry",
        "stop_loss",
        "take_profit",
        "price",
        "profit",
        "reason",
        "mode",
    ]

    with open(
        JOURNAL_FILE,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=headers
        )

        writer.writeheader()


# ============================================================
# WRITE JOURNAL
# ============================================================

def log_event(
    event,
    symbol="",
    signal="",
    volume=0.0,
    entry=0.0,
    stop_loss=0.0,
    take_profit=0.0,
    price=0.0,
    profit=0.0,
    reason="",
    mode=""
):

    initialize_journal()

    row = {

        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "event":
            event,

        "symbol":
            symbol,

        "signal":
            signal,

        "volume":
            volume,

        "entry":
            entry,

        "stop_loss":
            stop_loss,

        "take_profit":
            take_profit,

        "price":
            price,

        "profit":
            profit,

        "reason":
            reason,

        "mode":
            mode,
    }

    with open(
        JOURNAL_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=row.keys()
        )

        writer.writerow(row)


# ============================================================
# LOG SIGNAL
# ============================================================

def log_signal(
    symbol,
    signal,
    score,
    reason,
    mode
):

    log_event(

        event="SIGNAL",

        symbol=symbol,

        signal=signal,

        reason=(
            f"score={score}; "
            f"{reason}"
        ),

        mode=mode
    )


# ============================================================
# LOG ORDER
# ============================================================

def log_order(
    symbol,
    signal,
    volume,
    entry,
    stop_loss,
    take_profit,
    mode,
    reason=""
):

    log_event(

        event="ORDER",

        symbol=symbol,

        signal=signal,

        volume=volume,

        entry=entry,

        stop_loss=stop_loss,

        take_profit=take_profit,

        mode=mode,

        reason=reason
    )


# ============================================================
# LOG CLOSE
# ============================================================

def log_close(
    symbol,
    signal,
    volume,
    entry,
    price,
    profit,
    reason,
    mode
):

    log_event(

        event="CLOSE",

        symbol=symbol,

        signal=signal,

        volume=volume,

        entry=entry,

        price=price,

        profit=profit,

        reason=reason,

        mode=mode
    )