# ── GraphSentinel Frontend ─────────────────────────────────────────────────────
# Multi-stage Node 22-alpine build.
# Stage 1 (builder): npm ci installs exact lockfile-pinned deps.
# Stage 2 (runtime): copies node_modules, bind-mounts src/ at runtime.
#                    Vite HMR handles live reload — no rebuild for src/ changes.
# ──────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Copy manifests first — this layer is cached until package-lock.json changes.
# Changing package-lock.json is the ONLY trigger that requires --build.
COPY package.json package-lock.json ./

# npm ci: deterministic install from lockfile, fails if lockfile is out of sync
RUN npm ci

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM node:22-alpine AS runtime

# Non-root user (node user is built into the official node image, uid=1000)
WORKDIR /app

# Copy node_modules from builder (not from host — avoids native binary mismatch)
COPY --from=builder /app/node_modules ./node_modules

# Static config files needed at startup (not hot-reloaded via bind-mount)
COPY package.json package-lock.json ./
COPY vite.config.docker.js ./
COPY postcss.config.js tailwind.config.js eslint.config.js index.html ./
COPY public/ ./public/

# Source (src/) is bind-mounted by Compose — Vite HMR handles live updates.
# Changing any file in frontend/src/ reloads the browser instantly, no rebuild.

EXPOSE 5173

# Use the Docker-specific vite config so proxy points at http://backend:8000
CMD ["npx", "vite", "--config", "vite.config.docker.js", "--host", "0.0.0.0"]
