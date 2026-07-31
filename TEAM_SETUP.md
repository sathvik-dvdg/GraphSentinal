# GraphSentinel — Team Setup Guide

> **TL;DR for day-to-day use:**
> Source code edits hot-reload automatically — **do not rebuild on every commit**.
> Only run `make rebuild` when dependency manifests change.

---

## What requires a rebuild vs. what hot-reloads

| Change type | What to do |
|---|---|
| Edit `backend/app/**/*.py` | Nothing — uvicorn `--reload` picks it up automatically |
| Edit `frontend/src/**` | Nothing — Vite HMR updates your browser tab instantly |
| Edit `backend/requirements.txt` | `make rebuild` (reinstalls Python deps) |
| Edit `frontend/package.json` or `package-lock.json` | `make rebuild` (re-runs `npm ci`) |
| Edit any `Dockerfile` | `make rebuild` |
| Edit `.env.docker` | `make down && make up` (re-reads env file) |

---

## Section A — Docker Stack (Most Team Members — Start Here)

This path works on **Windows, Mac, and Linux** without WSL2 or Mininet.  
The backend uses **`DEMO_FALLBACK_FLOWS=true`** mode — synthetic network flows feed  
the GNN, so the full threat-detection pipeline and dashboard work without a real network.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git clone of this repo
- That's it — no Python, Node, or Ganache installation required on your machine

### First-time setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd GraphSentinal

# 2. Build all images (takes 3–10 minutes first time — PyTorch downloads ~800 MB)
make build

# 3. Start all services
make up

# 4. Verify everything is running
make ps
```

Then open:
- **Dashboard:** http://localhost:5174
- **Backend API:** http://localhost:8001/health
- **Ganache RPC:** http://localhost:8546

> **Note on ports:** Docker uses ports `5174`, `8001`, `8546` — intentionally different  
> from the local dev ports (`5173`, `8000`, `8545`) so both can run side by side.

### Daily workflow

```bash
# Start the stack (already built — fast, ~10 seconds)
make up

# Tail logs while working
make logs

# Stop cleanly (volumes are preserved — DB state survives)
make down
```

### When to rebuild

```bash
# Only needed when dependency manifests change:
make rebuild

# After a git pull that touched requirements.txt or package-lock.json:
git pull
make rebuild
```

### Checking that PyTorch is correctly pinned

```bash
# Should print: 2.4.0
docker compose exec backend python -c "import torch; print(torch.__version__)"

# Should print: False (CPU-only build in Docker)
docker compose exec backend python -c "import torch; print(torch.cuda.is_available())"
```

### Verifying the blockchain contract deployed

```bash
# Check blockchain logs for the contract address
docker compose logs blockchain | grep -i "contract"

# Check the shared file directly
docker compose exec backend cat /shared/contract_address.env
```

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `make up` hangs, blockchain never healthy | Contract deploy failed | `docker compose logs blockchain` — check for Hardhat errors |
| Backend shows `[Blockchain] Connected: False` | `contract_address.env` not found | Restart: `make down && make up` |
| Frontend shows "Network Error" / blank graph | Backend not ready yet | Wait 15s after `make up`, then refresh |
| Port already in use (5174/8001/8546) | Another process on that port | `make down` first, or check `make ps` |
| `torch` version wrong after pulling new code | Stale image layer | `make rebuild` |
| Old Python packages / strange import errors | Stale image | `make rebuild` |

---

## Section B — Scapy Clarification (Docker-safe)

`scapy==2.5.0` is listed in `requirements.txt` but **is not used for live packet capture**  
inside the running backend. A search of the backend source confirms zero calls to  
`sniff()`, `rdpcap()`, `sendp()`, or any live-capture interface.

**What scapy is used for:** It is listed as a dependency of the `check_env.py` diagnostic  
script only. The actual flow data in the backend comes exclusively from:

1. **OVS/Mininet** — when `ENFORCEMENT_MODE=ovs` and Mininet is running (WSL2 only)
2. **`DEMO_FALLBACK_FLOWS=true`** — synthetic flows defined in `flow_parser.py:demo_flows()`  
   (this is what Docker containers use — no packet capture, no host networking required)

**Conclusion:** Scapy does **not** impose any Docker networking limitation. The containerized  
backend runs cleanly in a standard bridge network with no `--net=host` or privileged mode needed.

---

## Section C — Mininet / OVS (WSL2 Only — Sairaj's Full Pipeline)

> **Skip this section if you are not working on the network simulation integration.**  
> Most team members use Section A + `DEMO_FALLBACK_FLOWS=true` and never need WSL2.

Mininet and Open vSwitch require a **real Linux kernel** with the `openvswitch` kernel  
module loaded. This cannot run inside Docker on Windows/Mac — it is architecturally  
incompatible (not a limitation we can work around).

The full pipeline runs split across two environments:

```
Windows Host:    Ganache (port 8545)  +  React Frontend (port 5173)
WSL2 Ubuntu:     FastAPI backend (port 8000)  +  Mininet/OVS (root)
```

### WSL2 prerequisites

- WSL2 with Ubuntu 22.04
- Python 3.12 inside WSL2
- Open vSwitch: `sudo apt-get install openvswitch-switch`
- Mininet: `sudo apt-get install mininet`
- The `backend/.venv` activated: `cd /mnt/d/GraphSentinal/backend && source .venv/bin/activate`

### Startup Sequence with Live Traffic

To receive real flows in the Dockerized backend:

1. **Set up the Shared Secret:**
   The backend and daemon must share a token. Generate a secure token:
   ```bash
   openssl rand -hex 32
   ```
   Add it to your local `.env.docker.local` (never committed) and your WSL2 shell:
   ```bash
   DAEMON_TOKEN="<your-generated-token>"
   ```
   *Make sure `DEMO_FALLBACK_FLOWS="false"` and `ENFORCEMENT_MODE=ovs` in `docker-compose.yml`.*

---

## Section D — Environment Variables Reference

| Variable | Default (Docker) | Description |
|---|---|---|
| `DEMO_FALLBACK_FLOWS` | `true` | **True = Docker mode** (synthetic flows). False = requires Mininet/OVS |
| `ENFORCEMENT_MODE` | `simulated` | `simulated` = log only, `ovs` = real OVS rules (WSL2 only) |
| `GANACHE_URL` | `http://blockchain:8545` | Internal Docker DNS. Local dev uses `http://127.0.0.1:8545` |
| `CONTRACT_ADDRESS` | _(auto at runtime)_ | Written by blockchain entrypoint — do not set manually in Docker |
| `BACKEND_API_TOKEN` | `change-me-for-demo` | Change for any non-demo environment |
| `REQUIRE_ML_MODEL` | `false` | If `true` and weights missing, backend refuses to start |
| `DEMO_ALLOW_MOCK_ML` | `true` | Allows heuristic fallback when GNN weights unavailable |

### Customizing your local Docker env

```bash
# Copy the committed template
cp .env.docker .env.docker.local
# Edit .env.docker.local — this file is gitignored, safe for real values
# Then update docker-compose.yml env_file: to point at .env.docker.local
```

---

## Section E — Fresh Start (When You're Truly Stuck)

If your environment is in a broken state, this is the nuclear option.

```bash
# Step 1: Stop containers (volumes preserved)
make down

# Step 2: If you need to wipe volumes too (fresh DB + fresh contract state):
# Copy-paste this command MANUALLY — it is intentionally not automated:
#
#   docker compose down -v
#
# WARNING: This deletes the backend-db volume (SQLite data) and contract-shared volume.

# Step 3: Rebuild from scratch
make build

# Step 4: Start
make up
```

> ⚠ `docker system prune` and `docker compose down -v` are **not in any Makefile target**  
> intentionally — they can cause data loss and should only be run manually after confirming  
> no one else is using the stack.
