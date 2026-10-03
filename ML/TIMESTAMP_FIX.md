# The 12-hour clock fix, and which artefacts predate it

**Status.** The fix is committed. The full-dataset audit **ran in Colab on
2026-10-03 and confirmed the defect in every file** (below). Nothing has been
retrained yet. Every model artefact in this directory predates the fix.

## The defect

Measured across all eight CICIDS2017 `TrafficLabelling_` files, 2,830,743 rows
(next section):

- **No file** shows an hour of 13 or later, or an AM/PM token.
- **Six of the eight are 12-hour by measurement.** They contain hours 1 to 5,
  which in a business-hours capture can only be afternoon traffic.
- **The other two cannot be classified.** Friday-Morning and
  Thursday-Morning-WebAttacks hold hours 8 to 12 only, and hours 8 to 12 read
  the same on both clocks. The fix moves 0 rows in both, which is correct
  whichever clock they use. A rule that had moved rows in a morning-only file
  would have been wrong, so those two zeros are evidence the rule behaves.

Before 2026-10-03 this rested on two timestamp values from the sample. The
commit that recorded the full-scale result (`4e2e192`) said "all eight files
are 12-hour" in its message; that overstated the two morning-only files.

`_parse_timestamps` parsed that string successfully as 03:57 using
`%d/%m/%Y %H:%M`, so afternoon traffic sorted before the same day's morning
traffic. The two `%p` formats in `_TS_FORMATS` need a meridiem token and never
matched. No later step corrected it.

Where a file is stamped this way, everything built on pooled time order is
affected:

- edge features 14 and 15 (`log_dt_since_pair`, `log_dt_since_src`);
- the order of windows, so `HostHistory` (node features 14 and 15) and the
  host memory are warmed in the wrong order;
- the BENIGN rank cut and the episode detection, so split composition.

## The fix

`preprocess._fix_12h_working_hours`, applied by `_parse_timestamps` and
controlled by two config fields:

| Field | Default | Meaning |
|---|---|---|
| `cfg.data.fix_12h_clock` | `True` | Apply the fix. `False` reproduces the old parse. |
| `cfg.data.pm_hours` | `[1, 7]` | Inclusive hours read as afternoon on a 12-hour day. |

Per calendar day: a day is on the 12-hour clock when no row on it shows an hour
of 13 or later and no row carries an AM/PM token. On such a day, hours inside
`pm_hours` move 12 hours later. A 24-hour day is never touched.

**The assumption.** `pm_hours` is a claim about the capture schedule, not about
timestamps: it is correct for a business-hours capture, where nothing is
recorded at 01:00 to 07:00, and it would be wrong for a 24-hour capture, where
it would silently move genuine night traffic. Hour 8 reads as 8 am only because
nothing was captured at 20:00. Set `fix_12h_clock = False` for any dataset that
is not a business-hours capture.

**The blind spot.** A day that mixes the two clocks. One genuine 24-hour row at
13:00 or later unflags the whole day, and that day's 12-hour rows stay
misparsed with nothing reporting it. The audit checks for this. If it is found
anywhere, the rule must become per-row, and the per-day rule is reverted.

Both fields are part of the split-parquet and graph cache names (suffix
`_pm1-7`), and `train()` refuses to resume a checkpoint trained under different
values. A checkpoint with no field counts as the old parse.

## The full-scale result (Cell A, Colab, 2026-10-03)

Bundle commit `0e2129d`. The installed package had the fix, and the package and
the audit script agreed on every row of every file under both parses. Verdict:
**CLEAN**. No calendar day mixes the two clocks.

| File | Rows | Hours before | Hour ≥ 12 (all noon) | Hour ≥ 13 | AM/PM tokens | Moved by the fix |
|---|---:|---|---:|---:|---:|---:|
| Tuesday | 445,909 | 1–5, 8–12 | 18,079 | 0 | 0 | 220,766 |
| Wednesday | 692,703 | 1–5, 8–12 | 23,993 | 0 | 0 | 227,337 |
| Friday-Morning (clock indeterminate) | 191,033 | 8–12 | 14,049 | 0 | 0 | 0 |
| Friday-Afternoon-PortScan | 286,467 | 1–3 | 0 | 0 | 0 | 286,467 |
| Friday-Afternoon-DDos | 225,745 | 3–5 | 0 | 0 | 0 | 225,745 |
| **Training, five files** | **1,841,857** | | | **0** | **0** | **960,315 (52.1%)** |
| Monday | 529,918 | 1–5, 8–12 | 57,941 | 0 | 0 | 222,799 |
| Thursday-Morning-WebAttacks (clock indeterminate) | 170,366 | 8–12 | 19,552 | 0 | 0 | 0 |
| Thursday-Afternoon-Infilteration | 288,602 | 1–5 | 0 | 0 | 0 | 288,602 |
| **All eight files** | **2,830,743** | | | **0** | **0** | **1,471,716 (52.0%)** |

Every `hour ≥ 12` count is noon rows only: no file has a single row at 13:00 or
later. Under the old parse, **52.1% of the training rows sat at the wrong hour.**
The training total agrees to within 11 rows with the 1,841,846 labelled rows
counted independently in the analysis report; the difference is label drops.

### The tiling: independent of any assumption

After the fix, each day's captures tile one working day, with one-minute
handoffs and no gap or overlap:

| Capture | After the fix | Under the old parse |
|---|---|---|
| Friday-Morning | 08:59 → 12:59 | 08:59 → 12:59 |
| Friday-Afternoon-PortScan | 13:00 → 15:29 | 01:00 → 03:29 |
| Friday-Afternoon-DDos | 15:30 → 17:02 | 03:30 → 05:02 |
| Thursday-Morning-WebAttacks | 08:59 → 12:59 | 08:59 → 12:59 |
| Thursday-Afternoon-Infilteration | 13:00 → 17:04 | 01:00 → 05:04 |

The single-file days do the same: Monday 08:55 → 17:01, Tuesday 08:53 → 17:00,
Wednesday 08:42 → 17:10.

This does not depend on the business-hours assumption behind `pm_hours`. The
fixed timestamps reconstruct one contiguous capture day per date. The old parse
put the afternoon captures at 01:00 to 05:04, before the morning capture of the
same day. No other reading survives that.

### Notes on the result

- **`pm_hours = [1, 7]` is not load-bearing here.** The hours present before the
  fix, across all eight files, are 1, 2, 3, 4, 5, 8, 9, 10, 11 and 12. Hours 6
  and 7 never occur, so `[1, 5]` gives an identical result and the window's two
  widest entries never fire. The business-hours assumption carries no risk on
  this dataset; the paper can say so rather than merely assume it.
- **The MIXED check is per file; the pipeline parses the pooled column.** They
  coincide here only because the global hour-≥13 count is zero. In general they
  need not: Friday is one calendar day across three files, and an hour-≥13 row
  in any one of them would unflag the pooled day, leaving both afternoon files
  misparsed while a per-file check flagged only the file holding that row. Not
  reworked, because it cannot arise on this data.
- **Monday has second resolution; the other files do not.** Monday's timestamps
  carry seconds (`08:55:58`, `17:01:34`); Tuesday to Friday are minute-only.
  Anything that assumes a uniform timestamp grid, such as the Phase 2b poll
  alignment (correction 8 in `phase2b_live_path_cost.py`), behaves differently on
  Monday than on the training files.
- **The audit's JSON files** (`timestamp_audit.json`,
  `timestamp_audit_verdict.json`) are on Drive under
  `GraphsentinalV2/retrain_fix12h/logs/`. They come into the repository with the
  retrain's result zip, at `ML/timestamp_audit.json`; the counts above are
  transcribed from the run's printed output.

## Evidence before the full-scale audit

Kept as the record of what the claim rested on before 2026-10-03.

| Scope | Result | Source |
|---|---|---|
| Mechanism | Established from the format list: a marker-less 12-hour afternoon time parses successfully as early morning. | `preprocess.py` |
| Sample, what it is | 20,000 rows, but only **19 distinct timestamp values**, in five contiguous blocks: Tuesday 10:10 to 10:15, Wednesday 10:43, Friday morning 10:42 to 10:51, Friday-Afternoon PortScan `2:55`, Friday-Afternoon DDoS `3:57`. Rows inside a block share timestamps and are not independent evidence about how a file is stamped. | `testdata/cicids2017_sample.csv` |
| Sample, what bears on the clock | **Two timestamp values:** `2:55` and `3:57`, one per Friday-Afternoon file. One observation each; the 8,000 rows carrying them are not 8,000 observations. The three morning blocks sit at hour 10 and say nothing either way, so Tuesday and Wednesday contribute nothing to the claim. | same |
| Sample, effect of the fix | 0 rows at hour 12 or later before, 0 AM/PM tokens. The fix moves 8,000 rows (those two blocks). Friday order before: PortScan 02:55, DDoS 03:57, Bot 10:42. After: Bot 10:42, PortScan 14:55, DDoS 15:57. No MIXED day. | `timestamp_audit_sample.json` |
| Five training CSVs, Monday, Thursday | **Measured 2026-10-03:** all eight files 12-hour, no AM/PM token, no hour ≥ 13 in 2,830,743 rows. See the full-scale result above. | Cell A, Colab |

## The audit, and where it runs

The CSVs are on Google Drive and training runs in Colab. They are not in the
repository and not on any development machine, so **Colab is the only place the
audit can run.**

**In Colab:** paste the whole of `ML/timestamp_audit.py` into one cell after
section 3 (the config cell) and run it. It reads the directory from
`cfg.dataset_path`, audits every CSV there, and writes `timestamp_audit.json`
to `/content/gs_logs` and to `cfg.log_path`.

**Command line**, if the files are ever local:

```
python ML/timestamp_audit.py /path/to/datasets/cicids2017
```

The script does not depend on the package for its own parse: it carries a copy,
because the package on Drive may predate the fix and importing that would audit
the old parse and report "0 rows moved". Separately, it cross-checks the
installed copy. If the package has the fix, both parses run over every real
Timestamp column and must agree row for row. If the package is stale, the run
says so, continues with its embedded copy, and tells you to re-zip and
reinstall.

It prints, per file and per calendar day under the old parse: rows, rows at
hour 13 or later, rows in the PM window, AM/PM tokens, rows the fix moves, and
min and max timestamp before and after.

| What to look for | Meaning |
|---|---|
| An "Afternoon" file with zero rows at hour 13 or later and zero AM/PM tokens | The defect is established for that file at full scale. |
| `MIXED-CLOCK DAYS: none` | No day holds both hour-13-or-later rows and PM-window rows. The per-day rule is sound for this dataset. |
| Any day flagged `MIXED` | The per-day rule is wrong for this dataset. Revert it and make it per-row. |
| `PACKAGE CHECK FAILED` | The package and the script parse the same rows differently. Resolve before retraining. |
| `STALE` | The package on Drive predates the fix. Re-zip and reinstall before retraining. |

The counts go into a follow-up commit that touches only this file and
`timestamp_audit.json`.

## Does a re-uploaded bundle invalidate Cell A's verdict?

Only if it changes what the verdict was about. From commit after `0e2129d`,
Cell A records the verdict's **basis**: a digest of the parse code
(`ML/timestamp_audit.py` and `preprocess.py`) and the name and size of every
dataset CSV. Cell B recomputes both and refuses on any difference. It does
**not** compare the bundle commit: committing the sample generator changes the
commit and nothing the audit measured.

The verdict from the 2026-10-03 run was written by an older Cell A and carries
no basis, so Cell B with a newer bundle refuses it and asks for Cell A again,
about two minutes. After that, a bundle that changes only the generator goes
straight to Cell B.

## Environment of the retrain

The epoch-31 card records torch `2.11.0+cu128` and Python only; its PyTorch
Geometric, pandas and NumPy versions are unknown. From this commit the card's
`framework` block records Python, torch, CUDA, GPU, PyTorch Geometric, pandas,
NumPy, scikit-learn and pyarrow. Cell A's runtime reported torch
`2.11.0+cu130`, PyTorch Geometric `2.8.0.post1` and pyarrow `23.0.1`; the
retrain's own card is the record. Section 8 of the analysis gains a row for the
retrain; the existing rows stay as they are, because the current numbers came
from the cu128 run.

## A retrain invalidates the evidence chain outside `ML/`

**The trap.** Retraining changes `weights.pt`. The class list and feature names
do not change, so `contract_version` stays `2.0.0`, the backend's
`EXPECTED_CONTRACT_FINGERPRINT` still matches, and **the backend boots happily
against the new weights** while every document and several code strings still
describe the old model. Nothing fails. The numbers are simply no longer about
the file on disk.

**The guard.** `tests/test_artifacts.py` fails when a file in `ML/` is not the
file `MANIFEST.json` names, when the manifest's headline numbers differ from
`test_report.json`, or when the model card names different weights. It catches
"new weights, old manifest". It cannot check prose: the list below is the rest.

## Order of operations

1. **Audit** in Colab.
2. **Add the counts** to this file (follow-up commit). If a MIXED day is
   flagged, revert the per-day rule and make it per-row first.
3. **Re-zip the package**, reinstall it in Colab, rebuild splits and graphs,
   **retrain, re-export**.
4. **Update `MANIFEST.json`.** Re-verify the weights digest and the model load
   inside the inference container. `tests/test_artifacts.py` must pass.
5. **Re-run the threshold study.** New operating points; `INTEGRATION.md` §4
   rewritten.
6. **Re-run the section 12 probes** on the test split. F2 and F6 are resolved
   either way (see the experiment below).
7. **Commit `make_testdata_sample.py`, then regenerate the sample.**
8. **Re-run the sensitivity control**, then Phase 2b only if the control moves.
9. **Rewrite** `INTEGRATION.md` §3, §4 and §10, the backend strings listed
   below, the project report and the shared page.

**Steps 1 and 3 to 8 are two Colab cells.** `ML/colab/` holds them: Cell A is
the audit and writes a machine-readable verdict; Cell B refuses to start unless
that verdict is clean, then retrains, runs the threshold study and the section
12 probes, regenerates the sample, runs the Phase 2b control, and writes one
zip with every artefact at its repository path. It is resumable by stage. See
`ML/colab/README.md`. The zip carries a regenerated `MANIFEST.json`; the
container load check in step 4, and steps 2 and 9, are done in the repository.

**The container load is the first thing done when the zip arrives, before
anything is rewritten.** It is the step most likely to stop the cascade: the
retrain saves under torch 2.11 and PyTorch Geometric 2.8 on Colab, and the
container loads under torch 2.4.0 and PyTorch Geometric 2.5.0.

It cannot run before the threshold study, because Cell B runs that study in
Colab and the container is not there. Reproducing the container inside Colab
would mean a Python 3.12 environment with torch 2.4.0, and Colab runs Python
3.13, for which torch 2.4.0 has no wheels. So the order is: threshold study in
Colab, container load first on arrival. A container failure would not
invalidate the study, which measures the model and not the loader; it would
block deploying these weights until the container's pins or the export change.

Two things lower the risk. The current weights already cross this version gap
and are recorded as loading in the container. And
`tests/test_artifacts.py::test_model_code_still_has_the_shipped_structure`
checks that today's code builds exactly the state-dict keys and shapes of those
weights: keys come from the module structure, not from the saving version.

Step 7 comes before step 8 on purpose. A control run on the old sample is
refused by the gate as soon as the sample is regenerated, because its sha256
changes.

Nothing in steps 3 to 9 moves before step 1 reports.

## What a retrain makes stale

Every number below was measured under the old parse, from the epoch-31
checkpoint of 2026-09-13. None has been regenerated.

**Regenerate** means produce it again. **Rewrite** means prose or code that
quotes numbers and must be edited by hand. **Annotate** means keep it, marked as
a pre-fix record.

| Artefact or document | Action | Step |
|---|---|---|
| `weights.pt`, `model.ts`, `model_card.json` | Regenerate | 3 |
| `MANIFEST.json` (digests and headline numbers) | Regenerate | 4 |
| `test_report.json` | Regenerate | 3 |
| `threshold_study.json`, `threshold_flow_level.csv`, `threshold_window_level.csv` | Regenerate | 5 |
| Section 12 probe tables in `GraphSentinel_Training.ipynb` | Regenerate | 6 |
| `testdata/cicids2017_sample.csv` | Regenerate | 7 |
| `phase2b_sensitivity.json` | Regenerate | 8 |
| `phase2b_results.json` | Annotate as the pre-fix record; regenerate only if the control moves | 8 |
| `timestamp_audit_sample.json` | Annotate: it describes the pre-regeneration sample | 7 |
| `GraphSage-model/` (baseline artefacts) | Not affected: the baseline was trained on the export without timestamps | none |
| `INTEGRATION.md` §1 (weights digest), §3 (measured performance), §4 (operating points), §6 (floor and confidence figures), §10 (verification status) | Rewrite | 9 |
| `RUNNING.md` (cites the weights digest check) | Rewrite | 9 |
| `backend/app/services/inference_v2.py`: the Botnet "unreliable" note and the claims list quote test F1, PR-AUC and "266 test edges" | Rewrite, and **re-derive the decision** | 9 |
| `backend/app/services/mitigation_policy.py`: rationales quote per-class test F1 and recall; Botnet is `alert_only` on the old model's numbers | Rewrite, and **re-derive the policy** | 9 |
| `backend/app/services/analysis_pipeline_v2.py`, `inference_client.py`: node-head figures in comments | Rewrite | 9 |
| The project report (`report/main.tex`, abstract and Chapter 6) | Rewrite | 9 |
| The shared analysis page | Rewrite | 9 |

`model_card.json` has no `fix_12h_clock` field. A missing field means **the old
parse**, not the default.

Ticking off the regenerate rows is not enough. The backend strings reach API
responses, and two of them encode decisions (Botnet is unreliable; Botnet is
never enforced) that were made from the old model's numbers.

## Outstanding experiment: does the fix change F2 and F6?

**Hypothesis, untested.** The misordered time is a shared root cause of two
negative findings: that zeroing the numeric edge features *raises* macro-F1
(F6), and that turning the host memory off raises it (F2). Wrong time order
corrupts the two time-gap edge features and the order in which host history
and memory are warmed. F1, the untrained GRU, does not depend on it.

**What cannot test it: the Phase 2b sample.** A scratch re-run of the
sensitivity control under the fixed parse still showed `argmax_changed: 0`.
That is not evidence against the hypothesis, or for it. Zeroing all twenty edge
features changed 0 of 15,833 predictions before the fix as well. The 0 is a
property of the sample, not of the parser.

**What does test it:** step 6. Today, pre-fix, over 227,325 test edges:

| Probe | Edge macro-F1 | Change |
|---|---:|---:|
| Full model | 0.7042 | |
| 20 numeric edge features zeroed | 0.7998 | +0.0956 |
| Memory reset every window | 0.8312 | +0.1270 |

| Outcome after the fix | Reading |
|---|---|
| The +0.0956 shrinks or reverses | The hypothesis holds for F6, and F6 must be rewritten. |
| The +0.0956 survives | F6 is a much stronger finding than it is today. |
| The +0.1270 changes size | Expected to some degree; F2's direction is what matters, since the GRU stays untrained. |

## The Phase 2b gate

The gate in `phase2b_live_path_cost.py` used to compare three file digests:
sample, weights, model card. None of them moves when the parse changes, because
the sample's bytes do not change. A control recorded under the old parse would
have certified a post-fix run on graphs it never saw.

- `phase2b_sensitivity_check.py` now records `preprocessing_sha256`: one digest
  over the `cfg.data` and `cfg.graph` fields that shape the graphs
  (`preprocess.preprocessing_digest`), with the settings beside it. The digest
  is taken over a canonical serialisation (sorted keys, fixed number
  formatting, lists and tuples alike), so it moves only when a setting moves.
- The gate compares it and refuses on mismatch or absence.
- `phase2b_results.json` carries the same digest, and the script refuses to
  replace a record made under different settings without `--overwrite`.

The existing `phase2b_sensitivity.json` is pre-fix and has no digest, so the
gate now refuses it.

## Also in this change

**Writes outside the repository.** `train()` mirrored its log and test report
to `/content/gs_logs` with an unconditional `mkdir(parents=True)`. Off Colab
that is a directory at the filesystem root (`C:\content` on Windows). All three
mirrors now go through `graphsentinel/utils/scratch.local_scratch`:

| `GRAPHSENTINEL_LOCAL_MIRROR` | Behaviour |
|---|---|
| unset | mirror only if `/content` already exists |
| `1` | mirror, creating `/content` if needed |
| `0` | never mirror |

**`train()` is now exercised.** `tests/test_train_smoke.py` runs one epoch on
synthetic traffic: cache names, selection, log and report writes, a finished-run
resume, the resume guard, and export. With the old unguarded line put back, it
fails, naming `C:\content`.

**Two defects in the test suite itself**, both found by that smoke test:

- `test_fsync_never_leaks_a_descriptor_when_it_raises` patched `os.fsync` to
  raise and "restored" it from `os.fsync`, that is, from its own stub. `fsync`
  then raised for every later test in the process. See the review note for
  what that did and did not hide. It now uses `monkeypatch`, and
  `test_no_test_patches_a_module_by_hand` forbids the shape.
- Three tests exported full-size models into `tempfile` directories that are
  never cleaned up: about 145 MB per test per run, 3.6 GB after two days of
  runs, which filled a disk. The three were
  `test_model_card_labels_which_split_its_metrics_came_from`,
  `test_engine_refuses_a_card_whose_class_list_does_not_match` and
  `test_fsync_never_leaks_a_descriptor_when_it_raises`, all introduced in
  commit `6b9160c`. They now use `tmp_path` and a small memory table, and
  `test_no_test_leaks_a_temp_directory` forbids the call. Both new scans were
  run against the file as it stood before the fix: they flag lines 1376, 1401
  and 1439 (the leaks) and 1456 and 1464 (the patch and its bad restore).

**The suite baseline is now 136 passed, 0 skipped** (2026-10-03). Earlier records say
"98 passed, 7 skipped". The seven skips were the tests that need `pyarrow`: the
split and graph construction tests. On the machine those records come from,
the split code had therefore never run at all. With `pyarrow` installed they
run, and they run under the fixed parse. Do not read "98 passed, 7 skipped" as
the baseline.

**A flaky guard, fixed by asserting the claim it names.**
`test_graph_builder_beats_the_v1_row_loop` asserted a ratio against the v1 row
loop and also an absolute floor of 150,000 flows/s. The floor failed about half
the time on a loaded machine with the builder unchanged: over five runs the
absolute rate ranged from 105,000 to 189,000 flows/s. The floor was removed,
not raised or lowered. The test's claim is the ratio, measured against the v1
loop in the same process under the same load, now as the best of three timings
for each half: 29x to 44x over five runs, against a bar of 20x.

## Review note: check the guard against the failure that prompted it

After writing a guard, check that it would have caught the specific failure it
was written for. In this project it has not been obvious in the moment:

- an encoding scan covered `graphsentinel/` only, and could not have caught the
  failure that prompted it, which was in `tests/`;
- an overwrite warning printed immediately before the write, and could not have
  prevented the overwrite it warned about;
- a suite-wide `/content` fixture guarded tests that never ran the code path
  the bug lived in.

Each was written from the symptom, not from the path.

**A fourth, and worse: a guard that created a bug.**
`test_fsync_never_leaks_a_descriptor_when_it_raises` was written to prove that
`export._fsync_path` cannot leak a file descriptor on Windows. It did prove
that. It also left `os.fsync` raising for the rest of the process, by restoring
it from its own stub, and nothing noticed for weeks.

What a raising `fsync` does depends on the caller:

| Caller | With `fsync` raising |
|---|---|
| `export._fsync_path` | Swallows `OSError` by design: a silent no-op. |
| `train._atomic_torch_save` | Does not swallow it: the write fails, and `save_checkpoint` reports no write. |

What it hid, measured rather than assumed:

- In the suite as committed, the test was 67th of 68 in `test_pipeline.py`. One
  test ran after it in that file, a source scan that writes nothing. Then
  `test_recon.py`, which never calls the export or checkpoint paths.
  `test_export_inference.py` and every export and checkpoint test in
  `test_pipeline.py` ran **before** it, under the real `fsync`.
- So the Windows write fix and the atomic checkpoint save were validated under
  the real `fsync` all along. The poisoning had an empty blast radius, by luck
  of test ordering and nothing else. The first test added after it that wrote a
  checkpoint, the `train()` smoke test, failed.
- Confirmed directly on 2026-10-02, Windows, each in a fresh process:

| Run | Result |
|---|---|
| Full suite with the fsync test deselected | 119 passed |
| Export and checkpoint tests only, fsync test deselected | 20 passed |
| Full suite | 120 passed |

The write path stands on its own merits.

**The finding is the luck, not the clean result.** The suite carried an order
dependency that nobody had declared. It passed only because no test that wrote
a checkpoint ran after position 67. Adding one such test, or running the suite
in random order, would have broken it, and the failure would have pointed at
the new test, not at the one that leaked. `monkeypatch` removes the dependency
instead of documenting it. The general lesson is separate from the one above:
a suite that passes in one order has shown nothing about the other orders, and
a test that changes shared state must be unable to leave it changed.

The guards added in this change were each run against the original failure:
the `/content` scan asserts it flags the old line, the manifest guard has a
test that swaps the weights, the smoke test was run with the old line restored,
and the two test-hygiene scans were run against the pre-fix test file.

The backend suite was searched for the same shape. It has none: its manual
save-and-restore sites capture the original before changing it, mocks go onto
fresh instances, and an autouse fixture resets the shared singletons after
every test.

## The sample

Within one file the old parse is a uniform shift, so each block of the sample
is internally monotonic and the per-block window search was unaffected. The
concatenated sample was not in true chronological order: the Friday-Afternoon
PortScan and DDoS blocks sorted before the Friday-Morning Botnet block.
`HostHistory` was warmed in that order and the `dt` features at block seams
were wrong.

`make_testdata_sample.py` has never been in this repository; it exists only as
a file held outside it. It should be committed to `ML/`, and the sample
regenerated with it after the retrain (step 7). A sample nobody can rebuild is
weaker provenance than no sample.
