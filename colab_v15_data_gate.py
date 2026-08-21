from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

DATA_PATH = Path(os.getenv("BROKER_DATA_PATH", "data/xauusd_m15_broker.csv"))
MIN_BARS = int(os.getenv("BROKER_MIN_BARS", "20000"))
REQUIRED = ("time", "open", "high", "low", "close")


def main() -> int:
    print("=" * 78)
    print("FOREX AUTO TRADER PRO - COLAB V15 DATA GATE")
    print("=" * 78)
    print(f"Path: {DATA_PATH}")
    print(f"Minimum bars: {MIN_BARS}")

    if not DATA_PATH.is_file():
        print("STATUS: BLOCKED_DATA_MISSING")
        print("Upload the exact broker XAUUSD M15 CSV before running strategy audits.")
        return 2

    frame = pd.read_csv(DATA_PATH)
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    missing = [column for column in REQUIRED if column not in frame.columns]
    if missing:
        print(f"STATUS: BLOCKED_MISSING_COLUMNS {missing}")
        return 2

    frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    invalid = (
        frame["time"].isna()
        | frame[["open", "high", "low", "close"]].isna().any(axis=1)
        | (frame["high"] < frame["low"])
        | (frame["high"] < frame["open"])
        | (frame["high"] < frame["close"])
        | (frame["low"] > frame["open"])
        | (frame["low"] > frame["close"])
    )
    duplicates = int(frame["time"].duplicated().sum())
    clean = frame.loc[~invalid].sort_values("time").drop_duplicates("time").reset_index(drop=True)

    print(f"Raw rows: {len(frame)}")
    print(f"Valid rows: {len(clean)}")
    print(f"Invalid rows: {int(invalid.sum())}")
    print(f"Duplicate timestamps: {duplicates}")
    if not clean.empty:
        print(f"First: {clean['time'].iloc[0]}")
        print(f"Last : {clean['time'].iloc[-1]}")
        print(f"Span days: {(clean['time'].iloc[-1] - clean['time'].iloc[0]).total_seconds() / 86400:.2f}")

    if len(clean) < MIN_BARS:
        print("STATUS: BLOCKED_INSUFFICIENT_BARS")
        return 2
    if int(invalid.sum()) != 0 or duplicates != 0:
        print("STATUS: BLOCKED_DATA_INTEGRITY")
        return 2

    clean.to_csv(DATA_PATH, index=False)
    print("STATUS: DATA_READY")
    print("No strategy or live-trading setting changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
