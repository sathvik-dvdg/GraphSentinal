"""
Build graphsentinel_colab_bundle.zip: everything the two Colab cells need.

    python ML/colab/build_bundle.py

Writes ML/colab/dist/graphsentinel_colab_bundle.zip. Upload that one file to
Drive, then paste cell_a.py and cell_b.py.

The bundle records the commit it was built from (BUILD.json), and the result
zip carries that into PROVENANCE.json. Build from a CLEAN tree: a dirty build
is recorded as dirty, and its commit hash then does not describe the code that
ran.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ML = REPO / "ML"
OUT = ML / "colab" / "dist" / "graphsentinel_colab_bundle.zip"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()


def files() -> list[Path]:
    keep: list[Path] = []
    pkg = ML / "graphsentinel_v2"
    keep += [p for p in (pkg / "graphsentinel").rglob("*.py")]
    keep += [p for p in pkg.glob("requirements*.txt")]
    keep += [p for p in (ML / "colab").rglob("*.py") if "dist" not in p.parts]
    keep += [ML / "timestamp_audit.py", ML / "phase2b_sensitivity_check.py",
             ML / "phase2b_live_path_cost.py", ML / "model_card.json"]
    gen = ML / "make_testdata_sample.py"          # not committed yet; optional
    if gen.exists():
        keep.append(gen)
    return sorted(set(keep))


def main() -> None:
    paths = files()
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise SystemExit(f"missing: {missing}")
    rel = [p.relative_to(REPO).as_posix() for p in paths]
    dirty = _git("status", "--porcelain", "--", *rel)
    build = {
        "commit": _git("rev-parse", "HEAD") or None,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD") or None,
        "dirty": bool(dirty),
        "dirty_files": dirty.splitlines(),
        "built_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "has_sample_generator": (ML / "make_testdata_sample.py").exists(),
        "files": rel,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for p, r in zip(paths, rel):
            z.write(p, r)
        z.writestr("BUILD.json", json.dumps(build, indent=2))
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1e3:.0f} kB, {len(rel)} files)")
    print(f"  commit {build['commit']}  branch {build['branch']}")
    if build["dirty"]:
        print("  WARNING: built from a DIRTY tree. Commit first, then rebuild, or the")
        print("  recorded commit will not describe the code that runs:")
        for line in build["dirty_files"]:
            print("     ", line)
    if not build["has_sample_generator"]:
        print("  note: ML/make_testdata_sample.py is not in the repo, so the run will")
        print("  skip the sample and phase2b stages and say so in PROVENANCE.json.")


if __name__ == "__main__":
    sys.exit(main())
