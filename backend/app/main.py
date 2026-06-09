# [WSL2]
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import socketio
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import init_db
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.inference_service import InferenceService
from app.services.reconciliation import ReconciliationWorker


sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    # ADDED another entry 

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

    try:
        app.state.reconciler = ReconciliationWorker()
        app.state.reconciler.start()
    except Exception as exc:
        print(f"[Reconcile] Disabled: {exc}")

    print(f"[DB] SQLite initialized ✓")
    print(f"[ML] Mode: {inference.mode} {'✓' if inference.mode == 'model' else '⚠ degraded'}")
    print(f"[Blockchain] Connected: {blockchain._connected} {'✓' if blockchain._connected else '✗'}")
    print(f"[Reconcile] Active: {app.state.reconciler is not None} ✓")
    yield
    if app.state.reconciler is not None:
        app.state.reconciler.stop()
    if app.state.monitor is not None:
        app.state.monitor.stop()


app = FastAPI(title="GraphSentinel API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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

from app.api.v1 import alerts, analyze, blocked, blockchain, forensics, graph, stats, timeline  # noqa: E402

app.include_router(analyze.router, prefix="/api/v1", tags=["analyze"])
app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
app.include_router(stats.router, prefix="/api/v1", tags=["stats"])
app.include_router(timeline.router, prefix="/api/v1", tags=["timeline"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(blocked.router, prefix="/api/v1", tags=["blocked"])
app.include_router(forensics.router, prefix="/api/v1", tags=["forensics"])
app.include_router(blockchain.router, prefix="/api/v1", tags=["blockchain"])


@app.get("/health")
async def health():
    inference = InferenceService.get_instance()
    blockchain = BlockchainAdapter.get_instance()
    reconciler = getattr(app.state, "reconciler", None)
    reconcile_health = reconciler.last_result if reconciler else {"status": "disabled"}
    status = "ok" if inference.mode == "model" else "degraded"
    if reconcile_health.get("status") == "error":
        status = "degraded"
    return {
        "status": status,
        "service": "GraphSentinel",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ml": inference.health(),
        "blockchain": blockchain.health(),
        "reconciliation": reconcile_health,
    }


@sio.event
async def connect(sid, environ):
    await sio.emit("connected", {"sid": sid, "service": "GraphSentinel"}, to=sid)


socket_app = socketio.ASGIApp(sio, app)

