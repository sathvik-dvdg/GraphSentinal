# ── GraphSentinel v2 inference service ────────────────────────────────────────
# Runs graphsentinel.inference.service:app — the HTTP boundary the backend talks
# to. This container, not the backend, is the only thing in the stack that
# imports torch.
#
# WHY A SEPARATE CONTAINER
#   InferenceEngine is stateful: a flow buffer, a 60s window boundary, and a
#   persistent host-memory module keyed by IP. In-process in the backend, the
#   MininetMonitor daemon thread and /api/v1/analyze request handlers would
#   interleave into one shared buffer with no coordination. That is a
#   correctness bug, not a deployment preference.
#
# WHY THE MODEL DIRECTORY IS A BIND MOUNT, NOT A COPY
#   weights.pt is 72.7 MiB and deliberately gitignored (see INTEGRATION.md), so
#   it is not in the build context on a fresh clone. Baking it in would make the
#   image unbuildable without it; mounting it turns a missing file into a clear
#   runtime error instead of a broken build.
#
# TORCH VERSION: this pin (2.4.0) is NOT the version the model was exported
#   from (2.11.0+cu128). InferenceEngine.from_artifacts() loads weights with
#   weights_only=False. See INTEGRATION.md — the three-way split is recorded
#   there and must be verified by loading the model inside this container.
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# curl is needed by the healthcheck below; nothing else is installed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Large wheels on a flaky link: be patient rather than fail halfway, matching
# the backend Dockerfile's settings.
ENV PIP_RETRIES=10 \
    PIP_TIMEOUT=120 \
    PIP_RESUME_RETRIES=10 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir --upgrade pip

# CPU-only torch from the PyTorch index. Pinned to match the backend image so
# the stack has one torch version rather than two.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cpu

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch-geometric==2.5.0

# Inference-only dependencies. requirements-train.txt (sklearn, pyarrow,
# matplotlib, onnx) is deliberately NOT installed — none of it is on the
# inference path.
COPY ML/graphsentinel_v2/requirements.txt /app/requirements.txt
# PANDAS/NUMPY PINNED HERE, not in the package. requirements.txt says
# `pandas>=2.0`, and an unpinned build on 2026-09-13 resolved pandas 3.0.5 —
# a major version that changed copy-on-write and default string dtypes, under
# an engine that builds every window through pandas. The package suite was
# verified locally on pandas 2.3.3 / numpy 2.2.6, so the container runs those.
# The torch constraints stop the runtime install from replacing torch.
RUN printf 'pandas==2.3.3\nnumpy==2.2.6\ntorch==2.4.0\ntorch-geometric==2.5.0\n' > /app/constraints.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    grep -viE '^(torch|torch-geometric)\b' /app/requirements.txt > /app/requirements-runtime.txt \
    && pip install -c /app/constraints.txt -r /app/requirements-runtime.txt

# The training package. Copied read-only; the service only imports from it.
COPY ML/graphsentinel_v2/graphsentinel /app/graphsentinel

# Model artefacts are bind-mounted here by docker-compose (./ML:/app/ML:ro).
ENV GRAPHSENTINEL_MODEL_DIR=/app/ML

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# /health returns 503 until the model has loaded, so this gates the backend on a
# genuinely ready service rather than just an open socket.
HEALTHCHECK --interval=10s --timeout=5s --retries=30 --start-period=30s \
    CMD curl -fsS http://localhost:8080/health || exit 1

CMD ["uvicorn", "graphsentinel.inference.service:app", "--host", "0.0.0.0", "--port", "8080"]
