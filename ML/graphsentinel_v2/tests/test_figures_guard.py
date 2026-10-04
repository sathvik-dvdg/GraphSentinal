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

import json
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
#: bare integers the four shapes below cannot see, by name (see that file)
NAMED = "ML/named_figures.json"
#: Files other things depend on by path and that have been lost before: the
#: open-items list every session starts from, and the archive that 70-odd code
#: comments cite by file name (`Error.md #29`).
REQUIRED = {"OPEN_ITEMS.md", NAMED, "docs/archive/Error.md", "docs/archive/decisions.md",
            "docs/archive/DATAFLOW.md", "docs/archive/INTEGRATION_GUIDE.md"}


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


def test_every_owner_and_mirror_file_is_present_and_tracked():
    """A deleted owner must fail by name, here, not as a FileNotFoundError in
    whichever test happens to read it -- and ML/TIMESTAMP_FIX.md is read by none."""
    try:
        tracked = set(subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                                     text=True, check=True).stdout.split("\n"))
    except Exception:
        pytest.skip("not a git checkout")
    missing = sorted(p for p in OWNERS | {MIRROR} | set(MIRRORS_MD) | REQUIRED
                     if p not in tracked or not (REPO / p).is_file())
    assert not missing, (f"{missing} missing from the working tree or from the index. These own "
                         "or mirror the measured figures, or are cited by path: restore them "
                         "(git log --full-history -- <path>), do not edit this list to match")


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


# ── Every figure in the owner, not only the eight key ones ───────────────────
#
# FIGURES above was a list written from memory, and on 2026-10-04 an audit found
# 57 of the owner's figures restated in other tracked files while the guard
# passed. So the list is now derived from MODEL_BEHAVIOUR.md itself: any number
# of a distinctive shape that the owner states may appear in another tracked
# file ONLY if it is declared for that file in RESTATED below. A declared
# figure is held to EQUALITY: it must still be one of the owner's figures and
# must still be in that file. Change a figure in the owner and every file that
# restates it fails here by name until it follows.

#: four-decimal values, thousands-separated counts, decimal percentages, "N of M"
_FIGURE = re.compile(r"(?<![\d.,])(\d\.\d{4}|\d{1,3}(?:,\d{3})+|\d+\.\d+%|\d+ of \d[\d,]*\d|\d+ of \d)(?!\d)")
#: shapes that are figures by form but identify nothing
GENERIC = {"0.0000", "1.0000", "0.0%", "100.0%"}


def _flat(text: str) -> str:
    """Markdown wraps lines mid-phrase: '58 of\n58 windows' is one figure."""
    return re.sub(r"\s+", " ", text)


def owner_figures() -> set[str]:
    return set(_FIGURE.findall(_flat((REPO / "MODEL_BEHAVIOUR.md").read_text(encoding="utf-8")))) - GENERIC


def restated(files: dict[str, str], figures: set[str]) -> dict[str, set[str]]:
    """path -> the owner's figures that file contains. Owners, the report, the
    evidence files and this file are not restatements."""
    out = {}
    for path, text in files.items():
        if path in OWNERS or path in (MIRROR, THIS) or path.startswith(EXEMPT_PREFIXES):
            continue
        flat = _flat(text)
        found = {f for f in figures if _pattern(f).search(flat)}
        if found:
            out[path] = found
    return out


#: path -> the owner's figures it is allowed to carry, and must carry.
#: Generated from the tree with `python tests/test_figures_guard.py`; a new
#: entry is a decision to keep a copy, so prefer citing the owner instead.
RESTATED: dict[str, list[str]] = {
    'AUDIT_2026-10-04.md': ['0.1326', '0.2967', '0.3094', '0.3394', '0.5737', '0.6292', '0.7994', '0.9487', '18,264', '90.8%'],
    'INTEGRATION.md': ['0 of 168', '0 of 68', '0.0038', '0.0232', '0.0243', '0.0265', '0.1224', '0.22%', '0.3984', '0.4475', '0.4571', '0.5208', '0.6567', '0.6811', '0.8706', '0.8857', '0.9234', '0.9344', '0.9568', '0.9670', '0.9688', '0.9804', '0.9940', '0.9941', '174,421', '18,264', '2 of 486', '226,342', '41 of 18,264', '58 of 58', '90.8%', '99.6%'],
    'ML/b08_ovs_constants_check.py': ['90.8%'],
    'ML/colab/cells/probes_confirm.py': ['0.5508', '0.7042'],
    'ML/colab/colab_runner.py': ['0.7042', '23,812'],
    'ML/graphsentinel_v2/graphsentinel/config.py': ['0.0024', '0.0158', '0.0192', '0.0397', '0.0723'],
    'ML/graphsentinel_v2/graphsentinel/export.py': ['0.7042', '0.7568'],
    'ML/graphsentinel_v2/tests/test_pipeline.py': ['0.0397', '0.0723', '0.1407', '0.7042', '0.7568', '0.9974', '158,746'],
    'ML/phase2b_live_path_cost.py': ['227,325'],
    'ML/verify_stack.py': ['18,264'],
    'RUNNING.md': ['0 of 168', '0.4475'],
    'RUN_GUIDE.md': ['0 of 68', '0.9961', '18,264', '58 of 58', '654,851'],
    'backend/app/services/analysis_pipeline_v2.py': ['0.4475'],
    'backend/app/services/inference_v2.py': ['0 of 168', '0.4475'],
    'backend/app/services/mitigation_policy.py': ['0 of 168', '0.2598', '0.9617', '17,909', '23,812', '904 of 918'],
}


def test_every_restated_figure_is_declared():
    found = restated(_tracked(), owner_figures())
    undeclared = {p: sorted(figs - set(RESTATED.get(p, ()))) for p, figs in found.items()}
    undeclared = {p: f for p, f in undeclared.items() if f}
    assert not undeclared, (
        "figures owned by MODEL_BEHAVIOUR.md are restated without being declared -- cite the "
        "owner's section, or declare them in RESTATED:\n  "
        + "\n  ".join(f"{p}: {f}" for p, f in sorted(undeclared.items())))


def test_declared_restatements_still_equal_the_owner():
    figures = owner_figures()
    files = _tracked()
    stale = []
    for path, declared in sorted(RESTATED.items()):
        flat = _flat(files.get(path, ""))
        for fig in declared:
            if fig not in figures:
                stale.append(f"{path}: carries {fig}, which MODEL_BEHAVIOUR.md no longer states")
            elif not _pattern(fig).search(flat):
                stale.append(f"{path}: declared to carry {fig} and does not")
    assert not stale, "\n  " + "\n  ".join(stale)


# ── Named figures: bare integers, by key ─────────────────────────────────────
#
# "12 rules", "58 of 58", "11 of the 21 sources" carry the claims and have no
# shape a pattern could match without matching every integer in the tree. So
# they are named in ML/named_figures.json: a value, the committed artefact it is
# read from, and the exact phrase each file states it in.

def _whole(value) -> re.Pattern:
    return re.compile(r"(?<![\d.,])" + re.escape(str(value)) + r"(?![\d]|[.,]\d)")


def _artefact_value(pointer: list, read) -> object:
    node = json.loads(read(pointer[0]))
    for key in pointer[1:]:
        node = node[key]
    return sum(node.values()) if isinstance(node, dict) else node


def named_figure_problems(registry: dict, read) -> list[str]:
    """``read``: path -> text, raising for a missing file."""
    out = []
    owner = registry["owner"]
    for key, fig in sorted(registry["figures"].items()):
        value, stated = fig["value"], fig["stated_as"]
        if owner not in stated:
            out.append(f"{key}: not stated in its owner {owner}")
        if "artefact" in fig:
            try:
                got = _artefact_value(fig["artefact"], read)
            except Exception as exc:  # noqa: BLE001
                out.append(f"{key}: artefact {fig['artefact']} unreadable ({exc!r})")
            else:
                if got != value:
                    out.append(f"{key}: registry says {value}, {fig['artefact'][0]} says {got}")
        for path, phrases in sorted(stated.items()):
            try:
                flat = _flat(read(path))
            except Exception:  # noqa: BLE001
                out.append(f"{key}: {path} is declared to state it and cannot be read")
                continue
            for phrase in phrases:
                if not _whole(value).search(phrase):
                    out.append(f"{key}: the phrase {phrase!r} does not carry the value {value}")
                elif _flat(phrase) not in flat:
                    out.append(f"{key} = {value}: {path} no longer says {phrase!r}")
    return out


def test_every_named_figure_equals_its_artefact_and_is_stated_as_declared():
    registry = json.loads((REPO / NAMED).read_text(encoding="utf-8"))
    found = named_figure_problems(registry, lambda path: (REPO / path).read_text(encoding="utf-8"))
    assert not found, "\n  " + "\n  ".join(found)


def test_the_named_figure_guard_catches_each_kind_of_drift():
    files = {"MODEL_BEHAVIOUR.md": "there were 12 rules\nadmitted", "RUN_GUIDE.md": "13 rules admitted",
             "ML/a.json": '{"rules": {"x": 8, "y": 5}}'}
    registry = {"owner": "MODEL_BEHAVIOUR.md", "figures": {
        "ok": {"value": 12, "stated_as": {"MODEL_BEHAVIOUR.md": ["12 rules admitted"]}},
        "artefact_moved": {"value": 12, "artefact": ["ML/a.json", "rules"],
                           "stated_as": {"MODEL_BEHAVIOUR.md": ["12 rules admitted"]}},
        "copy_drifted": {"value": 12, "stated_as": {"MODEL_BEHAVIOUR.md": ["12 rules admitted"],
                                                    "RUN_GUIDE.md": ["12 rules admitted"]}},
        "phrase_without_value": {"value": 12, "stated_as": {"MODEL_BEHAVIOUR.md": ["112 rules"]}},
        "no_owner": {"value": 13, "stated_as": {"RUN_GUIDE.md": ["13 rules admitted"]}},
        "file_gone": {"value": 12, "stated_as": {"MODEL_BEHAVIOUR.md": ["12 rules admitted"],
                                                 "GONE.md": ["12 rules"]}},
    }}
    found = named_figure_problems(registry, files.__getitem__)
    assert sorted(f.split(":")[0].split(" =")[0] for f in found) == [
        "artefact_moved", "copy_drifted", "file_gone", "no_owner", "phrase_without_value"]


if __name__ == "__main__":  # print RESTATED for the tree as it stands
    names = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split("\n")
    tree = {n: (REPO / n).read_text(encoding="utf-8", errors="ignore")
            for n in names if n.endswith(SCANNED) and (REPO / n).is_file()}
    print("RESTATED: dict[str, list[str]] = {")
    for path, figs in sorted(restated(tree, owner_figures()).items()):
        print(f"    {path!r}: {sorted(figs)!r},")
    print("}")
