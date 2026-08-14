# Broker XAUUSD data upload

Place the exact MT5 broker XAUUSD M15 history at:

`data/xauusd_m15_broker.csv`

Required columns:

`time,open,high,low,close`

Preferred columns:

`time,open,high,low,close,tick_volume,real_volume,spread`

Target: at least 20,000 M15 bars; more history is preferred.

The file must contain the exact XAUUSD symbol/feed intended for the bot, not Yahoo `GC=F`.

After upload, the `Gold V15 Data Quality` / broker audit workflow can validate it. Do not enable live trading from this dataset until the full robustness gates pass.
