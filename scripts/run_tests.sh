#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# EcoBarter — run all tests locally
# Usage: bash scripts/run_tests.sh
# ─────────────────────────────────────────────────────────────
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     EcoBarter — Local Test Runner        ║"
echo "╚══════════════════════════════════════════╝"

# ─────────────── Trade Engine (Go) ───────────────
echo ""
echo "▶ Trade Engine (Go)"
cd "$ROOT/services/trade"
go mod tidy -e
go vet ./...
go test -tags test -v -race -count=1 ./...
echo "✅ Trade Engine tests passed"

# ─────────────── Identity Service (Python) ───────
echo ""
echo "▶ Identity Service (Python)"
cd "$ROOT/services/identity"
pip install -q -r requirements-test.txt
pytest -v
echo "✅ Identity tests passed"

# ─────────────── Reputation Service (Python) ─────
echo ""
echo "▶ Reputation Service (Python)"
cd "$ROOT/services/reputation"
pip install -q -r requirements-test.txt
pytest -v
echo "✅ Reputation tests passed"

echo ""
echo "🎉 All tests passed!"
