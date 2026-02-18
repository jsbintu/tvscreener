---
description: How to launch the full MarketPilot application stack for local development
---

# Launch Full Stack

// turbo-all

This workflow starts all infrastructure services (Docker), the FastAPI backend, and the React frontend dev server.

## Prerequisites

- Docker Desktop must be running
- Python `.venv` must exist at project root (`.venv/`)
- Node dependencies must be installed (`frontend/node_modules/`)

## Steps

### 1. Start Infrastructure Services (QuestDB, Redis, ChromaDB)

```bash
docker compose up -d questdb redis chromadb
```

Wait ~10 seconds for containers to be healthy. Verify with:

```bash
docker compose ps
```

Expected: `questdb`, `redis`, `chromadb` all showing `Up`.

### 2. Start the FastAPI Backend

Open a **new terminal** and run:

```bash
cd c:\Users\Confidential\Documents\screener\tvscreener
.\.venv\Scripts\activate
$env:PYTHONPATH = "c:\Users\Confidential\Documents\screener\tvscreener\backend"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will be available at `http://localhost:8000`. Health check: `http://localhost:8000/health`.

### 3. Start the React Frontend Dev Server

Open a **new terminal** and run:

```bash
cd c:\Users\Confidential\Documents\screener\tvscreener\frontend
npm run dev
```

Frontend will be available at `http://localhost:5173`.

## Quick Verification

- Backend health: `http://localhost:8000/health`
- QuestDB console: `http://localhost:9000`
- Frontend app: `http://localhost:5173`

## Shutdown

To stop everything:

```bash
# Stop Docker infra
cd c:\Users\Confidential\Documents\screener\tvscreener
docker compose down

# Backend & Frontend: just Ctrl+C in their respective terminals
```
