# EcoBarter — Oracle Cloud Free Tier Deployment

All services run on a single **Ampere A1.Flex** VM (4 OCPUs, 24 GB RAM, ARM64) — the most capable Always Free resource Oracle offers. Total monthly cost: **$0**.

---

## Oracle Always Free Resources Used

| Resource | Spec | Cost |
|---|---|---|
| Ampere A1.Flex VM | 4 OCPUs, 24 GB RAM, Ubuntu 22.04 ARM64 | Free |
| Block Volume | 150 GB (200 GB limit shared across shapes) | Free |
| Flexible Load Balancer | 10 Mbps (1 always-free instance) | Free |
| Object Storage | 20 GB (backups) | Free |
| Outbound bandwidth | 10 TB/month | Free |

> The A1 instance gives 4 CPUs and 24 GB RAM — enough headroom to run all EcoBarter services comfortably.

---

## 1. Create Your Oracle Cloud Account

1. Go to [cloud.oracle.com](https://cloud.oracle.com) → **Start for free**
2. Choose a **Home Region** close to your users (you cannot change this later)
3. Complete identity verification (credit card required but not charged)
4. Wait for account activation (can take up to 30 minutes)

---

## 2. Create the Virtual Cloud Network (VCN)

In the OCI Console: **Networking → Virtual Cloud Networks → Create VCN**

| Field | Value |
|---|---|
| Name | `ecobarter-vcn` |
| IPv4 CIDR | `10.0.0.0/16` |
| DNS label | `ecobarter` |

After creation:

1. Click **Create Subnet**
   - Name: `public-subnet`
   - CIDR: `10.0.1.0/24`
   - Subnet type: **Public**
   - Route table: default (includes internet gateway)
   - Security list: default

2. Verify an **Internet Gateway** exists under Gateways (OCI creates one automatically with the VCN wizard — if not, create one and add a route `0.0.0.0/0 → igw` to the default route table).

---

## 3. Open Firewall Ports (Security List)

**Networking → Virtual Cloud Networks → ecobarter-vcn → Security Lists → Default Security List**

Add these **Ingress Rules**:

| Source | Protocol | Port | Description |
|---|---|---|---|
| `0.0.0.0/0` | TCP | 22 | SSH |
| `0.0.0.0/0` | TCP | 80 | HTTP (redirects to HTTPS via Traefik) |
| `0.0.0.0/0` | TCP | 443 | HTTPS |

All other ports stay closed. Services communicate internally on Docker's bridge network.

---

## 4. Launch the Ampere A1 Instance

**Compute → Instances → Create Instance**

| Field | Value |
|---|---|
| Name | `ecobarter-prod` |
| Image | **Canonical Ubuntu 22.04 (aarch64)** |
| Shape | `VM.Standard.A1.Flex` |
| OCPUs | `4` |
| Memory | `24 GB` |
| Subnet | `public-subnet` (auto-assign public IP) |
| SSH key | Upload your public key (`~/.ssh/id_ed25519.pub`) |

> If 4 OCPUs is unavailable due to capacity, retry a different AD or reduce to 2 OCPUs / 12 GB temporarily — capacity is sometimes limited in popular regions.

After launch, note the **Public IP** shown on the instance detail page.

---

## 5. Attach a Block Volume for Persistent Data

**Storage → Block Volumes → Create Block Volume**

| Field | Value |
|---|---|
| Name | `ecobarter-data` |
| Size | `150 GB` |
| Availability Domain | Same AD as your instance |
| VPUs | `10` (Balanced, free tier) |

Then: **Attached Block Volumes → Attach** → select your instance → use **iSCSI** attachment.

After attaching, SSH in and run the iSCSI connect commands shown in the OCI Console (they look like `sudo iscsiadm -m node ...`). Then format and mount:

```bash
# Check the device name (usually /dev/sdb)
lsblk

# Format (only do this once — destroys existing data)
sudo mkfs.ext4 /dev/sdb

# Create mount point
sudo mkdir -p /data

# Mount
sudo mount /dev/sdb /data

# Persist across reboots
echo '/dev/sdb /data ext4 defaults,_netdev,nofail 0 2' | sudo tee -a /etc/fstab
```

---

## 6. Install Docker on the Instance

```bash
ssh ubuntu@<PUBLIC_IP>

# Update and install prerequisites
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the Docker repository (arm64)
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list

# Install Docker CE and Compose plugin
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Allow ubuntu user to run docker without sudo
sudo usermod -aG docker ubuntu
newgrp docker

# Verify
docker --version
docker compose version
```

---

## 7. Configure DNS

At your domain registrar (or wherever you manage DNS), add:

| Type | Host | Value | TTL |
|---|---|---|---|
| `A` | `@` or `yourdomain.com` | `<PUBLIC_IP>` | 300 |
| `A` | `www` | `<PUBLIC_IP>` | 300 |

Wait for DNS propagation (up to 10 minutes with low TTL). Verify:

```bash
dig +short yourdomain.com
# Should return your Oracle instance's public IP
```

Traefik will automatically obtain a Let's Encrypt certificate once DNS resolves to the server.

---

## 8. Clone and Configure the Application

```bash
# Move data directories to the block volume
sudo mkdir -p /data/ecobarter
sudo chown ubuntu:ubuntu /data/ecobarter

# Clone the repository
git clone https://github.com/your-org/ecobarter.git /data/ecobarter
cd /data/ecobarter

# Create the Let's Encrypt storage file with correct permissions
mkdir -p letsencrypt
touch letsencrypt/acme.json
chmod 600 letsencrypt/acme.json
```

---

## 9. Generate and Validate Secrets

```bash
cd /data/ecobarter

# Generate strong secrets and print them
bash scripts/generate_secrets.sh
```

Copy the output into a new `.env` file:

```bash
# Create .env from the example
cp .env.example .env
nano .env  # or: vim .env
```

Fill in all values. At minimum, set:

```dotenv
# Infrastructure
POSTGRES_USER=ecobarter
POSTGRES_PASSWORD=<generated>
POSTGRES_DB=ecobarter
MONGO_INITDB_ROOT_USERNAME=ecobarter
MONGO_INITDB_ROOT_PASSWORD=<generated>

# Auth
JWT_SECRET=<64+ hex chars from generate_secrets.sh>

# Centrifugo
CENTRIFUGO_SECRET=<generated>
CENTRIFUGO_API_KEY=<generated>
CENTRIFUGO_ADMIN_PASSWORD=<generated>

# TLS / Domain
DOMAIN=yourdomain.com
ACME_EMAIL=you@yourdomain.com

# CORS
ALLOWED_ORIGINS=https://yourdomain.com

# Connection strings (use service names — Docker internal DNS)
POSTGRES_URL=postgresql://ecobarter:<password>@postgres:5432/ecobarter
POSTGRES_DSN=host=postgres user=ecobarter password=<password> dbname=ecobarter port=5432 sslmode=disable
CATALOG_MONGO_URL=mongodb://ecobarter:<password>@mongodb:27017/catalog?authSource=admin
NATS_URL=nats://nats:4222
VITE_API_BASE_URL=https://yourdomain.com
```

Validate before deploying:

```bash
# Load .env and run validation
bash -c 'set -a; source .env; set +a; bash scripts/validate_env.sh'
```

All variables should show **OK** (green). Fix any **MISSING** or **WEAK** values before continuing.

---

## 10. Deploy

```bash
cd /data/ecobarter

# Pull/build all images and start in detached mode
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Watch the startup:

```bash
docker compose logs -f
```

Within 60–90 seconds you should see:
- Databases healthy
- All services connected to NATS
- Traefik obtaining a Let's Encrypt certificate (check `docker compose logs traefik`)

Test the deployment:

```bash
# Health checks
curl -s https://yourdomain.com/api/v1/auth/me  # → 403 (expected — no token)
curl -s https://yourdomain.com/api/v1/catalog/products  # → []
curl -s https://yourdomain.com/api/v1/trade  # → {"status":"ok",...}
curl -s https://yourdomain.com/api/v1/reputation/leaderboard  # → []
```

---

## 11. Automatic Restart on Reboot

All services use `restart: unless-stopped` in `docker-compose.prod.yml`. Docker daemon itself needs to be enabled:

```bash
sudo systemctl enable docker
sudo systemctl enable containerd
```

To verify restart behavior after a reboot:

```bash
sudo reboot
# Wait ~2 minutes, then SSH back in
ssh ubuntu@<PUBLIC_IP>
docker ps  # All containers should be running
```

---

## 12. Database Migrations

Run migrations after first deployment (and after schema changes):

```bash
# Identity (Alembic)
docker compose exec identity-service alembic upgrade head

# Trade (golang-migrate — runs automatically on service start via initDB())
# No manual step needed
```

---

## 13. Backups to Oracle Object Storage

Oracle gives 20 GB of Object Storage free. Set up nightly backups:

```bash
# Install OCI CLI
bash -c "$(curl -L https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.sh)"
oci setup config  # Follow prompts — you'll need tenancy OCID, user OCID, region

# Create a bucket in OCI Console: Storage → Buckets → Create → "ecobarter-backups"

# Create backup script
cat > /data/ecobarter/scripts/backup.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
DATE=$(date +%Y%m%d_%H%M%S)
BUCKET="ecobarter-backups"

# PostgreSQL dump
docker compose -f /data/ecobarter/docker-compose.yml exec -T postgres \
  pg_dump -U ecobarter ecobarter | gzip > /tmp/postgres_${DATE}.sql.gz
oci os object put --bucket-name "$BUCKET" --file /tmp/postgres_${DATE}.sql.gz \
  --name "postgres/postgres_${DATE}.sql.gz" --force
rm /tmp/postgres_${DATE}.sql.gz

# MongoDB dump
docker compose -f /data/ecobarter/docker-compose.yml exec -T mongodb \
  mongodump --username ecobarter --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin --archive --gzip > /tmp/mongo_${DATE}.archive.gz
oci os object put --bucket-name "$BUCKET" --file /tmp/mongo_${DATE}.archive.gz \
  --name "mongo/mongo_${DATE}.archive.gz" --force
rm /tmp/mongo_${DATE}.archive.gz

echo "Backup complete: $DATE"
EOF
chmod +x /data/ecobarter/scripts/backup.sh

# Schedule nightly at 02:00 UTC
(crontab -l 2>/dev/null; echo "0 2 * * * bash -c 'set -a; source /data/ecobarter/.env; set +a; /data/ecobarter/scripts/backup.sh' >> /var/log/ecobarter-backup.log 2>&1") | crontab -
```

---

## 14. Useful Operations

### View logs
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f <service-name>
# e.g.: trade-engine, identity-service, traefik
```

### Restart a single service
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart identity-service
```

### Deploy an update
```bash
cd /data/ecobarter
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### Check resource usage
```bash
docker stats --no-stream
# Verify total RAM stays under ~20 GB (leaving 4 GB headroom for the OS)
```

### Renew certificates (automatic)
Traefik renews Let's Encrypt certificates automatically. To force a check:
```bash
docker compose restart traefik
```

---

## Architecture on Free Tier

```
Internet
    │
    ▼
Oracle Cloud (A1.Flex VM — 4 OCPUs, 24 GB RAM)
    │
Traefik :443 (TLS termination, security headers)
    ├── /api/v1/auth      → identity-service  (FastAPI, port 80)
    ├── /api/v1/catalog   → catalog-service   (FastAPI, port 80)
    ├── /api/v1/trade     → trade-engine      (Go/Gin, port 80)
    ├── /api/v1/reputation→ reputation-service(FastAPI, port 80)
    ├── /connection       → centrifugo        (WebSocket, port 8000)
    └── /                 → web-frontend      (SvelteKit, port 3000)
         │
         ├── postgres  (internal, 5432)
         ├── mongodb   (internal, 27017)
         ├── redis     (internal, 6379)
         └── nats      (internal, 4222)

Block Volume (/data) — 150 GB
    ├── pgdata/
    ├── mongodata/
    └── letsencrypt/
```

All database ports are internal only — never exposed to the internet.

---

## Expected Resource Usage at Idle

| Service | RAM | CPU |
|---|---|---|
| postgres | ~200 MB | 0.05 |
| mongodb | ~300 MB | 0.05 |
| redis | ~20 MB | 0.01 |
| nats | ~30 MB | 0.01 |
| identity-service | ~100 MB | 0.05 |
| catalog-service | ~100 MB | 0.05 |
| trade-engine | ~50 MB | 0.05 |
| reputation-service | ~80 MB | 0.03 |
| centrifugo | ~80 MB | 0.05 |
| web-frontend | ~150 MB | 0.05 |
| traefik | ~30 MB | 0.02 |
| **Total** | **~1.1 GB** | **~0.42** |

The 24 GB RAM and 4 OCPUs leave substantial headroom for traffic spikes and container rebuild operations.
