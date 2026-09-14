import re
import secrets
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timezone

import socketio
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import init_db
from app.services import auth_service
from app.services.blockchain_adapter import BlockchainAdapter
from app.services.inference_client import InferenceClient, InferenceUnavailable
from app.services.inference_service import InferenceService
from app.services.inference_v2 import build_state, verify_service_contract
from app.services.model_contract import ContractError
from app.services.reconciliation import ReconciliationWorker


request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")
_REQ_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """R-04 (M14-F01) — Assign or propagate a sanitized correlation/request ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming_id = request.headers.get("x-request-id") or request.headers.get("x-correlation-id")
        if incoming_id and _REQ_ID_PATTERN.match(incoming_id):
            req_id = incoming_id
        else:
            req_id = uuid.uuid4().hex

        token = request_id_ctx_var.set(req_id)
        request.state.request_id = req_id
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx_var.reset(token)


from app.websocket.server import sio



@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    inference = InferenceService.get_instance()
    blockchain = BlockchainAdapter.get_instance()
    # v2 startup contract check. build_state() RAISES when gs2_enabled and the
    # card is missing or declares a contract_version this code was not written
    # against — refusing the boot, deliberately, because the alternative is
    # attaching wrong class labels to real traffic with nothing in the output to
    # show for it. Not wrapped in try/except on purpose.
    app.state.gs2 = build_state()
    if app.state.gs2.ready:
        client = InferenceClient.get_instance()
        try:
            verify_service_contract(app.state.gs2, client.fetch_contract())
            client.contract_verified = True
        except ContractError:
            raise  # a service labelling with a different class list: refuse the boot
        except InferenceUnavailable as exc:
            # Not fatal: the service may still be loading. Scoring re-checks the
            # contract before its first submission and refuses until it matches.
            print(f"[ML-v2] Service not reachable at startup; contract check deferred: {exc}")
    app.state.monitor = None
    app.state.reconciler = None
    try:
        from app.mininet_monitor.monitor import MininetMonitor

        app.state.monitor = MininetMonitor(sio=sio, gs2_state=app.state.gs2)
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
    gs2 = app.state.gs2
    if gs2.enabled:
        contract = gs2.contract
        print(f"[ML-v2] Contract {contract.contract_version} [OK] classes={list(contract.classes)}")
        print(f"[ML-v2] Alerting: {'enabled' if gs2.can_alert else 'DISABLED (no fitted operating points)'}")
    else:
        print(f"[ML-v2] Disabled: {gs2.disabled_reason}")
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
app.add_middleware(RequestCorrelationMiddleware)

from app.api.v1 import alerts, analyze, audit, auth, blocked, blockchain, enforcement_actions, forensics, graph, healing, incidents, settings_route, stats, timeline  # noqa: E402

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(analyze.router, prefix="/api/v1", tags=["analyze"])
app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
app.include_router(stats.router, prefix="/api/v1", tags=["stats"])
app.include_router(timeline.router, prefix="/api/v1", tags=["timeline"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(blocked.router, prefix="/api/v1", tags=["blocked"])
app.include_router(healing.router, prefix="/api/v1", tags=["healing"])
app.include_router(incidents.router, prefix="/api/v1", tags=["incidents"])
app.include_router(forensics.router, prefix="/api/v1", tags=["forensics"])
app.include_router(blockchain.router, prefix="/api/v1", tags=["blockchain"])
app.include_router(settings_route.router, prefix="/api/v1", tags=["settings"])
app.include_router(enforcement_actions.router, prefix="/api/v1", tags=["enforcement-actions"])
app.include_router(audit.router, prefix="/api/v1", tags=["audit"])



@app.get("/health")
async def health():
    inference = InferenceService.get_instance()
    blockchain = BlockchainAdapter.get_instance()
    reconciler = getattr(app.state, "reconciler", None)
    monitor = getattr(app.state, "monitor", None)
    reconcile_health = reconciler.last_result if reconciler else {"status": "disabled"}
    monitor_health = monitor.health() if monitor else {"status": "disabled"}
    status = "ok" if inference.mode == "model" else "degraded"
    if reconcile_health.get("status") in {"error", "degraded"}:
        status = "degraded"

    gs2 = getattr(app.state, "gs2", None)
    ml_v2 = gs2.health() if gs2 is not None else {"enabled": False, "reason": "not initialised"}
    if gs2 is not None and gs2.enabled:
        # The inference service is a separate process; report whether it is
        # answering. Unreachable means NO SCORES, not "no threats" — the caller
        # must never read an unreachable service as a clean network.
        ml_v2["client"] = InferenceClient.get_instance().health()
        if not ml_v2["client"]["reachable"]:
            status = "degraded"

    return {
        "status": status,
        "service": "GraphSentinel",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ml": inference.health(),
        "ml_v2": ml_v2,
        "blockchain": blockchain.health(),
        "monitor": monitor_health,
        "reconciliation": reconcile_health,
    }


@sio.event
async def connect(sid, environ, auth=None):
    token = (auth or {}).get("token") if isinstance(auth, dict) else None
    api_key = environ.get("HTTP_X_API_KEY")
    key_ok = bool(api_key) and (
        (bool(settings.backend_api_token) and secrets.compare_digest(api_key, settings.backend_api_token))
        or (bool(settings.admin_api_token) and secrets.compare_digest(api_key, settings.admin_api_token))
    )
    if not (key_ok or auth_service.validate_session(token)):
        raise ConnectionRefusedError("Authentication required")
    await sio.emit("connected", {"sid": sid, "service": "GraphSentinel"}, to=sid)


@sio.event
async def disconnect(sid):
    """R-05 (M17-F01) — Clean disconnect handling for Socket.IO clients."""
    pass


socket_app = socketio.ASGIApp(sio, app)

