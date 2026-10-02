"""
Timestamp audit: is the 12-hour-clock defect (F3) present at full-dataset scale,
and is the per-day fix rule sound for this dataset?

TWO WAYS TO RUN IT. The CSVs live on Google Drive and training runs in Colab,
so the notebook is the main path, not the awkward one.

  COLAB   Paste this whole file into one cell AFTER section 3 (the config
          cell). It finds the CSVs through ``cfg.dataset_path`` and audits every
          *.csv there -- the five training files, Monday and Thursday. It needs
          nothing from the graphsentinel package, on purpose: the copy on Drive
          may predate the fix.

  CLI     python ML/timestamp_audit.py /path/to/datasets/cicids2017

Both print the tables below and write ``timestamp_audit.json``. Paste that
output into the commit that lands the fix.

WHAT IT REPORTS, per file and per calendar day, under the OLD parse:

  rows, rows at hour >= 13, rows in the PM window (hours 1..7 by default),
  rows carrying an AM/PM token, min/max timestamp, and how many rows the fix
  moves.

HOW TO READ IT.

  * An "Afternoon" file with ZERO rows at hour >= 13 and ZERO AM/PM tokens is
    on a marker-less 12-hour clock: the defect is established for that file.

  * MIXED flag. The fix decides per calendar day: a day with any row at
    hour >= 13 is taken as 24-hour and left alone. If a day MIXES the two
    clocks, its 12-hour rows stay misparsed and nothing says so. A
    business-hours capture has no genuine traffic at 01:00-07:00, so a day
    holding BOTH hour >= 13 rows AND PM-window rows is the tell. If MIXED never
    fires, the per-day rule is sound for this dataset. If it fires anywhere,
    DO NOT COMMIT THE FIX: the rule has to become per-row first.

  * PACKAGE CHECK. This file carries its own copy of the parse, because the
    graphsentinel package on Drive may predate the fix -- importing an old
    copy would audit the OLD parse and report "0 rows moved", reassuringly.
    Two copies can drift, so at the top of the run the installed package is
    inspected. If it has the fix, BOTH parses run over every real Timestamp
    column and must agree row for row. If it does not, the run says so and
    carries on with the embedded copy: re-zip and reinstall the package before
    any retraining, or training will still use the old parse.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import pandas as pd

PM_HOURS = (1, 7)          # must equal cfg.data.pm_hours

# ---- a deliberate copy of graphsentinel.data.preprocess -------------------
# tests/test_pipeline.py::test_audit_script_parses_exactly_like_the_package
# fails if this drifts from the package.
_TS_FORMATS = (
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y %I:%M:%S %p",
    "%d/%m/%Y %I:%M %p",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
)
_MERIDIEM = r"(?i)\b[ap]\.?m\b"


def parse(series: pd.Series, fix_12h: bool = True, pm_hours=PM_HOURS) -> pd.Series:
    s = series.astype(str).str.strip()
    best, best_ok = None, -1
    for fmt in _TS_FORMATS:
        parsed = pd.to_datetime(s, format=fmt, errors="coerce")
        ok = int(parsed.notna().sum())
        if ok > best_ok:
            best, best_ok = parsed, ok
        if ok == len(s):
            break
    if best_ok < len(s):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            best = best.fillna(pd.to_datetime(s, errors="coerce", dayfirst=True))
    if not fix_12h:
        return best
    hour = best.dt.hour
    marked = s.str.contains(_MERIDIEM, regex=True, na=False)
    is_24h_day = ((hour >= 13) | marked).groupby(best.dt.normalize(), dropna=False).transform("any")
    lo, hi = int(pm_hours[0]), int(pm_hours[1])
    shift = best.notna() & ~is_24h_day & (hour >= lo) & (hour <= hi)
    out = best + pd.to_timedelta(shift.astype("int64") * 12, unit="h")
    out.attrs["shifted_12h"] = int(shift.sum())
    return out
# ---------------------------------------------------------------------------


def find_package():
    """(module or None, state) for the INSTALLED graphsentinel.data.preprocess.

    state: "has_fix" | "stale" (importable, no fix) | "absent".
    """
    try:
        here = Path(__file__).resolve().parent / "graphsentinel_v2"
        if here.is_dir() and str(here) not in sys.path:
            sys.path.insert(0, str(here))
    except NameError:                      # pasted into a notebook: no __file__
        pass
    try:
        from graphsentinel.data import preprocess as pkg
    except Exception:
        return None, "absent"
    return pkg, ("has_fix" if hasattr(pkg, "_fix_12h_working_hours") else "stale")


def compare_with_package(pkg, raw: pd.Series, before, after, pm_hours) -> dict:
    """Run the PACKAGE's parse over the same real column; count disagreements."""
    out = {}
    for name, ours, fix in (("old_parse", before, False), ("fixed_parse", after, True)):
        theirs = pkg._parse_timestamps(raw, fix_12h=fix, pm_hours=tuple(pm_hours))
        differ = ~((ours == theirs) | (ours.isna() & theirs.isna()))
        out[name + "_rows_differing"] = int(differ.sum())
    out["agrees"] = not any(out.values())
    return out


def audit(path: Path, pm_hours=PM_HOURS, pkg=None) -> dict:
    head = pd.read_csv(path, nrows=0, encoding="latin-1")
    col = next((c for c in head.columns if str(c).strip().lower() == "timestamp"), None)
    if col is None:
        return {"file": path.name, "error": "no Timestamp column (MachineLearningCVE export?)"}
    raw = pd.read_csv(path, usecols=[col], encoding="latin-1",
                      on_bad_lines="skip", low_memory=False)[col]
    raw = raw.dropna().astype(str).str.strip().reset_index(drop=True)
    before = parse(raw, fix_12h=False)
    after = parse(raw, fix_12h=True, pm_hours=pm_hours)
    h = before.dt.hour
    lo, hi = pm_hours
    marked = raw.str.contains(_MERIDIEM, regex=True)
    moved = after != before

    days = []
    frame = pd.DataFrame({"day": before.dt.date, "ge13": h >= 13,
                          "pm": (h >= lo) & (h <= hi), "marked": marked,
                          "moved": moved, "t": before})
    for day, g in frame.dropna(subset=["t"]).groupby("day"):
        days.append({
            "day": str(day), "rows": int(len(g)),
            "hour_ge_13": int(g["ge13"].sum()),
            "pm_window_rows": int(g["pm"].sum()),
            "am_pm_tokens": int(g["marked"].sum()),
            "rows_moved_by_fix": int(g["moved"].sum()),
            "MIXED": bool(g["ge13"].any() and g["pm"].any()),
        })
    return {
        "file": path.name,
        "package_check": (compare_with_package(pkg, raw, before, after, pm_hours)
                          if pkg is not None else None),
        "pm_hours": list(pm_hours),
        "rows": int(len(raw)),
        "unparseable": int(before.isna().sum()),
        "hour_lt_12": int((h < 12).sum()),
        "hour_ge_12": int((h >= 12).sum()),
        "hour_ge_13": int((h >= 13).sum()),
        "pm_window_rows": int(((h >= lo) & (h <= hi)).sum()),
        "rows_with_am_pm_token": int(marked.sum()),
        "hours_present_before": sorted(int(x) for x in h.dropna().unique()),
        "min_before": str(before.min()), "max_before": str(before.max()),
        "rows_moved_by_fix": int(after.attrs.get("shifted_12h", 0)),
        "hours_present_after": sorted(int(x) for x in after.dt.hour.dropna().unique()),
        "min_after": str(after.min()), "max_after": str(after.max()),
        "days": days,
        "MIXED": any(d["MIXED"] for d in days),
    }


def run(paths, out_dirs=(), pm_hours=PM_HOURS) -> list:
    files = []
    for p in map(Path, paths):
        files += sorted(p.glob("*.csv")) if p.is_dir() else [p]
    if not files:
        raise SystemExit(f"no CSV files under {list(map(str, paths))}")
    pkg, state = find_package()
    print("=" * 74)
    if state == "has_fix":
        print(f"  PACKAGE CHECK: installed graphsentinel has the fix ({pkg.__file__}).")
        print("  Both parses run over every real column below and must agree.")
    elif state == "stale":
        print(f"  PACKAGE CHECK: the installed graphsentinel is STALE -- it predates")
        print(f"  the 12-hour clock fix ({pkg.__file__}).")
        print("  The audit continues with its embedded copy and is still valid, but")
        print("  TRAINING FROM THIS PACKAGE WOULD STILL USE THE OLD PARSE.")
        print("  Re-zip graphsentinel_v2 and reinstall it (notebook section 2.1).")
    else:
        print("  PACKAGE CHECK: graphsentinel is not importable here; using the")
        print("  embedded copy only. The two copies are NOT cross-checked in this run.")
    print("=" * 74)
    live = pkg if state == "has_fix" else None
    results = [audit(f, tuple(pm_hours), live) for f in files]

    for r in results:
        if "error" in r:
            print(f"\n{r['file']}: SKIPPED -- {r['error']}")
            continue
        print(f"\n{r['file']}  ({r['rows']:,} rows, {r['unparseable']:,} unparseable)")
        print(f"  old parse: hour<12 {r['hour_lt_12']:>9,} | hour>=12 {r['hour_ge_12']:>9,} | "
              f"hour>=13 {r['hour_ge_13']:>9,} | AM/PM tokens {r['rows_with_am_pm_token']:,}")
        print(f"             hours {r['hours_present_before']}")
        print(f"             {r['min_before']}  ->  {r['max_before']}")
        pc = r["package_check"]
        if pc is not None:
            print(f"  package vs embedded copy: old parse {pc['old_parse_rows_differing']:,} rows "
                  f"differ, fixed parse {pc['fixed_parse_rows_differing']:,} rows differ"
                  f"{'' if pc['agrees'] else '   <-- THE TWO COPIES DISAGREE'}")
        print(f"  fix moves {r['rows_moved_by_fix']:,} rows; hours after {r['hours_present_after']}")
        print(f"             {r['min_after']}  ->  {r['max_after']}")
        print(f"  {'day':<12s}{'rows':>10s}{'hour>=13':>10s}{'pm-window':>11s}"
              f"{'AM/PM':>8s}{'moved':>10s}  flag")
        for d in r["days"]:
            print(f"  {d['day']:<12s}{d['rows']:>10,}{d['hour_ge_13']:>10,}"
                  f"{d['pm_window_rows']:>11,}{d['am_pm_tokens']:>8,}"
                  f"{d['rows_moved_by_fix']:>10,}  {'MIXED' if d['MIXED'] else ''}")

    ok = [r for r in results if "error" not in r]
    mixed = [(r["file"], d["day"]) for r in ok for d in r["days"] if d["MIXED"]]
    print("\n" + "=" * 74)
    print(f"  PM window: hours {pm_hours[0]}..{pm_hours[1]}  |  files audited: {len(ok)}")
    print(f"  rows moved by the fix, all files: {sum(r['rows_moved_by_fix'] for r in ok):,}")
    if mixed:
        print(f"  MIXED-CLOCK DAYS: {len(mixed)}  <-- DO NOT COMMIT THE FIX AS IS")
        for f, d in mixed:
            print(f"      {f}  {d}")
        print("  A day holds both hour>=13 rows and PM-window rows. The per-day rule")
        print("  leaves that day's 12-hour rows misparsed. Make the rule per-row first.")
    else:
        print("  MIXED-CLOCK DAYS: none -- no day holds both hour>=13 rows and PM-window")
        print("  rows, so the per-day rule is sound for these files.")
    drift = [r["file"] for r in ok if r["package_check"] and not r["package_check"]["agrees"]]
    if state == "has_fix" and not drift:
        print("  PACKAGE CHECK: package and embedded copy agree on every row of every file.")
    elif drift:
        print(f"  PACKAGE CHECK FAILED on {drift}  <-- DO NOT COMMIT")
        print("  The package and this script parse the same rows differently. One of")
        print("  them is wrong; the counts above describe the embedded copy only.")
    else:
        print(f"  PACKAGE CHECK: not performed (package {state}).")
    print("=" * 74)

    for d in list(out_dirs) or [Path.cwd()]:
        try:
            dest = Path(d) / "timestamp_audit.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps({"package_state": state, "files": results},
                                       indent=2), encoding="utf-8")
            print(f"wrote {dest}")
        except OSError as exc:
            print(f"could not write to {d}: {exc}")
    return results


if "cfg" in globals():                                   # pasted into the notebook
    _cfg = globals()["cfg"]
    timestamp_audit = run(
        [_cfg.dataset_path],
        # local disk first: the Drive mount has lost freshly written files before
        out_dirs=([Path("/content/gs_logs")] if Path("/content").is_dir() else [])
        + [_cfg.log_path],
        pm_hours=tuple(getattr(_cfg.data, "pm_hours", PM_HOURS)),
    )
elif __name__ == "__main__":
    if "ipykernel" in sys.modules:
        raise SystemExit("Run section 3 first: this cell reads the dataset "
                         "directory from `cfg.dataset_path`.")
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    run(sys.argv[1:], out_dirs=[Path(__file__).resolve().parent])
