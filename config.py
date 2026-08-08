import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# FOREX AUTO TRADER PRO - GOLD V8
# Production target: MetaTrader 5 / XAUUSD
# ============================================================

TRADING_MODE = os.getenv("TRADING_MODE", "PAPER").upper()
DATA_SOURCE = os.getenv("DATA_SOURCE", "MT5").upper()

SYMBOL = os.getenv("MT5_SYMBOL", "XAUUSD")
TIMEFRAME = os.getenv("TIMEFRAME", "M15")

# Conservative risk defaults
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.0025"))   # 0.25%
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.01"))     # 1%
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "1"))

# Strategy
EMA_FAST = int(os.getenv("EMA_FAST", "20"))
EMA_SLOW = int(os.getenv("EMA_SLOW", "50"))

# Risk model
ATR_PERIOD = int(os.getenv("ATR_PERIOD", "14"))
ATR_SL_MULTIPLIER = float(os.getenv("ATR_SL_MULTIPLIER", "1.6"))
REWARD_RISK = float(os.getenv("REWARD_RISK", "1.6"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "78"))

# Execution protection
MAX_SPREAD_POINTS = float(os.getenv("MAX_SPREAD_POINTS", "80"))

# MT5 connection. Leave empty if the terminal is already logged in.
MT5_PATH = os.getenv("MT5_PATH", "").strip()
MT5_LOGIN = os.getenv("MT5_LOGIN", "").strip()
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "").strip()
MT5_SERVER = os.getenv("MT5_SERVER", "").strip()

# HARD SAFETY LOCK:
# Keep False until the strategy passes demo/forward validation.
ALLOW_LIVE_TRADING = False

if TRADING_MODE not in {"PAPER", "DEMO", "LIVE"}:
    raise ValueError("TRADING_MODE harus PAPER, DEMO, atau LIVE")

if DATA_SOURCE not in {"MT5", "YAHOO"}:
    raise ValueError("DATA_SOURCE harus MT5 atau YAHOO")

if RISK_PER_TRADE <= 0 or RISK_PER_TRADE > 0.02:
    raise ValueError("RISK_PER_TRADE harus > 0 dan <= 2%")

if MAX_DAILY_LOSS <= 0 or MAX_DAILY_LOSS > 0.05:
    raise ValueError("MAX_DAILY_LOSS harus > 0 dan <= 5%")

if MAX_OPEN_POSITIONS < 1:
    raise ValueError("MAX_OPEN_POSITIONS minimal 1")

if ATR_PERIOD < 5:
    raise ValueError("ATR_PERIOD terlalu kecil")

if ATR_SL_MULTIPLIER <= 0:
    raise ValueError("ATR_SL_MULTIPLIER harus > 0")

if REWARD_RISK < 1:
    raise ValueError("REWARD_RISK minimal 1.0")

if MIN_SCORE < 70 or MIN_SCORE > 100:
    raise ValueError("MIN_SCORE harus 70..100")

if TRADING_MODE == "LIVE" and not ALLOW_LIVE_TRADING:
    raise RuntimeError("LIVE TRADING masih DIKUNCI. Gunakan PAPER/DEMO untuk validasi.")
