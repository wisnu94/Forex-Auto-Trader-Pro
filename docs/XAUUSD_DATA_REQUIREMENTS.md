# XAUUSD Data Requirements — V15 Validation

## Decision
Do not promote a strategy using Yahoo `GC=F` as proof of XAUUSD spot profitability.

## Required validation dataset
- Instrument: the exact XAUUSD symbol used by the intended MT5 broker
- Timeframe: M15, with lower timeframe data available when intrabar ordering matters
- History: preferably 1–2 years or more
- Fields: timestamp, open, high, low, close, tick volume/volume when available, spread when available
- Timestamps: timezone and DST handling documented
- Data integrity: no duplicate timestamps, invalid OHLC, unexplained gaps, or mixed sessions

## Required evaluation
1. Re-run the canonical S80 baseline on broker-matched data.
2. Attribute BUY and SELL separately.
3. Evaluate rolling windows and untouched chronological holdouts.
4. Include spread, commission and conservative slippage.
5. Stress intrabar SL/TP ordering with lower-timeframe data where available.
6. Bootstrap trade outcomes only as a supplement, not as proof of future profitability.
7. Keep live trading disabled until all gates pass.

## Current blocker
The CI Yahoo source maps XAUUSD to `GC=F`, a gold-futures proxy. The V15 data-quality gate therefore remains NOT_DATA_READY for final XAUUSD validation.
