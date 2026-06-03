"""
trade_logger.py – JSON-based trade storage & state management.

Files:
  data/state.json   – current open position / IDLE state per symbol
  data/trades.json  – completed trade records (rolling 30 days)
"""
import json
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from config import DATA_DIR, TRADE_RETENTION_DAYS, INITIAL_CAPITAL, SYMBOLS

logger = logging.getLogger(__name__)
os.makedirs(DATA_DIR, exist_ok=True)

STATE_FILE  = os.path.join(DATA_DIR, "state.json")
TRADES_FILE = os.path.join(DATA_DIR, "trades.json")


# ─────────────────────────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────────────────────────

def _default_sym_state(capital: float = INITIAL_CAPITAL) -> dict:
    return {
        "status":        "IDLE",    # IDLE | IN_TRADE
        "capital":       capital,
        "trade_type":    None,      # LONG | SHORT
        "entry_price":   None,
        "stop_price":    None,
        "target_price":  None,
        "position_size": None,
        "entry_time":    None,
        "signal_candle_time": None,
        "last_check":    None,
    }


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            # Ensure all configured symbols exist
            for sym in SYMBOLS:
                if sym not in state:
                    state[sym] = _default_sym_state()
            return state
        except Exception as e:
            logger.warning(f"Could not read state.json, reinitialising: {e}")

    state = {sym: _default_sym_state() for sym in SYMBOLS}
    save_state(state)
    return state


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# TRADES
# ─────────────────────────────────────────────────────────────────────────────

def _parse_dt(s: str) -> datetime:
    """Parse an ISO-format datetime string (with or without tz)."""
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_trades() -> list:
    """Load all trades from the last TRADE_RETENTION_DAYS days."""
    if not os.path.exists(TRADES_FILE):
        return []
    try:
        with open(TRADES_FILE) as f:
            all_trades = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read trades.json: {e}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=TRADE_RETENTION_DAYS)
    kept = []
    for t in all_trades:
        try:
            if _parse_dt(t["entry_time"]) > cutoff:
                kept.append(t)
        except Exception:
            kept.append(t)   # keep if date unparseable
    return kept


def save_trade(trade: dict) -> None:
    trades = load_trades()
    trades.append(trade)
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2, default=str)
    logger.info(f"Trade saved: {trade['symbol']} {trade['result']}  PnL={trade['pnl']:.2f}")


def build_trade_record(
    symbol:         str,
    trade_type:     str,
    entry_price:    float,
    exit_price:     float,
    stop_price:     float,
    target_price:   float,
    position_size:  float,
    result:         str,
    exit_reason:    str,
    pnl:            float,
    capital_before: float,
    capital_after:  float,
    entry_time:     str,
    exit_time:      str,
    signal_candle_time: str = None,
) -> dict:
    return {
        "id":                str(uuid.uuid4()),
        "symbol":            symbol,
        "trade_type":        trade_type,
        "entry_price":       round(entry_price, 4),
        "exit_price":        round(exit_price,  4),
        "stop_price":        round(stop_price,  4),
        "target_price":      round(target_price, 4),
        "position_size":     round(position_size, 6),
        "result":            result,
        "exit_reason":       exit_reason,
        "pnl":               round(pnl, 2),
        "pnl_pct":           round(pnl / capital_before * 100, 3) if capital_before else 0,
        "capital_before":    round(capital_before, 2),
        "capital_after":     round(capital_after,  2),
        "entry_time":        entry_time,
        "exit_time":         exit_time,
        "signal_candle_time": signal_candle_time,
        "recorded_at":       datetime.now(timezone.utc).isoformat(),
    }
