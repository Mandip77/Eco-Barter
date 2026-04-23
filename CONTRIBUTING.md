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

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/Eco-Barter.git
cd Eco-Barter
cp .env.example .env
# Fill in values — see .env.example for guidance
```

### 2. Install dependencies

```bash
# Frontend
pnpm install

# Python services (pick the one you're working on)
cd services/identity && pip install -r requirements-test.txt
cd services/catalog  && pip install -r requirements-test.txt
cd services/reputation && pip install -r requirements-test.txt

# Go trade engine
cd services/trade && go mod download
```

### 3. Start the full stack

```bash
docker compose up -d --build
```

The SvelteKit dev server with hot reload:

```bash
pnpm --filter web dev   # http://localhost:5173
```

---

## Project Structure

```
services/
  identity/     # FastAPI — user registration, login, JWT (Python)
  catalog/      # FastAPI — product listings, image upload, AI suggestions (Python)
  trade/        # Gin — K-way circular trade matching engine (Go)
  reputation/   # FastAPI — EigenTrust scoring, leaderboard (Python)
apps/
  web/          # SvelteKit 2 + Svelte 5 + Tailwind 4 frontend
traefik/        # Reverse proxy config (routing rules, TLS)
scripts/        # Secret generation, environment validation
```

Each service is fully self-contained with its own `Dockerfile`, `requirements*.txt` or `go.mod`, and `tests/` directory.

---

## Development Workflow

1. Create a branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. Make your changes. Keep commits focused — one logical change per commit.

3. Run tests locally before pushing (see [Testing](#testing)).

4. Push and open a Pull Request against `main`.

CI runs automatically on every PR. It must pass before merging.

---

## Code Guidelines

### General
- Prefer editing existing files over creating new ones
- Don't add abstractions or error-handling that the current code doesn't need
- Keep each service self-contained — no cross-service imports

### Python (Identity / Catalog / Reputation)
- Use Pydantic models for all request/response schemas
- Type-hint function signatures
- Use `slowapi` for rate limiting — follow the existing per-endpoint pattern
- Format with `black` and lint with `ruff` if you have them; CI does not enforce a formatter but keep diffs readable

### Go (Trade Engine)
- `gofmt` before committing — CI runs `gofmt -l` and fails on diff
- Keep functions short and well-named; avoid comments that just restate the function name
- All new matching logic must have a corresponding test in `main_test.go`
- Use `go vet` clean output

### SvelteKit / Svelte 5
- Use Svelte 5 runes (`$state`, `$derived`, `$effect`) — no legacy `writable` stores in new code
- Tailwind classes over scoped `<style>` blocks unless structurally necessary
- TypeScript for all new `.ts` and `.svelte` files

---

## Testing

Run tests before opening a PR:

```bash
# Identity
cd services/identity && pytest tests/

# Reputation
cd services/reputation && pytest tests/

# Trade Engine
cd services/trade && go test ./... -race

# Frontend type check
pnpm --filter web check
```

Tests use SQLite in-memory databases — no running containers required for Python services.

If you're adding a new endpoint, add a corresponding test. If you're fixing a bug, add a test that would have caught it.

---

## Submitting a Pull Request

1. Make sure CI passes (build, lint, tests)
2. Write a clear PR description:
   - **What** changed
   - **Why** (link to issue if one exists)
   - **How to test** it manually
3. Keep PRs focused — separate unrelated changes into separate PRs
4. If your change is a large architectural addition (new service, new DB, etc.), open a Discussion or Issue labeled `RFC` first and wait for feedback

---

## Good First Issues

Not sure where to start? Look for issues labeled [`good first issue`](https://github.com/Mandip77/Eco-Barter/issues?q=label%3A%22good+first+issue%22) on GitHub.

Some areas that are always welcome:

- **Frontend polish** — responsive layout improvements, loading states, empty states
- **Test coverage** — catalog service has no tests yet
- **Docs** — improve inline comments, API docs, or the deployment guide
- **Accessibility** — keyboard navigation, ARIA labels, contrast ratios
- **Performance** — MongoDB index optimization, query profiling

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
