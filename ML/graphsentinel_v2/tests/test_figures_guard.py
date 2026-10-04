"""One authoritative location per measured figure.

This project's history is numbers disagreeing between copies of themselves. So
the key figures are owned by MODEL_BEHAVIOUR.md (measurements) and
ML/TIMESTAMP_FIX.md (the timestamp investigation), and nowhere else:

  * a key figure in any other tracked text file fails the build -- cite the
    owner's section instead of restating the number;
  * report/main.tex is the examiners' document and must carry the numbers, so
    it is held to EQUALITY: it must contain exactly the owner's figures;
  * evidence files (retrain logs, the pre-fix artefacts, the Phase 2b runs) are
    where the figures come FROM and are exempt.

To change a figure: change it in MODEL_BEHAVIOUR.md and here, and the report
must follow or this fails.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]

#: (figure as written in markdown, as written in LaTeX or None if the report
#: does not carry it, what it is)
FIGURES = [
    ("0.4441", "0.4441", "edge macro F1 over all five classes, installed model"),
    ("0.9961", "0.9961", "edge binary F1, installed model"),
    ("960,315", "960{,}315", "training rows moved by the clock fix"),
    ("1,471,716", None, "rows moved by the clock fix, all eight files"),
    ("97.73", "97.73", "% of test attack rows sharing a window with benign, fixed parse"),
    ("0.51%", "0.51\\%", "the same share under the old parse"),
    ("654,851", "654{,}851", "model parameters"),
    ("22,268", "22{,}268", "correct Volumetric_Flood test predictions clearing 0.90"),
]
OWNERS = {"MODEL_BEHAVIOUR.md", "ML/TIMESTAMP_FIX.md"}
MIRROR = "report/main.tex"
#: Documents that must quote a figure to do their job, held to EQUALITY like the
#: report: path -> the figures (markdown form) each must carry. RUN_GUIDE.md
#: gives the expected values of its verification checks.
MIRRORS_MD = {"RUN_GUIDE.md": ["0.9961", "654,851"]}
EXEMPT_PREFIXES = ("ML/retrain_logs/", "ML/prefix_epoch31/", "ML/phase2b_runs/")
THIS = "ML/graphsentinel_v2/tests/test_figures_guard.py"
SCANNED = (".md", ".py", ".tex", ".txt")


def _pattern(fig: str) -> re.Pattern:
    """The figure as a whole number: 0.51% must not match 0.512, nor 10.51%."""
    return re.compile(r"(?<![\d.,])" + re.escape(fig) + r"(?!\d)")


def violations(files: dict[str, str]) -> list[str]:
    """Key figures restated outside their owners. ``files``: path -> text."""
    out = []
    for path, text in sorted(files.items()):
        if path in OWNERS or path in (MIRROR, THIS) or path.startswith(EXEMPT_PREFIXES):
            continue
        allowed = set(MIRRORS_MD.get(path, ()))
        for md, tex, what in FIGURES:
            if md in allowed:
                continue
            for form in filter(None, (md, tex)):
                if _pattern(form).search(text):
                    out.append(f"{path}: restates {form} ({what}); cite MODEL_BEHAVIOUR.md instead")
                    break
    return out


def _tracked() -> dict[str, str]:
    try:
        names = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                               text=True, check=True).stdout.split("\n")
    except Exception:
        pytest.skip("not a git checkout")
    files = {}
    for n in names:
        if n.endswith(SCANNED) and (REPO / n).is_file():
            files[n] = (REPO / n).read_text(encoding="utf-8", errors="ignore")
    return files


def test_every_key_figure_is_in_its_owner():
    owner = (REPO / "MODEL_BEHAVIOUR.md").read_text(encoding="utf-8")
    missing = [md for md, _, _ in FIGURES if not _pattern(md).search(owner)]
    assert not missing, f"MODEL_BEHAVIOUR.md no longer states {missing}: update FIGURES with it"


def test_no_key_figure_is_restated_outside_its_owners():
    found = violations(_tracked())
    assert not found, "\n  " + "\n  ".join(found)


def test_the_report_carries_exactly_the_owners_figures():
    report = (REPO / MIRROR).read_text(encoding="utf-8")
    missing = [f"{tex} ({what})" for _, tex, what in FIGURES
               if tex and not _pattern(tex).search(report)]
    assert not missing, (
        "report/main.tex does not carry the owner's figure for: " + "; ".join(missing) +
        ". The report is held to equality with MODEL_BEHAVIOUR.md.")


def test_mirror_documents_carry_exactly_the_figures_declared_for_them():
    known = {md for md, _, _ in FIGURES}
    for path, figures in MIRRORS_MD.items():
        assert set(figures) <= known, f"{path}: {set(figures) - known} is not a key figure"
        text = (REPO / path).read_text(encoding="utf-8")
        missing = [f for f in figures if not _pattern(f).search(text)]
        assert not missing, (f"{path} must carry {missing}, the owner's figure(s); it is held "
                             "to equality with MODEL_BEHAVIOUR.md")


def test_the_guard_catches_a_restated_figure_and_spares_the_sources():
    files = {
        "INTEGRATION.md": "the model scores 0.4441 on test",          # a copy: caught
        "backend/app/x.py": "# 22,268 of 27,191 clear the floor",     # a copy: caught
        "notes.md": "threshold 0.512, share 10.51%, 0.44415",          # other numbers: spared
        "ML/retrain_logs/train_output.txt": "edge_macro_f1 0.4441",   # a source: spared
        "MODEL_BEHAVIOUR.md": "0.4441",                               # the owner: spared
        "report/main.tex": "0.4441",                                  # the mirror: spared
        "RUN_GUIDE.md": "expect 654,851 parameters; macro F1 0.4441",  # 654,851 declared; 0.4441 not
    }
    found = violations(files)
    assert [f.split(":")[0] for f in found] == ["INTEGRATION.md", "RUN_GUIDE.md", "backend/app/x.py"]
    assert "0.4441" in found[1]
