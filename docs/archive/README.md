# docs/archive

Historical documents. They are kept because other files cite them, not because
they describe the system as it is now. For the current system start at
`RUN_GUIDE.md` and `MODEL_BEHAVIOUR.md` in the repository root.

**These four files sat in the repository root until commit `aaff4fb`
(2026-10-04).** Anything that refers to one of them by bare name — a code
comment saying `Error.md #29`, an older document saying "see `decisions.md`" —
means the file in this folder.

| file | what it is |
|---|---|
| `Error.md` | The numbered issue tracker. Code comments, tests and migrations cite its entries as `Error.md #N` or `Error.md H5`, `N2`, `U4` and so on. |
| `decisions.md` | The decision log that goes with the tracker; cited as `decisions.md #N, Option A`. Restored from history at commit `6b33ead` and historical as of that commit. |
| `INTEGRATION_GUIDE.md` | The frozen v1 integration contract: API shapes and schemas. The current v2 wiring is `INTEGRATION.md` in the root. |
| `DATAFLOW.md` | The v1 architecture and data flow. |

## How many files cite the tracker

Counted with `git grep -lF 'Error.md'` over tracked files at commit `8a4a1cf`,
the last commit before the move: **72 files**, the tracker itself included. By
extension: 28 `.jsx`, 24 `.py`, 12 `.js`, 3 `.md`, and one each of `.cjs`,
`.css`, `.yml`, `.env.example` and `.env.docker`. Of the 72, 48 cite a numbered
entry in the form `Error.md #N`; the rest use a lettered entry or name the file
without an entry.

An earlier count of 38 was reported for the same thing. It is not recorded in
the repository and no single filter reproduces it. The nearest is 37, the
`.py`, `.js` and `.cjs` files, which is the full count without the 28 `.jsx`
components and the seven non-code files, so the likeliest explanation is a
search whose file-type filter did not include `.jsx`. That is an inference, not
a finding: the original command is not available to re-run.

The citations were left as they are. The figures guard
(`ML/graphsentinel_v2/tests/test_figures_guard.py`) fails if any of the four
files, or this one, is missing.
