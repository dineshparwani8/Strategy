import os

# ── Strategy Parameters ──────────────────────────────────────────────────────
INITIAL_CAPITAL     = 10_000.0   # USD per symbol
RISK_PER_TRADE      = 0.01       # 1 % of capital per trade
REWARD_MULTIPLE     = 1.0        # 1 R : 1 R
RETRACEMENT_PCT     = 0.50       # 50 % pull-back entry
TRANSACTION_FEE     = 0.0005     # 0.05 % per side (Binance taker)

# ── Market ────────────────────────────────────────────────────────────────────
SYMBOLS             = ["BTC/USDT", "ETH/USDT"]
TIMEFRAME           = "15m"
EXCHANGE_ID         = "binance"
CANDLE_LIMIT        = 100        # candles fetched per cycle

# ── Storage ───────────────────────────────────────────────────────────────────
DATA_DIR            = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TRADE_RETENTION_DAYS = 30

# ── Server ────────────────────────────────────────────────────────────────────
API_HOST            = "0.0.0.0"
API_PORT            = 8000
