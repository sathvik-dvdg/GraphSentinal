#!/bin/sh
# blockchain/docker-entrypoint.sh
# ──────────────────────────────────────────────────────────────────────────────
# Startup sequence:
#   1. Start Ganache in the background
#   2. Wait until Ganache JSON-RPC is responding
#   3. Run Hardhat deploy → writes CONTRACT_ADDRESS to /shared/contract_address.env
#   4. Mark deployment complete (healthcheck gate file)
#   5. Tail Ganache logs to keep the container alive
#
# The healthcheck tests for /shared/contract_address.env, NOT just Ganache RPC.
# This means backend's depends_on: condition: service_healthy only passes
# AFTER the contract is deployed — fixing the race condition where backend
# would start before CONTRACT_ADDRESS existed.
# ──────────────────────────────────────────────────────────────────────────────
set -e

SHARED_DIR="/shared"
CONTRACT_ENV_FILE="${SHARED_DIR}/contract_address.env"
GANACHE_LOG="/tmp/ganache.log"

echo "[Entrypoint] Starting Ganache blockchain node..."
npx ganache \
    --host 0.0.0.0 \
    --port 8545 \
    --deterministic \
    --accounts 5 \
    --chain.chainId 1337 \
    > "${GANACHE_LOG}" 2>&1 &

GANACHE_PID=$!

# ── Wait for Ganache RPC to be ready ─────────────────────────────────────────
echo "[Entrypoint] Waiting for Ganache RPC on port 8545..."
MAX_WAIT=30
COUNT=0
until wget -qO- --post-data='{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' \
           --header='Content-Type: application/json' \
           http://127.0.0.1:8545 > /dev/null 2>&1; do
    COUNT=$((COUNT + 1))
    if [ "$COUNT" -ge "$MAX_WAIT" ]; then
        echo "[Entrypoint] ERROR: Ganache did not start within ${MAX_WAIT}s"
        cat "${GANACHE_LOG}"
        exit 1
    fi
    sleep 1
done
echo "[Entrypoint] Ganache ready after ${COUNT}s."

# ── Deploy the smart contract ─────────────────────────────────────────────────
echo "[Entrypoint] Deploying IncidentLogger contract..."
DEPLOY_OUTPUT=$(npx hardhat run scripts/deploy.js --network localhost 2>&1)
echo "${DEPLOY_OUTPUT}"

# ── Parse CONTRACT_ADDRESS from deploy output ─────────────────────────────────
CONTRACT_ADDRESS=$(echo "${DEPLOY_OUTPUT}" | grep -i 'Deployed at:' | grep -oE '0x[0-9a-fA-F]{40}')

if [ -z "${CONTRACT_ADDRESS}" ]; then
    echo "[Entrypoint] ERROR: Could not parse CONTRACT_ADDRESS from deploy output."
    exit 1
fi

echo "[Entrypoint] Contract deployed at: ${CONTRACT_ADDRESS}"

# ── Write address to shared volume (this is the healthcheck gate) ─────────────
# The backend container reads this file on startup to get CONTRACT_ADDRESS.
# The healthcheck only passes once this file exists — guaranteeing backend
# never starts before the contract is live.
mkdir -p "${SHARED_DIR}"
printf "CONTRACT_ADDRESS=%s\nGANACHE_URL=http://blockchain:8545\n" \
    "${CONTRACT_ADDRESS}" > "${CONTRACT_ENV_FILE}"

echo "[Entrypoint] Wrote ${CONTRACT_ENV_FILE}"
echo "[Entrypoint] === Blockchain service READY ==="

# ── Keep container alive by tailing Ganache ──────────────────────────────────
tail -f "${GANACHE_LOG}" &
wait "${GANACHE_PID}"
