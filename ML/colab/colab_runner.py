"""
The retrain under the fixed timestamp parse, as two Colab cells.

    CELL A   cell_a()   the timestamp audit. Writes a machine-readable verdict.
    CELL B   cell_b()   everything else. Refuses unless the verdict is clean.

WHY IT IS SHAPED LIKE THIS. The steps after the audit need Colab only because
the data and the GPU are there, not because a person has to decide anything
mid-run. So the decisions are in code: Cell B reads Cell A's verdict, the
Phase 2b gate decides whether 2b runs, and nothing asks a question.

RESUMABLE. A long Colab run disconnects. Each stage writes a marker to Drive
when it finishes, and a stage whose marker and outputs are both present is
skipped. Re-running Cell B continues; it does not restart. Granularity is the
stage: an interrupted training stage restarts from the last epoch only while the
runtime is alive (the per-epoch checkpoint is on local disk, by design -- see
train.py), and from epoch 1 after a runtime recycle. Training is ~25 minutes.

NOTHING HERE TOUCHES THE OLD RUN. Checkpoints, logs and models go under
<project>/retrain_fix12h/ on Drive. The pre-fix artefacts are left alone.

Stages, in order:
    1 audit_gate       refuse unless Cell A's verdict says clean
    2 graphs           rebuild splits and graphs (new cache name, by itself)
    3 train_export     retrain, select on val edge macro-F1, export
    4 threshold_study  section 11.1 -> threshold_study.json + two CSVs
    5 probes           section 12 probes on the test split -> probes.json
    6 sample           regenerate the test sample, if the generator is bundled
    7 phase2b          sensitivity control, then 2b; the gate decides
    8 package          one zip, every artefact at its repo-relative path
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent              # <bundle>/ML/colab
BUNDLE = HERE.parents[1]                            # <bundle>
ML = BUNDLE / "ML"
for _p in (str(ML / "graphsentinel_v2"), str(ML)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RUN_NAME = "retrain_fix12h"
RESULT_ZIP = "graphsentinel_retrain_result.zip"
SESSION = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:6]
STAGES = ("audit_gate", "graphs", "train_export", "threshold_study", "probes",
          "sample", "phase2b", "package")
BAR = "=" * 78

#: The pre-fix probe figures the new ones are read against (test split,
#: epoch-31 checkpoint of 2026-09-13). See ML/TIMESTAMP_FIX.md.
PRE_FIX = {"full": 0.7042, "no_edge_feat": 0.7998, "memory_off": 0.8312}


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj) -> None:
    """Write, then READ BACK. On the Drive mount a write that returns is not
    evidence the file landed (train.py and export.py have the history)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, default=float)
    for attempt in range(3):
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
        try:
            if json.loads(path.read_text(encoding="utf-8")) is not None:
                return
        except Exception:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"could not write a readable {path}")


def copy_verified(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        return
    for attempt in range(3):
        shutil.copyfile(src, dst)
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            return
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"could not copy {src} to {dst}")


def ensure_file(dst: Path, *fallbacks: Path) -> Path:
    """``dst`` must exist and be non-empty; if not, take it from a fallback
    (the local mirror) and verify."""
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    for f in fallbacks:
        if f and f.exists() and f.stat().st_size > 0:
            copy_verified(f, dst)
            return dst
    raise RuntimeError(f"missing output {dst} (also looked in {[str(f) for f in fallbacks]})")


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            st.write(s)
        return len(s)

    def flush(self):
        for st in self.streams:
            st.flush()


@contextlib.contextmanager
def tee_stdout(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        with contextlib.redirect_stdout(_Tee(sys.stdout, fh)):
            yield


# --------------------------------------------------------------------------
# environment
# --------------------------------------------------------------------------
class Env:
    """Where things are. On Colab: Drive project folder + /content."""

    def __init__(self, base: Path, local: Path, is_colab: bool,
                 overrides: dict | None = None, allow_cpu: bool = False):
        self.base = Path(base)
        self.local = Path(local)
        self.is_colab = is_colab
        self.overrides = dict(overrides or {})
        self.allow_cpu = allow_cpu
        self.run_dir = self.base / RUN_NAME
        self.state = self.run_dir / "state"
        self.logs = self.run_dir / "logs"
        self.models = self.run_dir / "models"
        self.ckpt = self.run_dir / "checkpoints"
        self.local_logs = self.local / "gs_logs_fix12h"
        self.stage_tree = self.local / "gs_stage"
        self.dataset = self.base / "datasets" / "cicids2017"


def find_base(root: Path = Path("/content/drive/MyDrive")) -> Path:
    """The Drive folder that holds datasets/cicids2017 with all five training files."""
    import timestamp_audit as ta
    hits = []
    for depth in range(0, 5):
        hits += list(root.glob("/".join(["*"] * depth + ["datasets", "cicids2017"])))
    full = [h for h in hits if all((h / f).exists() for f in ta.TRAINING_FILES)]
    if not full:
        raise SystemExit(
            f"No datasets/cicids2017 folder with the five training CSVs under {root}.\n"
            f"Looked at: {[str(h) for h in hits] or 'nothing matched'}")
    return full[0].parents[1]


def colab_env(**kw) -> Env:
    try:
        from google.colab import drive  # type: ignore
        drive.mount("/content/drive", force_remount=False)
    except ImportError:
        raise SystemExit("Not on Colab. Use Env(base, local, is_colab=False) to run elsewhere.")
    return Env(find_base(), Path("/content"), is_colab=True, **kw)


def ensure_deps() -> None:
    missing = []
    for mod, pip_name in (("torch_geometric", "torch-geometric"), ("pyarrow", "pyarrow")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pip_name)
    if missing:
        print(f"installing {missing} ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", *missing], check=True)


def make_cfg(env: Env):
    """The config the epoch-31 model was trained with, plus the clock fix.

    Built from the model card in the bundle, so the retrain differs from the
    shipped run in the timestamp parse and in nothing else.
    """
    from graphsentinel.config import Config

    card = json.loads((ML / "model_card.json").read_text(encoding="utf-8"))
    cfg = Config.from_dict(card["config"])
    cfg.base_dir = str(env.base)
    cfg.data.fix_12h_clock = True
    cfg.data.pm_hours = [1, 7]
    cfg.data.processed_dir = str(env.local / "gs_processed_fix12h")
    cfg.checkpoint_dir = f"{RUN_NAME}/checkpoints"
    cfg.log_dir = f"{RUN_NAME}/logs"
    cfg.export.model_dir = f"{RUN_NAME}/models"
    cfg.export.export_onnx = False
    for dotted, value in env.overrides.items():          # tests only
        section, key = dotted.split(".")
        setattr(getattr(cfg, section), key, value)
    cfg.sync_taxonomy()
    cfg.ensure_dirs()
    return cfg


# --------------------------------------------------------------------------
# stage markers
# --------------------------------------------------------------------------
def _marker(env: Env, stage: str) -> Path:
    return env.state / f"{STAGES.index(stage) + 1}_{stage}.json"


def read_marker(env: Env, stage: str) -> dict | None:
    try:
        return json.loads(_marker(env, stage).read_text(encoding="utf-8"))
    except Exception:
        return None


def is_done(env: Env, stage: str) -> bool:
    """Done = the marker is readable AND every output it names is still there."""
    m = read_marker(env, stage)
    if not m:
        return False
    for rec in m.get("outputs", {}).values():
        p = Path(rec["path"])
        if not p.exists() or p.stat().st_size != rec["bytes"]:
            return False
    return True


def mark(env: Env, stage: str, outputs: dict | None = None, **extra) -> None:
    rec = {
        "stage": stage, "session": SESSION, "finished_at_utc": _now(),
        "outputs": {name: {"path": str(p), "bytes": Path(p).stat().st_size}
                    for name, p in (outputs or {}).items()},
        **extra,
    }
    write_json(_marker(env, stage), rec)


def print_plan(env: Env, always: tuple = ("audit_gate", "package")) -> None:
    print(BAR)
    print(f"  RETRAIN UNDER THE FIXED PARSE   session {SESSION}")
    print(f"  project : {env.base}")
    print(f"  run dir : {env.run_dir}")
    print(BAR)
    for s in STAGES:
        m = read_marker(env, s)
        if s in always:
            state = "runs every time"
        elif is_done(env, s):
            state = f"DONE in session {m['session']} at {m['finished_at_utc']} -- will be skipped"
            if m.get("skipped"):
                state = f"SKIPPED earlier ({m['skipped']}) -- will be re-checked"
        else:
            state = "to do"
        print(f"  {STAGES.index(s) + 1} {s:<16s} {state}")
    print(BAR)


# --------------------------------------------------------------------------
# CELL A
# --------------------------------------------------------------------------
def cell_a(env: Env | None = None) -> dict:
    """Audit every CSV in the dataset folder; write the verdict Cell B reads."""
    env = env or colab_env()
    import timestamp_audit as ta

    cfg = make_cfg(env)
    out_dirs = [env.local_logs, env.logs]
    ta.run([env.dataset], out_dirs=out_dirs, pm_hours=tuple(cfg.data.pm_hours))
    v = json.loads((env.local_logs / ta.VERDICT_NAME).read_text(encoding="utf-8"))
    ensure_file(env.logs / ta.VERDICT_NAME, env.local_logs / ta.VERDICT_NAME)
    ensure_file(env.logs / "timestamp_audit.json", env.local_logs / "timestamp_audit.json")
    print("\nNEXT: " + ("run Cell B." if v["clean"] else
                        "do NOT run Cell B -- it will refuse. Send timestamp_audit.json back."))
    return v


# --------------------------------------------------------------------------
# CELL B stages
# --------------------------------------------------------------------------
def stage_audit_gate(env: Env, cfg) -> dict:
    import timestamp_audit as ta
    v = None
    for d in (env.logs, env.local_logs):
        try:
            v = json.loads((d / ta.VERDICT_NAME).read_text(encoding="utf-8"))
            break
        except Exception:
            continue
    if v is None:
        raise SystemExit("AUDIT GATE: no verdict found. Run Cell A first.")
    if not v.get("clean"):
        raise SystemExit(f"AUDIT GATE: the audit verdict is NOT clean.\n  {v.get('reason')}\n"
                         "The retrain does not start. Send timestamp_audit.json back.")
    if list(v.get("pm_hours", [])) != [int(x) for x in cfg.data.pm_hours]:
        raise SystemExit(f"AUDIT GATE: the audit used pm_hours {v.get('pm_hours')}, "
                         f"the retrain would use {list(cfg.data.pm_hours)}. Re-run Cell A.")
    print(f"audit gate: clean -- {v['reason']}")
    mark(env, "audit_gate", verdict=v)
    return v


def stage_graphs(env: Env, cfg) -> None:
    from graphsentinel.data.preprocess import clock_tag
    from graphsentinel.train import prepare_graphs

    graphs = prepare_graphs(cfg, force=False, verbose=True)
    mark(env, "graphs",
         cache_tag=clock_tag(cfg),
         n_graphs={k: len(v) for k, v in graphs.items()})


def _quarantine_stale_mirror(cfg) -> None:
    """A pre-fix last.pt in the local mirror would be picked up by resume and
    refused by the resume guard. Move it aside instead of failing on it."""
    import torch
    from graphsentinel.utils import scratch

    mirror = scratch.LOCAL_ROOT / "gs_ckpt"
    if not mirror.is_dir():
        return
    for name in ("last.pt", "best.pt"):
        f = mirror / name
        if not f.exists():
            continue
        try:
            data = torch.load(f, map_location="cpu", weights_only=False).get("config", {}).get("data", {})
            same = (data.get("fix_12h_clock") is True
                    and list(data.get("pm_hours", [])) == list(cfg.data.pm_hours)
                    and data.get("taxonomy") == cfg.data.taxonomy)
        except Exception:
            same = False
        if not same:
            aside = f.with_name(f"{name}.prefix-{SESSION}")
            f.rename(aside)
            print(f"  moved a stale {name} aside -> {aside.name}")


def stage_train_export(env: Env, cfg) -> None:
    import torch
    from graphsentinel.export import export_all
    from graphsentinel.models.net import build_model
    from graphsentinel.train import train
    from graphsentinel.utils import scratch

    if env.is_colab and not torch.cuda.is_available() and not env.allow_cpu:
        raise SystemExit("No GPU attached. Runtime > Change runtime type > T4 GPU, then "
                         "re-run Cell B. (On CPU this stage takes hours.)")
    _quarantine_stale_mirror(cfg)
    t0 = time.time()
    with tee_stdout(env.local_logs / "train_output.txt"):
        report = train(cfg, resume=True, force_rebuild=False, verbose=True)
        model = build_model(cfg)
        model.load_state_dict(report["best_state"]["model"])
        status = export_all(cfg, model, metrics=report["best_state"]["metrics"], verbose=True)
    for k in ("weights", "model_card", "torchscript"):
        if not status.get(k) or str(status[k]).startswith("FAILED"):
            raise RuntimeError(f"export of {k} failed: {status.get(k)}")

    m = scratch.LOCAL_ROOT
    out = {
        "weights.pt": ensure_file(env.models / "weights.pt", m / "gs_models" / "weights.pt"),
        "model.ts": ensure_file(env.models / "model.ts", m / "gs_models" / "model.ts"),
        "model_card.json": ensure_file(env.models / "model_card.json", m / "gs_models" / "model_card.json"),
        "test_report.json": ensure_file(env.logs / "test_report.json", m / "gs_logs" / "test_report.json"),
        "training_log.csv": ensure_file(env.logs / "training_log.csv", m / "gs_logs" / "training_log.csv"),
        "best.pt": ensure_file(env.ckpt / "best.pt", m / "gs_ckpt" / "best.pt"),
        "train_output.txt": ensure_file(env.logs / "train_output.txt", env.local_logs / "train_output.txt"),
    }
    mark(env, "train_export", out,
         best_epoch=report["best_epoch"], best_val_metric=report["best_val_metric"],
         epochs_run=len(report["history"]), seconds=round(time.time() - t0, 1),
         weights_sha256=sha256(out["weights.pt"]),
         test_edge_macro_f1=report["metrics"].get("edge_macro_f1"))


def run_cell(env: Env, name: str, ns: dict, log_name: str) -> dict:
    """Execute a lifted notebook cell with the globals it expects."""
    src = (HERE / "cells" / name).read_text(encoding="utf-8")
    with tee_stdout(env.local_logs / log_name):
        try:
            exec(compile(src, name, "exec"), ns)
        except SystemExit as exc:
            raise RuntimeError(f"{name} stopped: {exc}") from exc
    ensure_file(env.logs / log_name, env.local_logs / log_name)
    return ns


def stage_threshold_study(env: Env, cfg) -> None:
    run_cell(env, "threshold_study.py", {"cfg": cfg, "GS_OUT": str(env.local_logs)},
             "threshold_study_output.txt")
    names = ("threshold_study.json", "threshold_flow_level.csv", "threshold_window_level.csv")
    out = {n: ensure_file(env.logs / n, env.local_logs / n) for n in names}
    study = json.loads(out["threshold_study.json"].read_text(encoding="utf-8"))
    for key in ("binary_gate", "alert_min_flows", "alert_window_seconds"):
        if key not in study:
            raise RuntimeError(f"threshold_study.json has no {key!r}: the backend would "
                               "load it as unverified")
    out["threshold_study_output.txt"] = env.logs / "threshold_study_output.txt"
    mark(env, "threshold_study", out, binary_gate=study["binary_gate"],
         alert_min_flows=study["alert_min_flows"])


def _floats(d: dict) -> dict:
    return {k: float(v) for k, v in d.items()
            if isinstance(v, (int, float)) or hasattr(v, "item")}


def stage_probes(env: Env, cfg) -> None:
    a = run_cell(env, "probes_information.py", {"cfg": cfg}, "probes_information_output.txt")
    b = run_cell(env, "probes_confirm.py", {"cfg": cfg}, "probes_confirm_output.txt")

    summary = {s: {k: float(v) for k, v in d.items()} for s, d in b["summary"].items()}
    mem = {s: _floats(m) for s, m in b["memory_off"].items()}

    def delta(split, key):
        return summary[split][key] - summary[split]["full"]

    table = {
        "what": "edge macro-F1, post-fix model; deltas are against that split's full model",
        "test": {
            "full": summary["test"]["full"],
            "no_edge_feat": summary["test"]["no_edge_feat"],
            "F6_delta_no_edge_feat": delta("test", "no_edge_feat"),
            "memory_off": mem["test"]["edge_macro_f1"],
            "F2_delta_memory_off": mem["test"]["edge_macro_f1"] - summary["test"]["full"],
        },
        "val": {
            "full": summary["val"]["full"],
            "no_edge_feat": summary["val"]["no_edge_feat"],
            "F6_delta_no_edge_feat": delta("val", "no_edge_feat"),
            "memory_off": mem["val"]["edge_macro_f1"],
            "F2_delta_memory_off": mem["val"]["edge_macro_f1"] - summary["val"]["full"],
        },
        "pre_fix_test_reference": {
            **PRE_FIX,
            "F6_delta_no_edge_feat": PRE_FIX["no_edge_feat"] - PRE_FIX["full"],
            "F2_delta_memory_off": PRE_FIX["memory_off"] - PRE_FIX["full"],
        },
    }
    probes = {
        "F2_F6": table,
        "information_sources_test": {name: _floats(m) for name, m in a["rows"].items()},
        "confirm": summary,
        "memory_off": mem,
        "leave_one_out_test": [
            {"feature": n, "index": int(i), "delta_macro_f1": float(d),
             "bruteforce_f1": float(bf), "portscan_f1": float(ps)}
            for n, i, d, bf, ps in b["loo"]],
    }
    write_json(env.logs / "probes.json", probes)
    print(f"\n{BAR}\n  F2 / F6 AFTER THE FIX   (test split, edge macro-F1)\n{BAR}")
    t, p = table["test"], table["pre_fix_test_reference"]
    print(f"  {'':<28s}{'post-fix':>10s}{'pre-fix':>10s}")
    print(f"  {'full model':<28s}{t['full']:>10.4f}{p['full']:>10.4f}")
    print(f"  {'F6: edge features zeroed':<28s}{t['F6_delta_no_edge_feat']:>+10.4f}{p['F6_delta_no_edge_feat']:>+10.4f}")
    print(f"  {'F2: memory off':<28s}{t['F2_delta_memory_off']:>+10.4f}{p['F2_delta_memory_off']:>+10.4f}")
    mark(env, "probes", {
        "probes.json": env.logs / "probes.json",
        "probes_information_output.txt": env.logs / "probes_information_output.txt",
        "probes_confirm_output.txt": env.logs / "probes_confirm_output.txt"},
        F6_delta_test=t["F6_delta_no_edge_feat"], F2_delta_test=t["F2_delta_memory_off"])


def build_stage_tree(env: Env) -> Path:
    """A repo-shaped tree on local disk: the bundled scripts plus the NEW
    artefacts, so phase2b can run exactly as it does in the repository."""
    root = env.stage_tree
    (root / "ML" / "testdata").mkdir(parents=True, exist_ok=True)
    for rel in ("graphsentinel_v2", ):
        dst = root / "ML" / rel
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ML / rel, dst, ignore=shutil.ignore_patterns("__pycache__"))
    for f in ML.glob("*.py"):
        shutil.copyfile(f, root / "ML" / f.name)
    for name, src in (("weights.pt", env.models / "weights.pt"),
                      ("model.ts", env.models / "model.ts"),
                      ("model_card.json", env.models / "model_card.json"),
                      ("test_report.json", env.logs / "test_report.json")):
        copy_verified(src, root / "ML" / name)
    return root


def stage_sample(env: Env, cfg) -> None:
    gen = ML / "make_testdata_sample.py"
    if not gen.exists():
        reason = ("make_testdata_sample.py is not in the bundle. It has never been "
                  "committed; commit it to ML/ and rebuild the bundle.")
        print(f"sample: SKIPPED -- {reason}")
        mark(env, "sample", skipped=reason)
        return
    root = build_stage_tree(env)
    sample = root / "ML" / "testdata" / "cicids2017_sample.csv"
    before = sha256(sample) if sample.exists() else None
    e = dict(os.environ, GS_DATASET_DIR=str(env.dataset), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "ML/make_testdata_sample.py"], cwd=root, env=e,
                       capture_output=True, text=True)
    (env.local_logs / "sample_output.txt").write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    print(r.stdout[-3000:])
    if r.returncode or not sample.exists() or sha256(sample) == before:
        raise RuntimeError(
            "make_testdata_sample.py did not produce a new ML/testdata/cicids2017_sample.csv "
            f"(exit {r.returncode}). The runner calls it with no arguments, from the repo "
            "root, with GS_DATASET_DIR set; adjust the call in stage_sample to its interface.\n"
            + r.stderr[-2000:])
    dst = ensure_file(env.run_dir / "testdata" / "cicids2017_sample.csv", sample)
    copy_verified(sample, dst)
    mark(env, "sample", {"cicids2017_sample.csv": dst}, sample_sha256=sha256(dst))


def stage_phase2b(env: Env, cfg) -> None:
    s = read_marker(env, "sample") or {}
    if s.get("skipped") or not s:
        reason = "the sample was not regenerated, and the control must run on the NEW sample"
        print(f"phase2b: SKIPPED -- {reason}")
        mark(env, "phase2b", skipped=reason)
        return
    root = build_stage_tree(env)
    copy_verified(env.run_dir / "testdata" / "cicids2017_sample.csv",
                  root / "ML" / "testdata" / "cicids2017_sample.csv")
    e = dict(os.environ, PYTHONIOENCODING="utf-8")
    out, record = {}, {}
    for script, result in (("phase2b_sensitivity_check.py", "phase2b_sensitivity.json"),
                           ("phase2b_live_path_cost.py", "phase2b_results.json")):
        r = subprocess.run([sys.executable, f"ML/{script}"], cwd=root, env=e,
                           capture_output=True, text=True)
        log = env.logs / (script[:-3] + "_output.txt")
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
        print(r.stdout[-2500:])
        record[script] = {"exit_code": r.returncode}
        produced = root / "ML" / result
        if produced.exists():
            out[result] = ensure_file(env.logs / result, produced)
            copy_verified(produced, out[result])
        if script == "phase2b_sensitivity_check.py":
            if r.returncode:
                raise RuntimeError("the sensitivity control failed:\n" + r.stderr[-2000:])
            moved = json.loads(produced.read_text(encoding="utf-8"))["all_zero_edge_features"]["argmax_changed"]
            record["control_argmax_changed"] = moved
        elif r.returncode:
            # The gate refusing is a RESULT, not an error: it means the control
            # did not move and 2b would be uninformative on this sample.
            record["gate"] = (r.stdout + r.stderr).strip().splitlines()[-12:]
            print("phase2b: the gate refused the live-path run (recorded; not an error).")
    mark(env, "phase2b", out, **record)


def _stage_records(env: Env) -> dict:
    return {s: read_marker(env, s) for s in STAGES if read_marker(env, s)}


def stage_package(env: Env, cfg) -> Path:
    from graphsentinel.config import CLASS_NAMES
    from graphsentinel.data.preprocess import preprocessing_digest, preprocessing_settings

    L, M, R = env.logs, env.models, env.run_dir
    artefacts = {                                   # repo-relative path -> source
        "ML/weights.pt": M / "weights.pt",
        "ML/model.ts": M / "model.ts",
        "ML/model_card.json": M / "model_card.json",
        "ML/test_report.json": L / "test_report.json",
        "ML/threshold_study.json": L / "threshold_study.json",
        "ML/threshold_flow_level.csv": L / "threshold_flow_level.csv",
        "ML/threshold_window_level.csv": L / "threshold_window_level.csv",
        "ML/probes.json": L / "probes.json",
        "ML/timestamp_audit.json": L / "timestamp_audit.json",
        "ML/phase2b_sensitivity.json": L / "phase2b_sensitivity.json",
        "ML/phase2b_results.json": L / "phase2b_results.json",
        "ML/testdata/cicids2017_sample.csv": R / "testdata" / "cicids2017_sample.csv",
    }
    for f in sorted(L.glob("*_output.txt")) + [L / "training_log.csv"]:
        artefacts[f"ML/retrain_logs/{f.name}"] = f
    required = ("ML/weights.pt", "ML/model.ts", "ML/model_card.json", "ML/test_report.json",
                "ML/threshold_study.json", "ML/probes.json", "ML/timestamp_audit.json")
    missing = [k for k in required if not artefacts[k].exists()]
    if missing:
        raise RuntimeError(f"cannot package: missing {missing}")
    artefacts = {k: v for k, v in artefacts.items() if v.exists()}

    report = json.loads(artefacts["ML/test_report.json"].read_text(encoding="utf-8"))
    card = json.loads(artefacts["ML/model_card.json"].read_text(encoding="utf-8"))
    metrics = report["metrics"]
    digests = {k: sha256(v) for k, v in artefacts.items()}
    pp = preprocessing_digest(cfg)

    manifest = {
        "bundle": "deploy",
        "created_utc": _now(),
        "files": [{"file": Path(k).name, "bytes": artefacts[k].stat().st_size,
                   "sha256": digests[k], "source": str(artefacts[k].parent),
                   "from": f"colab_runner session {SESSION}"}
                  for k in ("ML/model_card.json", "ML/weights.pt", "ML/model.ts",
                            "ML/test_report.json")],
        "classes": list(card["outputs"]["classes"]),
        "contract_version": card["contract_version"],
        "headline": {k: metrics[k] for k in (
            "edge_macro_f1", "edge_binary_f1", "edge_binary_pr_auc",
            "edge_recall_at_fpr_0.001", "node_macro_f1") if k in metrics},
        "per_class_edge_f1": {c: metrics.get(f"edge_f1_{c}") for c in card["outputs"]["classes"]},
        "best_epoch": report.get("best_epoch"),
        "split_protocol": ("episode -- train and test can share a burst; these are "
                           "NOT novel-attack numbers"
                           if cfg.data.split_strategy == "episode" else cfg.data.split_strategy),
        "fix_12h_clock": cfg.data.fix_12h_clock,
        "pm_hours": list(cfg.data.pm_hours),
        "preprocessing_sha256": pp,
    }
    try:
        build = json.loads((BUNDLE / "BUILD.json").read_text(encoding="utf-8"))
    except Exception:
        build = {"commit": None, "note": "BUILD.json not found in the bundle"}
    try:
        import torch
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        torch_version = torch.__version__
    except Exception:
        gpu, torch_version = None, None
    provenance = {
        "what": "retrain under the fixed 12-hour timestamp parse (ML/TIMESTAMP_FIX.md)",
        "packaged_at_utc": _now(),
        "packaged_in_session": SESSION,
        "weights_sha256": digests["ML/weights.pt"],
        "preprocessing_sha256": pp,
        "preprocessing_settings": preprocessing_settings(cfg),
        "fix_12h_clock": cfg.data.fix_12h_clock,
        "pm_hours": list(cfg.data.pm_hours),
        "package_built_from": build,
        "classes": list(CLASS_NAMES),
        "epochs_configured": cfg.train.epochs,
        "seed": cfg.train.seed,
        "environment": {"python": platform.python_version(), "torch": torch_version,
                        "gpu": gpu, "colab": env.is_colab},
        "stages": _stage_records(env),
        "artefact_sha256": digests,
        "not_in_this_zip": [k for k in (
            "ML/phase2b_sensitivity.json", "ML/phase2b_results.json",
            "ML/testdata/cicids2017_sample.csv") if k not in artefacts],
    }
    write_json(L / "MANIFEST.json", manifest)
    write_json(L / "PROVENANCE.json", provenance)
    artefacts["ML/MANIFEST.json"] = L / "MANIFEST.json"
    artefacts["ML/PROVENANCE.json"] = L / "PROVENANCE.json"

    local_zip = env.local / RESULT_ZIP
    with zipfile.ZipFile(local_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, src in sorted(artefacts.items()):
            z.write(src, rel)
    with zipfile.ZipFile(local_zip) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"the result zip is corrupt at {bad}")
        names = z.namelist()
    drive_zip = env.run_dir / RESULT_ZIP
    copy_verified(local_zip, drive_zip)
    mark(env, "package", {RESULT_ZIP: drive_zip}, files=names,
         zip_sha256=sha256(local_zip))

    print(f"\n{BAR}\n  RESULT ZIP  ({local_zip.stat().st_size / 1e6:.0f} MB, {len(names)} files)\n{BAR}")
    for n in names:
        print(f"    {n}")
    print(f"\n  on Drive : {drive_zip}")
    print("  Unzip it at the repository root: every file lands at its own path.")
    return local_zip


# --------------------------------------------------------------------------
# CELL B
# --------------------------------------------------------------------------
_RUN = {"graphs": stage_graphs, "train_export": stage_train_export,
        "threshold_study": stage_threshold_study, "probes": stage_probes,
        "sample": stage_sample, "phase2b": stage_phase2b}


def cell_b(env: Env | None = None, download: bool = True) -> Path:
    env = env or colab_env()
    if env.is_colab:
        ensure_deps()
    cfg = make_cfg(env)
    print_plan(env)

    stage_audit_gate(env, cfg)
    for stage, fn in _RUN.items():
        m = read_marker(env, stage) or {}
        if is_done(env, stage) and not m.get("skipped"):
            print(f"\n[{stage}] already done in session {m['session']} -- skipped")
            continue
        print(f"\n{BAR}\n  STAGE {STAGES.index(stage) + 1}: {stage}\n{BAR}")
        fn(env, cfg)
    print(f"\n{BAR}\n  STAGE 8: package\n{BAR}")
    z = stage_package(env, cfg)

    if env.is_colab and download:
        try:
            from google.colab import files  # type: ignore
            files.download(str(z))
        except Exception as exc:
            print(f"  browser download did not start ({type(exc).__name__}); "
                  f"take the zip from Drive instead.")
    print("\nDONE. Send the zip back; nothing else is needed from this session.")
    return z
