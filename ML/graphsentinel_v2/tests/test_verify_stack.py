"""ML/verify_stack.py is run in front of people when something is already broken.

So it must report, never raise, for every way a service can fail to answer, and
it must not pass a check about a model that is not loaded.
"""
from __future__ import annotations

import importlib.util
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture()
def vs():
    spec = importlib.util.spec_from_file_location("verify_stack", REPO / "ML" / "verify_stack.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def serve():
    """serve(respond) -> base URL of a local server answering GETs with respond(request)."""
    servers = []

    def start(respond):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                respond(self)

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_port}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


def _body(request, body: bytes, status: int = 200):
    request.send_response(status)
    request.send_header("Content-Type", "application/json")
    request.send_header("Content-Length", str(len(body)))
    request.end_headers()
    request.wfile.write(body)


def test_connection_refused_is_reported_not_raised(vs):
    # a port nothing listens on: bind one, read its number, close it
    closed = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    refused = closed.server_port
    closed.server_close()
    status, body = vs.get(f"http://127.0.0.1:{refused}/health")
    assert status is None and body["detail"].startswith("no answer")


def test_a_hung_service_times_out_and_is_reported(vs, serve, monkeypatch):
    monkeypatch.setattr(vs, "TIMEOUT", 0.3)
    url = serve(lambda r: time.sleep(1.5))
    started = time.monotonic()
    status, body = vs.get(f"{url}/health")
    assert time.monotonic() - started < 1.4
    assert status is None and body["detail"].startswith("no answer")


@pytest.mark.parametrize("payload", [b"<html>502 Bad Gateway</html>", b"", b"[1, 2]"])
def test_a_body_that_is_not_a_json_object_is_reported(vs, serve, payload):
    url = serve(lambda r: _body(r, payload))
    status, body = vs.get(f"{url}/health")
    assert status == 200 and "detail" in body and "model_dir" not in body


CLASSES = ["BENIGN", "Volumetric_Flood", "PortScan", "BruteForce", "Botnet"]
BACKEND = {"ml_v2": {"contract": {"classes": CLASSES},
                     "policy": {"floors": {"PortScan": 0.85}, "dry_run": True}}}


def _card(vs) -> dict:
    """The card as served. The parameter count is read from the manifest's
    neighbour rather than restated here."""
    import json
    card = json.loads((REPO / "ML" / "model_card.json").read_text(encoding="utf-8"))
    return {"contract_version": "2.0.0", "parameters": card["parameters"],
            "outputs": {"classes": CLASSES}}


def _run(vs, monkeypatch, answers) -> dict:
    monkeypatch.setattr(vs, "get", lambda url: next(v for k, v in answers.items() if url.endswith(k)))
    vs.main(["--skip-sample"])
    return {name.split()[0]: ok for name, ok, _ in vs.results}


def test_checks_5_and_6_are_unverifiable_with_no_model_loaded(vs, monkeypatch):
    """Without ML/weights.pt the service answers /health 503 and still serves the
    card. The card's parameter count and class order are then facts about a
    model that is not in memory, and used to be reported as PASS."""
    got = _run(vs, monkeypatch, {
        ":8081/health": (503, {"detail": "model not loaded"}),
        "/contract": (200, _card(vs)),
        ":8001/health": (200, BACKEND),
    })
    assert got["1"] is False
    assert got["5"] is None and got["6"] is None
    assert got["2"] is True and got["7"] is True


def test_checks_5_and_6_pass_with_the_model_loaded(vs, monkeypatch):
    got = _run(vs, monkeypatch, {
        ":8081/health": (200, {"model_dir": "/app/ML", "memory": {}}),
        "/contract": (200, _card(vs)),
        ":8001/health": (200, BACKEND),
    })
    assert got["1"] is True and got["5"] is True and got["6"] is True


def test_nothing_answering_exits_nonzero_without_a_traceback(vs, monkeypatch, capsys):
    monkeypatch.setattr(vs, "get", lambda url: (None, {"detail": "no answer: refused"}))
    assert vs.main(["--skip-sample"]) == 1
    out = capsys.readouterr().out
    assert "UNVERIFIABLE" in out and "0 of 8 checks passed" in out
