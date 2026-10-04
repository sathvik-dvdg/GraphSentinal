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

### 1. Look at four things in a browser

None of these has been seen rendered; each was compiled, linted and, where it has
logic, unit-tested (`node --test tests/unit/triage.test.js` from `frontend/`).

- **The header badge.** Reads `ml_v2` from `/health`: `v2: DRY-RUN`, `v2: OFF` on
  the `docker-compose.v1.yml` path, `v2: NO ANSWER`, `v2: UNKNOWN` before
  `/health` answers. The text has to stand alone; a tooltip is invisible on a
  projector. One screenshot on each compose path.
- **B17.** A blocked alert with no triage now reads `open` in the Alert Centre,
  with a separate `Host blocked` marker beside its status.
- **B19.** Resolve an incident in Forensics, reopen it on the server, and confirm
  it reappears on the next poll.
- **B20.** Sign in as a non-admin: Block, Unblock and Isolate are disabled with
  the reason in text under the button.

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

### 4. The Mininet run

The prerequisite for v2 ever acting on a flow, not only the last unverified link
(`MODEL_BEHAVIOUR.md` §1.1, §1.3). Needs Linux or WSL2 with Mininet and OVS;
`RUN_GUIDE.md` §11.

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
