# Contributing to EcoBarter

Thanks for your interest in EcoBarter — a sustainable, money-free goods exchange platform. Whether you want to fix a bug, build a feature, improve docs, or just share feedback, every contribution matters.

**Live site:** https://ecobarter.man-dip.dev
**GitHub:** https://github.com/Mandip77/Eco-Barter

---

## Table of Contents

- [Ways to Contribute](#ways-to-contribute)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Code Guidelines](#code-guidelines)
- [Testing](#testing)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Good First Issues](#good-first-issues)
- [Governance](#governance)
- [Code of Conduct](#code-of-conduct)

---

## Ways to Contribute

You don't have to write code to contribute:

| Contribution | How |
|---|---|
| Report a bug | Open a GitHub Issue with reproduction steps |
| Suggest a feature | Open a Discussion labeled `idea` |
| Improve documentation | Edit any `.md` file and open a PR |
| Write a test | Look for files with low coverage |
| Review a PR | Leave comments on open pull requests |
| Spread the word | Star the repo, share on LinkedIn, tell a friend |
| Provide feedback | Try the live site and open an issue with your thoughts |

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine + Compose plugin)
- [Node.js 20+](https://nodejs.org/) and [pnpm](https://pnpm.io/)
- [Go 1.21+](https://go.dev/dl/) — only needed if you're working on the trade engine locally
- Python 3.11+ — only needed if running service tests outside Docker

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/Eco-Barter.git
cd Eco-Barter
cp .env.example .env
```

### 2. Fill in your `.env`

The app will not start with missing secrets. At minimum, generate the required tokens:

```bash
# Run the helper script (recommended)
bash scripts/generate_secrets.sh

# Or generate individually
python -c "import secrets; print('JWT_SECRET=' + secrets.token_hex(32))"
python -c "import secrets; print('NATS_AUTH_TOKEN=' + secrets.token_hex(32))"
```

Paste the output into your `.env`. See `.env.example` for all required variables and descriptions.

### 3. Install frontend dependencies

```bash
pnpm install
```

### 4. Start the full stack

```bash
docker compose up -d --build
```

Services start in dependency order. PostgreSQL and MongoDB health checks must pass before application services start.

### 5. Run database migrations

```bash
# Identity service (PostgreSQL)
docker compose exec identity-service alembic upgrade head

# Trade engine migrations run automatically on startup
```

### 6. Start the frontend dev server

```bash
pnpm --filter web dev   # http://localhost:5173
```

Changes to the frontend hot-reload instantly. Backend changes require a container rebuild (`docker compose up -d --build <service-name>`).

---

## Project Structure

```
services/
  identity/     # FastAPI — user registration, login, JWT, password management (Python)
  catalog/      # FastAPI — product listings, image upload, AI suggestions (Python)
  trade/        # Gin — K-way circular trade matching engine, QR verification (Go)
  reputation/   # FastAPI — EigenTrust scoring, reviews, leaderboard (Python)
apps/
  web/          # SvelteKit 2 + Svelte 5 + Tailwind 4 frontend
scripts/        # Secret generation and environment validation
centrifugo_config.json   # Real-time WebSocket hub configuration
docker-compose.yml       # Base compose (dev + CI)
docker-compose.prod.yml  # Production overlay (Traefik TLS, resource limits)
```

Each service is fully self-contained with its own `Dockerfile`, `requirements.txt` or `go.mod`, and `tests/` directory. There are no shared libraries between services — communication is via HTTP or NATS.

---

## Development Workflow

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/the-bug-you-are-fixing
   ```

2. **Make your changes.** Keep commits focused — one logical change per commit.

3. **Validate your environment** if you changed any service startup code:
   ```bash
   bash -c 'set -a; source .env; set +a; bash scripts/validate_env.sh'
   ```

4. **Run tests** locally before pushing (see [Testing](#testing)).

5. **Push and open a Pull Request** against `main`.

CI runs automatically on every PR. It must pass before merging.

---

## Code Guidelines

### General

- Prefer editing existing files over creating new ones
- Don't add abstractions or error handling that the current code doesn't need
- Keep each service self-contained — no cross-service imports
- Don't hardcode secrets, connection strings, or environment-specific values — use `os.getenv()` / `os.Getenv()` and fail fast if the variable is missing

### Python (Identity / Catalog / Reputation)

- Use Pydantic models for all request/response schemas
- Type-hint all function signatures
- Use `slowapi` for rate limiting — follow the existing per-endpoint pattern
- Use `Depends(get_current_user_id)` on any endpoint that requires authentication
- Format with `black` and lint with `ruff` if you have them installed; CI does not enforce a formatter, but keep diffs readable

### Go (Trade Engine)

- `gofmt` before committing — CI runs `gofmt -l` and fails on a diff
- Keep functions short and well-named; avoid comments that restate the function name
- All new matching logic must have a corresponding test in `main_test.go`
- Use `go vet` — clean output required

### SvelteKit / Svelte 5

- Use Svelte 5 runes (`$state`, `$derived`, `$effect`) — no legacy `writable` stores in new code
- Tailwind utility classes over scoped `<style>` blocks unless structurally necessary
- TypeScript for all new `.ts` and `.svelte` files
- Mobile-first: test new UI at 375px width before submitting

### Security

- Never fall back to hardcoded secrets — if an env var is missing the service should crash loudly
- New endpoints that modify data must require authentication (`Depends(get_current_user_id)`)
- New endpoints that expose user-identifying data (UUIDs, emails) must require authentication
- File uploads must validate content type and enforce a size limit

---

## Testing

Run tests before opening a PR:

```bash
# Identity service
docker compose exec identity-service pytest tests/ -v

# Reputation service
docker compose exec reputation-service pytest tests/ -v

# Trade Engine (uses SQLite in-memory, no containers needed)
cd services/trade
go test -tags test ./... -race

# Frontend type check
pnpm --filter web check
```

Tests for Python services use SQLite in-memory databases — no running Docker containers are required if you install the test requirements locally:

```bash
cd services/identity && pip install -r requirements-test.txt && pytest tests/
```

**If you are adding a new endpoint:** add a corresponding test.
**If you are fixing a bug:** add a test that would have caught it.
**If you are touching the trade matcher:** add or update a test in `services/trade/main_test.go`.

---

## Submitting a Pull Request

1. Make sure CI passes (build, lint, tests)
2. Write a clear PR description:
   - **What** changed
   - **Why** (link to the issue if one exists)
   - **How to test** it manually
3. Keep PRs focused — separate unrelated changes into separate PRs
4. If your change is a large architectural addition (new service, new database, new auth flow), open a Discussion or Issue labeled `RFC` first and allow 48 hours for feedback before building

---

## Good First Issues

Not sure where to start? Look for issues labeled [`good first issue`](https://github.com/Mandip77/Eco-Barter/issues?q=label%3A%22good+first+issue%22) on GitHub.

Areas that are always welcome:

| Area | Ideas |
|---|---|
| **Frontend** | Loading skeleton states, empty state illustrations, better error messages |
| **Accessibility** | Keyboard navigation, ARIA labels, focus management in modals |
| **Test coverage** | Catalog service has no tests yet |
| **Docs** | Improve inline code comments, expand the API reference |
| **Performance** | MongoDB index review, pagination on the global reputation endpoint |
| **Mobile UX** | Swipe gestures in chat, pull-to-refresh on listings |

---

## Governance

This project uses a **liberal contribution model**:

- Pull requests are reviewed for correctness, security, and architecture fit — not subjective style
- Contributors who land **3 substantial PRs** are offered write access to the repository
- For significant changes, open an `RFC` issue and allow 48 hours for discussion before building

---

## Code of Conduct

Be respectful. Criticism should be directed at ideas and code, not people. We're all here to build something useful and learn along the way.

Issues or PRs that are disrespectful will be closed without discussion.

---

## Questions?

Open a [GitHub Discussion](https://github.com/Mandip77/Eco-Barter/discussions) or reach out via the contact on the GitHub profile.

We're happy to help you get your first contribution merged.
