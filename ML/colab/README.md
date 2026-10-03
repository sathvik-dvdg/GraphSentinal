# The retrain, as two Colab cells

One upload, two pastes, one download. Colab is needed because the CICIDS2017
CSVs and the GPU are there. No decision is left to a person mid-run.

## What to do

1. **Build the bundle** (on the repo machine, from a clean tree):
   `python ML/colab/build_bundle.py`
   It writes `ML/colab/dist/graphsentinel_colab_bundle.zip` (about 170 kB).
2. **Upload** that zip anywhere in your Google Drive.
3. **Paste `cell_a.py`** into a Colab cell and run it. About 2 to 5 minutes, no
   GPU needed. It prints `VERDICT: CLEAN` or `NOT CLEAN`, then a **preflight**:
   one PASS, WARN or FAIL line for each thing Cell B depends on.
4. **Paste `cell_b.py`** into a cell on a **GPU runtime** and run it. If Colab
   disconnects, run the same cell again: it continues.
5. **Send back the zip** it downloads, `graphsentinel_retrain_result.zip`. It is
   also saved on Drive under `<project>/retrain_fix12h/`.

If Cell A says `NOT CLEAN`, or any preflight line says FAIL, stop and send the
output back. Cell B will refuse to start on a verdict that is not clean.

## Cell A's preflight

Cell A exercises the Colab-only paths, so they fail in the two-minute cell and
not at stage 3 of a long run.

| Check | On failure |
|---|---|
| Drive mounted, project folder resolved | FAIL |
| Bundle installed, and the commit it was built from | WARN if built from a dirty tree |
| Dependencies import (this runs the `pip` install) | FAIL |
| `cfg` built from the model card; the dataset folder's CSVs, listed | FAIL if a training file is missing |
| The run folder on Drive is writable and reads back | FAIL |
| Free local disk | WARN under 5 GB |
| GPU present | **WARN, not FAIL**: Cell A runs fine on CPU, but it says so before anyone starts Cell B |
| Audit verdict | FAIL if not clean |

Only the browser download is left untried. It is the last thing Cell B does,
and the zip is on Drive either way.

**If the verdict says the fix moves 0 rows**, that is a contradiction, not a
finding. The committed sample carries rows copied verbatim from the two
Friday-Afternoon files, stamped `2:55` and `3:57`. A full audit that finds no
such rows means the wrong folder, replaced files, or a misread. Investigate
before concluding anything. Cell B refuses in that case too, because a retrain
would reproduce the existing model.

## What Cell B does

| # | Stage | Skipped on re-run when | Output |
|---|---|---|---|
| 1 | Audit gate | never; checked every run | refuses unless the verdict is clean |
| 2 | Graphs | never; a cache hit takes seconds | splits and graphs under the fixed parse |
| 3 | Train and export | its outputs exist on Drive | `weights.pt`, `model.ts`, `model_card.json`, `test_report.json` |
| 4 | Threshold study | its outputs exist | `threshold_study.json` and two CSVs |
| 5 | Section 12 probes | its outputs exist | `probes.json`, the F2 and F6 table |
| 6 | Split composition | its output exists | `split_composition.json`: what each split holds under both parses, and the model's confidence against the SDN floors |
| 7 | Sample | its output exists | the regenerated test sample |
| 8 | Phase 2b | its outputs exist | the control, then 2b if the gate allows |
| 9 | Package | never | the result zip |

The retrain uses the configuration in `ML/model_card.json`, the one the
epoch-31 model was trained with, plus `fix_12h_clock = True`. It differs from
the shipped run in the timestamp parse and in nothing else.

Everything is written under `<project>/retrain_fix12h/` on Drive. The pre-fix
checkpoints, logs and models are not touched.

**Resume.** Finished stages are skipped. Inside the training stage, a browser
disconnect resumes from the last epoch. A recycled runtime resumes from the
last checkpoint on Drive, which is written every 10th epoch
(`cfg.train.drive_checkpoint_every`), so it loses at most 10 epochs. Per-epoch
checkpoints otherwise stay on Colab's local disk, deliberately: the Drive mount
lost files under 40 overwrites of the same path. Training is about 25 minutes.

## What the zip contains

Every artefact at its repository path, so the repo side is one unzip at the
root: the model files, `test_report.json`, the threshold study, `probes.json`,
the audit, a regenerated `MANIFEST.json`, logs under `ML/retrain_logs/`, and
`PROVENANCE.json`.

`PROVENANCE.json` records the new weights digest, the preprocessing digest and
settings, `fix_12h_clock` and `pm_hours`, the commit the bundle was built from
and whether that tree was dirty, the environment, and for each stage which
session ran it and when.

## Stages 7 and 8 need the sample generator

`make_testdata_sample.py` has never been committed. Without it in `ML/`, the
bundle is built without it, stages 7 and 8 are skipped, and the zip says so in
`PROVENANCE.json` under `not_in_this_zip`. Phase 2b is not run on the old
sample, because regenerating the sample afterwards would invalidate that run.

The generator is a **Colab cell, not a script**. It asserts `cfg` exists, reads
the CSVs from `cfg.dataset_path`, and writes to `/content/gs_testdata` and then
to `Path(cfg.base_dir) / "testdata"`. Stage 7 therefore executes it with `cfg`
in scope, as the notebook would. (Stage numbers here are from the
9-stage runner; the 2026-10-03 retrain ran the 8-stage one, where these were 6
and 7.)

It is given a **copy** of the config whose `base_dir` is the retrain folder.
With the real `base_dir` it would write over the pre-fix sample in
`<project>/testdata`. The stage checks that folder before and after and fails
if anything in it changed. The dataset stays reachable because `dataset_dir` is
made absolute in the copy.

The generator prints a `MIXED windows` count. Stage 7 records it in the stage
marker and in `PROVENANCE.json` (`sample_mixed_windows`, and whether it is at
least 5). It is the only measure of whether the new sample can support Phase 2b.

This description of the generator comes from its author. The file itself has
still not been seen here; the stage was tested with a stand-in of the same
shape. (The first version of this stage called it as a subprocess with an
environment variable. That was a guess, and wrong on every point.)

## What has and has not been tested

| | Status |
|---|---|
| Both cells, end to end, off Colab | Run on synthetic traffic rewritten onto a marker-less 12-hour clock, one epoch, with stand-in Monday and Thursday files. All eight stages ran; the unzipped result passed the manifest guard. |
| The gate | Refuses when there is no verdict, when it is not clean, and when `pm_hours` differ. On 24-hour data the fix moves 0 rows and the verdict is not clean. |
| Resume | A second run skipped the finished stages and took 1 second. The every-10th-epoch Drive checkpoint is tested in the `train()` smoke test: an off-cycle epoch stays local, an on-cycle epoch reaches the primary path. |
| Stages 7 and 8 | Run with a **stand-in** generator of the documented shape. The pre-fix sample stayed untouched; a generator that writes into the pre-fix folder is refused. The real generator has not been seen. |
| The lifted cells | A test pins them to the notebook source, apart from declared edits. |
| Colab-only paths | Cell A's preflight now tries four of the five. **Still never run on Colab:** all of them. The preflight was run off Colab only, where the Drive and `pip` branches are not taken. |
| Real data and real duration | **Not run.** The 40-epoch run on the real files happens for the first time in Colab. |

## Three edits to the notebook cells

Stages 4 and 5 run the notebook's own cells, lifted into `cells/`. The headers
list every difference. One matters: the notebook's threshold cell wrote
`binary_threshold`, `window_seconds` and `window_rule_min_flows`. The backend
reads `binary_gate`, `alert_window_seconds` and `alert_min_flows`, which is
what the committed `threshold_study.json` has. The file in the repository was
produced by a later version of that cell which was never committed. Run as it
stood, the notebook cell would have produced a file the backend REFUSES:
`load_operating_points` raises `OperatingPointError` naming the missing keys
("a present-but-malformed file is a hard error", `INTEGRATION.md` section 4).
That is the better failure, but it would have surfaced only when the new file
reached the backend. The lifted cell writes the backend's keys, and stage 4
checks for them before the run moves on.

(An earlier version of this file, and the commit message of `6731f1a`, said the
backend would load such a file "silently as unverified". That was wrong; the
loader was not read before the sentence was written.)
