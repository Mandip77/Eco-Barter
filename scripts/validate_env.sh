#!/usr/bin/env bash
# Validate that all required environment variables are set before deploying.
# Usage: source .env && bash scripts/validate_env.sh
# Or:    bash -c 'set -a; source .env; set +a; bash scripts/validate_env.sh'

set -euo pipefail

REQUIRED=(
  POSTGRES_USER
  POSTGRES_PASSWORD
  POSTGRES_DB
  MONGO_INITDB_ROOT_USERNAME
  MONGO_INITDB_ROOT_PASSWORD
  JWT_SECRET
  CENTRIFUGO_SECRET
  CENTRIFUGO_API_KEY
  CENTRIFUGO_ADMIN_PASSWORD
  DOMAIN
  ACME_EMAIL
  ALLOWED_ORIGINS
)

WEAK_PATTERNS=(
  "change_me"
  "super_secret"
  "my_api_key"
  "ecopassword"
  "adminpassword"
  "secret"
  "password"
)

RED='\033[0;31m'
YEL='\033[1;33m'
GRN='\033[0;32m'
NC='\033[0m'

errors=0
warnings=0

echo ""
echo "── EcoBarter Environment Validation ────────────────────────────────────"
echo ""

for var in "${REQUIRED[@]}"; do
  val="${!var:-}"
  if [ -z "$val" ]; then
    echo -e "${RED}  MISSING   ${NC} $var"
    ((errors++))
  else
    # Check for weak/default values
    weak=0
    for pat in "${WEAK_PATTERNS[@]}"; do
      if echo "$val" | grep -qi "$pat"; then
        echo -e "${YEL}  WEAK      ${NC} $var  (contains '$pat' — replace with a generated secret)"
        ((warnings++))
        weak=1
        break
      fi
    done
    if [ $weak -eq 0 ]; then
      echo -e "${GRN}  OK        ${NC} $var"
    fi
  fi
done

# JWT_SECRET length check (should be >= 32 bytes = 64 hex chars)
jwt="${JWT_SECRET:-}"
if [ -n "$jwt" ] && [ ${#jwt} -lt 64 ]; then
  echo -e "${YEL}  SHORT     ${NC} JWT_SECRET is only ${#jwt} chars — use at least 64"
  ((warnings++))
fi

echo ""
echo "────────────────────────────────────────────────────────────────────────"

if [ $errors -gt 0 ]; then
  echo -e "${RED}  FAILED: $errors missing variable(s). Fix before deploying.${NC}"
  exit 1
elif [ $warnings -gt 0 ]; then
  echo -e "${YEL}  WARNING: $warnings weak/short value(s). Run scripts/generate_secrets.sh.${NC}"
  exit 1
else
  echo -e "${GRN}  All variables are set and look strong. Ready to deploy.${NC}"
fi
echo ""
