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

# ── Install all Python deps with exact torch pin ─────────────────────────────
# Strategy: generate a constraints file that pins torch==2.4.0+cpu and
# torch-geometric==2.5.0. pip honours constraints over requirements, so
# `torch>=2.4.1` in requirements.txt won't upgrade to a newer version.
#
# Why this matters: without constraints, `pip install -r requirements.txt`
# re-resolves the full graph and upgrades torch to the latest (e.g. 2.13.0),
# defeating the pin we set. Constraints are a hard ceiling — they cannot be
# overridden by any requirement specifier.
RUN pip install --no-cache-dir --upgrade pip

# Write the constraints file. These are absolute ceilings.
RUN printf 'torch==2.4.0\ntorch-geometric==2.5.0\n' > /build/constraints.txt

# Install torch 2.4.0 CPU-only wheel from PyTorch index
RUN pip install --no-cache-dir \
        torch==2.4.0 \
        --index-url https://download.pytorch.org/whl/cpu

# Install torch-geometric 2.5.0 (no scatter/sparse needed for SAGEConv pure path)
RUN pip install --no-cache-dir torch-geometric==2.5.0

# Install the rest of requirements.txt, stripped of torch lines
# We strip torch and torch-geometric so pip doesn't conflict with our constraints
RUN grep -v 'torch' requirements.txt > requirements-docker.txt && \
    pip install --no-cache-dir \
        --constraint /build/constraints.txt \
        -r requirements-docker.txt

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
# We must create /app/data before chown so that the named volume inherits
# the appuser permissions. Otherwise Docker creates it as root at runtime.
RUN mkdir -p /app/data && chown -R appuser:appgroup /app

# ── Entrypoint: sources /shared/contract_address.env then starts uvicorn ──────
COPY --chown=appuser:appgroup docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER appuser

# Expose internal port (compose maps 8001→8000 on host)
EXPOSE 8000

# Entrypoint sources blockchain shared env, then execs uvicorn with --reload
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
