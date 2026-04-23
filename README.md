# EcoBarter

**A sustainable, money-free marketplace powered by circular trade loops.**

**Live:** https://ecobarter.man-dip.dev

EcoBarter lets people trade goods and skills directly — no currency involved. Its matching engine finds K-way circular loops (2-party swaps, 3-way rings, and 4-way chains) so that even items with no direct counterpart can find a home. Physical handoffs are verified with QR codes, and a trust graph tracks reputation across every completed trade.

---

## Features

- **K-way circular matching** — Finds 2-, 3-, and 4-party trade loops automatically using PostgreSQL `FOR UPDATE SKIP LOCKED` to prevent race conditions under concurrent load
- **EigenTrust reputation** — Power-iteration trust scoring with exponential time decay (score halves every 90 days of inactivity); ranked tiers from Novice to Eco-Champion
- **Real-time coordination** — Centrifugo WebSocket hub pushes trade match alerts and chat messages instantly to all participants
- **QR handoff verification** — Each participant generates a QR code at the physical swap point; scanning it calls the verification API to mark their leg complete
- **CO₂ impact tracking** — Estimates kg of CO₂ saved per completed trade and surfaces it on each user's profile
- **Production-hardened** — Non-root containers, distroless Go runtime, env-driven secrets, CORS lockdown, per-endpoint rate limiting, Traefik TLS with HSTS

---

## Architecture

```
                         Internet
                            │
              ┌─────────────▼─────────────┐
              │    Traefik  :443 / :80     │  TLS termination
              │   (Let's Encrypt ACME)     │  Security headers
              └──────────────┬────────────┘  HTTP→HTTPS redirect
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
   /api/v1/auth       /api/v1/catalog    /api/v1/trade
   /api/v1/reputation  /connection        (all others)
          │                  │                  │
   ┌──────▼──────┐  ┌────────▼───────┐  ┌──────▼──────┐
   │  Identity   │  │    Catalog     │  │    Trade    │
   │  FastAPI    │  │    FastAPI     │  │   Engine    │
   │  Python     │  │    Python      │  │   Go/Gin    │
   │  PostgreSQL │  │    MongoDB     │  │  PostgreSQL │
   └──────┬──────┘  └────────┬───────┘  └──────┬──────┘
          │                  │                  │
   ┌──────▼──────┐           │          ┌──────▼──────┐
   │ Reputation  │           │          │  Centrifugo │
   │  FastAPI    │           │          │  WebSocket  │
   │  Python     │           │          │    Hub      │
   │  PostgreSQL │           │          │   + Redis   │
   └─────────────┘           │          └─────────────┘
                             │
                    ┌────────▼───────┐
                    │  Web Frontend  │
                    │   SvelteKit 5  │  Svelte 5 runes
                    │   Tailwind 4   │  Centrifuge.js
                    └────────────────┘

         All services communicate internally via NATS JetStream
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | SvelteKit 2, Svelte 5, Tailwind CSS 4, Vite 8, Centrifuge.js |
| Identity | FastAPI, SQLAlchemy, PyJWT, slowapi, PostgreSQL |
| Catalog | FastAPI, Motor (async), slowapi, MongoDB, NATS |
| Trade Engine | Go, Gin, GORM, golang-jwt, PostgreSQL |
| Reputation | FastAPI, SQLAlchemy, EigenTrust power-iteration, PostgreSQL |
| Real-time | Centrifugo v5, Redis 7 |
| Messaging | NATS 2.10 JetStream |
| Gateway | Traefik v3.3 |
| Containers | Docker Compose, distroless runtime (Go), non-root (Python) |
| Monorepo | Nx, pnpm |

---

## Repository Layout

```
EcoBarter/
├── apps/
│   └── web/                   # SvelteKit frontend
│       └── src/
│           ├── lib/
│           │   └── auth.svelte.ts     # Reactive auth state (Svelte 5 runes)
│           └── routes/
│               ├── +layout.svelte
│               ├── +page.svelte       # Marketplace (browse/chat/profile)
│               ├── layout.css         # Design system
│               ├── login/
│               └── negotiation/       # QR handoff coordination
├── services/
│   ├── identity/              # FastAPI auth service
│   ├── catalog/               # FastAPI product catalog
│   ├── trade/                 # Go trade matching engine
│   │   ├── matcher.go         # K-way loop matching (production, SQL JOINs)
│   │   ├── matcher_test_impl.go # Test build (SQLite-safe Go loops)
│   │   └── migrations/        # golang-migrate SQL files
│   └── reputation/            # FastAPI EigenTrust service
├── scripts/
│   ├── generate_secrets.sh    # Generates cryptographically strong .env values
│   └── validate_env.sh        # Pre-deploy environment variable audit
├── centrifugo_config.json
├── docker-compose.yml         # Base compose (dev + CI)
├── docker-compose.prod.yml    # Production overlay (Traefik, TLS, resource limits)
├── DEPLOY.md                  # Oracle Cloud free-tier deployment guide
└── .env.example
```

---

## Local Development

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Node 20+ and pnpm
- Go 1.25+ (for running trade service tests locally)

### 1. Clone and configure

```bash
git clone https://github.com/Mandip77/Eco-Barter.git
cd ecobarter
cp .env.example .env
# Edit .env with your local values — see .env.example for all required fields
```

### 2. Install frontend dependencies

```bash
pnpm install
```

### 3. Start all services

```bash
docker compose up -d --build
```

The base compose exposes Traefik's dashboard at `http://localhost:8080` and all services via `http://localhost`.

### 4. Run database migrations

```bash
# Identity service
docker compose exec identity-service alembic upgrade head

# Trade engine migrations run automatically on startup via initDB()
```

### 5. Start the frontend dev server (hot reload)

```bash
pnpm --filter web dev
```

The app is available at `http://localhost:5173`.

---

## Secrets Management

Never commit real secrets. The `.env` file is in `.gitignore`.

Generate strong secrets for a new deployment:

```bash
bash scripts/generate_secrets.sh
# Paste the output into your .env file
```

Validate before deploying:

```bash
bash -c 'set -a; source .env; set +a; bash scripts/validate_env.sh'
```

All 12 required variables are checked for presence and weak/default values. JWT secret is checked for minimum 64-character length.

---

## Environment Variables

| Variable | Description |
|---|---|
| `POSTGRES_USER` | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB` | PostgreSQL database name |
| `POSTGRES_URL` | Full connection string for Python services |
| `POSTGRES_DSN` | DSN string for Go trade engine |
| `MONGO_INITDB_ROOT_USERNAME` | MongoDB root username |
| `MONGO_INITDB_ROOT_PASSWORD` | MongoDB root password |
| `CATALOG_MONGO_URL` | Full MongoDB connection string |
| `JWT_SECRET` | HS256 signing secret — minimum 64 hex characters |
| `CENTRIFUGO_SECRET` | Centrifugo token secret |
| `CENTRIFUGO_API_KEY` | Centrifugo server API key |
| `CENTRIFUGO_ADMIN_PASSWORD` | Centrifugo admin UI password |
| `NATS_URL` | NATS server URL (`nats://nats:4222`) |
| `DOMAIN` | Production domain (e.g. `ecobarter.example.com`) |
| `ACME_EMAIL` | Email for Let's Encrypt certificate registration |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `ORIGIN` | SvelteKit origin URL — required for production (e.g. `https://ecobarter.man-dip.dev`) |
| `ANTHROPIC_API_KEY` | Enables AI trade suggestions in the catalog service (optional) |
| `VITE_API_BASE_URL` | API base URL injected into the frontend build |

See `.env.example` for a complete annotated template.

---

## Trade Matching

The trade engine listens on NATS for `catalog.preference.updated` events published whenever a user lists an item or updates what they want. On each event it attempts to find a match in order:

1. **K=2** — Direct swap: user A has what B wants, B has what A wants
2. **K=3** — Three-way ring: A→B→C→A
3. **K=4** — Four-way chain: A→B→C→D→A

All queries use `SELECT ... FOR UPDATE SKIP LOCKED` to prevent two workers from creating the same trade simultaneously. Once a loop is found, a `trade_proposals` row is created and all participants are notified in real time via Centrifugo.

---

## Reputation System

Each completed trade contributes to a user's EigenTrust score:

- The trust graph is built from completed `trade_proposals` (each participant trusts all others in the loop)
- Power iteration runs until convergence (Δ < 1×10⁻⁶) or 100 iterations
- Scores decay: `score × 0.5^(days_idle / 90)` — a dormant account loses half its trust every 90 days
- Tiers: **Novice** (score < 20), **Trusted** (20–50), **Eco-Champion** (> 50)
- Default score for new users: 10.0
- Estimated CO₂ saved: 5 kg per completed trade

---

## API Reference

| Method | Path | Service | Auth |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Identity | — |
| `POST` | `/api/v1/auth/login` | Identity | — |
| `GET` | `/api/v1/auth/me` | Identity | Bearer |
| `GET` | `/api/v1/catalog/products` | Catalog | — |
| `POST` | `/api/v1/catalog/products` | Catalog | Bearer |
| `POST` | `/api/v1/catalog/products/:id/image` | Catalog | Bearer |
| `GET` | `/api/v1/trade/proposals` | Trade | Bearer |
| `POST` | `/api/v1/trade/verify` | Trade | Bearer |
| `POST` | `/api/v1/trade/message` | Trade | Bearer |
| `GET` | `/api/v1/reputation/:username` | Reputation | — |
| `GET` | `/api/v1/reputation/leaderboard` | Reputation | — |
| `WS` | `/connection/websocket` | Centrifugo | — |

Rate limits: 5 req/min (register), 10 req/min (login), 30 req/min (catalog write), 60 req/min (trade).

---

## Production Deployment

See **[DEPLOY.md](DEPLOY.md)** for the full step-by-step guide to deploying on Oracle Cloud Always Free Tier ($0/month):

- 1× Ampere A1.Flex VM — 4 OCPUs, 24 GB RAM
- 150 GB block volume for database persistence
- Traefik handles HTTPS and automatic Let's Encrypt certificate renewal
- Nightly backups to Oracle Object Storage (20 GB free)

Quick deploy (after provisioning the VM and setting `.env`):

```bash
bash scripts/generate_secrets.sh     # generate secrets
nano .env                            # paste and fill in
bash -c 'set -a; source .env; set +a; bash scripts/validate_env.sh'
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## Testing

```bash
# Identity service
docker compose exec identity-service pytest

# Catalog service
docker compose exec catalog-service pytest

# Reputation service
docker compose exec reputation-service pytest

# Trade engine (uses SQLite build tag for in-process DB)
cd services/trade
go test -tags test ./...

# Frontend type check
pnpm --filter web check
```

---

## Security

- All containers run as non-root users; the Go runtime uses `gcr.io/distroless/static-debian12:nonroot`
- Secrets are environment-variable only — never in source or Docker images
- CORS is locked to `ALLOWED_ORIGINS` in production
- Traefik enforces HSTS (1 year, preload), removes `Server` and `X-Powered-By` headers, sets `Permissions-Policy`
- JWT uses HS256 with a minimum 64-character secret; the Go service hard-fails at startup if `JWT_SECRET` is unset
- Rate limiting on all mutation endpoints via `slowapi` (Python) and a fixed-window per-IP middleware (Go)

To report a security vulnerability, please email the maintainers directly rather than opening a public issue.

---

## Contributing

1. Fork the repository and create a feature branch
2. Run `bash scripts/validate_env.sh` and all service tests before opening a PR
3. Keep each service self-contained — shared logic belongs in the service that owns the data, not in a shared library
4. PRs that touch the trade matching engine must include tests in `services/trade/main_test.go`

---

## License

MIT — see [LICENSE](LICENSE) for details.
