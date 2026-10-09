# Blockchain handover

For Skanda. Written from the code on branch `fix/audit-p0-p1` at `5fd69a6`. No
source file was changed to write this. Every file and line cited was read.

The most important fact first: **no chain write has been executed in any
recorded run of this branch.** Not in the audit, not in the three live Mininet
runs, not in the demo rehearsal. The Hardhat tests cover the contract and the
backend tests cover the Python with mock clients; the two have not been seen
working together against a running Ganache. Section 7 is how to change that.

---

## 1. What the blockchain component is

Three parts:

- **Ganache**, a local Ethereum node (`ganache` 7, chain id 1337, deterministic
  accounts). Under Compose it runs in the `blockchain` container with its state
  on a volume; by hand it runs from `blockchain/` on port 8545.
- **`IncidentLogger.sol`**, one Solidity 0.8.19 contract, compiled and deployed
  with Hardhat (`blockchain/scripts/deploy.js`).
- **The Python bridge**, `blockchain/web3_bridge/web3_client.py`
  (`BlockchainClient`, on `web3` 7.4.0), which the backend loads through
  `backend/app/services/blockchain_adapter.py`.

What it stores: one record per incident the backend's v1 path raises, and one
per manual block. Each record holds the source IP, the attack label, a severity
from 1 to 10, whether the host was blocked, a pointer back to the SQLite row
(`local://incident/<id>`), the block timestamp, and a hash over those values.
Unblocks are recorded as an event, not as an incident.

Why: the SQLite database is the working record and anyone with file access can
edit it. The chain is the copy that cannot be edited afterwards, so an incident's
existence, time and content can be checked later against something the backend
does not control. That is the audit trail.

v2 never writes to the chain.

---

## 2. The contract: `IncidentLogger.sol`

`blockchain/contracts/IncidentLogger.sol`, 132 lines.

### Storage

| Name | Type | Visibility | Holds |
|---|---|---|---|
| `_incidents` | `mapping(uint256 => Incident)` | private | Every incident, keyed by its id. Ids start at 1. |
| `blockedIPs` | `mapping(string => bool)` | public | Whether an IP is currently marked blocked. |
| `_ipIncidentHistory` | `mapping(string => uint256[])` | private | For each IP, the ids of its incidents, in order. |
| `incidentCount` | `uint256` | public | The number of incidents, and the last id issued. |
| `deployer` | `address`, immutable | public | The account that deployed the contract. |

The `Incident` struct (`:12-21`): `id`, `incidentHash` (bytes32), `timestamp`,
`sourceIP`, `attackLabel`, `severity` (uint8), `isBlocked`, `forensicsURI`.

**There is no index by `forensicsURI`.** No mapping is keyed on it and no event
carries it. To find an incident by its URI you must read incidents one by one.

### Functions

| Function | Parameters | Access | What it writes or returns |
|---|---|---|---|
| `logIncident` (`:49-91`) | `_sourceIP`, `_attackLabel`, `_severity`, `_isBlocked`, `_forensicsURI` | `onlyDeployer` | Requires a non-empty IP, a non-empty label and severity 1–10. Increments `incidentCount`, computes `keccak256(sourceIP, block.timestamp, attackLabel, severity, newId)`, stores the struct, appends the id to the IP's history. If `_isBlocked`, sets `blockedIPs[ip] = true` and emits `NodeIsolated`. Emits `IncidentLogged`. Returns the new id. |
| `getIncident` (`:94-97`) | `_id` | view | The whole struct. Reverts "Incident not found" outside `1..incidentCount`. |
| `getIncidentCount` (`:99-101`) | — | view | `incidentCount`. |
| `isIPBlocked` (`:103-105`) | `_ip` | view | `blockedIPs[_ip]`. |
| `getIPHistory` (`:107-109`) | `_ip` | view | The array of incident ids for that IP. |
| `verifyIncident` (`:112-124`) | `_id`, `_sourceIP`, `_attackLabel`, `_severity`, `_timestamp` | view | Recomputes the hash from the arguments and returns whether it equals the stored one. |
| `releaseNode` (`:127-131`) | `_ip`, `_reason` | `onlyDeployer` | Requires `blockedIPs[_ip]` to be true ("IP is not blocked"). Sets it false, emits `NodeReleased`. Stores no incident. |
| `blockedIPs(string)`, `incidentCount()`, `deployer()` | — | view | Auto-generated getters. |

`onlyDeployer` (`:43-46`) reverts with "Unauthorized" unless the caller is the
deploying account.

### Events

| Event | Fields | Indexed |
|---|---|---|
| `IncidentLogged` | `id`, `incidentHash`, `sourceIP`, `attackLabel`, `timestamp` | `id`, `incidentHash` |
| `NodeIsolated` | `sourceIP`, `incidentId`, `timestamp` | `sourceIP` (a string, so the topic is its hash) |
| `NodeReleased` | `sourceIP`, `timestamp`, `reason` | `sourceIP` (same) |

The ABI the backend uses, `blockchain/web3_bridge/contract_abi.json`, matches
this: three events, the functions above, and a constructor.

### Duplicate URIs

**The contract accepts a second `logIncident` call with the same
`forensicsURI`.** Confirmed from the code: the function has exactly three
`require` statements (`:56-58`), on the IP, the label and the severity. Nothing
checks `_forensicsURI`, there is nothing to check it against, and the id is a
plain counter (`:60`). Two calls with identical arguments produce two incidents
with consecutive ids and different hashes (the id and, usually, the timestamp
differ). The Hardhat tests do not cover this case.

---

## 3. Data flow: from incident to chain

All of this runs in the backend's monitor thread, once per source that crosses
v1's threshold, **after** the block has been recorded.

1. **`backend/app/services/threat_analyzer.py:142-148`** calls
   `self.blockchain.store_incident(source_ip, attack_type, severity, is_blocked=True, incident_id=incident.id)`.
   `severity` is the score times ten, rounded, clamped to 1–10. `attack_type`
   is the backend's heuristic label (`DDoS`, `PortScan`, `SSHBrute`, `DoSHulk`,
   `Botnet`), not a model output. The incident row was created just before with
   `blockchain_status = "submitting"`.

2. **`blockchain_adapter.py:86-156`, `store_incident`.** If the adapter is not
   connected it returns `{'tx_hash': None, 'status': 'offline'}` at once
   (`:94-95`). Otherwise it runs the client call in a one-thread executor and
   waits `blockchain_tx_timeout_seconds`, which is **5 s** (`:121-124`).

3. **`web3_client.py:144-215`, `log_incident`.** Builds
   `forensics_uri = f"local://incident/{sqlite_incident_id}"` (`:150`), then
   `contract.functions.logIncident(source_ip, attack_type, severity, is_blocked, forensics_uri)`.
   `_send_contract_tx` (`:91-134`) estimates gas first (a call that would revert
   fails here, before anything is sent), then either signs with a private key
   or, with none configured, calls `transact` from Ganache's first account. The
   moment the transaction is sent the client reports its hash through
   `on_broadcast` (`:165-169`). Then it waits up to **15 s** for the receipt
   (`:173`) and decodes `IncidentLogged` from it to get the on-chain id
   (`:195-206`).

4. **Back in the adapter.** Three outcomes:
   - the client returned in time → its result, with `chain_id` and
     `contract_address` added (`:142-149`);
   - 5 s passed and a hash had been broadcast → `status: 'pending'` with that
     hash (`:127-133`);
   - 5 s passed and nothing had been broadcast → `status: 'pending'` with
     `tx_hash: None` (`:134-136`). This is the open window, BC-01.

5. **`threat_analyzer.py:212-250`, `_update_incident_after_actions`.** Writes
   the result to the incident row: `blockchain_tx`, `blockchain_chain_id`,
   `blockchain_contract_address`, `blockchain_block_number`,
   `blockchain_incident_id`, and `blockchain_status`:
   - `confirmed` when the receipt came back good;
   - `pending` when there is a hash and no receipt yet;
   - **`retry` for everything else** (`:236-239`), which includes "chain
     offline", a revert, and a timeout without a hash. The retry counter goes up
     and the reason is stored in `blockchain_last_error`.

   The hash is also copied to the `blocked_ips` row (`:245-248`) and to the
   enforcement log.

6. **`backend/app/api/v1/forensics.py`.** `GET /api/v1/forensics` returns the
   incidents from SQLite with their stored chain fields, and separately every
   on-chain record from `client.get_all_incidents()` (`:63`).

7. **The dashboard.** The Forensics page shows the hash in the incident's
   "Blockchain Evidence" card and lists the on-chain records in a table at the
   bottom. The Audit & Ledger page lists the same on-chain records.

**It is synchronous.** The poll loop waits for the write, up to 5 s per
incident.

**When Ganache is unreachable it is silent.** The adapter returns `offline`,
the incident is stored as `retry`, and nothing is logged: `blockchain_adapter.py`
has no logger at all. The only signs are `/health` → `blockchain.connected:
false`, the line `[Blockchain] Connected: False [ERROR]` printed once at
startup (`backend/app/main.py:104`), and `blockchain_last_error` on each
incident.

---

## 4. Reconciliation

`backend/app/services/reconciliation.py`. `ReconciliationWorker` is a thread
started with the backend (`main.py:89-91`). Every
`blockchain_retry_interval_seconds` (10 s) it calls
`reconcile_blockchain_outbox()` (`:152-336`), which does two things, ten rows at
most for each, oldest first.

If the adapter is not connected it returns `{"status": "offline"}` on its first
line and does neither (`:162-164`). See BC-03.

**Part 1: look up pending transactions** (`:180-248`). Rows picked: a
`blockchain_tx` is set, `blockchain_incident_id` is null, and
`blockchain_status` is null or **not** one of the terminal states `confirmed`,
`failed`, `permanent_failure`. For each it asks the node for the receipt:

- mined and successful → decode the event, store the on-chain id and block
  number, set `confirmed`;
- mined and reverted → `failed`;
- no receipt yet → leave it, unless it has been pending longer than
  `blockchain_pending_timeout_seconds` (180 s). Then the hash is cleared and the
  row goes to `retry`, or to `permanent_failure` once it has used its
  `blockchain_max_retries` (5).

**Part 2: retry unwritten incidents** (`:250-327`). Rows picked: no
`blockchain_tx`; a score at or over the threshold, or `is_blocked`; fewer than
five retries; status not `permanent_failure` or `confirmed`; and not currently
claimed. Each row is claimed by an atomic update to `submitting` with a 60 s
lease, so the monitor thread and the worker cannot both submit it, and then
`adapter.store_incident` is called again with the row's own values (`:290-296`).

**The B06 bug, and where it was fixed.** Unblock rows are written with
`attack_type = "Manual"` (`backend/app/api/v1/blocked.py:66`). They carry a
transaction hash, from `releaseNode`, and can never get an on-chain incident id,
because `releaseNode` creates no incident. Part 1's filter used to exclude rows
by `attack_type != "Manual-Unblock"`, a value no row ever has, so every unblock
row matched on every cycle, for ever. Ten of them filled the batch and real
pending transactions behind them were never looked at. The fix filters on
`blockchain_status` instead (`:186-191`), orders oldest first (`:195`), and
sends a row that fails every cycle to `permanent_failure` at the retry limit
(`:244-247`). It was made in commits `6a3c20d` and `7773811`, with two tests
(`AUDIT_2026-10-04.md`, the B06 row). Older notes credit `ae34631`; that commit
is a frontend colour refactor and did not touch this file.

---

## 5. What was not run, and what is unverified

- **A full chain write through Ganache has not been executed** in the audit or
  in the demo rehearsal. `mininet/demo/tested_run.txt` lists five incident rows,
  all with enforcement `simulated`; the run was made without Ganache
  (`DEMO_SETUP.md`, "Tested": "It has not been run with v2 on, with Ganache, or
  in front of the dashboard in a browser"). In the live Mininet runs Ganache
  was not running either, and all 16 incidents the audit read from them ended
  in `retry` (audit report §11).
- **`releaseNode` has not been executed** outside Hardhat tests, for the same
  reason.
- **The Hardhat suite** is documented as 25 passing (`RUN_GUIDE.md` §6,
  `npx hardhat test` from `blockchain/`). I did not run it for this handover.
- **B05's remaining window** (BC-01) is open. The half that is fixed, a timeout
  after broadcast, is covered by three tests against a mock client
  (`backend/tests/test_b05_broadcast_hash.py`), not against a chain.
- **Signing with a private key** (`web3_client.py:98-132`) has not been
  exercised on this branch as far as any recorded run shows. The default path is
  Ganache's unlocked first account.

---

## 6. Bugs to act on

BC-01 and BC-02 are in `OPEN_ITEMS.md`. BC-03 to BC-08 are things I found while
reading the adapter, the client and the contract; none is recorded elsewhere
yet. Sairaj's BACKEND.md carries the backend side of BC-01, BC-03 and BC-04
under BE-03, BE-09 and BE-13.

### BUG BC-01 (open item 5): One incident can be written to the chain twice
**File:** `backend/app/services/blockchain_adapter.py:134-136`; `backend/app/services/reconciliation.py:286-296`; `blockchain/contracts/IncidentLogger.sol:49-60`; `blockchain/web3_bridge/web3_client.py:150`, `:252-323`
**What is wrong:** The adapter waits 5 s for a write; the client's worker thread cannot be stopped. If the 5 s ends before the transaction has been sent, the adapter has no hash and the incident is stored as `retry`. The worker may still send it a moment later. Ten seconds on, the reconciler sees a row with no hash and sends the incident again. **The contract accepts both** (section 2, "Duplicate URIs"). The result is two on-chain incidents for one SQLite incident, with nothing linking the first one back, since the row only ever learns the second hash. On an append-only ledger that cannot be cleaned up.
**How to reproduce:** It needs a node slow enough that gas estimation plus sending takes more than 5 s; an idle Ganache will not do it. In a test: a mock client that sleeps 6 s before calling `on_broadcast`, one `store_incident`, one reconciler pass, and count the calls.
**What done / what remains:** The intended fix is decided and it is in Sairaj's file, `reconciliation.py`: before resubmitting a row with no hash, look on chain for an incident with `forensicsURI == "local://incident/<id>"` and adopt it. What he needs from you, and what I found on each point:

- *Does the contract accept a second call for the same URI?* **Yes**, confirmed above. The fix cannot rely on the contract refusing.
- *Can the URI be looked up on chain?* Only by enumeration. No mapping is keyed on it and `IncidentLogged` does not carry it, so it means `getIncident(i)` for each candidate id. `get_all_incidents()` already does this and returns `forensics_uri` for every record (`web3_client.py:281`, `:299`).
- *Does `/forensics` return enough to match on?* **No.** The Python client returns the URI, but the HTTP endpoint's `_normalize_chain_record` drops it (`backend/app/api/v1/forensics.py:18-34`) and `ChainRecord` has no such field. The reconciler runs in-process and can call `adapter.client.get_all_incidents()` directly, so this does not block the fix, but do not tell anyone the endpoint is the lookup.
- *Is the URI unique enough to match on alone?* **No, and this is the part to settle with Sairaj.** The URI is the SQLite row id. Ganache's state persists (the `--db` folder, the Compose `ganache-data` volume) while SQLite ids restart at 1 with every new database, and the test runs used throwaway databases. `local://incident/1` may already be on chain from an earlier database, for a different host. Adopting on URI alone would attach the wrong transaction. Match `sourceIP` and `attackLabel` too, and require the on-chain `timestamp` to be no earlier than the row's `created_at`.

If you would rather close it in the contract, a `mapping(string => uint256)` from URI to id with a `require` that it is unset would make a duplicate revert at gas estimation. That is a contract change, so a redeploy, a new address, a new ABI and new Hardhat tests, and the same cross-database collision would then **reject** a legitimate new incident. The consumer-side fix was chosen for that reason.

### BUG BC-02 (open item 10): `reference.bib` is missing
**File:** `report/main.tex:15`
**What is wrong:** This is a report problem, not a blockchain one; it is here because the citations it breaks include the two blockchain papers. `main.tex` loads `reference.bib` and cites `paper1` to `paper10`. No `.bib` file is tracked, so a clone cannot build the bibliography and the citations resolve as undefined. `paper1` and `paper4` are the ones cited for blockchain-based forensic integrity (`main.tex:319`, `:445`).
**How to reproduce:** Build the report from a fresh clone.
**What done / what remains:** Open. Only the author knows which ten papers these are. If you are assembling the bibliography, that is the file to create, with those ten keys.

### BUG BC-03: If Ganache is not up when the backend starts, nothing is ever written
**File:** `backend/app/services/blockchain_adapter.py:22-26`, `:61-69`; `backend/app/services/reconciliation.py:162-164`
**What is wrong:** The adapter connects once, when the backend starts, and never tries again. If Ganache is not answering at that moment, or `CONTRACT_ADDRESS` is empty or points at an address with no contract, the adapter stays disconnected for the life of the process. Every incident is stored as `retry`, and the reconciler, whose job is to retry them, returns "offline" on its first line and does nothing. Starting Ganache later does not help. Deploying the contract later does not help either, because the address is read from `backend/.env` only at startup.
**How to reproduce:** Start the backend, then Ganache, then run an attack. No hash appears, however long you wait.
**What done / what remains:** Not recorded before. Open; the code fix is Sairaj's. **For you it is an ordering rule: Ganache, then deploy, then the backend. After any redeploy, restart the backend.**

### BUG BC-04: The dashboard's chain table is missing the URI and always says "Confirmed"
**File:** `backend/app/api/v1/forensics.py:18-34`; `blockchain/web3_bridge/web3_client.py:252-300`
**What is wrong:** `get_all_incidents()` works out each record's real receipt status and its `forensics_uri`. The endpoint then rebuilds each record without the URI and with `"status": "confirmed"` written in as a constant. So the Audit & Ledger page's "Forensics URI" line is always blank, and a reverted transaction would be shown as confirmed. Separately, `get_all_incidents()` creates a new event filter from block 0 on every call and never removes it (`:255`), then makes two RPC calls per incident, and the endpoint calls it on the server's event loop (audit B10). The dashboard requests this endpoint every 10 s, and every 5 s while the Forensics page is open.
**How to reproduce:** With incidents on chain, `GET /api/v1/forensics` and read `blockchain_records`.
**What done / what remains:** B10 is recorded and held; the two field problems are not recorded. Open. The filter could be replaced by `get_logs` over a block range, which leaves nothing behind on the node.

### BUG BC-05: Unblocking a host the chain never recorded as blocked fails, and is never retried
**File:** `blockchain/contracts/IncidentLogger.sol:127-128`; `backend/app/api/v1/blocked.py:77-96`; `backend/app/services/reconciliation.py:252-259`
**What is wrong:** `releaseNode` requires `blockedIPs[_ip]` to be true. That flag is set only by a `logIncident` call with `isBlocked = true` that actually reached the chain. If the block's write never landed (Ganache was down, or the row is still in `retry`), the unblock's `releaseNode` reverts at gas estimation with "IP is not blocked". The backend stores the unblock row with status `error` and moves on. The reconciler will not pick it up: its retry query wants a score over the threshold or `is_blocked`, and an unblock row has a score of 0 and `is_blocked` false. And if the original block incident is written late by the reconciler, it is written with whatever `is_blocked` the row holds at that time, which after an unblock is false. So the chain can end up with no record that the host was ever blocked or released.
**How to reproduce:** Start the backend with Ganache down, run one attack, start Ganache, restart the backend, unblock the host from the dashboard. Read the new `Manual` row's `blockchain_last_error` in `/api/v1/forensics`.
**What done / what remains:** Not recorded before. Open. It does not arise if the chain is up for the whole demo.

### BUG BC-06: The chain says a host was isolated when the block was only simulated
**File:** `backend/app/services/threat_analyzer.py:142-148`; `blockchain/contracts/IncidentLogger.sol:84-87`
**What is wrong:** `store_incident` is always called with `is_blocked=True`, whatever the enforcement mode. In `simulated` mode, which is the default and what the demo uses, nothing is installed on the switch and traffic continues. The contract still sets `blockedIPs[ip] = true` and emits `NodeIsolated`. The enforcement status (`simulated` or `enforced`) exists only in SQLite; the chain has no field for it. So the permanent record states an isolation that did not happen.
**How to reproduce:** Run one attack with `ENFORCEMENT_MODE=simulated` and Ganache up, then call `isIPBlocked("10.0.0.2")` on the contract.
**What done / what remains:** Not recorded before. Open, and it is a decision as much as a bug: either the contract field means "the system decided to block", in which case say so wherever it is described, or it should carry the enforcement status. For the presentation, use the wording in section 8.

### BUG BC-07: The deploy script rewrites the backend's environment file and a tracked file
**File:** `blockchain/scripts/deploy.js:38-39`, `:47-58`
**What is wrong:** Besides deploying, the script does two things you may not expect. It opens `backend/.env`, deletes every `CONTRACT_ADDRESS=` and `GANACHE_URL=` line, and appends new ones with `GANACHE_URL=http://127.0.0.1:8545`. If the backend was configured to reach Ganache at another address (`backend/.env.example:15` notes that a backend in WSL needs the Windows host's IP), that setting is replaced without a word. It also overwrites `blockchain/web3_bridge/contract_abi.json`, which is tracked in git, so a deploy can leave the working tree dirty. `RUN_GUIDE.md` warns about the first.
**How to reproduce:** `git status` and `git diff backend/.env` before and after `npx hardhat run scripts/deploy.js --network localhost`.
**What done / what remains:** Documented as a warning, not changed. If `GANACHE_URL` in `backend/.env` is not the loopback address on the presentation machine, put it back after deploying.

### BUG BC-08: Housekeeping in the bridge and the Hardhat project
**File:** `blockchain/web3_bridge/web3_client.py:54-58`, `:207`, `:273`, `:301-303`, `:328-331`; `backend/app/services/blockchain_adapter.py:192-254`; `blockchain/package.json:6`
**What is wrong:** Smaller things, none of which stops the demo:

- **The signer must be the deployer.** `logIncident` and `releaseNode` are `onlyDeployer`. With no key configured the client uses Ganache's first account, which is also what `deploy.js` deploys from, so it works. But the client takes a key from `BLOCKCHAIN_PRIVATE_KEY`, `DEPLOYER_PRIVATE_KEY` **or a bare `PRIVATE_KEY`** environment variable. If any of those is set to a different account, every write reverts as "Unauthorized" at gas estimation, retries five times, and ends in `permanent_failure`.
- **The integrity check is never used.** `verifyIncident` exists in the contract and `verify_incident` in the client, and nothing in the backend or the dashboard calls either. `BlockchainAdapter.reconcile_tx`, which classifies a stored hash against the live chain, is not called either. The audit trail is written and displayed; it is not verified anywhere in the running system.
- `get_all_incidents` wraps its whole event path in `except Exception` and silently falls back to reading by count, which returns records with no transaction hash. A real error on the first path is invisible.
- A helper, `hex0x`, exists because hash formatting differs between `hexbytes` versions; the two places that format `incident_hash` do not use it and prefix `"0x"` by hand. Correct with the pinned `web3==7.4.0`; fragile if that changes.
- `blockchain/README.md` (stock Hardhat sample text) and `ignition/modules/Lock.js` (it deployed a `Lock` contract that is not in `contracts/`) were removed in the repo cleanup. `npm test` prints "no test specified"; the tests run with `npx hardhat test`.

**How to reproduce:** Read the cited lines.
**What done / what remains:** Not recorded before. Open, low priority. The first bullet is worth one check before the demo: make sure none of the three key variables is set in the shell that starts the backend.

---

## 7. Before the presentation: your checklist

Do this on the presentation machine, once, well before the day. It will be the
first time the chain path has run end to end on this branch.

1. **Start Ganache.** From `blockchain/` (`HOW_TO_RUN.md`, step 1):

   ```powershell
   npx ganache --host 0.0.0.0 --port 8545 --deterministic --accounts 5 --db ./ganache-data
   ```

   Wait for `Listening on 0.0.0.0:8545`.

2. **Deploy the contract.** From `blockchain/`, in a second terminal
   (`HOW_TO_RUN.md`, step 2):

   ```powershell
   npx hardhat run scripts/deploy.js --network localhost
   ```

   It prints `✅ Deployed at: 0x…` and `✅ backend/.env updated with
   CONTRACT_ADDRESS`. Only needed on first start or after clearing
   `ganache-data`. Read BC-07 for what else it changed.

3. **Start the backend after both.** Not before (BC-03). Its startup output
   must include `[Blockchain] Connected: True [OK]`.

4. **Confirm the connection.**
   `curl http://localhost:8001/health` and check `blockchain.connected` is
   `true` and `blockchain.contract_address` is the address from step 2. Do not
   rely on the dashboard for this: the green "Connected" dot on Audit & Ledger
   reports the backend, not Ganache (FRONTEND.md, FE-27). On that page a chain
   id of `1337` beside "Ganache · Chain" is the real sign; a dash means not
   connected.

5. **Run one attack** from the repository root, with the topology, daemon and
   backend up as in `mininet/demo/DEMO_SETUP.md`:

   ```
   python mininet/demo/run_demo.py --backend-url http://localhost:8001
   ```

   or just the first one, in WSL:
   `sudo python3 mininet/demo/attacks/flood.py`. Wait about twenty seconds.

6. **Find the hash.** Dashboard → Forensics → click the incident → "Blockchain
   Evidence". It should show a `0x…` hash, a `Confirmed` badge, a block number
   and an "On-Chain Log ID". The same record should be the newest row in
   "Blockchain Records" at the bottom of the page and on Audit & Ledger.

7. **If the hash is missing**, there is no adapter log to read; the adapter does
   not log. Look here instead, in this order:
   - `/health` → `blockchain.error`: the connection error from startup, if any.
   - `GET /api/v1/forensics` → the incident's `blockchain_status` and
     `blockchain_last_error`. What the text means:
     - `blockchain offline` or a "Cannot connect to Ganache" message: BC-03.
       Restart the backend.
     - `blockchain timeout`: the 5 s ran out before the transaction was sent.
       The reconciler will retry within 10 s; watch for a duplicate (BC-01).
     - `blockchain timeout after broadcast; receipt not yet seen`: sent, not
       yet mined. Status `pending`; the reconciler will confirm it.
     - `Gas estimation failed: … Unauthorized`: the signer is not the deployer
       (BC-08, first bullet).
     - `Gas estimation failed: … IP is not blocked`: BC-05.
   - `/health` → `reconciliation.blockchain`: `offline`, or counts of what the
     last pass reconciled and retried.

8. **Unblock that host** from the dashboard, signed in as admin, and check a
   second transaction hash appears on the new `Manual` row. That is
   `releaseNode`, which has never been run against a live chain either.

9. **Leave Ganache running** for the whole presentation. Do not redeploy
   between the rehearsal and the demo unless you also restart the backend.

Under Docker Compose steps 1 to 3 are done by the `blockchain` container's
entrypoint, which reuses the previous deployment if its bytecode is still on
the persisted chain; Ganache is then on host port 8546 and the backend on 8001.

---

## 8. How the blockchain fits the demo

After an attack the examiner sees an incident on the Forensics page with a
transaction hash, a block number and a "Confirmed" badge, and the same record in
the ledger table. What that shows is that the system wrote the incident's
source, label, severity and time to a ledger the application cannot rewrite, at
the moment it acted, and can show where: an audit trail that is append-only and
tamper-evident. What is honest to say: Ganache is a local test chain running on
this machine with one account, not a public or production network, so the hash
is a real transaction on a real EVM chain but the network gives none of the
guarantees a distributed one would; the label written to the chain is the
backend's port and volume heuristic, not a model's classification; the record
says the host was blocked while the block itself is simulated in the demo
(BC-06); the system writes and displays the record but does not yet verify it
anywhere (BC-08); and writes come only from v1's incidents, never from v2. Said
that way, it is a working mechanism for recording incidents immutably, shown on
a local chain.
