#!/bin/sh
# blockchain/docker-entrypoint.sh
# ──────────────────────────────────────────────────────────────────────────────
# Startup sequence:
#   1. Start Ganache with PERSISTENT storage at /data/ganache_db
#   2. Wait until Ganache JSON-RPC is responding
#   3. Determine contract deployment strategy:
#        - If /shared/contract_address.env exists AND contract bytecode is live
#          at that address → reuse the existing deployment (no redeployment)
#        - Otherwise → deploy a fresh IncidentLogger and save the new address
#   4. Write CONTRACT_ADDRESS to /shared/contract_address.env (healthcheck gate)
#   5. Tail Ganache logs to keep the container alive
#
# N-03 changes:
#   - Ganache is started with --database.dbPath /data/ganache_db so EVM state
#     survives container restart and recreation (when the ganache-data volume is
#     retained).
#   - Contract redeployment is skipped if the previously-deployed address still
#     has live bytecode on the persistent chain.
#   - A stale/invalid address triggers a fresh deployment with an explicit log.
# ──────────────────────────────────────────────────────────────────────────────
set -e

SHARED_DIR="/shared"
CONTRACT_ENV_FILE="${SHARED_DIR}/contract_address.env"
GANACHE_LOG="/tmp/ganache.log"
GANACHE_DB_PATH="/data/ganache_db"

echo "[Entrypoint] Starting Ganache blockchain node (persistent storage: ${GANACHE_DB_PATH})..."
npx ganache \
    --host 0.0.0.0 \
    --port 8545 \
    --deterministic \
    --accounts 5 \
    --chain.chainId 1337 \
    --database.dbPath "${GANACHE_DB_PATH}" \
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

# ── N-03: Determine whether a valid prior deployment can be reused ────────────
CONTRACT_ADDRESS=""
DEPLOY_REASON="no prior deployment found"

if [ -f "${CONTRACT_ENV_FILE}" ]; then
    # Parse the address from the existing env file
    EXISTING_ADDRESS=$(grep -oE '0x[0-9a-fA-F]{40}' "${CONTRACT_ENV_FILE}" | head -1)

    if [ -n "${EXISTING_ADDRESS}" ]; then
        echo "[Entrypoint] Found prior contract address: ${EXISTING_ADDRESS}"
        echo "[Entrypoint] Checking bytecode at that address..."

        # Ask Ganache for the bytecode at the existing address
        CODE_RESULT=$(wget -qO- \
            --post-data="{\"jsonrpc\":\"2.0\",\"method\":\"eth_getCode\",\"params\":[\"${EXISTING_ADDRESS}\",\"latest\"],\"id\":1}" \
            --header='Content-Type: application/json' \
            http://127.0.0.1:8545 2>/dev/null || true)

        # Extract the result field; a live contract has bytecode longer than "0x"
        CODE_VALUE=$(echo "${CODE_RESULT}" | grep -oE '"result":"0x[0-9a-fA-F]*"' | sed 's/"result":"//;s/"//')

        if [ -n "${CODE_VALUE}" ] && [ "${CODE_VALUE}" != "0x" ]; then
            echo "[Entrypoint] Bytecode confirmed at ${EXISTING_ADDRESS} — reusing existing deployment."
            CONTRACT_ADDRESS="${EXISTING_ADDRESS}"
            DEPLOY_REASON="reused"
        else
            DEPLOY_REASON="prior address has no bytecode (chain was reset or address is stale)"
            echo "[Entrypoint] WARNING: ${DEPLOY_REASON}. Deploying fresh contract."
        fi
    else
        DEPLOY_REASON="contract_address.env present but no valid address found"
        echo "[Entrypoint] WARNING: ${DEPLOY_REASON}. Deploying fresh contract."
    fi
fi

# ── Deploy only when necessary ────────────────────────────────────────────────
if [ -z "${CONTRACT_ADDRESS}" ]; then
    echo "[Entrypoint] Deploying IncidentLogger contract (reason: ${DEPLOY_REASON})..."
    DEPLOY_OUTPUT=$(npx hardhat run scripts/deploy.js --network localhost 2>&1)
    echo "${DEPLOY_OUTPUT}"

    CONTRACT_ADDRESS=$(echo "${DEPLOY_OUTPUT}" | grep -i 'Deployed at:' | grep -oE '0x[0-9a-fA-F]{40}')

    if [ -z "${CONTRACT_ADDRESS}" ]; then
        echo "[Entrypoint] ERROR: Could not parse CONTRACT_ADDRESS from deploy output."
        exit 1
    fi
    echo "[Entrypoint] Contract deployed at: ${CONTRACT_ADDRESS}"
else
    echo "[Entrypoint] Skipping deployment — reusing ${CONTRACT_ADDRESS}"
fi

# ── Write address to shared volume (this is the healthcheck gate) ─────────────
# The backend container reads this file on startup to get CONTRACT_ADDRESS.
# The healthcheck only passes once this file exists — guaranteeing backend
# never starts before the contract is live.
mkdir -p "${SHARED_DIR}"
printf "CONTRACT_ADDRESS=%s\nGANACHE_URL=http://blockchain:8545\n" \
    "${CONTRACT_ADDRESS}" > "${CONTRACT_ENV_FILE}"

echo "[Entrypoint] Wrote ${CONTRACT_ENV_FILE}"
echo "[Entrypoint] === Blockchain service READY ==="
echo "[Entrypoint] Contract : ${CONTRACT_ADDRESS}"
echo "[Entrypoint] Chain ID : 1337"

# ── Keep container alive by tailing Ganache ──────────────────────────────────
tail -f "${GANACHE_LOG}" &
wait "${GANACHE_PID}"
