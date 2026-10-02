# The retrain, as two Colab cells

One upload, two pastes, one download. Colab is needed because the CICIDS2017
CSVs and the GPU are there. No decision is left to a person mid-run.

## What to do

1. **Build the bundle** (on the repo machine, from a clean tree):
   `python ML/colab/build_bundle.py`
   It writes `ML/colab/dist/graphsentinel_colab_bundle.zip` (about 170 kB).
2. **Upload** that zip anywhere in your Google Drive.
3. **Paste `cell_a.py`** into a Colab cell and run it. About 2 to 5 minutes, no
   GPU needed. It ends with `VERDICT: CLEAN` or `NOT CLEAN`.
4. **Paste `cell_b.py`** into a cell on a **GPU runtime** and run it. If Colab
   disconnects, run the same cell again: it continues.
5. **Send back the zip** it downloads, `graphsentinel_retrain_result.zip`. It is
   also saved on Drive under `<project>/retrain_fix12h/`.

If Cell A says `NOT CLEAN`, stop and send back `timestamp_audit.json`. Cell B
will refuse to start anyway.

## What Cell B does

| # | Stage | Skipped on re-run when | Output |
|---|---|---|---|
| 1 | Audit gate | never; checked every run | refuses unless the verdict is clean |
| 2 | Graphs | never; a cache hit takes seconds | splits and graphs under the fixed parse |
| 3 | Train and export | its outputs exist on Drive | `weights.pt`, `model.ts`, `model_card.json`, `test_report.json` |
| 4 | Threshold study | its outputs exist | `threshold_study.json` and two CSVs |
| 5 | Section 12 probes | its outputs exist | `probes.json`, the F2 and F6 table |
| 6 | Sample | its output exists | the regenerated test sample |
| 7 | Phase 2b | its outputs exist | the control, then 2b if the gate allows |
| 8 | Package | never | the result zip |

The retrain uses the configuration in `ML/model_card.json`, the one the
epoch-31 model was trained with, plus `fix_12h_clock = True`. It differs from
the shipped run in the timestamp parse and in nothing else.

Everything is written under `<project>/retrain_fix12h/` on Drive. The pre-fix
checkpoints, logs and models are not touched.

**Resume granularity is the stage.** Training keeps its per-epoch checkpoint on
Colab's local disk, deliberately (the Drive mount has lost files under repeated
overwrite). So a browser disconnect resumes mid-training, but a recycled
runtime restarts training from epoch 1. Training is about 25 minutes.

## What the zip contains

Every artefact at its repository path, so the repo side is one unzip at the
root: the model files, `test_report.json`, the threshold study, `probes.json`,
the audit, a regenerated `MANIFEST.json`, logs under `ML/retrain_logs/`, and
`PROVENANCE.json`.

`PROVENANCE.json` records the new weights digest, the preprocessing digest and
settings, `fix_12h_clock` and `pm_hours`, the commit the bundle was built from
and whether that tree was dirty, the environment, and for each stage which
session ran it and when.

## Stages 6 and 7 need the sample generator

`make_testdata_sample.py` has never been committed. Without it in `ML/`, the
bundle is built without it, stages 6 and 7 are skipped, and the zip says so in
`PROVENANCE.json` under `not_in_this_zip`. Phase 2b is not run on the old
sample, because regenerating the sample afterwards would invalidate that run.

When the generator is committed: the runner calls it with no arguments, from
the repository root, with the dataset folder in the `GS_DATASET_DIR`
environment variable, and expects a new `ML/testdata/cicids2017_sample.csv`.
**That interface is a guess.** If the script takes something else, the stage
fails with a message saying so, and `stage_sample` in `colab_runner.py` is the
one place to change.

## What has and has not been tested

| | Status |
|---|---|
| Both cells, end to end, off Colab | Run on synthetic traffic rewritten onto a marker-less 12-hour clock, one epoch, with stand-in Monday and Thursday files. All eight stages ran; the unzipped result passed the manifest guard. |
| The gate | Refuses when there is no verdict, when it is not clean, and when `pm_hours` differ. On 24-hour data the fix moves 0 rows and the verdict is not clean. |
| Resume | A second run skipped the finished stages and took 1 second. |
| Stages 6 and 7 | Run with a **stand-in** generator. The real one has not been seen. |
| The lifted cells | A test pins them to the notebook source, apart from declared edits. |
| Colab-only paths | **Not run:** mounting Drive, finding the project folder on a real Drive, the `pip` install, the GPU check, the browser download. |
| Real data and real duration | **Not run.** The 40-epoch run on the real files happens for the first time in Colab. |

## Three edits to the notebook cells

Stages 4 and 5 run the notebook's own cells, lifted into `cells/`. The headers
list every difference. One matters: the notebook's threshold cell wrote
`binary_threshold`, `window_seconds` and `window_rule_min_flows`. The backend
reads `binary_gate`, `alert_window_seconds` and `alert_min_flows`, which is
what the committed `threshold_study.json` has. The file in the repository was
produced by a later version of that cell which was never committed. Run as it
stood, the notebook cell would have produced a file the backend loads as
"unverified", silently. The lifted cell writes the backend's keys.
