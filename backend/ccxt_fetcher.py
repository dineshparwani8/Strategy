import ccxt
import pandas as pd
import logging
from config import EXCHANGE_ID, TIMEFRAME, CANDLE_LIMIT

logger = logging.getLogger(__name__)


def get_exchange():
    exchange_cls = getattr(ccxt, EXCHANGE_ID)
    return exchange_cls({"enableRateLimit": True})


def fetch_ohlcv(symbol: str, limit: int = CANDLE_LIMIT) -> pd.DataFrame:
    """
    Fetch OHLCV candles from exchange.
    Returns DataFrame with: Open_Time, Open, High, Low, Close, Volume
    NOTE: The last candle may still be forming; callers should slice [:-1] for closed candles.
    """
    exchange = get_exchange()
    raw = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
    df["Open_Time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.drop(columns=["timestamp"], inplace=True)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def fetch_ticker(symbol: str) -> dict:
    """Fetch latest ticker data (price, 24 h stats)."""
    try:
        exchange = get_exchange()
        t = exchange.fetch_ticker(symbol)
        return {
            "symbol":     symbol,
            "price":      t.get("last", 0) or 0,
            "change_pct": t.get("percentage", 0) or 0,
            "volume_24h": t.get("baseVolume", 0) or 0,
            "high_24h":   t.get("high", 0) or 0,
            "low_24h":    t.get("low", 0) or 0,
        }
    except Exception as e:
        logger.error(f"Ticker fetch failed for {symbol}: {e}")
        return {"symbol": symbol, "price": 0, "change_pct": 0,
                "volume_24h": 0, "high_24h": 0, "low_24h": 0}
