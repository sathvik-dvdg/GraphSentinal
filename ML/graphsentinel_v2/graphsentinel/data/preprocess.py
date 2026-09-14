"""
Vectorised ingestion, cleaning and leakage-free splitting.

Three defects from the original notebook are fixed here.

1. Per-file 70/15/15 chronological splitting. Putting the first 70 % of
   Tuesday's SSH brute force in train and its last 15 % in test lets the model
   memorise one attack's signature and score 0.99 while learning nothing. All
   three protocols implemented here keep whole attack bursts on one side of the
   boundary.

2. Row-by-row Python cleaning. Everything below is a vectorised pandas/NumPy
   operation over whole columns.

3. A global ``StandardScaler`` pickled from a static offline snapshot. No
   scaler is fitted here at all -- scaling now lives in the inference path as an
   EMA tracker (``inference.ema_scaler``) whose warm-start statistics are
   *exported* from training rather than frozen into it.
"""
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..config import CLASS_TO_IDX, FILE_DAYS, RAW_LABEL_MAP, Config
from .schema import LABEL_COLUMN, TIMESTAMP_COLUMN, normalise_columns, validate_dataset

# Columns every downstream stage needs regardless of feature configuration.
STRUCTURAL_COLUMNS = [
    "Source IP",
    "Destination IP",
    "Source Port",
    "Destination Port",
    "Protocol",
    "Timestamp",
    "Label",
]

# CICIDS2017 TrafficLabelling_ timestamps are day-first and inconsistently
# include seconds and AM/PM markers.
_TS_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %I:%M:%S %p",
    "%d/%m/%Y %I:%M %p",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
)


def _parse_timestamps(series: pd.Series) -> pd.Series:
    """Robust vectorised timestamp parsing.

    Tries each known format across the whole column at once and keeps the one
    that resolves the most rows, then fills stragglers with a general parse.
    """
    s = series.astype(str).str.strip()
    best: Optional[pd.Series] = None
    best_ok = -1
    for fmt in _TS_FORMATS:
        parsed = pd.to_datetime(s, format=fmt, errors="coerce")
        ok = int(parsed.notna().sum())
        if ok > best_ok:
            best, best_ok = parsed, ok
        if ok == len(s):
            break
    assert best is not None
    if best_ok < len(s):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fallback = pd.to_datetime(s, errors="coerce", dayfirst=True)
        best = best.fillna(fallback)
    return best


def load_raw(
    cfg: Config, verbose: bool = True
) -> pd.DataFrame:
    """Load every configured CSV into one chronologically ordered frame.

    Only the columns actually needed are read (``usecols``), which cuts both
    wall-clock and peak memory by roughly 4x on the 85-column CSVs.
    """
    reports = validate_dataset(
        cfg.dataset_path,
        cfg.data.csv_files,
        require_ips=cfg.data.require_ip_columns,
        verbose=verbose,
    )

    wanted = list(
        dict.fromkeys(
            STRUCTURAL_COLUMNS
            + cfg.data.edge_feature_cols
            + cfg.data.volumetric_cols
        )
    )

    frames: List[pd.DataFrame] = []
    for fname, rep in reports.items():
        fpath = cfg.dataset_path / fname
        raw_header = pd.read_csv(
            fpath, nrows=0, low_memory=False, encoding="latin-1"
        )
        rename = normalise_columns(raw_header.columns)
        canonical_to_raw = {
            rename.get(c, str(c).strip()): c for c in raw_header.columns
        }

        usecols, missing = [], []
        for col in wanted:
            raw = canonical_to_raw.get(col)
            if raw is None:
                missing.append(col)
            else:
                usecols.append(raw)
        if missing and verbose:
            print(f"  {fname}: missing columns skipped -> {missing}")

        df = pd.read_csv(
            fpath,
            usecols=usecols,
            low_memory=False,
            encoding="latin-1",
            on_bad_lines="skip",
        )
        df.rename(columns={v: k for k, v in canonical_to_raw.items() if v in df.columns},
                  inplace=True)
        df.columns = [str(c).strip() for c in df.columns]

        # --- labels: vectorised strip + map, unmapped rows dropped -----------
        df[LABEL_COLUMN] = (
            df[LABEL_COLUMN].astype(str).str.strip().map(RAW_LABEL_MAP)
        )
        df = df[df[LABEL_COLUMN].notna()]

        df["capture_day"] = FILE_DAYS.get(fname, Path(fname).stem)
        df["source_file"] = fname

        if verbose:
            counts = df[LABEL_COLUMN].value_counts().to_dict()
            print(f"  {fname[:48]:48s} -> {len(df):>9,} rows {counts}")
        frames.append(df)

    if not frames:
        raise RuntimeError("No usable rows loaded.")

    data = pd.concat(frames, ignore_index=True)
    del frames

    # --- timestamps ------------------------------------------------------
    data[TIMESTAMP_COLUMN] = _parse_timestamps(data[TIMESTAMP_COLUMN])
    n_bad_ts = int(data[TIMESTAMP_COLUMN].isna().sum())
    if n_bad_ts:
        if verbose:
            print(f"  dropping {n_bad_ts:,} rows with unparseable timestamps")
        data = data[data[TIMESTAMP_COLUMN].notna()]

    # Global chronological order. This is the single most important line in the
    # file: every split, every window and every memory update depends on the
    # pooled traffic being in real time order, not file order.
    data.sort_values(TIMESTAMP_COLUMN, kind="mergesort", inplace=True)
    data.reset_index(drop=True, inplace=True)
    # Unix seconds. Going through datetime64[s] rather than dividing an int64
    # by 1e9 keeps this correct whether pandas resolved the column at ns or us
    # precision -- pandas 3 defaults to us, which silently made the old
    # divide-by-1e9 form off by a factor of 1000.
    data["t"] = (
        data[TIMESTAMP_COLUMN].to_numpy(dtype="datetime64[s]").astype("int64")
    )

    if verbose:
        span = data[TIMESTAMP_COLUMN]
        print(f"\n  pooled: {len(data):,} rows | {span.min()} -> {span.max()}")
    return data


def clean(df: pd.DataFrame, cfg: Config, verbose: bool = True) -> pd.DataFrame:
    """Vectorised cleaning. No per-row Python anywhere."""
    n0 = len(df)
    feat_cols = [
        c
        for c in cfg.data.edge_feature_cols + cfg.data.volumetric_cols
        if c in df.columns
    ]

    # inf -> NaN over the numeric block in one shot
    numeric = df[feat_cols].apply(pd.to_numeric, errors="coerce")
    numeric.replace([np.inf, -np.inf], np.nan, inplace=True)
    df[feat_cols] = numeric
    del numeric

    df = df.dropna(subset=feat_cols + ["Source IP", "Destination IP", "t"])

    # IP hygiene: CICIDS2017 has a handful of malformed/empty address cells.
    for col in ("Source IP", "Destination IP"):
        df[col] = df[col].astype(str).str.strip()
    df = df[(df["Source IP"] != "") & (df["Destination IP"] != "")]
    df = df[df["Source IP"] != df["Destination IP"]]  # self-loops carry no topology

    if cfg.data.drop_duplicates:
        # Exact duplicate flows are a CICFlowMeter artefact. Keyed on identity +
        # time so genuinely repeated connections survive.
        df = df.drop_duplicates(
            subset=["Source IP", "Destination IP", "Source Port",
                    "Destination Port", "Protocol", "t"],
            keep="first",
        )

    df = df.reset_index(drop=True)
    if verbose:
        print(f"  cleaned: {n0:,} -> {len(df):,} rows (removed {n0 - len(df):,})")
    return df


def clip_outliers(df: pd.DataFrame, cfg: Config, cols: List[str]) -> pd.DataFrame:
    """Clip heavy tails using quantiles computed *within this split only*."""
    q = cfg.data.clip_quantile
    present = [c for c in cols if c in df.columns]
    if not present:
        return df
    upper = df[present].quantile(q)
    lower = df[present].quantile(1 - q)
    df[present] = df[present].clip(lower=lower, upper=upper, axis=1)
    return df


# --------------------------------------------------------------------------
# Splitting
# --------------------------------------------------------------------------
def split(
    df: pd.DataFrame, cfg: Config, verbose: bool = True
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (train, val, test) under the configured protocol."""
    strategy = cfg.data.split_strategy
    if strategy == "episode":
        out = _split_episode(df, cfg, verbose=verbose)
    elif strategy == "temporal":
        out = _split_temporal(df, cfg)
    elif strategy == "day_holdout":
        out = _split_day_holdout(df, cfg)
    elif strategy == "host_holdout":
        out = _split_host_holdout(df, cfg, verbose=verbose)
    elif strategy == "attack_holdout":
        out = _split_attack_holdout(df, cfg)
    else:
        raise ValueError(f"Unknown split_strategy: {strategy}")

    if verbose:
        print(f"\n  split protocol: {strategy}")
        for name, part in zip(("train", "val", "test"), out):
            dist = part["Label"].value_counts().to_dict()
            print(f"    {name:5s}: {len(part):>9,} rows  {dist}")

    # A split that lost a class is a silent evaluation failure: macro F1 will
    # look fine because the missing class simply never comes up.
    all_labels = set(df["Label"].unique())
    for name, part in zip(("train", "val", "test"), out):
        missing = all_labels - set(part["Label"].unique())
        if missing:
            print(
                f"    WARNING: {name} split contains no {sorted(missing)}. "
                "Metrics for those classes are meaningless -- widen the split "
                "or use a protocol that keeps every class in every split."
            )
    return out


def _rank_cuts(t: np.ndarray, train_frac: float, val_frac: float):
    """Split points chosen by ROW RANK, not by fraction of wall-clock time.

    CICIDS2017 is five capture days scattered across a week, so the pooled
    timeline is mostly empty. Cutting at "70% of the time span" lands in the
    dead air BETWEEN capture days and yields an empty split -- observed on real
    data as a validation set of 179 rows containing no BENIGN at all, which
    silently destroyed checkpoint selection: epoch 1 scored a fluke 0.667 on
    four nodes, every later epoch scored 0.000, early stopping fired, and the
    exported "best" model was the untrained one.

    Ranking by row position guarantees each split receives its share of actual
    traffic no matter how the capture days are spaced.
    """
    n = len(t)
    if n == 0:
        return None, None
    i_a = min(max(int(n * train_frac), 1), n - 1)
    i_b = min(max(int(n * (train_frac + val_frac)), i_a + 1), n - 1)
    return float(t[i_a]), float(t[i_b])


_TRAIN_FRAC = 0.70
_VAL_FRAC = 0.15


def _apply_cuts(grp, t, cut_a, cut_b, gap, min_frac=0.02):
    """Slice into (train, val, test) by ROW POSITION, then trim a dead zone.

    Positional slicing rather than time comparison. Deriving cut *times* from
    rank positions and then filtering with ``t < cut_a`` looks equivalent but is
    not: attack traffic arrives in dense bursts separated by silence, and a
    filter can

      * empty a split entirely, when the rank band between the two cuts happens
        to fall in the silence between two bursts (observed on real CICIDS2017
        PortScan: validation received 0 of 158 746 rows), or
      * discard tens of thousands of rows, when a burst is dense enough that the
        +/- gap window around a cut swallows a large slab of it.

    Positional slicing gives each split its share of rows by construction. The
    dead zone is then trimmed from the INNER edges only, and only while every
    split keeps at least ``min_frac`` of the group -- a separation gap that
    starves a split is worse than no gap.
    """
    n = len(grp)
    if n < 3:
        return grp.iloc[:n], grp.iloc[n:n], grp.iloc[n:n]

    i_a = min(max(int(n * _TRAIN_FRAC), 1), n - 2)
    i_b = min(max(int(n * (_TRAIN_FRAC + _VAL_FRAC)), i_a + 1), n - 1)

    floor = max(int(n * min_frac), 1)
    t_arr = np.asarray(t)

    for g in (gap, gap // 2, 0):
        tr, va, te = grp.iloc[:i_a], grp.iloc[i_a:i_b], grp.iloc[i_b:]
        if g > 0:
            ta, tb = float(t_arr[i_a]), float(t_arr[i_b])
            tr = tr[t_arr[:i_a] < ta - g]
            va = va[(t_arr[i_a:i_b] > ta + g) & (t_arr[i_a:i_b] < tb - g)]
            te = te[t_arr[i_b:] > tb + g]
        if min(len(tr), len(va), len(te)) >= floor:
            return tr, va, te

    # last resort: no dead zone at all, but never an empty split
    return grp.iloc[:i_a], grp.iloc[i_a:i_b], grp.iloc[i_b:]


def _adaptive_gap(t: np.ndarray, requested: int, max_frac: float = 0.05) -> int:
    """Shrink the dead zone when a class spans less time than the zone itself.

    A fixed 300 s gap silently deletes an entire 17-minute attack episode: the
    train side ends at 70 % minus 300 s and the val side starts at 70 % plus
    300 s, which is past the end of the burst. Capping the gap at a fraction of
    the class's own span keeps the separation meaningful without erasing short
    attacks. Real CICIDS2017 bursts run for hours, so this only binds on small
    or synthetic captures -- but silently emptying a split is exactly the kind
    of failure that shows up as a suspiciously clean F1.
    """
    span = float(t.max() - t.min()) if t.size else 0.0
    return int(min(requested, max(span * max_frac, 1.0)))


def _episodes(t: np.ndarray, gap: int) -> np.ndarray:
    """Label contiguous bursts: a silence longer than ``gap`` starts a new one."""
    if t.size == 0:
        return np.zeros(0, dtype=np.int64)
    return np.concatenate([[0], np.cumsum(np.diff(t) > gap)]).astype(np.int64)


def _split_episode(df: pd.DataFrame, cfg: Config, verbose: bool = True):
    """Assign whole attack episodes to splits; never cut a burst in half.

    The v1 notebook took the first 70 % of each CSV for train and the last 15 %
    for test. Since each CICIDS2017 file contains one long attack, that put the
    beginning and the end of the *same* burst on both sides of the evaluation,
    and the model could score well by recognising that specific burst.

    Here the traffic is grouped into episodes first. A class with several
    episodes gets whole episodes assigned to each split, so train and test
    contain genuinely different instances of the attack. A class with only one
    episode -- which is most of CICIDS2017 -- cannot be split that way, so it
    falls back to a chronological cut with a dead zone, and the fallback is
    reported rather than hidden. When that fallback is used, the honest reading
    of the number is "within-episode generalisation", and the zero-day claim
    has to come from the ``attack_holdout`` protocol instead.
    """
    parts = {"train": [], "val": [], "test": []}
    notes: List[str] = []

    for label, grp in df.groupby("Label", sort=False):
        grp = grp.sort_values("t", kind="mergesort")
        t = grp["t"].to_numpy()
        gap = _adaptive_gap(t, cfg.data.split_gap_seconds)

        if label == "BENIGN":
            cut_a, cut_b = _rank_cuts(t, cfg.data.train_frac, cfg.data.val_frac)
            tr, va, te = _apply_cuts(grp, t, cut_a, cut_b, gap)
            parts["train"].append(tr); parts["val"].append(va); parts["test"].append(te)
            continue

        ep = _episodes(t, cfg.data.episode_gap_seconds)
        n_ep = int(ep.max()) + 1

        if n_ep >= cfg.data.min_episodes_for_split:
            n_tr = max(int(n_ep * cfg.data.train_frac), 1)
            n_va = max(int(n_ep * cfg.data.val_frac), 1)
            tr = grp[ep < n_tr]
            va = grp[(ep >= n_tr) & (ep < n_tr + n_va)]
            te = grp[ep >= n_tr + n_va]
            # Episodes are wildly uneven in size -- one stray flow can be its own
            # "episode". If whole-episode assignment starves val or test, fall
            # back to a rank cut so every split still sees this class.
            if min(len(tr), len(va), len(te)) < max(int(len(grp) * 0.02), 1):
                cut_a, cut_b = _rank_cuts(t, cfg.data.train_frac, cfg.data.val_frac)
                tr, va, te = _apply_cuts(grp, t, cut_a, cut_b, gap)
                notes.append(
                    f"{label}: {n_ep} episodes but sizes too uneven "
                    f"({len(grp)} rows) -- used a rank cut instead"
                )
            else:
                notes.append(
                    f"{label}: {n_ep} episodes -> {n_tr}/{n_va}/{n_ep - n_tr - n_va}"
                )
            parts["train"].append(tr); parts["val"].append(va); parts["test"].append(te)
        else:
            cut_a, cut_b = _rank_cuts(t, cfg.data.train_frac, cfg.data.val_frac)
            tr, va, te = _apply_cuts(grp, t, cut_a, cut_b, gap)
            parts["train"].append(tr); parts["val"].append(va); parts["test"].append(te)
            notes.append(
                f"{label}: only {n_ep} episode(s) -- fell back to a chronological "
                f"cut with a {gap}s dead zone (within-episode generalisation only)"
            )

    if verbose and notes:
        print("  episode assignment:")
        for n in notes:
            print(f"    {n}")

    return tuple(
        pd.concat(parts[k]).sort_values("t").reset_index(drop=True)
        if parts[k]
        else df.iloc[0:0].copy()
        for k in ("train", "val", "test")
    )


def _split_host_holdout(df: pd.DataFrame, cfg: Config, verbose: bool = True):
    """Attack hosts in test never appear as attack hosts in train.

    Tests the question a memorised signature fails: does this detect the same
    technique from a source it has never seen? Benign traffic is split
    chronologically so the background still looks like real traffic.
    """
    attack = df[df["Label"] != "BENIGN"]
    hosts = pd.unique(attack["Source IP"])
    rng = np.random.default_rng(cfg.train.seed)
    order = rng.permutation(len(hosts))
    n_tr = int(len(hosts) * cfg.data.train_frac)
    n_va = int(len(hosts) * cfg.data.val_frac)
    sets = {
        "train": set(hosts[order[:n_tr]]),
        "val": set(hosts[order[n_tr : n_tr + n_va]]),
        "test": set(hosts[order[n_tr + n_va :]]),
    }
    if verbose:
        print(
            "  host holdout: "
            + ", ".join(f"{k}={len(v)} attack hosts" for k, v in sets.items())
        )

    benign = df[df["Label"] == "BENIGN"]
    t = benign["t"].to_numpy()
    cut_a = t.min() + (t.max() - t.min()) * cfg.data.train_frac
    cut_b = t.min() + (t.max() - t.min()) * (cfg.data.train_frac + cfg.data.val_frac)
    benign_parts = {
        "train": benign[t < cut_a],
        "val": benign[(t >= cut_a) & (t < cut_b)],
        "test": benign[t >= cut_b],
    }
    return tuple(
        pd.concat([attack[attack["Source IP"].isin(sets[k])], benign_parts[k]])
        .sort_values("t")
        .reset_index(drop=True)
        for k in ("train", "val", "test")
    )


def _split_temporal(df: pd.DataFrame, cfg: Config):
    """One global chronological cut across pooled traffic, with dead zones.

    The gap either side of each boundary is discarded so an attack burst that
    happens to straddle the cut cannot appear on both sides.
    """
    t = df["t"].to_numpy()
    cut_a, cut_b = _rank_cuts(t, cfg.data.train_frac, cfg.data.val_frac)
    gap = _adaptive_gap(t, cfg.data.split_gap_seconds)
    train, val, test = _apply_cuts(df, t, cut_a, cut_b, gap)
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)


def _split_day_holdout(df: pd.DataFrame, cfg: Config):
    """Whole capture days held out. The strongest generalisation test here.

    Train/val come from the non-holdout days (chronological), test is entirely
    unseen days -- different traffic baseline, different attack instances.
    """
    hold = set(cfg.data.holdout_days)
    test = df[df["capture_day"].isin(hold)]
    rest = df[~df["capture_day"].isin(hold)]
    if rest.empty:
        raise ValueError("holdout_days consumed every capture day")

    t = rest["t"].to_numpy()
    cut = t.min() + (t.max() - t.min()) * (
        cfg.data.train_frac / (cfg.data.train_frac + cfg.data.val_frac)
    )
    gap = _adaptive_gap(t, cfg.data.split_gap_seconds)
    train = rest[t < cut - gap]
    val = rest[t > cut + gap]
    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)


def _split_attack_holdout(df: pd.DataFrame, cfg: Config):
    """Zero-day protocol: one attack family is never seen during training.

    Train and val contain BENIGN + all non-held-out attacks. Test contains the
    held-out family plus a benign background drawn from the same time range, so
    the reported number answers "does this generalise to an attack it has never
    seen", which a leaky per-file split cannot.
    """
    hold = set(cfg.data.holdout_attacks)
    if not hold:
        raise ValueError("attack_holdout requires cfg.data.holdout_attacks")

    is_held = df["Label"].isin(hold)
    held_rows = df[is_held]
    if held_rows.empty:
        raise ValueError(f"No rows for holdout attacks {hold}")

    seen = df[~is_held]
    t = seen["t"].to_numpy()
    cut = t.min() + (t.max() - t.min()) * (
        cfg.data.train_frac / (cfg.data.train_frac + cfg.data.val_frac)
    )
    gap = _adaptive_gap(t, cfg.data.split_gap_seconds)
    train = seen[t < cut - gap]
    val = seen[t > cut + gap]

    # Benign background contemporaneous with the held-out attack, so the test
    # graph looks like real traffic rather than a pile of pure attack flows.
    lo, hi = held_rows["t"].min(), held_rows["t"].max()
    background = df[(df["t"] >= lo) & (df["t"] <= hi) & (df["Label"] == "BENIGN")]
    test = pd.concat([held_rows, background]).sort_values("t")

    return train.reset_index(drop=True), val.reset_index(drop=True), test.reset_index(drop=True)


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def build_splits(
    cfg: Config, force: bool = False, verbose: bool = True
) -> Dict[str, pd.DataFrame]:
    """Load -> clean -> split -> cache to parquet. Resumable."""
    cfg.ensure_dirs()
    paths = {
        # The taxonomy is part of the key. Without it, a grouped run silently
        # loads parquets written under cicids6 -- which were built with
        # FTP-Patator and the three extra DoS subtypes ALREADY DROPPED. The
        # rows would then be relabelled by index: SSHBrute -> BruteForce,
        # DoSHulk -> DoS, with none of the extra data and none of the extra
        # bursts that were the entire point. Measured 2026-08-29 (run 10):
        # BruteForce came out at exactly 2,301 edges (SSH-Patator alone,
        # missing FTP-Patator) and DoS at exactly 105,629 (Hulk alone).
        name: cfg.processed_path / f"{name}_{cfg.data.taxonomy}_{cfg.data.split_strategy}.parquet"
        for name in ("train", "val", "test")
    }

    if not force and all(p.exists() for p in paths.values()):
        if verbose:
            print("RESUME: cached splits found, loading parquet.")
        return {k: pd.read_parquet(v) for k, v in paths.items()}

    if verbose:
        print("STEP 1/4  loading raw CSVs")
    df = load_raw(cfg, verbose=verbose)

    if verbose:
        print("\nSTEP 2/4  cleaning")
    df = clean(df, cfg, verbose=verbose)

    if verbose:
        print("\nSTEP 3/4  splitting")
    train, val, test = split(df, cfg, verbose=verbose)
    del df

    if verbose:
        print("\nSTEP 4/4  clipping outliers per split and caching")
    all_feats = cfg.data.edge_feature_cols + cfg.data.volumetric_cols
    out = {}
    for name, part in (("train", train), ("val", val), ("test", test)):
        part = clip_outliers(part, cfg, all_feats)
        part["y"] = part["Label"].map(CLASS_TO_IDX).astype("int16")
        part["binary_label"] = (part["y"] > 0).astype("int8")
        part.to_parquet(paths[name], index=False)
        out[name] = part
        if verbose:
            print(f"    wrote {paths[name].name}  ({len(part):,} rows)")
    return out


def class_counts(df: pd.DataFrame) -> np.ndarray:
    """Per-class row counts aligned to CLASS_TO_IDX order."""
    counts = np.zeros(len(CLASS_TO_IDX), dtype=np.int64)
    vc = df["y"].value_counts()
    for idx, n in vc.items():
        counts[int(idx)] = int(n)
    return counts
