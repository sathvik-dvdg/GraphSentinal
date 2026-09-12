#!/bin/sh
# backend/docker-entrypoint.sh
# ──────────────────────────────────────────────────────────────────────────────
# Sources /shared/contract_address.env (written by the blockchain container's
# entrypoint AFTER the smart contract is deployed) and exports its variables
# into the environment before uvicorn starts.
#
# This is safe because depends_on: condition: service_healthy guarantees the
# blockchain container's healthcheck has already passed — meaning the file
# exists before this script ever runs.
# ──────────────────────────────────────────────────────────────────────────────

SHARED_ENV="/shared/contract_address.env"

if [ -f "${SHARED_ENV}" ]; then
    echo "[Backend] Loading blockchain config from ${SHARED_ENV}"
    # Export each key=value line, skip blank lines and comments
    while IFS='=' read -r key value; do
        case "$key" in
            '#'*|'') continue ;;
        esac
        export "${key}=${value}"
        echo "[Backend]   ${key}=<set>"
    done < "${SHARED_ENV}"
else
    echo "[Backend] WARNING: ${SHARED_ENV} not found — blockchain will be disconnected"
fi

echo "[Backend] Starting uvicorn..."
# On Docker Desktop + WSL2, uvicorn's WatchFiles reloader recursively watches
# the source bind mount and periodically crashes with "Input/output error
# (os error 5)" when the virtiofs layer faults — putting the backend into a
# restart loop (healthcheck: unhealthy, every API call returns nothing).
#
# RELOAD defaults to OFF so `docker compose up` is stable regardless of mount
# health. Set RELOAD=1 in .env.docker.local for hot-reload once your mounts
# are healthy (`wsl --shutdown` + Docker Desktop restart clears the fault).
# Either way, editing backend/app/** while RELOAD is off just needs
# `docker compose restart backend`; migrations apply on restart by design.
if [ "${RELOAD:-0}" = "1" ] || [ "${RELOAD:-}" = "true" ]; then
    echo "[Backend]   hot-reload ENABLED (watching /app/app)"
    exec uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 \
        --reload --reload-dir /app/app
else
    echo "[Backend]   hot-reload disabled (set RELOAD=1 to enable)"
    exec uvicorn app.main:socket_app --host 0.0.0.0 --port 8000
fi
