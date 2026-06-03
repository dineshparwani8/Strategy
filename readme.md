# Engulf-Bot · Live Forward Tester

Forward-testing the **Engulfing Retracement Strategy** on **BTC/USDT** and **ETH/USDT** (15-minute timeframe) using live Binance data via CCXT.

## Stack
| Layer | Tech |
|---|---|
| Backend | Python 3.11 · FastAPI · APScheduler |
| Live Data | CCXT → Binance (public, no API key needed) |
| Storage | JSON files (rolling 30-day trade history) |
| Frontend | Vanilla HTML / CSS / JS · Chart.js |

## Strategy (quick summary)
1. **Signal** – Bullish or Bearish Engulfing candle that is body > 0.25 %, preceded by a strong candle (body ≥ 50 % of range)
2. **Entry** – 50 % retracement into the signal candle, filled on the NEXT closed candle
3. **Stop** – Low (Long) / High (Short) of signal candle
4. **Target** – 1 R from entry
5. **Risk** – 1 % of capital per trade · 0.05 % fee per side (OCO logic)

## Quick Start

```bash
# 1. Install dependencies
cd backend
pip install -r requirements.txt

# 2. Run
python main.py
```

Open **http://localhost:8000** — the dashboard loads automatically.

The scheduler fires at :00 :15 :30 :45 UTC every hour. You can also hit **⟳ Run Check** in the dashboard to trigger a manual check.

## Data Files
```
backend/data/
  state.json    ← current open positions & capital per symbol
  trades.json   ← all trades (auto-purged after 30 days)
```

## Vercel Deployment (frontend only)
1. Push the `frontend/` folder to a GitHub repo
2. Import into Vercel — it deploys as a static site
3. Update `const API = ""` in `app.js` to your backend URL (e.g. Railway/Render)

## Folder Structure
```
Strategy/
├── backend/
│   ├── main.py          ← FastAPI + scheduler
│   ├── strategy.py      ← signal detection + exit logic
│   ├── ccxt_fetcher.py  ← Binance live data
│   ├── trade_logger.py  ← JSON storage
│   ├── config.py        ← all settings
│   ├── requirements.txt
│   └── data/            ← auto-created on first run
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```
