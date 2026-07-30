# ── GraphSentinel Backend ──────────────────────────────────────────────────────
# Multi-stage: builder installs all Python deps (including heavy torch wheels)
# Runtime stage is lean; source code is bind-mounted via Compose for hot-reload.
# ──────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# System build deps needed for some C-extension wheels (e.g. pydantic, scapy)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libffi-dev \
        libssl-dev \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# ── Copy manifests first (cache layer) ────────────────────────────────────────
COPY requirements.txt .

# ── Install PyTorch 2.4.0 CPU-only first (separate index, large wheel) ────────
# Pinned exactly to match the working dev venv. CPU-only avoids ~3 GB CUDA DLLs.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
        torch==2.4.0 \
        --index-url https://download.pytorch.org/whl/cpu

# ── Install torch-geometric 2.5.0 (matches requirements.txt pin) ─────────────
# torch-geometric 2.5.0 + torch 2.4.0/cpu does NOT require torch-scatter or
# torch-sparse for the SAGEConv layer used here — pure Python message-passing
# path is used. Installing them would require building from source against
# torch 2.4.0 CPU ABI, which is fragile and unnecessary for this workload.
RUN pip install --no-cache-dir torch-geometric==2.5.0

# ── Install the rest of requirements (excluding torch lines) ──────────────────
# We pre-installed torch above; pip will honour the already-installed version.
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Runtime OS deps: none needed beyond base slim (no GPU, no OVS)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ─────────────────────────────────────────────────────────────
RUN groupadd --gid 1001 appgroup \
 && useradd --uid 1001 --gid 1001 --shell /bin/bash --create-home appuser

# ── Copy installed site-packages from builder ─────────────────────────────────
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app

# Source code is NOT copied here — it is bind-mounted at runtime by Compose.
# This means any edit to backend/app/ triggers uvicorn --reload, not a rebuild.
# Only requirements.txt changes require a docker compose up --build.

# ── Ownership ─────────────────────────────────────────────────────────────────
RUN chown -R appuser:appgroup /app

# ── Entrypoint: sources /shared/contract_address.env then starts uvicorn ──────
COPY --chown=appuser:appgroup docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER appuser

# Expose internal port (compose maps 8001→8000 on host)
EXPOSE 8000

# Entrypoint sources blockchain shared env, then execs uvicorn with --reload
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
