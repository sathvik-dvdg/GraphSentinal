"""The shipped artefacts in ML/ must be the ones MANIFEST.json describes.

THE TRAP THIS GUARDS. A retrain replaces weights.pt. The class list and feature
names do not change, so the contract version stays 2.0.0 and the backend boots
happily against the new weights -- while MANIFEST.json, test_report.json and
every document quoting them still describe the OLD model. Nothing fails; the
numbers are simply no longer about the file on disk.

MANIFEST.json records a sha256 per shipped file. If the weights on disk are not
the weights it names, this fails, and that one check catches the whole class.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ML_DIR = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_mismatches(ml_dir: Path) -> list[str]:
    """Every way the files in ``ml_dir`` disagree with its MANIFEST.json."""
    manifest = json.loads((ml_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    for entry in manifest["files"]:
        f = ml_dir / entry["file"]
        if not f.exists():
            continue                      # weights.pt is gitignored: absent is not wrong
        if f.stat().st_size != entry["bytes"] or _sha256(f) != entry["sha256"]:
            problems.append(f"{entry['file']}: on disk is not the file MANIFEST.json names")

    # the manifest's headline numbers must be the test report's numbers
    report = ml_dir / "test_report.json"
    if report.exists():
        metrics = json.loads(report.read_text(encoding="utf-8"))["metrics"]
        for key, value in manifest.get("headline", {}).items():
            if key in metrics and abs(metrics[key] - value) > 1e-12:
                problems.append(f"headline {key}: MANIFEST {value} vs test_report {metrics[key]}")

    # and the model card must name the same weights
    card = ml_dir / "model_card.json"
    if card.exists():
        named = json.loads(card.read_text(encoding="utf-8")).get("artifacts", {}).get("weights", {})
        listed = {e["file"]: e["sha256"] for e in manifest["files"]}
        if isinstance(named, dict) and named.get("sha256") != listed.get("weights.pt"):
            problems.append("model_card.json and MANIFEST.json name different weights")
    return problems


def test_shipped_artefacts_match_the_manifest():
    if not (ML_DIR / "MANIFEST.json").exists():
        pytest.skip("no MANIFEST.json beside the package")
    problems = manifest_mismatches(ML_DIR)
    assert not problems, (
        "ML/ no longer matches MANIFEST.json:\n  " + "\n  ".join(problems) +
        "\nIf the model was retrained, every artefact and document keyed to the "
        "old weights is stale -- follow the order in ML/TIMESTAMP_FIX.md."
    )
    if not (ML_DIR / "weights.pt").exists():
        pytest.skip("weights.pt is not on this machine; the other files matched")


def test_the_manifest_guard_catches_swapped_weights(tmp_path):
    """The guard must fail on the failure it exists for: new weights, old manifest."""
    old = b"old weights"
    (tmp_path / "weights.pt").write_bytes(old)
    (tmp_path / "test_report.json").write_text(json.dumps({"metrics": {"edge_macro_f1": 0.70}}), encoding="utf-8")
    manifest = json.dumps({
        "files": [{"file": "weights.pt", "bytes": len(old),
                   "sha256": hashlib.sha256(old).hexdigest()}],
        "headline": {"edge_macro_f1": 0.70},
    })
    (tmp_path / "MANIFEST.json").write_text(manifest, encoding="utf-8")
    assert manifest_mismatches(tmp_path) == []

    (tmp_path / "weights.pt").write_bytes(b"NEW weights")       # the retrain
    assert any("weights.pt" in p for p in manifest_mismatches(tmp_path))

    (tmp_path / "weights.pt").write_bytes(old)                  # or only the report moved
    (tmp_path / "test_report.json").write_text(json.dumps({"metrics": {"edge_macro_f1": 0.81}}), encoding="utf-8")
    assert any("headline" in p for p in manifest_mismatches(tmp_path))
