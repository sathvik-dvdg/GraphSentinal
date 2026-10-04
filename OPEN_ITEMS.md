# GraphSentinel — Open Items

Work that has been decided and is not done. This file exists because that list
used to live in a chat log, and a session that did not have the log started
blind. **Update it in the same commit that closes or opens an item.** The
figures guard (`ML/graphsentinel_v2/tests/test_figures_guard.py`) fails if this
file is missing.

Measured numbers are not restated here; each item cites the section of
`MODEL_BEHAVIOUR.md` that owns them.

Last updated: 2026-10-04.

---

## Open

### 1. Look at the dashboard badge in a browser

The header badge now reads `ml_v2` from `/health` and shows `v2: OFF` on the
`docker-compose.v1.yml` path, `v2: NO ANSWER` when the inference service is
unreachable, and `v2: UNKNOWN` until `/health` has answered
(`frontend/src/components/ui/DetectionPathBadge.jsx`). **It has only been
compiled, never looked at.** One screenshot of each compose path settles whether
it renders, wraps or truncates. The text has to stand alone, because a tooltip is
invisible on a projector.

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
`python ML\verify_stack.py`. A person has to do this.

### 4. The Mininet run

The prerequisite for v2 ever acting on a flow, not only the last unverified link
(`MODEL_BEHAVIOUR.md` §1.1, §1.3). Needs Linux or WSL2 with Mininet and OVS;
`RUN_GUIDE.md` §11.

### 5. B05's remaining window — a timeout before broadcast

B05 is fixed for a write that times out **after** it was broadcast (see Closed).
Not closed: if the adapter's timeout fires **before** the client has broadcast
(slow signing or gas estimation), the adapter still returns no hash, the worker
thread cannot be stopped and may broadcast afterwards, and the incident is
retried. Closing it needs the client to check, immediately before sending,
whether its caller has already given up. Not attempted; it changes the client's
send path and wants a decision first.

### 6. B17, B19, B20 — frontend state

As listed in `AUDIT_2026-10-04.md`. Each changes what an operator sees and none
has a recorded decision on the intended behaviour: whether a blocked alert with
no triage reads as open or resolved (B17), whether the server's status overrides
a locally resolved incident on the next poll (B19), and what the dashboard shows
a user whose role may not block (B20). There is no frontend unit-test harness, so
these also need a browser to verify.

### 7. The B08 result onto the shared page

`MODEL_BEHAVIOUR.md` §1.2, including the source-level paragraph added on
2026-10-04. **Which page is not recorded in the repository.**

### 8. The Colab pass, Cell A first

`ML/colab/`.

### 9. `UNRELIABLE_CLASSES`

`backend/app/services/inference_v2.py`. **What is to be done to it is not
recorded in the repository**; it currently names Botnet only.

### 10. `reference.bib`

`report/main.tex` loads `reference.bib` and cites `paper1` to `paper10`; no
`.bib` file is tracked, so the report does not build its bibliography from a
clone.

### 11. Code comments cite `Error.md` by bare file name

The four historical documents moved to `docs/archive/` on 2026-10-04. Roughly
seventy files cite the tracker as `Error.md #29`, by name, not by path, and were
left as they are; `README.md` says where the file lives and the guard requires
`docs/archive/Error.md` to exist. Rewriting the citations is optional.

---

## Closed on 2026-10-04

- **B05, after broadcast.** The chain client reports the transaction hash as soon
  as it has broadcast; the adapter returns that hash with `pending` when its own
  timeout fires; the reconciler looks it up. Three tests in
  `backend/tests/test_b05_broadcast_hash.py`, each failing before the fix; the
  third reproduced the double write. Open item 5 is what is left.
- **Check 10 on the manual path.** With `backend/.env` at the tracked values,
  `python MLerify_stack.py` on the manual path passed all ten checks.
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
- **To find what removed a file, use `git log --full-history -- <path>`.** Plain
  `git log -- <path>` can omit the removing commit. Check `git status` first: a
  staged, uncommitted deletion has no commit at all.
- **A health window, a throughput floor or a timeout chosen on an idle machine
  says so where it is documented.**
