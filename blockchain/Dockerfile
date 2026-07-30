# ── GraphSentinel Blockchain (Ganache + Hardhat deploy) ───────────────────────
# Node 22-alpine: lightweight, contains npx, npm, ganache, hardhat.
# No multi-stage needed — this is a tooling container, not a build artifact.
# ──────────────────────────────────────────────────────────────────────────────
FROM node:22-alpine

# wget needed in the entrypoint for the Ganache readiness probe
RUN apk add --no-cache wget bash

WORKDIR /blockchain

# ── Copy manifests first (cache layer for npm ci) ─────────────────────────────
COPY package.json package-lock.json ./

# Install all node_modules (ganache, hardhat, ethers, dotenv)
RUN npm ci

# ── Copy smart contract source + scripts + ABI bridge ─────────────────────────
COPY contracts/ ./contracts/
COPY scripts/   ./scripts/
COPY web3_bridge/ ./web3_bridge/
COPY hardhat.config.js ./

# ── Compile contracts so artifacts are available before deploy ────────────────
RUN npx hardhat compile

# ── Entrypoint script ─────────────────────────────────────────────────────────
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# /shared is a named volume shared with the backend container.
# contract_address.env is written here after deploy.
VOLUME ["/shared"]

# Ganache RPC port (Compose maps 8546→8545 on host for side-by-side with local)
EXPOSE 8545

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
