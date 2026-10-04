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

### 5. B05 — record the submission hash before waiting for a receipt

Decision already taken: record the transaction hash at submission, before any
receipt wait; return it with `pending`; the reconciler looks it up. Three tests
go with it. Audit item B05 in `AUDIT_2026-10-04.md`.

### 6. B17, B19, B20 — frontend state

As listed in `AUDIT_2026-10-04.md`.

### 7. The B08 result onto the shared page

`MODEL_BEHAVIOUR.md` §1.2, including the source-level paragraph added on
2026-10-04.

### 8. The Colab pass, Cell A first

`ML/colab/`.

### 9. `UNRELIABLE_CLASSES`

### 10. `reference.bib`

### 11. Code comments cite `Error.md` by bare file name

The four historical documents moved to `docs/archive/` on 2026-10-04. Roughly
seventy files cite the tracker as `Error.md #29`, by name, not by path, and were
left as they are; `README.md` says where the file lives and the guard requires
`docs/archive/Error.md` to exist. Rewriting the citations is optional.

---

## Closed on 2026-10-04

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
