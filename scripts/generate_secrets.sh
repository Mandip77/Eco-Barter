#!/usr/bin/env bash
# Generate cryptographically strong secrets for EcoBarter.
# Run once, copy the output into your .env file.
# Usage: bash scripts/generate_secrets.sh

set -euo pipefail

hex() { python3 -c "import secrets; print(secrets.token_hex($1))"; }
pw()  { python3 -c "import secrets,string; a=string.ascii_letters+string.digits+'@#%^&*'; print(''.join(secrets.choice(a) for _ in range($1)))"; }

echo ""
echo "# ── Paste the lines below into your .env file ──────────────────────────"
echo ""
echo "POSTGRES_PASSWORD=$(pw 24)"
echo "MONGO_INITDB_ROOT_PASSWORD=$(pw 24)"
echo ""
echo "# Min 64 hex chars for JWT"
echo "JWT_SECRET=$(hex 32)"
echo ""
echo "# Centrifugo — min 32 hex chars each"
echo "CENTRIFUGO_SECRET=$(hex 32)"
echo "CENTRIFUGO_API_KEY=$(hex 32)"
echo "CENTRIFUGO_ADMIN_PASSWORD=$(pw 20)"
echo ""
echo "# ────────────────────────────────────────────────────────────────────────"
echo ""
echo "IMPORTANT: Store these values in a password manager or secret vault."
echo "Never commit them to git."
