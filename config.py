import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# FOREX AUTO TRADER PRO
# V1 - TRADING CORE
# ============================================================

TRADING_MODE = os.getenv("TRADING_MODE", "PAPER").upper()

SYMBOL = os.getenv("MT5_SYMBOL", "EURUSD")
TIMEFRAME = os.getenv("TIMEFRAME", "M15")

# Risk
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.005"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.02"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "1"))

# Strategy
EMA_FAST = int(os.getenv("EMA_FAST", "20"))
EMA_SLOW = int(os.getenv("EMA_SLOW", "50"))

# Stop Loss / Take Profit
ATR_PERIOD = int(os.getenv("ATR_PERIOD", "14"))
ATR_SL_MULTIPLIER = float(
    os.getenv("ATR_SL_MULTIPLIER", "1.5")
)
REWARD_RISK = float(
    os.getenv("REWARD_RISK", "2.0")
)

# Spread protection
MAX_SPREAD_POINTS = float(
    os.getenv("MAX_SPREAD_POINTS", "30")
)

# Safety
ALLOW_LIVE_TRADING = False


# ============================================================
# VALIDATION
# ============================================================

if TRADING_MODE not in {"PAPER", "DEMO", "LIVE"}:
    raise ValueError(
        "TRADING_MODE harus PAPER, DEMO, atau LIVE"
    )

if RISK_PER_TRADE <= 0 or RISK_PER_TRADE > 0.02:
    raise ValueError(
        "RISK_PER_TRADE harus > 0 dan <= 2%"
    )

if MAX_DAILY_LOSS <= 0 or MAX_DAILY_LOSS > 0.05:
    raise ValueError(
        "MAX_DAILY_LOSS harus > 0 dan <= 5%"
    )

if MAX_OPEN_POSITIONS < 1:
    raise ValueError(
        "MAX_OPEN_POSITIONS minimal 1"
    )

if ATR_PERIOD < 5:
    raise ValueError(
        "ATR_PERIOD terlalu kecil"
    )

if ATR_SL_MULTIPLIER <= 0:
    raise ValueError(
        "ATR_SL_MULTIPLIER harus > 0"
    )

if REWARD_RISK < 1:
    raise ValueError(
        "REWARD_RISK minimal 1.0"
    )

# Hard safety lock:
# V1 belum boleh mengirim order LIVE.
if TRADING_MODE == "LIVE" and not ALLOW_LIVE_TRADING:
    raise RuntimeError(
        "LIVE TRADING masih dikunci pada V1."
    )