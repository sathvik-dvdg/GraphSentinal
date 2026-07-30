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
exec uvicorn app.main:socket_app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
