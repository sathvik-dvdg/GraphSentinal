"""
Artefact export and the versioned model contract.

The v1 coupling was ``from model import GraphSAGEClassifier`` in the backend.
That single import statement meant the backend's process had to contain the ML
code, share its Python and PyTorch versions, and break whenever the
architecture changed. It is the reason ``in_channels`` was frozen at 7.

The replacement is a *data* contract, not a code one. Export writes:

    weights.pt          state dict + the config that produced it
    model_card.json     the whole contract: feature names and order, class
                        names, input schema, version, training provenance
    edge_scaler.json    warm-start statistics for the live EMA scaler
    node_scaler.json
    model.ts            TorchScript, when the graph traces cleanly
    model.onnx          ONNX, when the scatter ops export cleanly

The backend reads ``model_card.json`` and speaks to the inference service over
HTTP. It never imports a model class and never hard-codes a feature count.

A caveat worth stating plainly rather than discovering in production: graph
networks with dynamic scatter/gather and variable node counts do not always
export cleanly to ONNX, and a partial export is worse than none. Both exporters
are therefore best-effort and report exactly what happened. The service
boundary is the contract that always holds; ONNX is an optimisation.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import torch

from .config import CLASS_NAMES, Config
from .data.graph_builder import (
    EDGE_FEATURE_NAMES,
    NODE_FEATURE_NAMES,
    VOLUMETRIC_EDGE_IDX,
)
from .data.ports import vocab_summary
from .inference.ema_scaler import EMAScaler
from .models.net import GraphSentinelNet


def _git_sha() -> Optional[str]:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_model_card(cfg: Config, model: GraphSentinelNet, metrics: Optional[dict] = None) -> dict:
    """Everything a consumer needs, in one machine-readable document."""
    return {
        "name": "GraphSentinel",
        "contract_version": cfg.export.contract_version,
        "created_at": time.time(),
        "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": _git_sha(),
        "framework": {
            "torch": torch.__version__,
            "python": platform.python_version(),
        },
        "graph": {
            "node_entity": "ip_address",
            "edge_entity": "network_flow",
            "directed": True,
            "reverse_edges_added": cfg.graph.add_reverse_edges,
            "window_seconds": cfg.graph.window_seconds,
            "window_stride_seconds": cfg.graph.window_stride_seconds,
        },
        "inputs": {
            "node_features": {
                "count": len(NODE_FEATURE_NAMES),
                "names": NODE_FEATURE_NAMES,
                "dtype": "float32",
                "shape": ["num_nodes", len(NODE_FEATURE_NAMES)],
            },
            "edge_features": {
                "count": len(EDGE_FEATURE_NAMES),
                "names": EDGE_FEATURE_NAMES,
                "dtype": "float32",
                "shape": ["num_edges", len(EDGE_FEATURE_NAMES)],
                "volumetric_indices": VOLUMETRIC_EDGE_IDX,
            },
            "categorical": {
                "edge_dst_port": {"dtype": "int64", "vocab": vocab_summary()["port_vocab_size"]},
                "edge_src_port": {"dtype": "int64", "vocab": vocab_summary()["port_vocab_size"]},
                "edge_proto": {"dtype": "int64", "vocab": vocab_summary()["proto_vocab_size"]},
            },
            "edge_index": {"dtype": "int64", "shape": [2, "num_edges"]},
            "node_ip_int": {"dtype": "int64", "shape": ["num_nodes"],
                            "note": "uint32 form of the IPv4 address; keys the memory store"},
        },
        "outputs": {
            "node_logits": {"shape": ["num_nodes", len(CLASS_NAMES)]},
            "edge_logits": {"shape": ["num_edges", len(CLASS_NAMES)]},
            "classes": CLASS_NAMES,
            "threat_score": "1 - softmax(logits)[BENIGN]",
            # Per-class additive offsets in LOG space, fitted on validation.
            # The backend MUST apply these before argmax or its class labels
            # will differ from the reported metrics:
            #     pred = argmax(log(softmax(edge_logits)) + edge_logit_bias)
            # All zeros (or absent) means plain argmax. Ranking, thresholds and
            # the threat score are unaffected -- an additive bias cannot
            # reorder a single class's own scores.
            "edge_logit_bias": None,
        },
        "port_vocabulary": vocab_summary(),
        # The mode describes what the engine CAN do, and "used" says what this
        # export actually shipped. train() and evaluate() never touch EMAScaler
        # -- the builder's own output is already self-normalising (log1p,
        # ratios clipped to [0,1], fixed divisors) -- so unless a caller passes
        # scalers to export_all, none are written and running with
        # edge_scaler=None is FAITHFUL to training, not a distribution
        # mismatch. Saying "load edge_scaler.json" unconditionally sent a
        # backend audit hunting for a file that was never meant to exist.
        "scaling": {
            "mode": "ema_streaming",
            "used_in_this_export": False,   # overwritten below when scalers ship
            "note": (
                "This export ships NO scaler files, and that is correct: the "
                "model was trained on raw graph-builder output, which is "
                "self-normalising. Run the engine with edge_scaler=None / "
                "node_scaler=None to match training. If edge_scaler.json and "
                "node_scaler.json ARE present, load them into "
                "graphsentinel.inference.ema_scaler.EMAScaler and call "
                "partial_fit() per window before transform(); never a frozen "
                "StandardScaler."
            ),
        },
        "memory": {
            "enabled": cfg.model.use_memory,
            "dim": cfg.model.memory_dim,
            "capacity_slots": cfg.model.memory_capacity,
            "ttl_seconds": cfg.model.memory_ttl_seconds,
            "footprint_bytes": (
                model.memory.occupancy()["bytes"] if model.memory is not None else 0
            ),
        },
        "parameters": model.parameter_count(),
        "config": cfg.to_dict(),
        # WHY THIS IS LABELLED. export_all is called with the metrics stored in
        # the best CHECKPOINT, and train() stores val_metrics there -- so these
        # are VALIDATION numbers at the selected epoch, not test numbers. They
        # share key names with test_report.json, which holds the test numbers,
        # so an unlabelled card invites quoting validation as the headline. A
        # backend integration audit on 2026-09-13 caught exactly that: the card
        # said edge_macro_f1 0.7568 while the test report said 0.7042.
        "metrics_split": "validation",
        "metrics_note": (
            "Metrics below are VALIDATION at the selected epoch. Test metrics "
            "live in test_report.json under the same key names -- do not mix "
            "them, and quote the split with every number."
        ),
        "metrics": metrics or {},
        "deprecations": {
            "in_channels_7": (
                "The 7-feature node contract is retired. Node features are now "
                f"{len(NODE_FEATURE_NAMES)} structural values and flow features moved "
                "to edges. graphsentinel.models.compat.GraphSAGEClassifier still "
                "loads v1 weights for a transition period."
            ),
            "scaler_pkl": "Replaced by the EMA scaler JSON files.",
        },
    }


def make_dummy_inputs(model: GraphSentinelNet, n_nodes: int = 8, n_edges: int = 24):
    from .data.graph_builder import NUM_EDGE_FEATURES, NUM_NODE_FEATURES

    g = torch.Generator().manual_seed(0)
    x = torch.randn(n_nodes, NUM_NODE_FEATURES, generator=g)
    edge_index = torch.randint(0, n_nodes, (2, n_edges), generator=g)
    edge_attr = torch.randn(n_edges, NUM_EDGE_FEATURES, generator=g)
    dst_port = torch.randint(0, 64, (n_edges,), generator=g)
    src_port = torch.randint(0, 64, (n_edges,), generator=g)
    proto = torch.randint(0, 6, (n_edges,), generator=g)
    mem = torch.zeros(n_nodes, model.memory_dim) if model.use_memory else None
    return x, edge_index, edge_attr, dst_port, src_port, proto, mem


class _ExportWrapper(torch.nn.Module):
    """Tuple-in / tuple-out wrapper. Tracers dislike dict outputs."""

    def __init__(self, model: GraphSentinelNet):
        super().__init__()
        self.model = model

    def forward(self, x, edge_index, edge_attr, dst_port, src_port, proto, memory_state):
        out = self.model(x, edge_index, edge_attr, dst_port, src_port, proto, memory_state)
        return out["node_logits"], out["edge_logits"]


#: Local mirror for the exported artefacts. Same reasoning as the checkpoint
#: mirror in train.py: /content is a real filesystem, the Drive mount is not.
_LOCAL_MODEL_DIR = Path("/content/gs_models")


def _mirror_dir() -> Optional[Path]:
    if not Path("/content").is_dir():
        return None
    try:
        _LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        return _LOCAL_MODEL_DIR
    except OSError:
        return None


def _fsync_path(p: Path) -> None:
    """Flush a just-written file to disk, portably.

    THE BUG THIS REPLACES, found by a backend integration audit on 2026-09-13
    running the suite on Windows:

        fd = os.open(tmp, os.O_RDONLY)
        os.fsync(fd)          # on Windows this RAISES OSError(9) on a
        os.close(fd)          # read-only descriptor, so close never runs
        except OSError: pass

    The leaked descriptor holds a Windows file lock on the .tmp, so the
    following os.replace() dies with PermissionError(WinError 32), the outer
    handler swallows that too, and export_all reports FAILED for every single
    artefact while leaving three orphan .tmp files behind. On Linux, fsync of
    an O_RDONLY descriptor succeeds, which is why every Colab run looked fine.

    Two fixes in one: open for WRITING (what fsync is actually for), and close
    in a finally so a raising fsync can never leak the handle. A platform that
    refuses the fsync still gets a correctly written file -- the data is
    already flushed by the writer; fsync only shortens the window in which a
    power loss could lose it.
    """
    fd = None
    try:
        # O_RDWR on every platform: fsync needs a writable descriptor, and
        # opening read-only is precisely what made Windows raise.
        fd = os.open(p, os.O_RDWR)
        os.fsync(fd)
    except OSError:
        pass
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _verified_write(path: Path, write: Callable[[Path], None],
                    read_back: Callable[[Path], None]) -> Optional[str]:
    """Write atomically, then PROVE the file can be read before claiming it.

    Run of 2026-09-13: this function's predecessor printed

        ok weights      /content/drive/.../models/weights.pt
        ok model_card   /content/drive/.../models/model_card.json

    and the verification cell, one cell later in the same kernel, reported

        MISSING  weights.pt
        MISSING  model_card.json

    A write that returns without raising is not evidence on that mount. So:
    write to a temp file, fsync, os.replace, then OPEN IT AGAIN. An artefact
    is only reported as exported once it has been read back. The local mirror
    gets the same treatment and is the copy that actually survives.

    Returns the path that verified, or None if no destination did.
    """
    landed: Optional[Path] = None
    mirror = _mirror_dir()
    reasons: list[str] = []
    for target in ([mirror / path.name] if mirror else []) + [path]:
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            write(tmp)
            _fsync_path(tmp)
            os.replace(tmp, target)
            read_back(target)         # the actual proof
            if landed is None or target == path:
                landed = target
        except Exception as exc:
            reasons.append(f"{target.parent}: {type(exc).__name__}: {exc}")
            # Never leave an orphan .tmp behind. On the run that found this,
            # export reported FAILED for every artefact and left weights.pt.tmp,
            # model_card.json.tmp and model.ts.tmp in the output directory,
            # which looks like a half-finished export rather than a failed one.
            try:
                tmp.unlink()
            except OSError:
                pass
            continue
    if landed is None and reasons:
        # Silently swallowing the cause is how this bug survived: the caller saw
        # "FAILED" with no reason and no way to tell a full disk from a locked
        # file. Carry the reasons out.
        _verified_write.last_errors = reasons     # type: ignore[attr-defined]
    return str(landed) if landed else None


def export_all(
    cfg: Config,
    model: GraphSentinelNet,
    out_dir: Optional[str | Path] = None,
    edge_scaler: Optional[EMAScaler] = None,
    node_scaler: Optional[EMAScaler] = None,
    metrics: Optional[dict] = None,
    logit_bias: Optional[list] = None,
    verbose: bool = True,
) -> dict:
    out_dir = Path(out_dir) if out_dir else cfg.model_path
    out_dir.mkdir(parents=True, exist_ok=True)
    model = model.eval().cpu()
    status = {"weights": None, "model_card": None, "torchscript": None, "onnx": None}

    # --- weights ---------------------------------------------------------
    wpath = out_dir / "weights.pt"
    _blob = {"model": model.state_dict(), "config": cfg.to_dict()}
    status["weights"] = _verified_write(
        wpath,
        lambda p: torch.save(_blob, p),
        lambda p: torch.load(p, map_location="cpu", weights_only=False)["model"],
    ) or "FAILED: could not write a readable weights.pt to local disk or to " + str(out_dir)

    # --- scalers ---------------------------------------------------------
    _shipped_scalers = False
    if edge_scaler is not None:
        edge_scaler.save(out_dir / "edge_scaler.json")
        _shipped_scalers = True
    if node_scaler is not None:
        node_scaler.save(out_dir / "node_scaler.json")
        _shipped_scalers = True

    # --- torchscript -----------------------------------------------------
    wrapper = _ExportWrapper(model)
    dummy = make_dummy_inputs(model)
    if cfg.export.export_torchscript:
        try:
            with torch.no_grad():
                traced = torch.jit.trace(wrapper, dummy, strict=False, check_trace=False)
            tpath = out_dir / "model.ts"
            status["torchscript"] = _verified_write(
                tpath,
                lambda p: traced.save(str(p)),
                lambda p: torch.jit.load(str(p), map_location="cpu"),
            ) or "FAILED: model.ts would not read back after writing"
        except Exception as exc:  # pragma: no cover - environment dependent
            status["torchscript"] = f"FAILED: {type(exc).__name__}: {exc}"

    # --- onnx ------------------------------------------------------------
    if cfg.export.export_onnx:
        try:
            opath = out_dir / "model.onnx"
            torch.onnx.export(
                wrapper,
                dummy,
                str(opath),
                input_names=[
                    "x", "edge_index", "edge_attr",
                    "edge_dst_port", "edge_src_port", "edge_proto", "memory_state",
                ],
                output_names=["node_logits", "edge_logits"],
                dynamic_axes={
                    "x": {0: "num_nodes"},
                    "edge_index": {1: "num_edges"},
                    "edge_attr": {0: "num_edges"},
                    "edge_dst_port": {0: "num_edges"},
                    "edge_src_port": {0: "num_edges"},
                    "edge_proto": {0: "num_edges"},
                    "memory_state": {0: "num_nodes"},
                    "node_logits": {0: "num_nodes"},
                    "edge_logits": {0: "num_edges"},
                },
                opset_version=cfg.export.onnx_opset,
                do_constant_folding=True,
            )
            status["onnx"] = str(opath)
        except ModuleNotFoundError as exc:  # pragma: no cover
            status["onnx"] = (
                f"SKIPPED: {exc.name} not installed "
                "(pip install onnx onnxscript onnxruntime)"
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            status["onnx"] = f"FAILED: {type(exc).__name__}: {exc}"

    # --- model card (last: records artefact hashes) -----------------------
    card = build_model_card(cfg, model, metrics)
    card["scaling"]["used_in_this_export"] = _shipped_scalers
    if logit_bias is not None:
        card["outputs"]["edge_logit_bias"] = list(logit_bias)
    card["artifacts"] = {
        k: ({"path": Path(v).name, "sha256": _sha256(Path(v))}
            if v and not str(v).startswith(("FAILED", "SKIPPED")) and Path(v).exists()
            else v)
        for k, v in status.items()
        if v
    }
    cpath = out_dir / "model_card.json"
    _card_text = json.dumps(card, indent=2, default=float)
    status["model_card"] = _verified_write(
        cpath,
        lambda p: p.write_text(_card_text, encoding="utf-8"),
        lambda p: json.loads(p.read_text(encoding="utf-8"))["outputs"]["classes"],
    ) or "FAILED: could not write a readable model_card.json"

    if verbose:
        print("EXPORT")
        for k, v in status.items():
            if str(v).startswith("FAILED"):
                mark = "!! "
            elif str(v).startswith("SKIPPED"):
                mark = "-- "
            else:
                mark = "ok "
            print(f"  {mark}{k:<12s} {v}")
        onnx_status = str(status.get("onnx", ""))
        if onnx_status.startswith("FAILED"):
            print(
                "\n  ONNX export failed. This happens with graph networks whose\n"
                "  scatter/gather shapes are dynamic. The HTTP inference service is\n"
                "  the supported decoupling path and does not depend on ONNX."
            )
        elif onnx_status.startswith("SKIPPED"):
            print("\n  ONNX skipped: pip install onnx onnxscript onnxruntime")
    return status


def verify_export(out_dir: str | Path, model: GraphSentinelNet, tol: float = 1e-4) -> dict:
    """Confirm exported artefacts reproduce the eager model's outputs."""
    out_dir = Path(out_dir)
    dummy = make_dummy_inputs(model)
    wrapper = _ExportWrapper(model.eval())
    with torch.no_grad():
        ref_node, ref_edge = wrapper(*dummy)

    results = {}
    ts = out_dir / "model.ts"
    if ts.exists():
        try:
            loaded = torch.jit.load(str(ts))
            with torch.no_grad():
                n, e = loaded(*dummy)
            results["torchscript"] = {
                "node_max_abs_diff": float((n - ref_node).abs().max()),
                "edge_max_abs_diff": float((e - ref_edge).abs().max()),
                "pass": bool((n - ref_node).abs().max() < tol),
            }
        except Exception as exc:
            results["torchscript"] = {"pass": False, "error": str(exc)}

    onnx_path = out_dir / "model.onnx"
    if onnx_path.exists():
        try:
            import onnxruntime as ort

            sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            names = [i.name for i in sess.get_inputs()]
            feed = {n: v.numpy() for n, v in zip(names, dummy) if v is not None}
            n, e = sess.run(None, feed)
            results["onnx"] = {
                "node_max_abs_diff": float(np.abs(n - ref_node.numpy()).max()),
                "pass": bool(np.abs(n - ref_node.numpy()).max() < 1e-3),
            }
        except Exception as exc:
            results["onnx"] = {"pass": False, "error": str(exc)}

    return results
