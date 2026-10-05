# Start here

For Susheep, Sairaj and Skanda. Do the steps in order. Steps 1 to 3 are the
same for all three of you; step 4 is your own file.

---

## 1. Switch to the working branch

All current work is on `fix/audit-p0-p1`. Do not work on `main`.

```bash
git fetch origin
git switch fix/audit-p0-p1
git pull
```

Then check you have what you need:

```bash
ls docs/handover/        # START_HERE.md FRONTEND.md BACKEND.md BLOCKCHAIN.md
ls scripts/check_env.sh
```

One file is **not in git** and you must get it from Sathwik directly:
`ML/weights.pt` (the v2 model, gitignored). Put it at exactly that path. Without
it the v2 inference service never becomes healthy.

Create the two local environment files (also not in git):

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

---

## 2. Test your environment

In a WSL or Linux terminal, from the repository root:

```bash
bash scripts/check_env.sh --no-install --no-build
```

This changes nothing. It prints one line per check and a summary table.

- **Exit code 0, nothing under FAILED:** your machine can run the project
  directly. Go to step 4.
- **Anything under FAILED:** choose one of the two options in step 3.

Send Sathwik the summary table if you are unsure which option fits.

---

## 3. If the check fails: two options

### Option A: run it in Docker (quickest)

Use this if you only need the stack running and do not want to change your
machine. You need Docker Desktop and nothing else from the check.

From the repository root, in PowerShell. Build **one image at a time**; building
all four together has crashed on a low-memory machine.

```powershell
docker compose build inference
docker compose build blockchain
docker compose build backend
docker compose build frontend

docker compose up -d
docker compose ps        # wait until all four say healthy
```

| Service | Address |
|---|---|
| Dashboard | http://localhost:5174 |
| Backend | http://localhost:8001 (`/health` to check) |
| Inference (v2) | http://localhost:8081 |
| Ganache | http://localhost:8546 |

Sign in with `admin` / `change-me-for-demo`.

**What Docker cannot do.** There is no Mininet inside Docker. The backend shows
synthetic demo traffic instead, and v2 refuses to score it. That is fine for
frontend and blockchain work. It is **not** enough for Mininet, the demo
attacks, or anything about live traffic: for those use Option B.

**When you must update the images.** Most source code is mounted into the
containers, so most edits need no rebuild.

| You changed | Do this |
|---|---|
| `frontend/src/**`, `frontend/public/**` | Nothing. The browser reloads by itself. |
| `backend/app/**`, `backend/migrations/**` | `docker compose restart backend` |
| `ML/model_card.json`, `ML/weights.pt`, other files in `ML/` | `docker compose restart inference backend` |
| `backend/requirements.txt`, `backend/Dockerfile`, `backend/docker-entrypoint.sh` | `docker compose build backend` then `docker compose up -d backend` |
| `frontend/package.json`, `package-lock.json`, `tailwind.config.js`, `vite.config.docker.js`, `postcss.config.js`, `index.html`, `frontend/Dockerfile` | `docker compose build frontend` then `docker compose up -d frontend` |
| `ML/graphsentinel_v2/graphsentinel/**` (the v2 package), its `requirements.txt`, `docker/inference.Dockerfile` | `docker compose build inference` then `docker compose up -d inference` |
| `blockchain/contracts/**`, `blockchain/scripts/**`, `blockchain/package.json`, `blockchain/Dockerfile` | `docker compose build blockchain` then `docker compose up -d blockchain`, then `docker compose restart backend` |
| `docker-compose.yml`, `.env.docker` | `docker compose up -d` (it recreates what changed) |

Rule of thumb: **after every `git pull`, look at which files changed** (`git
diff --stat HEAD@{1}`) and apply the row that matches. If you are not sure,
rebuild that one service. A changed contract needs a fresh chain to redeploy:
`docker compose down`, then remove only the `ganache-data` and `contract-shared`
volumes. Do not use `docker compose down -v` casually: it also wipes the
backend's database.

### Option B: fix the versions and run it directly

Use this if you need Mininet, or you will be working on the code daily.

```bash
sudo -v                          # so the script can use apt
bash scripts/check_env.sh        # without --no-install it fixes what it can
```

It installs the exact versions pinned in the project's own files, then re-checks
each one. Run it again until the FAILED list is empty.

What it will not do for you, and tells you the command for instead:

- **Change your Python or Node version.** Python must be 3.10 to 3.12. If yours
  is newer (3.13 or 3.14), several pinned packages will not install. Create a
  3.12 virtual environment first, activate it, and run the script inside it.
- **Supply `ML/weights.pt`** or fill in values in `backend/.env`.
- **Free a port** that something else is using.

Then start the stack by hand: `RUN_GUIDE.md` §5 (three terminals). For the
Mininet demo, follow `mininet/demo/DEMO_SETUP.md`.

---

## 4. Your file, and where to begin

Read your own file first, then section 9 of `BACKEND.md` (one page: how the two
models are really used, and what to say in the presentation).

### Susheep: frontend

**Read:** `docs/handover/FRONTEND.md`. Background if needed: `RUN_GUIDE.md` §5.

**Docker is enough for you** (Option A), except for the final demo check.

Start in this order:

1. Bring the stack up and open the dashboard. Nothing in the recent frontend
   changes has been seen in a browser; you are the first.
2. Work through FE-01 to FE-13 in section 6, ticking each off in the browser.
3. Fix before the presentation: **FE-23** (the screen says GraphSAGE classified
   the attack type; it did not), **FE-22** (a Settings toggle freezes the
   dashboard), **FE-29** (a false "demo mode" badge on load), **FE-28**
   (one-line typo).
4. Bring the decisions in FE-14 to FE-20 to Sathwik; they need an answer, not
   code.
5. Run the unit tests after every change: `cd frontend && node --test tests/unit/*.test.js`

### Sairaj: backend and Mininet

**Read:** `docs/handover/BACKEND.md`, then `mininet/demo/DEMO_SETUP.md`. For the
numbers: `MODEL_BEHAVIOUR.md` §1.

**You need Option B.** Mininet does not run in Docker.

Start in this order:

1. Get the demo running end to end on your machine: topology, daemon, inference
   service, backend, then `python mininet/demo/run_demo.py --backend-url
   http://localhost:8001`. Three attacks should give three incidents.
2. Then the full rehearsal that has never been done: the same run with v2 on,
   Ganache up, and the dashboard open.
3. Fix first: **BE-09** (the chain never connects if Ganache starts after the
   backend), agreed with Skanda.
4. Then the two measurements, in order: **BE-01**, **BE-02**. No live run is
   needed for either.
5. Then **BE-03** with Skanda (the double chain write).
6. Run the tests after every change: `cd backend && python -m pytest -q -p no:cacheprovider`

Do not change the model, the 0.75 threshold or the 0.90 floor. `BACKEND.md`
says why.

### Skanda: blockchain

**Read:** `docs/handover/BLOCKCHAIN.md`. Background: `HOW_TO_RUN.md` steps 1
and 2.

**Docker is enough to start** (the blockchain container deploys the contract by
itself). Use Option B when you run the checklist with real attacks.

Start in this order:

1. Run the contract tests: `cd blockchain && npm ci && npx hardhat test`
2. Do the checklist in section 7 of your file. No chain write has ever been run
   end to end on this branch; this will be the first.
3. Remember the order: **Ganache, then deploy, then the backend.** Restart the
   backend after any redeploy (BC-03).
4. Settle **BC-01** with Sairaj: the contract accepts duplicates, and the
   matching rule needs more than the URI.
5. Decide **BC-06** with Sathwik: the chain records a host as blocked when the
   block was only simulated.

---

## 5. How to work on the branch

- Make your own branch from `fix/audit-p0-p1` for each fix
  (`git switch -c fix/fe-23-forensics-label`), and open a pull request back
  into `fix/audit-p0-p1`. Do not push directly to it.
- Put the bug ID in the commit message (`FE-23: …`).
- When you close or open an item that is in `OPEN_ITEMS.md`, update that file in
  the same commit. A test fails if the file is missing.
- If you find something that is not in your handover file, add it there in the
  same format.
- Keep `ENFORCEMENT_MODE=simulated`. Nobody needs `ovs` before the presentation.

## 6. If you are stuck

| Problem | Look at |
|---|---|
| The stack will not start | `RUN_GUIDE.md` §10 (troubleshooting table) |
| Dashboard says OFFLINE on the manual path | `frontend/.env` needs `VITE_BACKEND_URL=http://localhost:8001` |
| `/health` says `blockchain.connected: false` | `BLOCKCHAIN.md` section 7, step 7 |
| An attack shows nothing on the dashboard | `DEMO_SETUP.md`, "Running the attacks": the target port must be open |
| A Docker build dies with an npm error | memory; build one image at a time |
