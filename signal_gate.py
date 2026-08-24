from __future__ import annotations

import os
from typing import Final

from config import MIN_SCORE, REWARD_RISK, ATR_SL_MULTIPLIER, SYMBOL, TIMEFRAME
from data import get_bars
from strategy import generate_signal

_ALLOWED_TIMEFRAMES: Final[frozenset[str]] = frozenset({"M15", "M30", "H1"})


def main() -> int:
    mode = os.getenv("TRADING_MODE", "DEMO").strip().upper()
    execute = os.getenv("CTRADER_EXECUTE", "false").strip().lower() == "true"
    if mode != "DEMO":
        raise RuntimeError("signal_gate hanya boleh berjalan dalam DEMO")
    if execute:
        raise RuntimeError("CTRADER_EXECUTE harus false pada signal gate")
    if TIMEFRAME not in _ALLOWED_TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {TIMEFRAME}")

    df = get_bars(SYMBOL, TIMEFRAME, count=300)
    signal = generate_signal(
        df,
        min_score=MIN_SCORE,
        reward_risk=REWARD_RISK,
        atr_sl_multiplier=ATR_SL_MULTIPLIER,
    )

    action = str(signal.get("signal", "HOLD"))
    score = int(signal.get("precision_score", 0))
    print(f"symbol={SYMBOL} timeframe={TIMEFRAME} action={action} score={score}")
    print(f"precision_pass={bool(signal.get('precision_pass', False))}")
    print(f"reason={signal.get('reason', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
