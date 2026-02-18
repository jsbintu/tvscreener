# MarketPilot — Production Deployment Guide

## Prerequisites

| Tool      | Version    | Purpose              |
|-----------|------------|----------------------|
| Docker    | ≥ 24.0    | Container runtime    |
| Docker Compose | ≥ 2.20 | Service orchestration |
| Domain    | —          | HTTPS via Traefik    |
| DNS       | A record → server IP | Domain routing   |

---

## 1. Clone & Configure

```bash
git clone <repo-url> marketpilot && cd marketpilot
cp .env.example .env
```

**Edit `.env` — required variables:**

```env
# Security
APP_ENV=production
APP_SECRET_KEY=<64-char random string>
JWT_SECRET_KEY=<64-char random string>
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRY_MINUTES=15
JWT_REFRESH_EXPIRY_DAYS=7

# API Keys
GOOGLE_API_KEY=<your-key>
FINNHUB_API_KEY=<your-key>
ALPACA_API_KEY=<your-key>
ALPACA_SECRET_KEY=<your-key>
QUANTDATA_API_KEY=<your-key>

# Deployment
DOMAIN=yourdomain.com
ACME_EMAIL=admin@yourdomain.com
CORS_ORIGINS=https://yourdomain.com
```

Generate secure random keys:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 2. SSL Certificates (Traefik)

Traefik handles HTTPS automatically via Let's Encrypt. Ensure:

- Port 80 and 443 are open on your server
- DNS A record points to your server IP
- `DOMAIN` and `ACME_EMAIL` are set in `.env`

Certificates are stored in `./traefik/acme.json` (auto-created).

---

## 3. Deploy

```bash
# Build and start all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Check service health
docker compose ps
curl -s https://$DOMAIN/health | jq
```

### Services Started

| Service   | Port (internal) | Description                    |
|-----------|-----------------|--------------------------------|
| backend   | 8000            | FastAPI API server             |
| frontend  | 80              | React SPA (nginx)              |
| questdb   | 8812/9000       | Time-series database           |
| redis     | 6379            | Cache + Celery broker          |
| chromadb  | 8001            | Vector store for RAG           |
| celery    | —               | Background task workers        |
| beat      | —               | Periodic task scheduler        |
| flower    | 5555            | Celery monitoring UI           |
| traefik   | 80/443          | Reverse proxy + HTTPS          |

---

## 4. Seed Data

```bash
# Seed OHLCV historical data (50 tickers, 1 year)
docker compose exec backend python -m scripts.seed_market_data

# Seed RAG knowledge base (SEC filings + news)
docker compose exec backend python -m scripts.seed_rag
```

---

## 5. Verify

```bash
# API health
curl https://$DOMAIN/health

# Auth endpoints
curl -X POST https://$DOMAIN/v1/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"SecureP@ss123"}'

# QuestDB console
# Available at http://localhost:9000 (not exposed via Traefik)
```

---

## 6. Monitoring

### Logs

```bash
docker compose logs -f backend
docker compose logs -f celery
```

### Metrics

- Prometheus: `https://$DOMAIN/metrics`
- Flower: `http://localhost:5555` (Celery monitoring)

### QuestDB Console

- `http://localhost:9000` (direct access only)

---

## 7. Updates

```bash
git pull origin main
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## 8. Backup

```bash
# QuestDB data
docker compose exec questdb /opt/questdb/bin/questdb backup

# Redis snapshot
docker compose exec redis redis-cli BGSAVE
```

---

## Security Checklist

- [ ] All API keys set in `.env`
- [ ] `APP_ENV=production`
- [ ] `APP_SECRET_KEY` is unique 64+ chars
- [ ] `JWT_SECRET_KEY` is unique 64+ chars
- [ ] Firewall: only ports 80, 443 exposed
- [ ] QuestDB console (9000) not exposed publicly
- [ ] CORS origins set to production domain only
- [ ] Regular backups configured
