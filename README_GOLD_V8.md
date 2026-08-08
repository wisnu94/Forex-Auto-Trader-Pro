# Forex Auto Trader Pro — GOLD V8

## Tujuan
Versi ini mengubah target produksi menjadi **XAUUSD / Gold melalui MetaTrader 5** dan mempertahankan Yahoo Finance hanya sebagai sumber backtest CI.

### Yang berubah
1. `config.py`
   - default symbol: `XAUUSD`
   - timeframe: `M15`
   - risk default: `0.25% / trade`
   - max daily loss: `1%`
   - minimum precision score: `78`
   - live trading tetap terkunci.

2. `data.py`
   - production data: MetaTrader 5
   - `copy_rates_from_pos()` untuk OHLC
   - tick, spread, dan broker symbol dibaca langsung dari MT5.
   - Yahoo hanya dipakai jika `source="YAHOO"`.

3. `strategy.py`
   - MTF H1 + M15 wajib searah.
   - ADX + DI direction.
   - RSI anti-exhaustion.
   - ATR volatility regime.
   - EMA distance anti-chasing.
   - candle confirmation.
   - score floor 78.

4. `run_backtest.py`
   - backtest memakai `GC=F` sebagai proxy Gold karena GitHub Actions tidak menjalankan terminal MT5.
   - jangan menganggap hasil `GC=F` identik dengan XAUUSD broker.

## Penting: MT5 tidak berjalan langsung di iPhone
Bot Python MT5 membutuhkan terminal MetaTrader 5. Official MetaTrader5 Python package tersedia untuk Windows x64. Jalankan bot di **Windows VPS/PC yang memiliki MT5**, sementara iPhone dipakai untuk memantau.

## Instalasi pada Windows VPS
```bash
pip install -r requirements-mt5.txt
```

Pastikan MT5 sudah terinstall dan login ke akun broker.

## `.env` contoh
```env
TRADING_MODE=PAPER
DATA_SOURCE=MT5
MT5_SYMBOL=XAUUSD
TIMEFRAME=M15

RISK_PER_TRADE=0.0025
MAX_DAILY_LOSS=0.01
MAX_OPEN_POSITIONS=1

MIN_SCORE=78
ATR_SL_MULTIPLIER=1.6
REWARD_RISK=1.6

MAX_SPREAD_POINTS=80
```

Jika broker menggunakan symbol lain, misalnya `XAUUSDm`, ubah:
```env
MT5_SYMBOL=XAUUSDm
```

## Urutan validasi
1. PAPER
2. DEMO
3. forward-test minimal beberapa minggu
4. baru pertimbangkan LIVE

`ALLOW_LIVE_TRADING=False` sengaja tidak diubah.

## Target kualitas
Target 70–80% win-rate **tidak dijamin**. Yang harus kita cari adalah kombinasi:
- positive expectancy
- profit factor > 1
- drawdown terkendali
- hasil tidak runtuh pada data out-of-sample
- BUY dan SELL sama-sama tervalidasi

Jangan mengubah threshold hanya untuk membuat satu backtest terlihat bagus.
