# [WSL2]
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import socketio
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_db
from app.services import auth_service
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.inference_service import InferenceService
from app.services.reconciliation import ReconciliationWorker


sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.cors_origins_list,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    inference = InferenceService.get_instance()
    blockchain = BlockchainAdapter.get_instance()
    app.state.monitor = None
    app.state.reconciler = None
    try:
        from app.mininet_monitor.monitor import MininetMonitor

        app.state.monitor = MininetMonitor(sio=sio)
        app.state.monitor.start()
    except Exception as exc:
        print(f"[Monitor] Disabled: {exc}")

    # N-05: start ReconciliationWorker for continuous blockchain outbox & OVS reconciliation
    try:
        app.state.reconciler = ReconciliationWorker(interval=settings.blockchain_retry_interval_seconds)
        app.state.reconciler.start()
    except Exception as exc:
        print(f"[Reconcile] Disabled: {exc}")

    print(f"[DB] SQLite initialized [OK]")
    print(f"[ML] Mode: {inference.mode} {'[OK]' if inference.mode == 'model' else '[degraded]'}")
    print(f"[Blockchain] Connected: {blockchain._connected} {'[OK]' if blockchain._connected else '[ERROR]'}")
    print(f"[Reconcile] Active: {app.state.reconciler is not None} [OK]")
    yield
    if app.state.reconciler is not None:
        app.state.reconciler.stop()
    if app.state.monitor is not None:
        app.state.monitor.stop()


app = FastAPI(title="GraphSentinel API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 MB


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies to prevent memory exhaustion DoS."""

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return Response(content="Request body too large", status_code=413)
        return await call_next(request)


app.add_middleware(RequestSizeLimitMiddleware)

from app.api.v1 import alerts, analyze, auth, blocked, blockchain, enforcement_actions, forensics, graph, settings_route, stats, timeline  # noqa: E402

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(analyze.router, prefix="/api/v1", tags=["analyze"])
app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
app.include_router(stats.router, prefix="/api/v1", tags=["stats"])
app.include_router(timeline.router, prefix="/api/v1", tags=["timeline"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(blocked.router, prefix="/api/v1", tags=["blocked"])
app.include_router(forensics.router, prefix="/api/v1", tags=["forensics"])
app.include_router(blockchain.router, prefix="/api/v1", tags=["blockchain"])
app.include_router(settings_route.router, prefix="/api/v1", tags=["settings"])
app.include_router(enforcement_actions.router, prefix="/api/v1", tags=["enforcement-actions"])


@app.get("/health")
async def health():
    inference = InferenceService.get_instance()
    blockchain = BlockchainAdapter.get_instance()
    reconciler = getattr(app.state, "reconciler", None)
    monitor = getattr(app.state, "monitor", None)
    reconcile_health = reconciler.last_result if reconciler else {"status": "disabled"}
    monitor_health = monitor.health() if monitor else {"status": "disabled"}
    status = "ok" if inference.mode == "model" else "degraded"
    if reconcile_health.get("status") == "error":
        status = "degraded"
    return {
        "status": status,
        "service": "GraphSentinel",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ml": inference.health(),
        "blockchain": blockchain.health(),
        "monitor": monitor_health,
        "reconciliation": reconcile_health,
    }


@sio.event
async def connect(sid, environ, auth=None):
    # Same auth gate as require_session_or_api_key, adapted for Socket.IO's
    # connect-time auth payload (Error.md #18/#27 — this socket pushes the
    # same live security data as the now-gated REST endpoints).
    token = (auth or {}).get("token") if isinstance(auth, dict) else None
    api_key = environ.get("HTTP_X_API_KEY")
    key_ok = bool(api_key) and bool(settings.backend_api_token) and secrets.compare_digest(api_key, settings.backend_api_token)
    if not (key_ok or auth_service.validate_session(token)):
        raise ConnectionRefusedError("Authentication required")
    await sio.emit("connected", {"sid": sid, "service": "GraphSentinel"}, to=sid)


socket_app = socketio.ASGIApp(sio, app)

