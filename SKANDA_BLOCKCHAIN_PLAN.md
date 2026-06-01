# ⛓️ SKANDA — BLOCKCHAIN IMPLEMENTATION PLAN
## GraphSentinel | Role: Blockchain Engineer
### AI IDE: Claude Code / AntGravity / Codex

---

## PASTE THIS EXACT BLOCK WHEN STARTING YOUR AI IDE SESSION

```
You are the blockchain implementation assistant for GraphSentinel —
a Self-Healing Cyber Defense System.

YOUR ROLE: You assist Skanda who is building the local Ganache blockchain
forensics layer for tamper-proof incident logging.

FROZEN CONSTRAINTS — NEVER VIOLATE:
- Blockchain: LOCAL ONLY — Ganache 7.9.x (NO Infura, NO Alchemy, NO testnet)
- Solidity: 0.8.19 STRICTLY
- Hardhat: 2.22.x | hardhat-toolbox: 5.x
- ethers: 6.x (for scripts) | Web3.py: 7.x (for Python bridge)
- Chain ID: 1337 (Ganache default)
- Ganache Port: 8545
- Ganache accounts: 5, deterministic (always same keys)
- Contract: ONE contract only — IncidentLogger.sol

YOUR SCOPE — ONLY GENERATE CODE FOR:
  blockchain/contracts/*
  blockchain/scripts/*
  blockchain/test/*
  blockchain/web3_bridge/web3_client.py
  blockchain/web3_bridge/contract_abi.json
  blockchain/hardhat.config.js

DO NOT touch: frontend/, backend/, ml/

WHAT YOUR FILES PROVIDE TO TEAMMATES:
  → To Sairaj (Backend): web3_client.py  (Python class)
                          contract_abi.json
                          CONTRACT_ADDRESS (written to backend .env)
  → To Susheep (Frontend): CONTRACT_ADDRESS for ethers.js read calls

DUAL-STORAGE FORENSICS (THIS IS YOUR ARCHITECTURE):
  SQLite (Sairaj)  ← fast queries, full flow data
       ↕ linked by incident ID
  Ganache chain    ← tamper-proof proof of existence
       • keccak256 hash fingerprints each incident
       • If SQLite record modified → hash won't match chain

NEVER suggest cloud blockchain. Local Ganache only.
When I ask to scaffold, generate file-by-file with full code.
Add // [Windows] or // [WSL2] comment in every file header.
```

---

## WEEK-BY-WEEK TASK BREAKDOWN

### WEEK 1 — Environment Setup [Windows]

```powershell
# [Windows PowerShell]
# STEP 1: Verify Node.js is installed
node --version   # Need v18.x or v20.x
npm --version    # Need 9.x or 10.x

# If not installed: https://nodejs.org (LTS)

# STEP 2: Create blockchain directory in monorepo
cd C:\Projects\graphsentinel\blockchain

# STEP 3: Initialize package.json
npm init -y

# STEP 4: Install Hardhat
npm install --save-dev hardhat@2.22.0
npm install --save-dev @nomicfoundation/hardhat-toolbox@5
npm install --save-dev ganache@7.9.0
npm install ethers@6

# STEP 5: Install dotenv
npm install dotenv

# STEP 6: Initialize Hardhat project structure
npx hardhat init
# Choose: "Create a JavaScript project"
# Say YES to all prompts

# STEP 7: Verify Ganache starts
npx ganache --port 8545 --deterministic --accounts 5
# Expected output (keep this terminal open):
# RPC Listening on 127.0.0.1:8545
# Account 0: 0xf39Fd6e51aad... (1000 ETH)
# Private Key 0: 0xac09...
# (5 accounts shown)
# Press Ctrl+C to stop for now

# STEP 8: Install dotenv-cli for env reading
npm install --save-dev dotenv-cli

# STEP 9: Create directory structure
mkdir -p contracts scripts test web3_bridge

# STEP 10: Web3.py bridge setup in WSL2
# [WSL2 terminal] - needed for Sairaj to use
cd /mnt/c/Projects/graphsentinel/backend
source .venv/bin/activate
pip install web3==7.4.0
python -c "from web3 import Web3; print('web3 OK')"

echo "Week 1 complete ✓"
```

**Week 1 Checkpoint:** `npx ganache --port 8545 --deterministic` shows 5 accounts.

---

### WEEK 2 — Write + Test IncidentLogger.sol

```solidity
// blockchain/contracts/IncidentLogger.sol
// [Windows — Hardhat compile]
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title IncidentLogger
 * @author Skanda (GraphSentinel Blockchain)
 * @notice Tamper-proof forensic ledger for cyber incidents.
 *         Deployed on local Ganache chain — NO cloud provider.
 *
 * DESIGN PRINCIPLE:
 *   This contract does NOT store full attack data (too expensive).
 *   It stores a keccak256 FINGERPRINT of the incident + key metadata.
 *   The full data lives in Sairaj's SQLite database.
 *   The fingerprint on-chain PROVES the SQLite data was not modified.
 *   If SQLite is tampered → fingerprint mismatch → tampering detected.
 */
contract IncidentLogger {

    // ─── Data Types ───────────────────────────────────────────────
    enum AttackType {
        Unknown,     // 0
        DDoS,        // 1
        PortScan,    // 2
        SSHBrute,    // 3
        Botnet,      // 4
        DoSHulk      // 5
    }

    struct Incident {
        uint256  id;
        bytes32  incidentHash;   // keccak256 proof — immutable fingerprint
        uint256  timestamp;      // block.timestamp — cannot be faked
        string   sourceIP;       // attacker IP address
        string   attackLabel;    // human-readable attack name
        uint8    severity;       // 1 (low) to 10 (critical)
        bool     isBlocked;      // was the node isolated?
        string   forensicsURI;   // pointer to SQLite: "local://incident/42"
    }

    // ─── State Variables ──────────────────────────────────────────
    mapping(uint256 => Incident) private _incidents;
    mapping(string  => bool)     public  blockedIPs;
    mapping(string  => uint256[]) private _ipIncidentHistory;

    uint256 public incidentCount;
    address public immutable deployer;

    // ─── Events ───────────────────────────────────────────────────
    event IncidentLogged(
        uint256 indexed id,
        bytes32 indexed incidentHash,
        string          sourceIP,
        string          attackLabel,
        uint256         timestamp
    );

    event NodeIsolated(
        string  indexed sourceIP,
        uint256         incidentId,
        uint256         timestamp
    );

    event NodeReleased(
        string  indexed sourceIP,
        uint256         timestamp,
        string          reason
    );

    // ─── Constructor ──────────────────────────────────────────────
    constructor() {
        deployer = msg.sender;
        incidentCount = 0;
    }

    // ─── Core Function: Log an incident ───────────────────────────
    /**
     * @dev Called by backend (via Web3.py) when GNN detects an attack.
     * @param _sourceIP    IP address of the attacker node
     * @param _attackLabel Attack classification (e.g., "DDoS")
     * @param _severity    1–10 severity score
     * @param _isBlocked   Whether the node was automatically isolated
     * @param _forensicsURI Link to SQLite record (e.g., "local://incident/42")
     * @return newId       The on-chain incident ID (use to update SQLite tx_hash)
     */
    function logIncident(
        string  memory _sourceIP,
        string  memory _attackLabel,
        uint8          _severity,
        bool           _isBlocked,
        string  memory _forensicsURI
    ) external returns (uint256 newId) {
        require(bytes(_sourceIP).length > 0,    "IP cannot be empty");
        require(bytes(_attackLabel).length > 0, "Attack label required");
        require(_severity >= 1 && _severity <= 10, "Severity: 1-10 only");

        unchecked { newId = ++incidentCount; }

        // Generate tamper-proof fingerprint
        bytes32 hash = keccak256(abi.encodePacked(
            _sourceIP,
            block.timestamp,
            _attackLabel,
            _severity,
            newId
        ));

        _incidents[newId] = Incident({
            id:            newId,
            incidentHash:  hash,
            timestamp:     block.timestamp,
            sourceIP:      _sourceIP,
            attackLabel:   _attackLabel,
            severity:      _severity,
            isBlocked:     _isBlocked,
            forensicsURI:  _forensicsURI
        });

        // Track IP history
        _ipIncidentHistory[_sourceIP].push(newId);

        // Update block state
        if (_isBlocked) {
            blockedIPs[_sourceIP] = true;
            emit NodeIsolated(_sourceIP, newId, block.timestamp);
        }

        emit IncidentLogged(newId, hash, _sourceIP, _attackLabel, block.timestamp);
        return newId;
    }

    // ─── Read Functions ───────────────────────────────────────────
    function getIncident(uint256 _id)
        external view returns (Incident memory)
    {
        require(_id > 0 && _id <= incidentCount, "Incident not found");
        return _incidents[_id];
    }

    function getIncidentCount() external view returns (uint256) {
        return incidentCount;
    }

    function isIPBlocked(string memory _ip) external view returns (bool) {
        return blockedIPs[_ip];
    }

    function getIPHistory(string memory _ip)
        external view returns (uint256[] memory)
    {
        return _ipIncidentHistory[_ip];
    }

    // ─── Verify tamper-proof integrity ────────────────────────────
    /**
     * @dev Verifies an incident was not tampered with.
     *      Called during forensics demo to prove immutability.
     * @return true if the provided data matches the stored hash
     */
    function verifyIncident(
        uint256 _id,
        string  memory _sourceIP,
        string  memory _attackLabel,
        uint8          _severity,
        uint256        _timestamp
    ) external view returns (bool) {
        Incident storage inc = _incidents[_id];
        bytes32 recomputed = keccak256(abi.encodePacked(
            _sourceIP, _timestamp, _attackLabel, _severity, _id
        ));
        return recomputed == inc.incidentHash;
    }

    // ─── Admin: Release a blocked node ───────────────────────────
    function releaseNode(string memory _ip, string memory _reason) external {
        require(blockedIPs[_ip], "IP is not blocked");
        blockedIPs[_ip] = false;
        emit NodeReleased(_ip, block.timestamp, _reason);
    }
}
```

```javascript
// blockchain/test/IncidentLogger.test.js  [Windows]
const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("IncidentLogger", function () {

  let contract;
  let owner;

  beforeEach(async function () {
    [owner] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("IncidentLogger");
    contract = await Factory.deploy();
    await contract.waitForDeployment();
  });

  // TEST 1: Basic log
  it("should log an incident and return ID=1", async function () {
    const tx = await contract.logIncident(
      "10.0.0.2", "DDoS", 9, false, "local://incident/1"
    );
    await tx.wait();
    expect(await contract.getIncidentCount()).to.equal(1n);
  });

  // TEST 2: Severity bounds
  it("should reject severity 0 and 11", async function () {
    await expect(
      contract.logIncident("10.0.0.2", "DDoS", 0, false, "local://incident/2")
    ).to.be.revertedWith("Severity: 1-10 only");
    await expect(
      contract.logIncident("10.0.0.2", "DDoS", 11, false, "local://incident/3")
    ).to.be.revertedWith("Severity: 1-10 only");
  });

  // TEST 3: Blocking
  it("should set blockedIPs when isBlocked=true", async function () {
    await contract.logIncident("10.0.0.5", "SSHBrute", 8, true, "local://incident/4");
    expect(await contract.isIPBlocked("10.0.0.5")).to.equal(true);
    expect(await contract.isIPBlocked("10.0.0.1")).to.equal(false);
  });

  // TEST 4: Events
  it("should emit IncidentLogged and NodeIsolated events", async function () {
    await expect(
      contract.logIncident("10.0.0.8", "Botnet", 6, true, "local://incident/5")
    )
      .to.emit(contract, "IncidentLogged")
      .withArgs(
        1n,
        await contract.getIncident(1n).then(i => i.incidentHash).catch(() => ethers.ZeroHash),
        "10.0.0.8", "Botnet",
        (await ethers.provider.getBlock("latest")).timestamp + 1n
      );
  });

  // TEST 5: TAMPER-PROOF DEMO — the key viva proof
  it("should detect tampered data via hash mismatch", async function () {
    await contract.logIncident("10.0.0.2", "DDoS", 9, false, "local://incident/6");
    const incident = await contract.getIncident(1n);

    // Verify with correct data → true
    const isValid = await contract.verifyIncident(
      1n, "10.0.0.2", "DDoS", 9, incident.timestamp
    );
    expect(isValid).to.equal(true);

    // Verify with TAMPERED data (changed attackLabel) → false
    const isTampered = await contract.verifyIncident(
      1n, "10.0.0.2", "PortScan", 9, incident.timestamp
    );
    expect(isTampered).to.equal(false);
    // ↑ THIS IS YOUR VIVA DEMO PROOF POINT
  });

  // TEST 6: Unblock
  it("should release a blocked IP", async function () {
    await contract.logIncident("10.0.0.3", "PortScan", 7, true, "local://incident/7");
    expect(await contract.isIPBlocked("10.0.0.3")).to.equal(true);
    await contract.releaseNode("10.0.0.3", "MANUAL_OVERRIDE");
    expect(await contract.isIPBlocked("10.0.0.3")).to.equal(false);
  });

});
```

```bash
# Run tests:
npx hardhat test
# Expected: 6 passing
```

**Week 2 Checkpoint:** `npx hardhat test` → 6 passing.

---

### WEEK 3 — Deploy Script + ABI Export

```javascript
// blockchain/scripts/deploy.js  [Windows]
const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("\n═══════════════════════════════════════════════");
  console.log("  GraphSentinel — IncidentLogger Deployment");
  console.log("═══════════════════════════════════════════════");

  // Get deployer account (Ganache account[0])
  const [deployer] = await ethers.getSigners();
  console.log(`Deployer: ${deployer.address}`);

  const balance = await ethers.provider.getBalance(deployer.address);
  console.log(`Balance:  ${ethers.formatEther(balance)} ETH`);

  // Deploy contract
  console.log("\nDeploying IncidentLogger...");
  const Factory = await ethers.getContractFactory("IncidentLogger");
  const contract = await Factory.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log(`✅ Deployed at: ${address}`);

  // Verify contract responds
  const count = await contract.getIncidentCount();
  console.log(`✅ Contract live — incidentCount: ${count}`);

  // ── Export ABI ────────────────────────────────────────────────
  const artifactPath = path.join(
    __dirname, "../artifacts/contracts/IncidentLogger.sol/IncidentLogger.json"
  );
  const artifact = JSON.parse(fs.readFileSync(artifactPath, "utf8"));

  const abiDest = path.join(__dirname, "../web3_bridge/contract_abi.json");
  fs.writeFileSync(abiDest, JSON.stringify(artifact.abi, null, 2));
  console.log(`✅ ABI exported → web3_bridge/contract_abi.json`);

  // ── Write .env files ──────────────────────────────────────────
  const blockchainEnv = `CONTRACT_ADDRESS=${address}\nGANACHE_URL=http://127.0.0.1:8545\n`;
  fs.writeFileSync(path.join(__dirname, "../.env"), blockchainEnv);
  console.log(`✅ blockchain/.env written`);

  // Append to backend .env (for Sairaj)
  const backendEnvPath = path.join(__dirname, "../../backend/.env");
  const backendEnvEntry = `\n# ─── Blockchain (from Skanda's deploy) ───\nCONTRACT_ADDRESS=${address}\nGANACHE_URL=http://127.0.0.1:8545\n`;

  if (fs.existsSync(backendEnvPath)) {
    // Remove old CONTRACT_ADDRESS line if exists
    let existing = fs.readFileSync(backendEnvPath, "utf8");
    existing = existing.replace(/CONTRACT_ADDRESS=.*/g, "").replace(/GANACHE_URL=.*/g, "");
    fs.writeFileSync(backendEnvPath, existing + backendEnvEntry);
  } else {
    fs.writeFileSync(backendEnvPath, backendEnvEntry);
  }
  console.log(`✅ backend/.env updated with CONTRACT_ADDRESS`);

  console.log("\n═══════════════════════════════════════════════");
  console.log("  SHARE WITH SAIRAJ:");
  console.log(`  CONTRACT_ADDRESS = ${address}`);
  console.log("  (already written to backend/.env)");
  console.log("═══════════════════════════════════════════════\n");
}

main().catch((e) => { console.error(e); process.exit(1); });
```

```javascript
// blockchain/hardhat.config.js  [Windows]
require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config();

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.19",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200    // Optimize for deployment cost
      }
    }
  },
  networks: {
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 1337,
    }
  },
  // No external networks — local only
};
```

```bash
# Deploy sequence (must run in this order):
# Terminal 1: Start Ganache (leave running)
npx ganache --port 8545 --deterministic --accounts 5 --db ./ganache-data

# Terminal 2: Compile + Deploy
npx hardhat compile
npx hardhat run scripts/deploy.js --network localhost

# Expected output:
# ✅ Deployed at: 0x5FbDB...
# ✅ ABI exported → web3_bridge/contract_abi.json
# ✅ backend/.env updated with CONTRACT_ADDRESS
```

**Week 3 Checkpoint:** Contract deployed. ABI in `web3_bridge/`. CONTRACT_ADDRESS in both .env files.

---

### WEEK 4 — Web3.py Bridge (Python — for Sairaj)

```python
# blockchain/web3_bridge/web3_client.py  [WSL2]
# ─────────────────────────────────────────────────────────────────
# CREATED BY: Skanda (Blockchain)
# USED BY:    Sairaj (Backend) via blockchain_adapter.py
# PURPOSE:    Python interface to IncidentLogger.sol on Ganache
# ─────────────────────────────────────────────────────────────────

import json
import os
from datetime import datetime, timezone
from web3 import Web3
from web3.exceptions import ContractLogicError

class BlockchainClient:
    """
    GraphSentinel — Local Ganache Forensics Client
    NO Infura. NO Alchemy. NO cloud.
    All data stored on local Ganache chain at 127.0.0.1:8545
    """

    def __init__(self):
        ganache_url = os.getenv("GANACHE_URL", "http://127.0.0.1:8545")

        self.w3 = Web3(Web3.HTTPProvider(
            ganache_url,
            request_kwargs={"timeout": 10}
        ))

        if not self.w3.is_connected():
            raise ConnectionError(
                f"\n[BlockchainClient] Cannot connect to Ganache at {ganache_url}\n"
                "Fix: Open a terminal and run:\n"
                "  cd C:\\Projects\\graphsentinel\\blockchain\n"
                "  npx ganache --port 8545 --deterministic\n"
            )

        # Load ABI from Skanda's exported file
        abi_path = os.path.join(os.path.dirname(__file__), "contract_abi.json")
        if not os.path.exists(abi_path):
            raise FileNotFoundError(
                f"ABI not found at {abi_path}\n"
                "Fix: Run deploy.js first:\n"
                "  npx hardhat run scripts/deploy.js --network localhost"
            )
        with open(abi_path) as f:
            self.abi = json.load(f)

        # Get contract address from env
        contract_address = os.getenv("CONTRACT_ADDRESS", "").strip()
        if not contract_address:
            raise ValueError(
                "CONTRACT_ADDRESS not set in .env\n"
                "Fix: Re-run deploy.js and check backend/.env"
            )

        self.contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(contract_address),
            abi=self.abi
        )

        # Use Ganache account[0] as the transaction sender
        self.account = self.w3.eth.accounts[0]
        chain_id = self.w3.eth.chain_id
        print(f"[BlockchainClient] Connected to chain {chain_id} | Account: {self.account}")

    # ── WRITE: Log an incident ────────────────────────────────────
    def log_incident(
        self,
        source_ip: str,
        attack_type: str,
        severity: int,
        is_blocked: bool,
        sqlite_incident_id: int
    ) -> dict:
        """
        Store an incident fingerprint on Ganache.
        Called by backend after SQLite record is created.

        Returns: {
            tx_hash:      "0x...",
            block_number: 142,
            incident_id:  3,      ← on-chain ID (not same as SQLite ID)
            status:       "confirmed",
            gas_used:     68432
        }
        """
        forensics_uri = f"local://incident/{sqlite_incident_id}"
        severity = max(1, min(int(severity), 10))

        try:
            tx_hash = self.contract.functions.logIncident(
                source_ip,
                attack_type,
                severity,
                is_blocked,
                forensics_uri
            ).transact({
                "from": self.account,
                "gas": 250000     # Well above actual ~68k
            })

            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)

            # Parse return value from logs
            on_chain_id = self.contract.functions.getIncidentCount().call()

            return {
                "tx_hash":      receipt.transactionHash.hex(),
                "block_number": receipt.blockNumber,
                "incident_id":  on_chain_id,
                "status":       "confirmed" if receipt.status == 1 else "failed",
                "gas_used":     receipt.gasUsed,
            }

        except ContractLogicError as e:
            return {"tx_hash": None, "status": "contract_error", "error": str(e)}
        except Exception as e:
            return {"tx_hash": None, "status": "error", "error": str(e)}

    # ── READ: Get all incidents ───────────────────────────────────
    def get_all_incidents(self) -> list:
        """
        Read all incidents from chain.
        Used by backend /forensics endpoint → shown in frontend Blockchain panel.
        """
        count = self.contract.functions.getIncidentCount().call()
        incidents = []

        for i in range(1, count + 1):
            try:
                raw = self.contract.functions.getIncident(i).call()
                incidents.append({
                    "id":              raw[0],
                    "incident_hash":   "0x" + raw[1].hex(),
                    "timestamp":       datetime.fromtimestamp(
                                         raw[2], tz=timezone.utc
                                       ).isoformat(),
                    "source_ip":       raw[3],
                    "attack_type":     raw[4],
                    "severity":        raw[5],
                    "is_blocked":      raw[6],
                    "forensics_uri":   raw[7],
                })
            except Exception as e:
                print(f"[BlockchainClient] Couldn't read incident {i}: {e}")

        return incidents

    # ── READ: Check if IP is blocked on chain ────────────────────
    def is_ip_blocked(self, ip: str) -> bool:
        return self.contract.functions.isIPBlocked(ip).call()

    # ── WRITE: Release a blocked node ────────────────────────────
    def release_node(self, ip: str, reason: str = "MANUAL_OVERRIDE") -> dict:
        tx_hash = self.contract.functions.releaseNode(ip, reason).transact({
            "from": self.account,
            "gas": 100000
        })
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=15)
        return {
            "tx_hash": receipt.transactionHash.hex(),
            "status": "confirmed" if receipt.status == 1 else "failed"
        }

    # ── VERIFY: Tamper-proof demo ─────────────────────────────────
    def verify_incident(self, incident_id: int, source_ip: str,
                         attack_type: str, severity: int, timestamp: int) -> bool:
        """
        Returns True if the incident data matches the on-chain hash.
        Returns False if the data was tampered with.
        USE THIS IN THE VIVA DEMO to prove tamper-proof logging.
        """
        return self.contract.functions.verifyIncident(
            incident_id, source_ip, attack_type, severity, timestamp
        ).call()
```

```python
# blockchain/web3_bridge/test_client.py  [WSL2]
# Quick integration test — run after deploy.js

import os
os.environ["CONTRACT_ADDRESS"] = open("../.env").read().split("CONTRACT_ADDRESS=")[1].split("\n")[0]
os.environ["GANACHE_URL"] = "http://127.0.0.1:8545"

from web3_client import BlockchainClient

client = BlockchainClient()
print("Connection OK ✓")

# Test write
result = client.log_incident("10.0.0.2", "DDoS", 9, False, sqlite_incident_id=1)
print(f"TX Hash: {result['tx_hash']}")
print(f"Block:   {result['block_number']}")
print(f"Gas:     {result['gas_used']}")

# Test read
incidents = client.get_all_incidents()
print(f"On-chain incidents: {len(incidents)}")
print(incidents[0])

# Test verify (should be True)
inc = incidents[0]
is_valid = client.verify_incident(
    1, inc["source_ip"], inc["attack_type"], inc["severity"],
    int(inc["timestamp"][:19].replace("T", " ").replace("-", "").replace(":", "").replace(" ", "").replace("Z","")[:10])
)
print(f"Tamper check (should be True): {is_valid}")
```

**Week 4 Checkpoint:** `python test_client.py` shows TX hash, 1 on-chain incident.

---

### WEEK 5 — Persistence + Demo Reliability

```bash
# CRITICAL: Make Ganache state persist between restarts
# Use --db flag so blockchain history survives restart

# blockchain/.gitignore
echo "ganache-data/" >> .gitignore
echo "node_modules/" >> .gitignore
echo ".env" >> .gitignore
echo "artifacts/" >> .gitignore
echo "cache/" >> .gitignore

# Start Ganache WITH persistence:
npx ganache --port 8545 --deterministic --accounts 5 --db ./ganache-data

# Now if you close Ganache and restart with same command,
# all previous transactions are still there!
```

```javascript
// blockchain/scripts/demo_seed.js  [Windows]
// Seed 3 pre-existing incidents for demo startup — makes demo look active
const { ethers } = require("hardhat");

async function seedDemoData() {
  const Factory = await ethers.getContractFactory("IncidentLogger");
  const address = process.env.CONTRACT_ADDRESS;
  const contract = Factory.attach(address);

  console.log("Seeding demo incidents...");

  await contract.logIncident("10.0.0.2", "DDoS",      9, false, "local://incident/1");
  await contract.logIncident("10.0.0.5", "SSHBrute",  8, true,  "local://incident/2");
  await contract.logIncident("10.0.0.8", "Botnet",    6, false, "local://incident/3");

  console.log(`✅ Seeded 3 incidents. Total: ${await contract.getIncidentCount()}`);
}

seedDemoData().catch(console.error);
```

**Week 5 Checkpoint:** `ganache-data/` persists. Restarting Ganache preserves all incidents.

---

### WEEK 6–7 — Hand Off to Sairaj + Frontend Integration

```javascript
// For Susheep (Frontend) — read blockchain directly using ethers.js
// This goes in frontend/src/services/blockchainService.js

// frontend/src/services/blockchainService.js  [Windows]
import { ethers } from 'ethers'

const GANACHE_URL = 'http://127.0.0.1:8545'
const CONTRACT_ADDRESS = import.meta.env.VITE_CONTRACT_ADDRESS

// ABI — Susheep: copy this from blockchain/web3_bridge/contract_abi.json
// Or better: fetch via backend /api/v1/forensics which returns blockchain_records
const MINIMAL_ABI = [
  "function getIncidentCount() view returns (uint256)",
  "function getIncident(uint256 id) view returns (tuple(uint256,bytes32,uint256,string,string,uint8,bool,string))",
  "function isIPBlocked(string ip) view returns (bool)",
]

export async function getAllOnChainIncidents() {
  // TODO: ALTERNATIVE — just call GET /api/v1/forensics
  // which Sairaj's backend already handles.
  // Only use ethers.js direct read if you want real-time contract events.

  try {
    const provider = new ethers.JsonRpcProvider(GANACHE_URL)
    const contract = new ethers.Contract(CONTRACT_ADDRESS, MINIMAL_ABI, provider)
    const count = await contract.getIncidentCount()

    const incidents = []
    for (let i = 1n; i <= count; i++) {
      const raw = await contract.getIncident(i)
      incidents.push({
        id:           Number(raw[0]),
        incident_hash: "0x" + Buffer.from(raw[1].slice(2), 'hex').toString('hex'),
        timestamp:    new Date(Number(raw[2]) * 1000).toISOString(),
        source_ip:    raw[3],
        attack_type:  raw[4],
        severity:     Number(raw[5]),
        is_blocked:   raw[6],
        forensics_uri: raw[7],
      })
    }
    return incidents
  } catch (e) {
    console.warn('[Blockchain] Direct read failed — using backend API', e)
    return null
  }
}
```

---

### WEEK 8 — Demo Hardening + Viva Proof Script

```bash
# PRE-DEMO GANACHE START COMMAND (always use this exact command):
npx ganache --port 8545 --deterministic --accounts 5 --db ./ganache-data

# POST-DEMO RESET (if you want fresh chain for next run):
# DO NOT delete ganache-data in demo session — it has your seeded incidents

# DEPLOY SEQUENCE FOR CLEAN START:
# 1. Stop any running Ganache
npx kill-port 8545

# 2. Start fresh Ganache
npx ganache --port 8545 --deterministic --accounts 5

# 3. Redeploy contract
npx hardhat run scripts/deploy.js --network localhost

# 4. Seed demo data
npx hardhat run scripts/demo_seed.js --network localhost

# 5. Verify
node -e "
const {Web3} = require('web3');
const w = new Web3('http://127.0.0.1:8545');
w.eth.getBlockNumber().then(n => console.log('Ganache block:', n));
"
```

**VIVA DEMO SCRIPT — Blockchain Forensics Section:**
```
1. Show Ganache terminal — running, block count increasing
2. Trigger attack from Mininet → watch frontend
3. Alert fires → backend writes SQLite → blockchain TX fires
4. Show BlockchainPanel in React: TX hash appears with ✓
5. Open Ganache terminal → show "eth_sendTransaction" in logs
6. TAMPER-PROOF PROOF (key moment):
   a. "What if an attacker deletes this log from our database?"
   b. Run: python verify_tamper.py 1 "10.0.0.2" "DDoS" 9
      → Output: "VALID: Incident matches on-chain hash ✓"
   c. Manually change attack_type in SQLite to "BENIGN"
   d. Run: python verify_tamper.py 1 "10.0.0.2" "BENIGN" 9
      → Output: "TAMPERED: Hash mismatch — data was modified ⚠️"
7. "This is why blockchain matters — the proof is permanent"
```

---

## FAILURE TRIAGE GUIDE

```
SYMPTOM: Ganache won't start (EADDRINUSE)
  → Fix: npx kill-port 8545
  → Then: npx ganache --port 8545 --deterministic

SYMPTOM: deploy.js fails with "Cannot read properties of undefined"
  → Fix: npx hardhat compile first, then run deploy.js

SYMPTOM: web3_client.py — "CONTRACT_ADDRESS not set"
  → Fix: Check backend/.env for CONTRACT_ADDRESS line
  → Run deploy.js again to regenerate

SYMPTOM: web3_client.py — "ContractLogicError"
  → Fix: Severity is out of range OR IP is empty
  → Check: print all args before calling log_incident()

SYMPTOM: Transaction receipt timeout (15s exceeded)
  → Fix: Increase timeout to 30s in wait_for_transaction_receipt()
  → Or: Check Ganache is still running

SYMPTOM: ABI mismatch error
  → Fix: Re-run deploy.js after ANY Solidity change
  → The ABI in web3_bridge/ must match deployed contract

SYMPTOM: Previous incidents gone after Ganache restart
  → Fix: Use --db ./ganache-data flag every time
  → Never restart without this flag during demo
```
