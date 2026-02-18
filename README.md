# Bubby Vision

> AI-Powered Trading Analysis Platform

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React 19 + TypeScript + Vite |
| Backend | FastAPI + Celery + LangChain |
| Data | QuestDB (time-series) + Redis (cache/pubsub) + ChromaDB (RAG) |
| AI | Gemini 2.0 Flash multi-agent (analyst, strategist, news, risk) |

## Quick Start

```bash
# 1. Start infrastructure
docker compose up -d

# 2. Backend
cd backend
cp .env.example .env       # fill in API keys
pip install -r requirements.txt
uvicorn app.main:app --reload

# 3. Frontend
cd frontend
npm install
npm run dev                 # → http://localhost:5173
```

## Features

- **Real-Time Dashboard** — 9 panels: Fear & Greed, Top Movers, Sector Heatmap, Earnings Calendar, Short Squeeze Scanner
- **Stock Screener** — Filter by market, price, volume, change; breakout conviction scanning
- **Options Flow** — Live options activity with Greeks visualization
- **AI Chat** — Multi-agent analysis with RAG-powered market memory
- **Watchlist** — Live WebSocket prices + custom alert triggers
- **Splash Screen** — Animated bear-logo entry on app start

## Docker Services

| Container | Purpose | Port |
|-----------|---------|------|
| bv-backend | FastAPI API server | 8000 |
| bv-frontend | React SPA via Nginx | 3000 |
| bv-questdb | Time-series database | 9000 |
| bv-redis | Cache + Celery broker | 6379 |
| bv-chromadb | Vector store for RAG | 8100 |
| bv-celery-worker | Background task processing | — |
| bv-celery-beat | Periodic scheduler | — |
| bv-flower | Celery monitoring | 5555 |

## Testing

```bash
# Frontend (67+ tests)
cd frontend && npx vitest run

# Backend (34+ tests)
cd backend && python -m pytest tests/ -v
```

## License

Private — All rights reserved.
