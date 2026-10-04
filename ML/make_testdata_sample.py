# ============================================================================
#  MAKE THE TEST SAMPLE  --  a Colab cell, not a script.
#
#  exec()'d with `cfg` already in the namespace (colab_runner's sample stage
#  does exactly that). Takes no arguments. Reads the training CSVs from
#  cfg.dataset_path and writes cicids2017_sample.csv to
#  Path(cfg.base_dir) / "testdata", and to /content/gs_testdata on Colab.
#
#  WHAT IT SELECTS, AND WHY IN WINDOW SPACE.
#  The sample exists for Phase 2b, which zeroes edge features and asks how
#  many predictions move. A window that holds one class only is classifiable
#  from its shape, so zeroing its features moves nothing: the v1 generator
#  picked windows by flow DENSITY, got single-class windows, and Phase 2b came
#  back +0.0000 on every row with a control that moved 0 of 15,833 predictions.
#  So for each attack class this picks the contiguous run of 60 s windows that
#  holds the most USABLE windows -- at least min_edges_per_graph flows (the
#  builder's floor, read from cfg), at least one flow of the class, and at
#  least one BENIGN flow -- within a row budget, breaking ties on fewest rows.
#
#  Selection happens AFTER cleaning, on the rows the consumer will keep, and
#  the rows written are the source rows of those windows. The MIXED count it
#  prints is measured on the written file, read back through the same steps
#  phase2b_live_path_cost.py uses -- not on the selection.
# ============================================================================
import json
from pathlib import Path

import numpy as np
import pandas as pd

assert "cfg" in globals(), (
    "make_testdata_sample.py is a Colab cell: exec it with `cfg` in the namespace "
    "(colab_runner's sample stage does). It produces nothing without one.")

from graphsentinel.config import CLASS_NAMES  # noqa: E402
from graphsentinel.data import preprocess as pre  # noqa: E402

W = int(cfg.graph.window_seconds)
FLOOR = int(cfg.graph.min_edges_per_graph)
TOTAL_ROWS = 20_000                       # the size of the v1 sample
TARGETS = [c for c in CLASS_NAMES if c != "BENIGN"]
BUDGET = TOTAL_ROWS // len(TARGETS)
OUT_NAME = "cicids2017_sample.csv"


def prepare(raw: pd.DataFrame) -> pd.DataFrame:
    """The consumer's steps (phase2b_live_path_cost.py), on a raw frame with
    a `_srcline` column. Returns the cleaned rows with `t` and `wid`."""
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df["Label"] = df["Label"].astype(str).str.strip().map(pre.RAW_LABEL_MAP)
    df = df[df["Label"].notna()].copy()
    df["Timestamp"] = pre._parse_timestamps(
        df["Timestamp"], fix_12h=cfg.data.fix_12h_clock, pm_hours=cfg.data.pm_hours)
    df = df[df["Timestamp"].notna()].sort_values("Timestamp", kind="mergesort")
    df["t"] = df["Timestamp"].to_numpy(dtype="datetime64[s]").astype("int64")
    df = pre.clean(df, cfg, verbose=False)     # clean BEFORE selecting
    # Windows on the minute grid. The consumer anchors at the sample's first
    # row, (t - t0) // W; on minute-resolution files t0 is a whole minute, so
    # the two agree. The count printed at the end is taken the consumer's way.
    df["wid"] = df["t"] // W
    return df.reset_index(drop=True)


def best_run(wid, lab, target, budget):
    """(first, last) window id of the best contiguous run, its usable-window
    count and its row count; None when no window is usable."""
    order = np.argsort(wid, kind="mergesort")
    wid, lab = np.asarray(wid)[order], np.asarray(lab)[order]
    uniq, start, count = np.unique(wid, return_index=True, return_counts=True)
    n_t = np.add.reduceat((lab == target).astype(np.int64), start)
    n_b = np.add.reduceat((lab == "BENIGN").astype(np.int64), start)
    usable = (count >= FLOOR) & (n_t > 0) & (n_b > 0)
    if not usable.any():
        return None
    best, lo, rows, good = None, 0, 0, 0
    for hi in range(len(uniq)):
        rows += int(count[hi]); good += int(usable[hi])
        while rows > budget and lo <= hi:
            rows -= int(count[lo]); good -= int(usable[lo]); lo += 1
        # Leading unusable windows add rows and no usable window: the
        # fewest-rows tie-break needs them dropped even when within budget.
        while lo < hi and not usable[lo]:
            rows -= int(count[lo]); lo += 1
        if lo > hi or good == 0:
            continue
        # maximise usable windows; tie-break on FEWEST rows
        key = (good, -rows)
        if best is None or key > best[0]:
            best = (key, int(uniq[lo]), int(uniq[hi]), good, rows)
    if best is None:                       # every usable window alone exceeds the budget
        return None
    return {"first_wid": best[1], "last_wid": best[2], "usable_windows": best[3], "rows": best[4]}


def mixed_windows(df: pd.DataFrame) -> int:
    """Windows the consumer will build that hold >= FLOOR flows, >= 1 attack
    and >= 1 BENIGN -- anchored the consumer's way, at the first row."""
    t = df["t"].to_numpy()
    wid = (t - t.min()) // W
    g = pd.DataFrame({"wid": wid, "benign": df["Label"].to_numpy() == "BENIGN"}).groupby("wid")["benign"]
    n, nb = g.size(), g.sum()
    return int(((n >= FLOOR) & (nb > 0) & (nb < n)).sum())


if __name__ == "__main__":
    picks = {}                                  # target -> (file, run, raw rows)
    header = None
    for fname in cfg.data.csv_files:
        path = Path(cfg.dataset_path) / fname
        if not path.exists():
            raise SystemExit(f"missing training file {path}")
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="latin-1",
                          low_memory=False, on_bad_lines="skip")
        if header is None:
            header = list(raw.columns)
        elif len(raw.columns) != len(header):
            raise SystemExit(f"{fname} has {len(raw.columns)} columns, the first file {len(header)}")
        raw.columns = header
        raw["_srcline"] = np.arange(len(raw), dtype=np.int64)
        df = prepare(raw)
        for target in TARGETS:
            if not (df["Label"] == target).any():
                continue
            run = best_run(df["wid"].to_numpy(), df["Label"].to_numpy(), target, BUDGET)
            if run is None:
                print(f"  {fname[:44]:<44s} {target:<18s} no usable window")
                continue
            print(f"  {fname[:44]:<44s} {target:<18s} {run['usable_windows']:>4} usable windows "
                  f"in {run['rows']:,} rows")
            old = picks.get(target)
            if old is None or (run["usable_windows"], -run["rows"]) > (old[1]["usable_windows"], -old[1]["rows"]):
                keep = df.loc[df["wid"].between(run["first_wid"], run["last_wid"]), "_srcline"]
                picks[target] = (fname, run, raw[raw["_srcline"].isin(keep)].assign(_file=fname))
        del raw, df

    missing = [t for t in TARGETS if t not in picks]
    if not picks:
        raise SystemExit("no class has a usable window -- nothing to write")
    # Two classes can pick overlapping windows of one file: keep each SOURCE
    # row once. Identical rows at different source lines are both kept.
    sample = (pd.concat([p[2] for p in picks.values()])
              .drop_duplicates(subset=["_file", "_srcline"])
              .drop(columns=["_file", "_srcline"]))

    out_dirs = [Path(cfg.base_dir) / "testdata"]
    if Path("/content").is_dir():               # Colab only; never create C:\content
        out_dirs.insert(0, Path("/content/gs_testdata"))
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)
        sample.to_csv(d / OUT_NAME, index=False, encoding="latin-1")

    # Measured on the WRITTEN file, the consumer's way.
    back = pd.read_csv(out_dirs[-1] / OUT_NAME, dtype=str, keep_default_na=False,
                       encoding="latin-1", low_memory=False)
    back["_srcline"] = 0
    final = prepare(back)
    mixed = mixed_windows(final)
    print(f"\n  wrote {len(sample):,} rows -> {', '.join(str(d / OUT_NAME) for d in out_dirs)}")
    print("  per class: " + json.dumps({t: {"file": f, **r} for t, (f, r, _) in picks.items()}))
    if missing:
        print(f"  NO USABLE WINDOW for {missing}: the sample cannot test those classes")
    print(f"  after the consumer's cleaning: {len(final):,} rows, "
          f"{final['Label'].value_counts().to_dict()}")
    print(f"  MIXED windows: {mixed}")
