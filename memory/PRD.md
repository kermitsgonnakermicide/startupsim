# SCALE India Investment - PRD

## Original Problem Statement
Build a full-stack Indian paper-trading simulator for 90 unlisted Indian startups ("SCALE India Investment"). Prices are synthetic (5 crore shares / company cap table), react to demand pressure (every student's buy/sell) and live Indian news sentiment scored by MarketBot. Dark-terminal crimson UI, WebSocket live feed, admin application approval + Brevo email, watchlist, sector-filtered News tab, threshold price alerts, leaderboard.

## Implemented (latest first)

### Iteration 10 (2026-05-03) - Price Alerts + News UX
- Threshold price alerts on any listed startup.
- Per-user WebSocket fan-out for alert delivery.
- Browser push notifications + in-app toasts.
- News-to-market jump actions in the UI.
- News warmup and sector balancing.
- Tightened news alias filtering.

### Iteration 9 (2026-05-02) - Sector-balanced Indian news
- Replaced general RSS aggregation with per-company Google News RSS queries.
- News tab defaults to `matchedOnly=true`.

### Iteration 8 (2026-05-01) - Full StartupMarket pivot
- 90 Indian startups, 5 crore shares cap table, and Rs 5,00,000 starting SimRupees.
- `startup_engine.py` for in-memory price simulation with demand pressure and algo drift.
- `marketbot.py` for chat and sentiment scoring, now OpenAI-backed with offline fallback.
- ThemeContext, MarketBot chat widget, News tab, IndicesTicker, and AI insight columns.

### Earlier (1-7)
- Legacy NSE app, watchlist, admin bulk ops, trade lock, leaderboard hide-toggle, auth, admin approval, and Brevo email.

## Architecture

```text
/app/
|-- backend/
|   |-- alerts_service.py
|   |-- data/stocks.py
|   |-- startup_engine.py
|   |-- news_feeds.py
|   |-- marketbot.py
|   |-- nse_fetcher.py
|   |-- server.py
|   `-- tests/
`-- frontend/src/
    |-- App.js
    |-- hooks/useMarketFeed.js
    `-- components/
```

## Remaining Backlog

### P0
- Cron-style background refresh for `/api/marketbot/refresh-news`.

### P1
- Recent headlines inside ChartModal.
- Optional email alerts via Brevo.
- Public read-only leaderboard URL.
- Export transaction history to CSV.
- Mobile responsiveness improvements.
- Featured Trader of the Week highlight.
- Service-worker based push alerts.

### P2
- Continue splitting `server.py` into route modules.
- Audit log for admin actions.
- Leaderboard aggregation improvements for larger user counts.
- Clean up defunct NSE-only paths.
