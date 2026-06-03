"""
strategy.py – Forward-testing version of the Engulfing Retracement strategy.

Every 15-minute cycle:
  closed[-3] = prev-filter candle
  closed[-2] = signal / engulfing candle
  closed[-1] = trigger / entry candle  (just closed)
"""
import pandas as pd
import logging
from config import RISK_PER_TRADE, REWARD_MULTIPLE, RETRACEMENT_PCT, TRANSACTION_FEE

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def calculate_pnl(entry: float, exit_price: float, size: float,
                  trade_type: str, fee: float = TRANSACTION_FEE) -> float:
    fees = (entry * size + exit_price * size) * fee
    if trade_type == "LONG":
        return (exit_price - entry) * size - fees
    return (entry - exit_price) * size - fees


def calculate_position_size(capital: float, risk_per_unit: float) -> float:
    """risk 1 % of capital; risk_per_unit = |entry - stop|."""
    return (capital * RISK_PER_TRADE) / risk_per_unit


# ─────────────────────────────────────────────────────────────────────────────
# TRADE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def check_trade_exit(sym_state: dict, candle: pd.Series) -> dict | None:
    """
    Returns exit info if SL or TP was hit on `candle`, else None.
    Uses OCO logic: if both hit, assume SL (worst case).
    """
    trade_type = sym_state["trade_type"]
    stop   = sym_state["stop_price"]
    target = sym_state["target_price"]
    hi, lo = candle["High"], candle["Low"]

    sl_hit = (lo <= stop)   if trade_type == "LONG" else (hi >= stop)
    tp_hit = (hi >= target) if trade_type == "LONG" else (lo <= target)

    if not sl_hit and not tp_hit:
        return None

    if sl_hit and tp_hit:
        return {"exit_price": stop,   "result": "LOSS", "exit_reason": "OCO_SL"}
    if sl_hit:
        return {"exit_price": stop,   "result": "LOSS", "exit_reason": "SL"}
    return     {"exit_price": target, "result": "WIN",  "exit_reason": "TP"}


# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL DETECTION  +  ENTRY CHECK  (one function, one cycle)
# ─────────────────────────────────────────────────────────────────────────────

def run_signal_check(closed_df: pd.DataFrame, capital: float) -> dict:
    """
    Inspect the last 3 closed candles.

    Pattern:
      prev  = closed[-3]  — filter: must be a strong candle (body ≥ 50 % range)
      row   = closed[-2]  — engulfing signal candle  (body > 0.25 % of Open)
      trig  = closed[-1]  — entry trigger candle

    Returns:
      {"action": "NONE"}
      {"action": "ENTER",          trade_type, entry/stop/target/size, times}
      {"action": "TRADE_COMPLETED", ... + exit_price, result, pnl}
    """
    if len(closed_df) < 4:
        return {"action": "NONE"}

    prev = closed_df.iloc[-3]
    row  = closed_df.iloc[-2]   # signal candle
    trig = closed_df.iloc[-1]   # trigger candle

    # ── Filter 1: current body > 0.25 % ──────────────────────────────────────
    body = abs(row["Close"] - row["Open"])
    if body / row["Open"] * 100 < 0.25:
        return {"action": "NONE"}

    # ── Filter 2: prev is a strong candle (body ≥ 50 % of range) ─────────────
    prev_body  = abs(prev["Close"] - prev["Open"])
    prev_range = prev["High"] - prev["Low"]
    if prev_range == 0 or prev_body < 0.5 * prev_range:
        return {"action": "NONE"}

    # ── Engulfing detection ───────────────────────────────────────────────────
    bullish = (
        prev["Close"] < prev["Open"]
        and row["Close"] > row["Open"]
        and row["Open"]  <= prev["Close"]
        and row["Close"] >= prev["Open"]
    )
    bearish = (
        prev["Close"] > prev["Open"]
        and row["Close"] < row["Open"]
        and row["Open"]  >= prev["Close"]
        and row["Close"] <= prev["Open"]
    )
    if not bullish and not bearish:
        return {"action": "NONE"}

    # ── Build setup ───────────────────────────────────────────────────────────
    if bullish:
        impulse     = row["Close"] - row["Low"]
        entry_price = row["Close"] - RETRACEMENT_PCT * impulse
        stop_price  = row["Low"]
        trade_type  = "LONG"
    else:
        impulse     = row["High"] - row["Close"]
        entry_price = row["Close"] + RETRACEMENT_PCT * impulse
        stop_price  = row["High"]
        trade_type  = "SHORT"

    risk = abs(entry_price - stop_price)
    if risk <= 0:
        return {"action": "NONE"}

    if trade_type == "LONG":
        target_price = entry_price + REWARD_MULTIPLE * risk
        triggered    = trig["Low"] <= entry_price
    else:
        target_price = entry_price - REWARD_MULTIPLE * risk
        triggered    = trig["High"] >= entry_price

    if not triggered:
        return {"action": "NONE"}

    size = calculate_position_size(capital, risk)

    base = {
        "trade_type":        trade_type,
        "entry_price":       entry_price,
        "stop_price":        stop_price,
        "target_price":      target_price,
        "position_size":     size,
        "signal_candle_time": str(row["Open_Time"]),
        "entry_time":        str(trig["Open_Time"]),
    }

    # ── OCO check on the trigger candle itself (same-candle exit) ─────────────
    fake_state = {
        "trade_type":   trade_type,
        "stop_price":   stop_price,
        "target_price": target_price,
    }
    exit_info = check_trade_exit(fake_state, trig)

    if exit_info:
        pnl = calculate_pnl(entry_price, exit_info["exit_price"], size, trade_type)
        return {
            "action":    "TRADE_COMPLETED",
            **base,
            "exit_price":  exit_info["exit_price"],
            "result":      exit_info["result"],
            "exit_reason": exit_info["exit_reason"],
            "pnl":         pnl,
            "exit_time":   str(trig["Open_Time"]),
        }

    return {"action": "ENTER", **base}
