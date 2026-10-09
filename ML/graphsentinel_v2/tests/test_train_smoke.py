"""train() end to end, once, on synthetic traffic.

WHY THIS EXISTS. Until this file, no test called train(). The suite checked its
pieces and inspected its source, so a defect in how the pieces are wired could
only be found by a real Colab run -- or by accident, which is how the unguarded
/content log mirror was found. One epoch here covers, for real: the split and
graph cache names, the training loop, checkpoint selection, the log and report
writes, a finished-run resume, the resume guard, and export.

THE RULE THIS FILE FOLLOWS: a guard is only worth having if it would have
caught the failure that prompted it. The /content assertion below fails on the
pre-fix train() -- that was checked by putting the old line back.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphsentinel import train as train_mod  # noqa: E402
from graphsentinel.config import Config  # noqa: E402
from graphsentinel.data.preprocess import clock_tag  # noqa: E402
from graphsentinel.export import export_all  # noqa: E402
from graphsentinel.models.net import build_model  # noqa: E402
from graphsentinel.utils import scratch  # noqa: E402

from make_synthetic import write_dataset  # noqa: E402


def test_train_runs_end_to_end_and_writes_only_where_told(tmp_path, monkeypatch):
    pytest.importorskip("pyarrow", reason="train() caches splits to parquet")

    # No Colab disk on this machine, real or stand-in.
    absent = tmp_path / "content"
    monkeypatch.setattr(scratch, "LOCAL_ROOT", absent)
    monkeypatch.delenv(scratch.ENV_VAR, raising=False)
    real_root_existed = Path("/content").exists()

    write_dataset(tmp_path / "datasets/cicids2017", seed=7)
    c = Config()
    c.base_dir = str(tmp_path)
    c.graph.window_seconds = c.graph.window_stride_seconds = 30
    c.train.epochs = 1
    c.train.mixed_precision = False
    c.model.memory_capacity = 4096
    c.ensure_dirs()

    report = train_mod.train(c, resume=False, verbose=False)

    # --- it trained, selected and evaluated ---------------------------------
    assert report["best_epoch"] == 1 and len(report["history"]) == 1
    assert "edge_macro_f1" in report["metrics"] and "evasion_ablation" in report

    # --- everything it wrote is under base_dir ------------------------------
    for f in (c.checkpoint_path / "best.pt", c.checkpoint_path / "last.pt",
              c.log_path / "training_log.csv", c.log_path / "test_report.json"):
        assert f.exists(), f
    assert not absent.exists(), "train() created the local mirror root"
    assert real_root_existed or not Path("/content").exists(), \
        "train() wrote to /content on a machine that has none"

    # --- cache names carry the clock fix ------------------------------------
    tag = clock_tag(c)
    assert tag == "_pm1-7"
    stem = f"{c.data.taxonomy}_{c.data.split_strategy}"
    assert (c.processed_path / f"train_{stem}{tag}.parquet").exists()
    assert (c.processed_path / f"graphs_{stem}_w30{tag}.pt").exists()

    # --- resuming a finished run trains nothing and still reports -----------
    again = train_mod.train(c, resume=True, verbose=False)
    assert again["best_epoch"] == 1 and len(again["history"]) == 1

    # --- the resume guard refuses the other parse ---------------------------
    c.data.fix_12h_clock = False
    with pytest.raises(RuntimeError, match="fix_12h_clock"):
        train_mod.train(c, resume=True, verbose=False)
    c.data.fix_12h_clock = True

    # --- the selected weights export and reload -----------------------------
    model = build_model(c)
    model.load_state_dict(report["best_state"]["model"])
    status = export_all(c, model, out_dir=tmp_path / "exported",
                        metrics=report["best_state"]["metrics"], verbose=False)
    for k in ("weights", "model_card", "torchscript"):
        assert status[k] and not str(status[k]).startswith("FAILED"), (k, status[k])
    assert not absent.exists()

    # --- with a local mirror (Colab), Drive gets last.pt only every Nth epoch -
    # Per-epoch saves are local-only so the Drive mount is not overwritten 40
    # times; every Nth epoch they also go to the primary path, so a recycled
    # runtime loses at most N epochs instead of all of them.
    import torch
    absent.mkdir()                               # the mirror root now exists
    primary_last = c.checkpoint_path / "last.pt"

    def epoch_on_drive():
        return torch.load(primary_last, map_location="cpu", weights_only=False)["epoch"]

    assert epoch_on_drive() == 1
    c.train.epochs, c.train.drive_checkpoint_every = 2, 0
    train_mod.train(c, resume=True, verbose=False)
    assert torch.load(absent / "gs_ckpt" / "last.pt", weights_only=False)["epoch"] == 2
    assert epoch_on_drive() == 1, "epoch 2 must have stayed on local disk"

    c.train.epochs, c.train.drive_checkpoint_every = 3, 3
    train_mod.train(c, resume=True, verbose=False)
    assert epoch_on_drive() == 3, "epoch 3 is an Nth epoch and must reach the primary path"
