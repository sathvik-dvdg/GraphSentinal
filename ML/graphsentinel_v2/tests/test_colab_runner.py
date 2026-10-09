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

    # the fix moves nothing: refused, and reported as a CONTRADICTION with the
    # sample's verbatim 2:55 / 3:57 rows, never as "the defect is absent"
    v = ta.verdict([_file(f, moved=0) for f in ta.TRAINING_FILES], "has_fix")
    assert not v["clean"] and "moves 0 rows" in v["reason"]
    assert "CONTRADICTS" in v["reason"] and "2:55" in v["reason"]
    assert "not present" not in v["reason"]

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

    # clean, but written by a Cell A that did not record what it is valid for
    ok = {"clean": True, "reason": "ok", "pm_hours": [1, 7]}
    (env.logs / ta.VERDICT_NAME).write_text(json.dumps(ok), encoding="utf-8")
    with pytest.raises(SystemExit, match="older Cell A"):
        cr.stage_audit_gate(env, Cfg)

    env.dataset.mkdir(parents=True)
    (env.dataset / "Tuesday-WorkingHours.pcap_ISCX.csv").write_text("x", encoding="utf-8")
    ok["basis"] = cr.verdict_basis(env)
    (env.logs / ta.VERDICT_NAME).write_text(json.dumps(ok), encoding="utf-8")
    assert cr.stage_audit_gate(env, Cfg)["clean"] is True

    # a new bundle commit with the SAME parse code is fine: the generator, say
    ok["basis"]["bundle_commit"] = "someothercommit"
    (env.logs / ta.VERDICT_NAME).write_text(json.dumps(ok), encoding="utf-8")
    assert cr.stage_audit_gate(env, Cfg)["clean"] is True

    # different parse code, or different CSVs: the verdict is about something else
    ok["basis"]["parse_code_sha256"] = "0" * 64
    (env.logs / ta.VERDICT_NAME).write_text(json.dumps(ok), encoding="utf-8")
    with pytest.raises(SystemExit, match="parse code"):
        cr.stage_audit_gate(env, Cfg)
    ok["basis"] = cr.verdict_basis(env)
    (env.dataset / "Tuesday-WorkingHours.pcap_ISCX.csv").write_text("xy", encoding="utf-8")
    (env.logs / ta.VERDICT_NAME).write_text(json.dumps(ok), encoding="utf-8")
    with pytest.raises(SystemExit, match="dataset CSVs"):
        cr.stage_audit_gate(env, Cfg)


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
    # The reference is the EPOCH-31 card: the retrain is defined as that run
    # plus the clock fix. Since the retrain was installed, ML/model_card.json is
    # the retrained card; it must differ from epoch 31 only in the fix and in
    # where the run writes.
    card = json.loads((ML_DIR / "prefix_epoch31" / "model_card.json").read_text(encoding="utf-8"))["config"]
    shipped = json.loads((ML_DIR / "model_card.json").read_text(encoding="utf-8"))["config"]

    def flat(d, p=""):
        out = {}
        for k, v in d.items():
            out.update(flat(v, p + k + ".") if isinstance(v, dict) else {p + k: v})
        return out
    a, b = flat(card), flat(shipped)
    differ = {k for k in set(a) | set(b) if a.get(k, "<absent>") != b.get(k, "<absent>")}
    assert differ <= {"data.fix_12h_clock", "data.pm_hours", "data.processed_dir", "checkpoint_dir",
                      "log_dir", "export.model_dir", "export.export_onnx",
                      "train.drive_checkpoint_every"}, sorted(differ)

    assert cfg.data.fix_12h_clock is True and list(cfg.data.pm_hours) == [1, 7]
    assert "fix_12h_clock" not in card["data"], "the epoch-31 card predates the fix"
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
    notebook cell wrote three differently named keys, and the loader raises
    OperatingPointError on a present file that lacks any of the three."""
    src = (COLAB / "cells" / "threshold_study.py").read_text(encoding="utf-8")
    for key in ('"binary_gate"', '"alert_min_flows"', '"alert_window_seconds"'):
        assert key in src
    loader = ML_DIR.parent / "backend" / "app" / "services" / "operating_points.py"
    if loader.exists():
        text = loader.read_text(encoding="utf-8")
        for key in ("binary_gate", "alert_min_flows", "alert_window_seconds"):
            assert f'"{key}"' in text


_CELL_SHAPED_GENERATOR = """
assert "cfg" in dir(), "Run section 3 (config) first."
from pathlib import Path
src = Path(cfg.dataset_path)
out = Path(cfg.base_dir) / "testdata"
out.mkdir(parents=True, exist_ok=True)
(out / "sample_new.csv").write_text("a,b\\n" + src.name + ",1\\n", encoding="utf-8")
print("MIXED windows: {mixed}")
"""


def _sample_env(cr, tmp_path, monkeypatch, generator: str):
    bundle_ml = tmp_path / "bundle_ml"
    bundle_ml.mkdir()
    (bundle_ml / "make_testdata_sample.py").write_text(generator, encoding="utf-8")
    import shutil
    shutil.copyfile(ML_DIR / "model_card.json", bundle_ml / "model_card.json")
    monkeypatch.setattr(cr, "ML", bundle_ml)
    env = cr.Env(tmp_path / "base", tmp_path / "local", is_colab=False)
    env.dataset.mkdir(parents=True)
    old = env.base / "testdata" / "cicids2017_sample.csv"
    old.parent.mkdir(parents=True)
    old.write_text("PRE-FIX\n", encoding="utf-8")
    return env, cr.make_cfg(env), old


def test_stage_sample_runs_the_generator_as_a_cell_and_protects_the_old_sample(
        cr, tmp_path, monkeypatch):
    """The generator is a Colab cell: it needs `cfg` in scope, reads
    cfg.dataset_path and writes Path(cfg.base_dir)/"testdata". Run with the real
    base_dir it would overwrite the pre-fix sample."""
    env, cfg, old = _sample_env(cr, tmp_path, monkeypatch,
                                _CELL_SHAPED_GENERATOR.format(mixed=7))
    cr.stage_sample(env, cfg)

    assert old.read_text(encoding="utf-8") == "PRE-FIX\n", "the pre-fix sample was touched"
    new = env.run_dir / "testdata" / "cicids2017_sample.csv"
    assert new.exists() and "cicids2017" in new.read_text(encoding="utf-8")   # it read cfg.dataset_path
    m = cr.read_marker(env, "sample")
    assert m["mixed_windows"] == 7 and m["mixed_windows_sufficient"] is True
    assert m["generator_wrote"] == "sample_new.csv"
    assert cfg.base_dir == str(env.base), "the caller's cfg must not be changed"


def test_stage_sample_records_a_thin_sample_and_refuses_a_write_to_the_old_folder(
        cr, tmp_path, monkeypatch):
    env, cfg, _ = _sample_env(cr, tmp_path, monkeypatch,
                              _CELL_SHAPED_GENERATOR.format(mixed=3))
    cr.stage_sample(env, cfg)
    m = cr.read_marker(env, "sample")
    assert m["mixed_windows"] == 3 and m["mixed_windows_sufficient"] is False

    # a generator that ignores cfg.base_dir and writes into the pre-fix folder
    rogue = _CELL_SHAPED_GENERATOR.format(mixed=9).replace(
        'Path(cfg.base_dir) / "testdata"', f'Path(r"{env.base}") / "testdata"')
    (cr.ML / "make_testdata_sample.py").write_text(rogue, encoding="utf-8")
    with pytest.raises(RuntimeError, match="PRE-FIX sample folder"):
        cr.stage_sample(env, cfg)


def test_preflight_reports_each_dependency_of_cell_b(cr, ta, tmp_path, capsys):
    env = cr.Env(tmp_path / "base", tmp_path / "local", is_colab=False)
    env.dataset.mkdir(parents=True)
    for f in ta.TRAINING_FILES[:-1]:                       # one training file missing
        (env.dataset / f).write_text("x", encoding="utf-8")
    cfg = cr.make_cfg(env)
    checks = cr.preflight(env, cfg, {"clean": False, "reason": "a day mixes the clocks"})
    by = {c["check"].split(";")[0].split(",")[0][:22]: c for c in checks}
    status = {c["check"]: c["status"] for c in checks}

    assert [c for c in checks if "dataset folder holds 4 CSVs" in c["check"]][0]["status"] == "FAIL"
    assert status["audit verdict"] == "FAIL"
    assert status["dependencies import"] == "PASS"
    assert status["run folder is writable and reads back"] == "PASS"
    assert status["GPU present"] in ("PASS", "WARN")       # a missing GPU warns in Cell A
    out = capsys.readouterr().out
    assert "PREFLIGHT" in out and "[FAIL]" in out
    assert json.loads((env.logs / "preflight.json").read_text(encoding="utf-8"))["checks"]


def test_audit_never_counts_an_unparseable_row_as_moved(ta, tmp_path):
    """NaT != NaT is True. An unparseable timestamp must not be counted as moved,
    and the per-day column must sum to the file figure."""
    import pandas as pd

    f = tmp_path / "Tuesday-WorkingHours.pcap_ISCX.csv"
    pd.DataFrame({"Timestamp": ["4/7/2017 9:00", "4/7/2017 2:00", "not a date",
                                "4/7/2017 3:30"], "Label": ["BENIGN"] * 4}).to_csv(f, index=False)
    r = ta.audit(f)
    assert r["unparseable"] == 1
    assert r["rows_moved_by_fix"] == 2
    assert sum(d["rows_moved_by_fix"] for d in r["days"]) == 2


def test_audit_gates_on_the_config_training_set(cr, ta):
    """TRAINING_FILES is a fallback for the command line. Where a config exists,
    the verdict gates on cfg.data.csv_files, so the two lists cannot drift."""
    import inspect
    card = json.loads((ML_DIR / "model_card.json").read_text(encoding="utf-8"))
    assert cr.training_files() == tuple(card["config"]["data"]["csv_files"])
    assert "required_files=tuple(cfg.data.csv_files)" in inspect.getsource(cr.cell_a)
    src = (ML_DIR / "timestamp_audit.py").read_text(encoding="utf-8")
    assert "required_files=tuple(_cfg.data.csv_files)" in src
    # today the fallback matches; if the training set changes, the config wins
    assert set(ta.TRAINING_FILES) == set(cr.training_files())


def test_split_composition_sees_windows_the_way_the_builder_does(cr):
    """An attack row shares a window with benign only when a BENIGN row OF THE
    SAME SPLIT falls in its window, with windows anchored at the split's first
    row exactly as GraphBuilder anchors them."""
    import pandas as pd

    t0 = 1_499_000_000
    rows = ([(t0 + 5, "BENIGN")] +                       # window 0: benign
            [(t0 + 10 + i, "PortScan") for i in range(9)] +   # window 0: 9 scans
            [(t0 + 130 + i, "PortScan") for i in range(3)] +  # window 2: alone
            [(t0 + 200, "Botnet")])                           # window 3: alone
    part = pd.DataFrame({"t": [r[0] for r in rows], "Label": [r[1] for r in rows],
                         "source_file": "f.csv"})
    c = cr.split_composition(part, window_seconds=60, min_edges=8)
    assert c["PortScan"]["rows"] == 12
    assert c["PortScan"]["rows_sharing_window_with_benign"] == 9
    assert c["PortScan"]["rows_in_graphable_windows"] == 9     # window 0 has 10 rows
    assert c["PortScan"]["windows"] == 2
    assert c["Botnet"]["rows_sharing_window_with_benign"] == 0
    assert c["Botnet"]["rows_in_graphable_windows"] == 0       # below the 8-flow floor
    assert "rows_sharing_window_with_benign" not in c["BENIGN"]


def test_split_composition_runs_before_the_sample_and_is_packaged(cr):
    import inspect
    assert cr.STAGES.index("split_composition") == cr.STAGES.index("probes") + 1
    assert cr._RUN["split_composition"] is cr.stage_split_composition
    assert '"ML/split_composition.json"' in inspect.getsource(cr.stage_package)
    cell = (COLAB / "cells" / "split_composition.py").read_text(encoding="utf-8")
    assert "from colab_runner import boundary_sharing, split_composition" in cell
    assert "fix_12h_clock = fix" in cell                  # both parses, not one


# --------------------------------------------------------------------------
# make_testdata_sample.py: a Colab cell, exec'd with cfg in scope
# --------------------------------------------------------------------------
GEN = ML_DIR / "make_testdata_sample.py"


def _gen_cfg(tmp_path, files):
    from graphsentinel.config import Config
    card = json.loads((ML_DIR / "model_card.json").read_text(encoding="utf-8"))
    cfg = Config.from_dict(card["config"])
    cfg.data.fix_12h_clock = True
    cfg.data.pm_hours = [1, 7]
    cfg.data.csv_files = list(files)
    cfg.base_dir = str(tmp_path / "run")
    cfg.data.dataset_dir = str(tmp_path / "dataset")
    return cfg


def test_sample_generator_without_cfg_raises_rather_than_producing_nothing(tmp_path):
    with pytest.raises(AssertionError, match="cfg"):
        exec(compile(GEN.read_text(encoding="utf-8"), str(GEN), "exec"), {"__name__": "__main__"})


def test_best_run_maximises_usable_windows_then_fewest_rows(tmp_path):
    import numpy as np
    ns = {"cfg": _gen_cfg(tmp_path, []), "__name__": "not_main"}
    exec(compile(GEN.read_text(encoding="utf-8"), str(GEN), "exec"), ns)
    best_run, floor = ns["best_run"], ns["FLOOR"]
    # window 0: dense PortScan only (unusable); 1 and 2: mixed (usable);
    # 3: mixed but below the floor; 4: mixed and usable, alone
    wid, lab = [], []
    for w, n_ps, n_b in ((0, 30, 0), (1, floor, 1), (2, floor, 1), (3, 2, 1), (4, floor, 1)):
        wid += [w] * (n_ps + n_b); lab += ["PortScan"] * n_ps + ["BENIGN"] * n_b
    run = best_run(np.array(wid), np.array(lab), "PortScan", budget=10_000)
    assert run["usable_windows"] == 3                  # 1, 2 and 4 -- not the dense window
    assert (run["first_wid"], run["last_wid"]) == (1, 4)   # fewest rows: window 0 left out
    assert best_run(np.array([0] * 30), np.array(["PortScan"] * 30), "PortScan", 10_000) is None


def test_sample_generator_writes_mixed_windows_from_source_rows(tmp_path, capsys):
    """End to end on synthetic Friday-afternoon traffic stamped on the
    marker-less 12-hour clock: the written rows are source rows, and the
    MIXED count it prints is the one the consumer's steps give."""
    import pandas as pd
    import numpy as np

    src = pd.read_csv(ML_DIR / "testdata" / "cicids2017_sample.csv", dtype=str,
                      keep_default_na=False, encoding="latin-1", low_memory=False)
    lab = src.columns[-1]
    rows = pd.concat([src[src[lab].str.strip() == "PortScan"].head(400),
                      src[src[lab].str.strip() == "BENIGN"].head(400)]).reset_index(drop=True)
    ts = rows.columns[[c.strip() for c in rows.columns].index("Timestamp")]
    rows[ts] = [f"7/7/2017 2:{(i % 20):02d}" for i in range(len(rows))]   # 12-hour, no AM/PM
    name = "Friday-WorkingHours-Afternoon-PortScan.pcap_ISCX.csv"
    (tmp_path / "dataset").mkdir()
    rows.to_csv(tmp_path / "dataset" / name, index=False, encoding="latin-1")

    cfg = _gen_cfg(tmp_path, [name])
    exec(compile(GEN.read_text(encoding="utf-8"), str(GEN), "exec"),
         {"cfg": cfg, "__name__": "__main__"})
    out = capsys.readouterr().out
    written = pd.read_csv(tmp_path / "run" / "testdata" / "cicids2017_sample.csv", dtype=str,
                          keep_default_na=False, encoding="latin-1", low_memory=False)
    assert len(written) > 0
    key = lambda d: set(map(tuple, d.astype(str).to_numpy().tolist()))
    assert key(written) <= key(rows), "every written row is a source row, verbatim"
    mixed = int(out.split("MIXED windows:")[1].split()[0])
    assert mixed >= 5, out
    assert "NO USABLE WINDOW" in out          # this source has PortScan only
    assert not Path("C:/content").exists() or Path("/content").is_dir()


def _flows(stamps, labels):
    import pandas as pd
    n = len(stamps)
    return pd.DataFrame({
        "Timestamp": stamps, "Label": labels,
        "Source IP": [f" 10.0.0.{i % 5} " for i in range(n)],   # padded on purpose
        "Destination IP": [f"10.0.1.{i % 3}" for i in range(n)],
        "Source Port": [1000 + i for i in range(n)], "Destination Port": 80, "Protocol": 6,
        **{c: 1.0 for c in ("Flow Duration", "Total Fwd Packets", "Total Backward Packets",
                            "Total Length of Fwd Packets", "Total Length of Bwd Packets",
                            "Fwd Packet Length Max", "Bwd Packet Length Max", "Flow IAT Mean",
                            "Fwd IAT Total", "Bwd IAT Total", "SYN Flag Count",
                            "RST Flag Count", "ACK Flag Count", "PSH Flag Count",
                            "Flow Bytes/s", "Flow Packets/s")}})


def _cleaned(raw, fix):
    from graphsentinel.config import Config
    from graphsentinel.data import preprocess as pre
    card = json.loads((ML_DIR / "model_card.json").read_text(encoding="utf-8"))
    cfg = Config.from_dict(card["config"])
    cfg.data.fix_12h_clock, cfg.data.pm_hours = fix, [1, 7]
    df = raw.copy()
    df["Timestamp"] = pre._parse_timestamps(df["Timestamp"], fix_12h=fix, pm_hours=[1, 7])
    df = df.sort_values("Timestamp", kind="mergesort")
    df["t"] = df["Timestamp"].to_numpy(dtype="datetime64[s]").astype("int64")
    sliced = df[df["Label"] != "never"]           # a slice, as callers pass one
    return pre.clean(sliced, cfg, verbose=False)


def test_clean_writes_its_strip_without_a_chained_assignment_warning():
    import warnings
    raw = _flows(["4/7/2017 9:00"] * 20, ["BENIGN"] * 20)
    raw.loc[3, "Flow Duration"] = float("inf")      # dropna must DROP, as on real data
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = _cleaned(raw, fix=True)
    assert not out["Source IP"].str.startswith(" ").any(), "the strip must reach the frame"


def test_clean_keeps_the_same_rows_per_class_under_both_parses():
    """The split totals differ between parses; clean() must not be why. Its
    dedup key includes t, and both parses map raw stamps one-to-one, so the
    duplicate groups -- and, the sort being stable, the row kept -- match."""
    stamps = ["4/7/2017 9:00", "4/7/2017 2:09", "4/7/2017 2:09", "4/7/2017 10:10",
              "4/7/2017 3:00", "4/7/2017 9:00"]
    labels = ["BENIGN", "BruteForce", "BENIGN", "BruteForce", "BENIGN", "BruteForce"]
    import pandas as pd
    base = _flows(stamps, labels)
    twin = base.copy()
    twin["Label"] = labels[::-1]           # exact duplicates whose labels CONFLICT
    raw = pd.concat([base, twin], ignore_index=True)
    old = _cleaned(raw, fix=False)
    new = _cleaned(raw, fix=True)
    assert len(old) == len(new) == len(base)      # every twin was a duplicate
    assert old["Label"].value_counts().to_dict() == new["Label"].value_counts().to_dict()


def test_manifest_records_an_empty_class_as_none_not_zero(cr):
    report = {"edge_confusion": [[5, 0, 0, 0, 0], [0, 3, 0, 0, 0], [0, 0, 2, 0, 0],
                                 [0, 0, 0, 1, 0], [0, 0, 0, 0, 0]]}
    from graphsentinel.config import Config
    card = json.loads((ML_DIR / "model_card.json").read_text(encoding="utf-8"))
    Config.from_dict(card["config"])                    # sets the flood4 class list
    assert cr._edges_in_test(report, "PortScan") is True
    assert cr._edges_in_test(report, "Botnet") is False


def test_package_includes_the_verdict_with_its_basis(cr):
    import inspect
    assert '"ML/timestamp_audit_verdict.json"' in inspect.getsource(cr.stage_package)


def test_boundary_sharing_finds_a_cut_inside_one_timestamp(cr):
    """The PortScan case: one timestamp in train, validation and test."""
    import pandas as pd

    def part(rows):
        return pd.DataFrame({"t": [r[0] for r in rows], "Label": [r[1] for r in rows]})

    splits = {"train": part([(100, "PortScan")] * 3 + [(160, "PortScan")] * 2 + [(10, "BENIGN")]),
              "val": part([(160, "PortScan")] * 4 + [(700, "BENIGN")]),
              "test": part([(160, "PortScan")] * 1 + [(220, "PortScan")] * 5 + [(1400, "BENIGN")])}
    b = cr.boundary_sharing(splits)
    assert b["PortScan"]["train|val"] == {"shared_timestamps": 1, "train_rows_on_shared": 2,
                                          "val_rows_on_shared": 4, "shared": [160]}
    assert b["PortScan"]["val|test"]["test_rows_on_shared"] == 1
    assert b["PortScan"]["distinct_timestamps"] == {"train": 2, "val": 1, "test": 2}
    assert b["BENIGN"]["train|val"]["shared_timestamps"] == 0


def test_markers_are_named_by_stage_and_legacy_names_still_count(cr, tmp_path):
    """Adding a stage must never make a finished one look unfinished: a stage
    marked under the old positional name ('3_train_export.json') is still done."""
    env = cr.Env(tmp_path / "base", tmp_path / "local", is_colab=False)
    out = tmp_path / "weights.pt"
    out.write_bytes(b"x" * 10)
    env.state.mkdir(parents=True, exist_ok=True)
    legacy = {"stage": "train_export", "session": "old", "finished_at_utc": "t",
              "outputs": {"weights.pt": {"path": str(out), "bytes": 10}}}
    (env.state / "3_train_export.json").write_text(json.dumps(legacy), encoding="utf-8")
    assert cr.is_done(env, "train_export")
    cr.mark(env, "probes", {"weights.pt": out})
    assert (env.state / "probes.json").exists()


def test_a_measurement_stage_reruns_when_its_code_changes(cr, tmp_path, monkeypatch):
    env = cr.Env(tmp_path / "base", tmp_path / "local", is_colab=False)
    out = tmp_path / "split_composition.json"
    out.write_text("{}", encoding="utf-8")
    cr.mark(env, "split_composition", {"split_composition.json": out})
    assert cr.is_done(env, "split_composition")
    monkeypatch.setattr(cr, "_code_digest", lambda stage: "0" * 64)    # the cell changed
    assert not cr.is_done(env, "split_composition")
    # a stage whose re-run would refit something is not code-keyed
    assert "threshold_study" not in cr.CODE_KEYED and "train_export" not in cr.CODE_KEYED
