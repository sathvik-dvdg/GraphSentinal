# ── GraphSentinel Makefile ─────────────────────────────────────────────────────
# Short commands for the Docker workflow.
# Run from the repo root (same directory as docker-compose.yml).
#
# REBUILD vs HOT-RELOAD:
#   Source code changes  → hot-reload automatically (no rebuild needed)
#   requirements.txt changes   → make rebuild  (backend)
#   package-lock.json changes  → make rebuild  (frontend or blockchain)
#   Dockerfile changes         → make rebuild
# ──────────────────────────────────────────────────────────────────────────────

.PHONY: up build rebuild down logs ps shell-backend shell-frontend clean help

# ── Default target ─────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  GraphSentinel Docker Commands"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make build      Build all images (first time or after Dockerfile changes)"
	@echo "  make up         Start all services in detached mode"
	@echo "  make rebuild    Force rebuild + restart (use after requirements.txt changes)"
	@echo "  make down       Stop and remove containers (volumes are preserved)"
	@echo "  make logs       Tail logs for all services (Ctrl+C to stop)"
	@echo "  make ps         Show status of all containers"
	@echo "  make shell-backend    Open a shell in the running backend container"
	@echo "  make shell-frontend   Open a shell in the running frontend container"
	@echo "  make clean      ⚠ INTERACTIVE: stops containers + shows volume cleanup command"
	@echo "  make help       Show this message"
	@echo ""
	@echo "  Access URLs (Docker stack):"
	@echo "    Frontend:   http://localhost:5174"
	@echo "    Backend:    http://localhost:8001"
	@echo "    Ganache:    http://localhost:8546"
	@echo ""

# ── Build ──────────────────────────────────────────────────────────────────────
build:
	docker compose build

# ── Start (detached) ───────────────────────────────────────────────────────────
up:
	docker compose up -d

# ── Rebuild and restart ────────────────────────────────────────────────────────
# Use this after: requirements.txt, package-lock.json, or any Dockerfile changes.
rebuild:
	docker compose up -d --build

# ── Stop containers (volumes are kept) ────────────────────────────────────────
# WARNING: Do NOT add -v flag here. Volume removal is deliberate and interactive.
#          See the 'clean' target below for explicit volume management guidance.
down:
	docker compose down

# ── Logs ──────────────────────────────────────────────────────────────────────
logs:
	docker compose logs -f

# ── Status ────────────────────────────────────────────────────────────────────
ps:
	docker compose ps

# ── Shells ────────────────────────────────────────────────────────────────────
shell-backend:
	docker compose exec backend /bin/bash

shell-frontend:
	docker compose exec frontend /bin/sh

# ── Clean (interactive — does NOT auto-delete volumes) ────────────────────────
# ⚠ IMPORTANT: This target intentionally does NOT run `docker compose down -v`
# or `docker system prune`. Accidental volume deletion loses the SQLite DB.
# If you truly need a fresh start (volumes too), copy-paste the command below
# AFTER confirming no one else is using it:
#
#   docker compose down -v   ← deletes backend-db and contract-shared volumes
#
# This target just stops containers and reminds you of that command.
clean:
	@echo ""
	@echo "  ⚠  Stopping containers (volumes are PRESERVED)..."
	docker compose down
	@echo ""
	@echo "  ──────────────────────────────────────────────────────────────────"
	@echo "  To also delete volumes (fresh SQLite DB + fresh contract state):"
	@echo "    docker compose down -v"
	@echo "  Run that command manually — it is intentionally NOT automated here."
	@echo "  ──────────────────────────────────────────────────────────────────"
	@echo ""
