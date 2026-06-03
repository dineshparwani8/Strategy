"""
main.py – FastAPI backend + APScheduler (15-minute cron).

Start with:  python main.py
Dashboard:   http://localhost:8000
"""
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from strategy import run_signal_check, check_trade_exit, calculate_pnl
from ccxt_fetcher import fetch_ohlcv, fetch_ticker
from trade_logger import (
    load_state, save_state,
    load_trades, save_trade, build_trade_record,
    _default_sym_state,
)
from config import SYMBOLS, TRANSACTION_FEE, INITIAL_CAPITAL, API_HOST, API_PORT

# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
)
logger = logging.getLogger("engulf-bot")


# ─────────────────────────────────────────────────────────────────────────────
# CORE STRATEGY LOOP
# ─────────────────────────────────────────────────────────────────────────────

def run_strategy_check() -> None:
    """Runs every 15 minutes (or on demand). Mutates data/state.json."""
    logger.info("═══ Strategy check ═══")
    state = load_state()
    now   = datetime.now(timezone.utc).isoformat()

    for symbol in SYMBOLS:
        sym = state[symbol]
        sym["last_check"] = now
        capital = sym["capital"]

        try:
            df     = fetch_ohlcv(symbol, limit=50)
            closed = df.iloc[:-1].copy()   # exclude forming candle

            just_closed_trade = False

            # ── 1. MANAGE OPEN TRADE ─────────────────────────────────────────
            if sym["status"] == "IN_TRADE":
                latest    = closed.iloc[-1]
                exit_info = check_trade_exit(sym, latest)

                if exit_info:
                    pnl           = calculate_pnl(
                        sym["entry_price"],
                        exit_info["exit_price"],
                        sym["position_size"],
                        sym["trade_type"],
                        TRANSACTION_FEE,
                    )
                    capital_after = capital + pnl

                    trade = build_trade_record(
                        symbol=symbol,
                        trade_type=sym["trade_type"],
                        entry_price=sym["entry_price"],
                        exit_price=exit_info["exit_price"],
                        stop_price=sym["stop_price"],
                        target_price=sym["target_price"],
                        position_size=sym["position_size"],
                        result=exit_info["result"],
                        exit_reason=exit_info["exit_reason"],
                        pnl=pnl,
                        capital_before=capital,
                        capital_after=capital_after,
                        entry_time=sym["entry_time"],
                        exit_time=str(latest["Open_Time"]),
                        signal_candle_time=sym.get("signal_candle_time"),
                    )
                    save_trade(trade)

                    sym.update({
                        "status":             "IDLE",
                        "capital":            capital_after,
                        "trade_type":         None,
                        "entry_price":        None,
                        "stop_price":         None,
                        "target_price":       None,
                        "position_size":      None,
                        "entry_time":         None,
                        "signal_candle_time": None,
                    })
                    capital           = capital_after
                    just_closed_trade = True
                    logger.info(f"[{symbol}] {exit_info['result']} via {exit_info['exit_reason']}  PnL=${pnl:+.2f}  Cap=${capital_after:.2f}")

            # ── 2. SCAN FOR NEW SIGNAL (only if IDLE and no exit this cycle) ─
            if sym["status"] == "IDLE" and not just_closed_trade:
                result = run_signal_check(closed, capital)

                if result["action"] == "ENTER":
                    sym.update({
                        "status":             "IN_TRADE",
                        "trade_type":         result["trade_type"],
                        "entry_price":        result["entry_price"],
                        "stop_price":         result["stop_price"],
                        "target_price":       result["target_price"],
                        "position_size":      result["position_size"],
                        "entry_time":         result["entry_time"],
                        "signal_candle_time": result["signal_candle_time"],
                    })
                    logger.info(
                        f"[{symbol}] {result['trade_type']} ENTERED @ {result['entry_price']:.2f}"
                        f"  SL={result['stop_price']:.2f}  TP={result['target_price']:.2f}"
                    )

                elif result["action"] == "TRADE_COMPLETED":
                    capital_after = capital + result["pnl"]
                    trade = build_trade_record(
                        symbol=symbol,
                        trade_type=result["trade_type"],
                        entry_price=result["entry_price"],
                        exit_price=result["exit_price"],
                        stop_price=result["stop_price"],
                        target_price=result["target_price"],
                        position_size=result["position_size"],
                        result=result["result"],
                        exit_reason=result["exit_reason"],
                        pnl=result["pnl"],
                        capital_before=capital,
                        capital_after=capital_after,
                        entry_time=result["entry_time"],
                        exit_time=result["exit_time"],
                        signal_candle_time=result["signal_candle_time"],
                    )
                    save_trade(trade)
                    sym["capital"] = capital_after
                    logger.info(f"[{symbol}] SAME-CANDLE {result['result']}  PnL=${result['pnl']:+.2f}")

        except Exception as exc:
            logger.error(f"[{symbol}] Error: {exc}", exc_info=True)

        state[symbol] = sym

    save_state(state)
    logger.info("═══ Check complete ═══")


# ─────────────────────────────────────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────────────────────────────────────

scheduler = BackgroundScheduler(timezone="UTC")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_strategy_check,
        CronTrigger(minute="0,15,30,45", timezone="UTC"),
        id="strategy_check",
        name="15m Engulf Strategy",
        replace_existing=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    logger.info("Scheduler started  —  checks at :00 :15 :30 :45 UTC")

    # Run immediately on startup so the dashboard isn't empty
    try:
        run_strategy_check()
    except Exception as e:
        logger.warning(f"Startup check failed (market may be closed): {e}")

    yield
    scheduler.shutdown(wait=False)


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Engulf-Bot  |  Forward Tester", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── /api/status ───────────────────────────────────────────────────────────────
@app.get("/api/status")
async def get_status():
    state = load_state()
    return {
        "symbols":     state,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


# ── /api/trades ───────────────────────────────────────────────────────────────
@app.get("/api/trades")
async def get_trades(symbol: str = None, limit: int = 200):
    trades = load_trades()
    if symbol:
        trades = [t for t in trades if t["symbol"] == symbol]
    trades = sorted(trades, key=lambda x: x.get("exit_time", x.get("entry_time", "")), reverse=True)
    return {"trades": trades[:limit], "total": len(trades)}


# ── /api/stats ────────────────────────────────────────────────────────────────
@app.get("/api/stats")
async def get_stats():
    trades = load_trades()
    state  = load_state()

    total   = len(trades)
    wins    = sum(1 for t in trades if t["result"] == "WIN")
    losses  = total - wins
    win_rate = wins / total * 100 if total else 0
    total_pnl = sum(t["pnl"] for t in trades)

    per_symbol = {}
    for sym in SYMBOLS:
        st = [t for t in trades if t["symbol"] == sym]
        sw = sum(1 for t in st if t["result"] == "WIN")
        per_symbol[sym] = {
            "trades":    len(st),
            "wins":      sw,
            "losses":    len(st) - sw,
            "win_rate":  round(sw / len(st) * 100, 1) if st else 0,
            "pnl":       round(sum(t["pnl"] for t in st), 2),
            "capital":   round(state[sym]["capital"], 2),
            "return_pct": round((state[sym]["capital"] / INITIAL_CAPITAL - 1) * 100, 2),
        }

    # Equity curve: one data point per completed trade
    sorted_trades = sorted(trades, key=lambda x: x.get("exit_time", ""))
    equity = []
    for sym in SYMBOLS:
        sym_trades = [t for t in sorted_trades if t["symbol"] == sym]
        for t in sym_trades:
            equity.append({
                "time":    t["exit_time"],
                "symbol":  sym,
                "capital": t["capital_after"],
                "pnl":     t["pnl"],
            })

    return {
        "total_trades":    total,
        "wins":            wins,
        "losses":          losses,
        "win_rate":        round(win_rate, 2),
        "total_pnl":       round(total_pnl, 2),
        "initial_capital": INITIAL_CAPITAL,
        "per_symbol":      per_symbol,
        "equity_curve":    equity,
    }


# ── /api/prices ───────────────────────────────────────────────────────────────
@app.get("/api/prices")
async def get_prices():
    result = {}
    for symbol in SYMBOLS:
        result[symbol] = fetch_ticker(symbol)
    return result


# ── /api/candles/{symbol} ─────────────────────────────────────────────────────
@app.get("/api/candles/{symbol:path}")
async def get_candles(symbol: str, limit: int = 60):
    try:
        df = fetch_ohlcv(symbol, limit=limit)
        candles = [
            {
                "time":   row["Open_Time"].isoformat(),
                "open":   row["Open"],
                "high":   row["High"],
                "low":    row["Low"],
                "close":  row["Close"],
                "volume": row["Volume"],
            }
            for _, row in df.iterrows()
        ]
        return {"symbol": symbol, "candles": candles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── /api/trigger-check ────────────────────────────────────────────────────────
@app.post("/api/trigger-check")
async def trigger_check():
    """Manually run a strategy check (useful for testing)."""
    try:
        run_strategy_check()
        return {
            "status":  "ok",
            "message": "Strategy check completed",
            "time":    datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── /api/reset ────────────────────────────────────────────────────────────────
@app.post("/api/reset")
async def reset_state(confirm: str = ""):
    """Reset all positions to initial capital. Pass ?confirm=yes."""
    if confirm != "yes":
        raise HTTPException(status_code=400, detail="Pass ?confirm=yes to reset")
    state = {sym: _default_sym_state(INITIAL_CAPITAL) for sym in SYMBOLS}
    save_state(state)
    return {"status": "ok", "message": "State reset to initial capital"}


# ── Serve frontend ────────────────────────────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=False, log_level="info")
