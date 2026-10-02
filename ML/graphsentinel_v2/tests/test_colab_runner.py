"""The Colab runner's decisions, tested without Colab, data or a GPU.

The full two-cell flow was run end to end on synthetic traffic when it was
written (see ML/colab/README.md). These tests pin the parts that decide things:
the audit verdict, the stage-skip rule, the config the retrain uses, and that
the lifted notebook cells are the notebook's cells.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ML_DIR = Path(__file__).resolve().parents[2]
COLAB = ML_DIR / "colab"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def ta():
    return _load("timestamp_audit", ML_DIR / "timestamp_audit.py")


@pytest.fixture(scope="module")
def cr(ta):
    return _load("colab_runner", COLAB / "colab_runner.py")


def _file(name, moved=100, mixed=False, agrees=True):
    return {"file": name, "rows": 1000, "hour_ge_13": 0, "pm_window_rows": moved,
            "rows_with_am_pm_token": 0, "rows_moved_by_fix": moved,
            "package_check": {"agrees": agrees},
            "days": [{"day": "2017-07-07", "MIXED": mixed}]}


def test_verdict_is_clean_only_when_every_condition_holds(ta):
    good = [_file(f) for f in ta.TRAINING_FILES]
    assert ta.verdict(good, "has_fix")["clean"] is True

    # a day that mixes both clocks: the per-day rule is unsound
    v = ta.verdict(good[:-1] + [_file(ta.TRAINING_FILES[-1], mixed=True)], "has_fix")
    assert not v["clean"] and v["mixed_days"] and "per-row" in v["reason"]

    # a training file that was never audited
    v = ta.verdict(good[:-1], "has_fix")
    assert not v["clean"] and v["missing_training_files"] == [ta.TRAINING_FILES[-1]]

    # the package and the script disagree
    v = ta.verdict(good[:-1] + [_file(ta.TRAINING_FILES[-1], agrees=False)], "has_fix")
    assert not v["clean"] and v["package_disagreements"]

    # the fix moves nothing: the defect is not there, a retrain changes nothing
    v = ta.verdict([_file(f, moved=0) for f in ta.TRAINING_FILES], "has_fix")
    assert not v["clean"] and "moves 0 rows" in v["reason"]

    # a file that could not be read
    v = ta.verdict(good + [{"file": "Monday.csv", "error": "no Timestamp column"}], "has_fix")
    assert not v["clean"]


def test_cell_b_refuses_without_a_clean_verdict(cr, ta, tmp_path):
    env = cr.Env(tmp_path / "base", tmp_path / "local", is_colab=False)

    class Cfg:
        class data:
            pm_hours = [1, 7]

    with pytest.raises(SystemExit, match="Run Cell A first"):
        cr.stage_audit_gate(env, Cfg)

    env.logs.mkdir(parents=True)
    bad = {"clean": False, "reason": "1 calendar day(s) mix the clocks", "pm_hours": [1, 7]}
    (env.logs / ta.VERDICT_NAME).write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(SystemExit, match="NOT clean"):
        cr.stage_audit_gate(env, Cfg)

    stale = {"clean": True, "reason": "ok", "pm_hours": [1, 5]}
    (env.logs / ta.VERDICT_NAME).write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(SystemExit, match="pm_hours"):
        cr.stage_audit_gate(env, Cfg)

    ok = {"clean": True, "reason": "ok", "pm_hours": [1, 7]}
    (env.logs / ta.VERDICT_NAME).write_text(json.dumps(ok), encoding="utf-8")
    assert cr.stage_audit_gate(env, Cfg)["clean"] is True


def test_a_stage_is_done_only_while_its_outputs_exist(cr, tmp_path):
    env = cr.Env(tmp_path / "base", tmp_path / "local", is_colab=False)
    out = tmp_path / "weights.pt"
    out.write_bytes(b"x" * 10)
    assert not cr.is_done(env, "train_export")
    cr.mark(env, "train_export", {"weights.pt": out})
    assert cr.is_done(env, "train_export")

    out.write_bytes(b"x" * 11)                 # replaced by something else
    assert not cr.is_done(env, "train_export")
    out.unlink()                               # or lost, as the Drive mount has done
    assert not cr.is_done(env, "train_export")


def test_retrain_config_is_the_shipped_config_plus_the_clock_fix(cr, tmp_path):
    env = cr.Env(tmp_path / "base", tmp_path / "local", is_colab=False)
    cfg = cr.make_cfg(env)
    card = json.loads((ML_DIR / "model_card.json").read_text(encoding="utf-8"))["config"]

    assert cfg.data.fix_12h_clock is True and list(cfg.data.pm_hours) == [1, 7]
    assert "fix_12h_clock" not in card["data"], "the shipped card predates the fix"
    for section in ("model", "loss", "train", "graph"):
        got = getattr(cfg, section).__dict__
        for key, value in card[section].items():
            assert got[key] == value, (section, key)
    for key in ("taxonomy", "split_strategy", "clip_quantile", "edge_feature_cols"):
        assert getattr(cfg.data, key) == card["data"][key]
    # the new run never writes over the old one
    assert cr.RUN_NAME in str(cfg.checkpoint_path) and cr.RUN_NAME in str(cfg.model_path)


def test_find_base_wants_all_five_training_files(cr, ta, tmp_path):
    partial = tmp_path / "A" / "datasets" / "cicids2017"
    partial.mkdir(parents=True)
    (partial / ta.TRAINING_FILES[0]).write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit):
        cr.find_base(tmp_path)

    full = tmp_path / "nested" / "Project" / "datasets" / "cicids2017"
    full.mkdir(parents=True)
    for f in ta.TRAINING_FILES:
        (full / f).write_text("x", encoding="utf-8")
    assert cr.find_base(tmp_path) == tmp_path / "nested" / "Project"


# (notebook cell index, file, [(text in the file, text in the notebook)])
_LIFTED = [
    (33, "threshold_study.py", [
        ('OUT = Path(globals().get("GS_OUT", "/content/gs_logs"));',
         'OUT = Path("/content/gs_logs");'),
        ('    "binary_gate": T_BIN,', '    "binary_threshold": T_BIN,'),
        ('    "alert_window_seconds": scored_cfg.graph.window_seconds,',
         '    "window_seconds": scored_cfg.graph.window_seconds,'),
        ('    "alert_min_flows": (int(bw["min_flows"])',
         '    "window_rule_min_flows": (int(bw["min_flows"])'),
    ]),
    (35, "probes_information.py", []),
    (36, "probes_confirm.py", [
        ("memory_off = {}\n", ""),
        ("    memory_off[split] = m\n", ""),
    ]),
]


@pytest.mark.parametrize("idx,name,edits", _LIFTED)
def test_lifted_cells_are_the_notebook_cells(idx, name, edits):
    """The runner executes these instead of a person running the notebook. They
    must be the notebook's cells, apart from the edits their headers declare."""
    nb = json.loads((ML_DIR / "GraphSentinel_Training.ipynb").read_text(encoding="utf-8"))
    original = "".join(nb["cells"][idx]["source"])
    text = (COLAB / "cells" / name).read_text(encoding="utf-8")
    body = text.split("# " + "-" * 76 + "\n", 1)[1]
    for now, was in edits:
        assert body.count(now) == 1, (name, now)
        body = body.replace(now, was)
    assert body.rstrip("\n") == original.rstrip("\n")


def test_threshold_study_writes_the_keys_the_backend_reads():
    """backend/app/services/operating_points.py reads exactly these three. The
    notebook cell wrote three differently named keys; loaded as is, the backend
    would silently report the operating points as unverified."""
    src = (COLAB / "cells" / "threshold_study.py").read_text(encoding="utf-8")
    for key in ('"binary_gate"', '"alert_min_flows"', '"alert_window_seconds"'):
        assert key in src
    loader = ML_DIR.parent / "backend" / "app" / "services" / "operating_points.py"
    if loader.exists():
        text = loader.read_text(encoding="utf-8")
        for key in ("binary_gate", "alert_min_flows", "alert_window_seconds"):
            assert f'"{key}"' in text
