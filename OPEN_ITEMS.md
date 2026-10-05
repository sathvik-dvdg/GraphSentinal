# GraphSentinel — Open Items

Work that has been decided and is not done. This file exists because that list
used to live in a chat log, and a session that did not have the log started
blind. **Update it in the same commit that closes or opens an item.** The
figures guard (`ML/graphsentinel_v2/tests/test_figures_guard.py`) fails if this
file is missing.

Measured numbers are not restated here; each item cites the section of
`MODEL_BEHAVIOUR.md` that owns them.

Last updated: 2026-10-05.

---

## Open

### 1. Look at the frontend in a browser

Nothing below has been seen rendered. Each was built, linted against the
baseline and, where it has logic, unit-tested (`node --test tests/unit/*.test.js`
from `frontend/`; 16 tests).

- **The header badges.** `BLOCKS: v1 MODEL` with `v2: DRY-RUN` / `OFF` /
  `NO ANSWER` / `UNKNOWN`; and the connection badge: `LIVE`, `RECONNECTING…`,
  `CONNECTION LOST — RETRYING`, `LIVE (POLLING) — SOCKET RETRYING`, `OFFLINE`.
  The longer labels may wrap or crowd the top bar.
- **Stop the backend while the dashboard is open.** The badge should leave
  `LIVE` within one poll, the panels should keep their last data marked stale
  with the reason (`HTTP 500` / `no answer`), and the socket should keep retrying.
- **B17, B18, B19, B20.** A blocked alert reads `open` with a `Host blocked`
  marker; a triage click does not flicker back; a reopened incident reappears;
  a non-admin sees Block, Unblock, Isolate, the threshold Save and Reload Model
  disabled with the reason in text.
- **Simulate Attack.** Absent on Forensics, Audit & Ledger and Timeline;
  disabled with its reason on a live backend.
- **The colour refactor.** 661 hex literals became references to
  `src/constants/colors.js` with the same values, so nothing should look
  different. One exception: a note colour in the node inspector moved from
  `#6b7280` to the subtle text grey.
- **The shell notices.** The first-load skeleton, and the truncation banner on
  the two graph pages.

### 2. The backend health window has not been checked under load

`docker-compose.yml` gives the backend 180 seconds to turn healthy. That was
chosen on an idle machine, as the 75 it replaced was. `RUN_GUIDE.md` §4 now says
so. Still open: start the stack while the machine is busy and record how long
the backend takes.

### 3. The recording

`RUN_GUIDE.md` names `docs/demo/verify_stack_run.mp4`, which does not exist. It
does not need the dashboard:

```
docker compose up -d blockchain inference backend
```

Three services, no browser, no Vite, and all ten checks, since none touches the
frontend. Record the terminal through `docker compose ps` and
`python ML/verify_stack.py`. A person has to do this.

### 4. On live OVS flows v2 is wrong, and the cause is not separated

Three live runs on 2026-10-05 (`MODEL_BEHAVIOUR.md` §1.3, §9 item 21). The
mechanism works. The model does not: half the flows of a benign-only window are
predicted as attacks, the wrong predictions are confident enough to clear the
floor, and the admitted rules land on benign web fetches.

Three candidate causes. State of each:

1. **The flood's shape — tested, run 3.** One conversation is one edge of the
   graph whatever its packet count; a CICIDS2017 flood is many flows converging
   on a victim. Sent as many conversations the flood did receive rules. That is
   **not** a detection: benign fetches to the same port received rules at the
   same confidence. What the test established is that a single-conversation flood
   is invisible to this model by construction; it did not establish that a
   many-conversation flood is recognised.
2. **Re-submission — counted, not removed.** A conversation is submitted once per
   poll while it stays in the table; the factor per window is in
   `ML/live_loop_run3.json`. It inflates every conversation alike, so it cannot
   explain a missed flood. Still to do: replay
   `ML/retrain_logs/live_loop/daemon_responses_run3.txt` through `flow_parser`
   with each conversation submitted once, and see whether benign fetches are
   still labelled attacks. No live run needed.
3. **Features — listed, not measured.** An OVS dump fills half of the model's
   edge features; the rest are pinned or zero (`flow_mapping.py`,
   `MODEL_BEHAVIOUR.md` §1.3). Still to do, and it needs no live run either:
   score the committed sample with those features forced to their OVS values,
   as `ML/b08_ovs_constants_check.py` does for v1. This is the most likely
   place the benign-as-attack labelling comes from and it is the next step.

Also still to do: ground truth written by the traffic script per conversation, so
results are counted rather than read from a log; and more than three runs before
any rate is quoted.

**Do not move the 0.90 floor on this evidence.** Wrong rules cleared it, on three
runs of one hand-written script on one topology. Raising it now would be fitting
an operating point to an anecdote. Measure 2 and 3 first.

No claim that v2's rules are right on live traffic, and `dry_run` stays true.

### 5. B05's remaining window — a timeout before broadcast

B05 is fixed for a write that times out **after** it was broadcast (see Closed).
Not closed: if the adapter's timeout fires **before** the client has broadcast,
the adapter returns no hash, the worker thread may broadcast afterwards, and the
incident is retried.

**Intended approach: make the consumer idempotent. Do not change the client's
send path.** Before the reconciler resubmits a row that has no hash, it looks for
an on-chain incident with the same `forensicsURI` (`local://incident/<id>`) and
adopts it if one exists. The contract accepts duplicates for one URI and
`/forensics` already enumerates incidents, so the lookup exists. It is O(N):
unacceptable on a request path (audit B10), acceptable in the scheduled
reconciler, and it can scan recent incidents only. This closes the window for any
cause, not only the race between the timeout and the broadcast.

### 14. Frontend decisions that were not made

Found while doing the frontend pass of 2026-10-05; each needs a person, most
need a browser.

- **Simulate Attack is now disabled against a live backend.** That was the
  instruction, and it follows from the rule that synthetic flows must not enter
  the real incident record. The consequence: with `VITE_USE_MOCK` unset there is
  no way to trigger a demo incident from the dashboard; it needs Mininet
  traffic. If the demo depends on the button, this has to be revisited.
- **The landing page states figures the project does not claim.** A detection
  accuracy and a sub-second isolation time appear as marketing copy
  (`frontend/src/pages/LandingPage.jsx`). `MODEL_BEHAVIOUR.md` §10 says latency
  has not been measured and scopes every accuracy figure. The figures guard does
  not scan `.jsx`. Left as written; it is the authors' copy.
- **Two palettes.** The pages draw with one red, grey and green
  (`danger`, `textSubtle`, `success`) and the Tailwind tokens define others
  (`gs-threat`, `gs-muted`). Both are now named in `constants/colors.js`;
  merging them changes how the app looks.
- **The timed splash.** `AppShell` shows a full-page loading screen for a fixed
  1.8 s regardless of whether anything is loading.
- **The topology scaffold.** `utils/topologyScaffold.js` draws a controller and a
  switch that the backend does not report, marked `source: 'configured'`, around
  the hosts it does report. It adds no hosts and draws nothing when the backend
  returns none. Whether configured infrastructure counts as "not from the API"
  is a judgement; it was kept.
- **Per-panel skeletons.** The first-load skeleton is one strip from the shell,
  not a skeleton shaped like each page's panels.
- **Tailwind utility fallbacks in `globals.css`.** Eighteen hand-written
  spacing utilities (`mt-1`, `p-2`, ...) are unused by name but were kept: they
  are utility names, and the file says they work around a Tailwind 4 regression.

### 13. The monitor keeps nothing of a scored window

`_score_v2` discards the rules and verdicts `score_flows` returns; only counters
reach `/health`. The first live run could not say which flows its rules were on.
The per-rule log lines added on 2026-10-05 are the only record. If rules are ever
to drive anything, they need to be kept somewhere a person or a test can read.

### 6. A second `live_rule_check.py` run against the same service gives a different answer

Found on 2026-10-05 and not investigated. Against a freshly started inference
service the script scores the committed sample as the documented number of
windows. Run **again against the same running process**, it reported one window
and one rule. `ML/live_rule_check.json` is the first run. Until this is
understood, restart the inference service before `python ML/verify_stack.py` if
checks 8 and 9 are to show the documented counts, and say so in `RUN_GUIDE.md`
§6 once the cause is known.

### 7. Keep the shared page in step with `MODEL_BEHAVIOUR.md`

The shared page is the artifact "GraphSentinel ML — Technical Analysis":
<https://claude.ai/artifact/RjvjQqf7DYjQNyxP9cRytt>. It restates figures the
guard cannot see, so any change to §1.2, §6 or §9 has to be carried there by
hand. **As of 2026-10-05 it is in step**: it carries the source-level v1 result
with the six-host caveat first, the false-flag reading of the Bot rows on
OVS-shaped input, PortScan as alert-only, and the Botnet non-claim. Its title and
gallery name read rev. 3.

### 8. The Colab pass, Cell A first

`ML/colab/`.

### 9. The report still describes PortScan as enforceable

`report/main.tex` describes the policy's confidence floors for PortScan and
BruteForce. PortScan is `alert_only` since 2026-10-05; the report has not been
changed.

### 10. `reference.bib`

`report/main.tex` loads `reference.bib` and cites `paper1` to `paper10`; no
`.bib` file is tracked, so the report does not build its bibliography from a
clone. Only the author knows which ten papers these are.

### 11. Code comments cite `Error.md` by bare file name

The four historical documents moved to `docs/archive/` on 2026-10-04. Roughly
seventy files cite the tracker as `Error.md #29`, by name, not by path, and were
left as they are; `README.md` says where the file lives and the guard requires
`docs/archive/Error.md` to exist. Rewriting the citations is optional.

---

## Closed on 2026-10-05

- **The loop shows itself from the log.** The backend prints its `graphsentinel.*`
  INFO lines by default; the provenance gate logs admissions as it logs refusals;
  the daemon can record its own responses (`DAEMON_DUMP_LOG`). Tests in
  `backend/tests/test_v2_loop_visibility.py`. Run 3 used all three.
- **§10's binary claim is scoped** to the offline CICIDS2017 test set, with the
  non-claim that it does not transfer to live OVS input beside it.
- **Route A (Colab) is closed without being run.** Route B worked; the backend's
  dependencies were not checked on Colab's Python.
- **Working files of the live runs.** Everything a run depends on is in
  `ML/retrain_logs/live_loop/`, including the scripts that assembled the evidence.
  `C:\dev\gs_live` on the development machine still holds the originals plus
  three throwaway SQLite databases and service logs; it is not tracked and
  nothing depends on it.

- **The Mininet run: the backend's ingestion path, end to end, on real OVS flows.**
  Live, not replayed, in WSL2 with the OVS kernel datapath and the repository's
  own topology and daemon, unmodified. No poll failed, the provenance gate
  refused nothing, no window was unscored, and the backend logged its own admitted
  and withheld lines. Evidence: `ML/retrain_logs/live_loop_run.txt`,
  `ML/live_loop_run.json`, `ML/retrain_logs/live_loop/`. What the rules were made
  on is open item 4. Open vSwitch, Mininet, hping3 and nmap are now installed in
  this machine's Ubuntu WSL distribution; how to run it again is `RUN_GUIDE.md` §7.

- **PortScan is `alert_only`**, floor unchanged; BruteForce stays enforceable.
  The decision, and that it suppresses less than the one first approved, is
  recorded in `backend/app/services/mitigation_policy.py` and
  `MODEL_BEHAVIOUR.md` §6. Re-run on the manual path: all ten checks, the same
  rules admitted. This was listed as "`UNRELIABLE_CLASSES`"; the mechanism is the
  policy, not that constant.
- **B17, B19, B20** implemented as decided: a blocked alert with no triage is
  open; the server's incident state wins and the local overlay is cleared on
  every successful fetch; the role is stored and enforcement controls are
  disabled with a reason for a non-admin, and a refused request is shown, not
  only logged. Rules in `frontend/src/utils/triage.js`, six unit tests. Visual
  confirmation is open item 1.
- **`MODEL_BEHAVIOUR.md` §1.2** says in words that the Bot rows over the
  threshold on OVS-shaped input are false flags, not detections.
- **`AUDIT_2026-10-04.md` Part 1** carries B05's fix and its remaining window.

## Closed on 2026-10-04

- **B05, after broadcast.** The chain client reports the transaction hash as soon
  as it has broadcast; the adapter returns that hash with `pending` when its own
  timeout fires; the reconciler looks it up. Three tests in
  `backend/tests/test_b05_broadcast_hash.py`, each failing before the fix; the
  third reproduced the double write. Open item 5 is what is left.
- **Check 10 on the manual path.** With `backend/.env` at the tracked values,
  `python ML/verify_stack.py` on the manual path passed all ten checks.
- **Both models are blind to Botnet traffic.** Recorded as a limitation and as a
  non-claim in `MODEL_BEHAVIOUR.md` §9 and §10.
- **The registry's last figure has its artefact**, read from the confidence table
  in `ML/split_composition.json`.
- **`docs/archive/README.md`** says where the four files came from and records the
  citation count and how it was taken.

- **Source-level base rate for v1.** Measured and written into
  `MODEL_BEHAVIOUR.md` §1.2; the population counts are in
  `ML/b08_ovs_constants.json` under `source_population`.
- **`verify_stack.py` checks 5 and 6 passed with no model loaded.** They, and the
  other checks with a real "cannot tell" case, now report `UNVERIFIABLE`, which
  counts against the exit code.
- **`verify_stack.py` failure modes.** Connection refused, a hung service and a
  body that is not a JSON object are each reported, not raised; one test each in
  `ML/graphsentinel_v2/tests/test_verify_stack.py`.
- **Named-figure registry.** `ML/named_figures.json`: bare integers by key, each
  held to its artefact and to the phrase every file states it in.
- **Dashboard badge reads `ml_v2.enabled`.** Code only; see open item 1.
- **Historical documents archived.** `DATAFLOW.md`, `INTEGRATION_GUIDE.md`,
  `Error.md` and `decisions.md` are in `docs/archive/`.
- **`backend/.env` on the development machine** set to the tracked threshold and
  `simulated`. That file is not tracked, so this is a note, not a commit.

---

## Standing rules these items produced

- **Do not bulk-delete markdown and add a `*.md` ignore rule in one change.** The
  rule makes `git add` of a restored file do nothing, silently, so the restore
  appears to work and commits nothing.
- **An item that points at something outside the repository names it here.** A
  URL, a page, a person. Three items stalled because their target or intended
  behaviour was only in a chat log.
- **Do not put backslashes in a shell heredoc.** A command in this file lost a
  backslash and gained a control character that way. Paths in markdown use
  forward slashes, which PowerShell accepts.
- **To find what removed a file, use `git log --full-history -- <path>`.** Plain
  `git log -- <path>` can omit the removing commit. Check `git status` first: a
  staged, uncommitted deletion has no commit at all.
- **A health window, a throughput floor or a timeout chosen on an idle machine
  says so where it is documented.**
