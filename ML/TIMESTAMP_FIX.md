# The 12-hour clock fix, and which artefacts predate it

**Status.** The fix is committed. The full-dataset audit is **outstanding**: it
can only run in Colab. Nothing has been retrained. Every model artefact in this
directory predates the fix.

## The defect

The claim that CICIDS2017's afternoon rows are stamped on a 12-hour clock with
**no AM/PM marker** currently rests on **two timestamp values**: `7/7/2017 2:55`
(Friday-Afternoon PortScan) and `7/7/2017 3:57` (Friday-Afternoon DDoS). That is
one observation per file, not two independent sources. Whether those files are
stamped that way throughout, and whether any other file is, is outstanding (see
the audit).

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

## Evidence so far

The audit is **load-bearing, not confirmatory.** The sample evidence is thin.

| Scope | Result | Source |
|---|---|---|
| Mechanism | Established from the format list: a marker-less 12-hour afternoon time parses successfully as early morning. | `preprocess.py` |
| Sample, what it is | 20,000 rows, but only **19 distinct timestamp values**, in five contiguous blocks: Tuesday 10:10 to 10:15, Wednesday 10:43, Friday morning 10:42 to 10:51, Friday-Afternoon PortScan `2:55`, Friday-Afternoon DDoS `3:57`. Rows inside a block share timestamps and are not independent evidence about how a file is stamped. | `testdata/cicids2017_sample.csv` |
| Sample, what bears on the clock | **Two timestamp values:** `2:55` and `3:57`, one per Friday-Afternoon file. One observation each; the 8,000 rows carrying them are not 8,000 observations. The three morning blocks sit at hour 10 and say nothing either way, so Tuesday and Wednesday contribute nothing to the claim. | same |
| Sample, effect of the fix | 0 rows at hour 12 or later before, 0 AM/PM tokens. The fix moves 8,000 rows (those two blocks). Friday order before: PortScan 02:55, DDoS 03:57, Bot 10:42. After: Bot 10:42, PortScan 14:55, DDoS 15:57. No MIXED day. | `timestamp_audit_sample.json` |
| Five training CSVs, Monday, Thursday | **OUTSTANDING.** | the Colab audit |

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

**The suite baseline is now 120 passed, 0 skipped.** Earlier records say
"98 passed, 7 skipped". The seven skips were the tests that need `pyarrow`: the
split and graph construction tests. On the machine those records come from,
the split code had therefore never run at all. With `pyarrow` installed they
run, and they run under the fixed parse. Do not read "98 passed, 7 skipped" as
the baseline.

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
