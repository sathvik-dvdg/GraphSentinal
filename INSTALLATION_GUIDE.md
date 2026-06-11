# GraphSentinel — WSL2 Installation & Startup Guide

Complete setup guide for running the GraphSentinel pipeline on Windows 11 with WSL2 (Ubuntu 22.04).

---

## System Topology

```
Windows 11 Host
├── React Frontend Dashboard     (Port 5173 — PowerShell)
└── Ganache Blockchain           (Port 8545 — PowerShell)

WSL2 (Ubuntu 22.04)
├── FastAPI Backend              (Port 8000 — Bash)
├── Mininet Topology & OVS       (Root — Bash)
└── GraphSAGE GNN Inference      (Python / PyTorch)
```

---

## Part 1 — WSL2 Setup (Windows PowerShell, Run as Administrator)

### Step 1.1 — Enable Required Windows Features

```powershell
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

Restart your PC after running these.

### Step 1.2 — Install WSL2 and Ubuntu 22.04

```powershell
wsl --install
wsl --set-default-version 2
wsl --install -d Ubuntu-22.04
```

Restart your PC again when prompted.

### Step 1.3 — First Launch

After reboot, open **Ubuntu 22.04** from the Start Menu. On first launch it will ask you to create a Unix username and password:

```
Enter new UNIX username: sathvik
New password:               ← won't show while typing, that's normal
Retype new password:
```

### Step 1.4 — Verify WSL2 is Active

```powershell
wsl --version
# Should show WSL version 2.x.x
```

> **Troubleshooting 0x80080005 error:** If WSL install fails with this error, ensure virtualization is enabled in your BIOS (Intel VT-x / AMD-V), then download and install the WSL2 kernel update from https://aka.ms/wsl2kernel and retry.

---

## Part 2 — Ubuntu System Dependencies (Inside WSL2 Terminal)

### Step 2.1 — Update Package Lists

```bash
sudo apt update && sudo apt upgrade -y
```

### Step 2.2 — Install Python 3.12 and venv

```bash
sudo apt install python3.12 python3.12-venv python3.12-dev python3-pip -y
```

Verify:

```bash
python3 --version
# Expected: Python 3.12.x
```

### Step 2.3 — Install Mininet and Open vSwitch

```bash
sudo apt install mininet -y
```

### Step 2.4 — Install the OpenFlow Controller

```bash
sudo apt install openvswitch-testcontroller -y
```

Verify:

```bash
which controller
# Expected: /usr/bin/controller
```

---

## Part 3 — Python Virtual Environment Setup

> **Important:** Always create the venv inside WSL2's home directory (`~`), NOT inside `/mnt/c/...`. Windows-mounted paths (NTFS) don't support Linux symlinks properly, which breaks venvs.

### Step 3.1 — Create the venv with system-site-packages

The `--system-site-packages` flag allows the venv to access system-installed packages like Mininet:

```bash
python3 -m venv ~/graphsentinel-venv --system-site-packages
```

### Step 3.2 — Activate the venv

```bash
source ~/graphsentinel-venv/bin/activate
```

Your prompt should now show `(graphsentinel-venv)`.

### Step 3.3 — Verify pip resolves to the venv

```bash
which pip
# Expected: /home/sathvik/graphsentinel-venv/bin/pip
```

### Step 3.4 — Install project dependencies

```bash
cd /mnt/c/dev/GraphSentinal/backend
pip install -r requirements.txt
```

---

## Part 4 — Startup Sequence (Run in Order Every Time)

Open a separate terminal for each step as indicated.

### Step 4.1 — Start Ganache Blockchain

**Environment:** Windows PowerShell (Terminal 1)  
**Directory:** `C:\dev\GraphSentinal\blockchain`

```powershell
npx ganache --host 0.0.0.0 --port 8545 --deterministic --accounts 5 --db ./ganache-data
```

Wait for: `Listening on 0.0.0.0:8545`

### Step 4.2 — Deploy Smart Contract

**Environment:** Windows PowerShell (Terminal 2)  
**Directory:** `C:\dev\GraphSentinal\blockchain`

```powershell
npx hardhat run scripts/deploy.js --network localhost
```

Wait for: `✅ CONTRACT_ADDRESS written to backend/.env`

> Only needed on first start or after clearing Ganache database folders.

### Step 4.3 — Start FastAPI Backend

**Environment:** WSL2 Bash (Terminal 3)

```bash
source ~/graphsentinel-venv/bin/activate
cd /mnt/c/dev/GraphSentinal/backend
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
```

Wait for all three status lines:

```
[DB] SQLite initialized [OK]
[ML] Mode: model [OK]
[Blockchain] Connected: True [OK]
```

### Step 4.4 — Start Mininet Network Simulation

**Environment:** WSL2 Bash (Terminal 4)

```bash
cd /mnt/c/dev/GraphSentinal
sudo ~/graphsentinel-venv/bin/python3 mininet/topologies/base_topology.py
```

Wait for: `GraphSentinel network READY`

> Keep this terminal open. Do not exit.

> **Why use the full venv path with sudo?** Plain `sudo python3` ignores your venv. Passing the explicit path gives root privileges while keeping access to all venv packages.

### Step 4.5 — Start React Frontend

**Environment:** Windows PowerShell (Terminal 5)  
**Directory:** `C:\dev\GraphSentinal\frontend`

```powershell
npm run dev
```

Access the dashboard at: **http://localhost:5173**

---

## Part 5 — Path Reference (Windows ↔ WSL2)

| Windows Path | WSL2 Equivalent |
|---|---|
| `C:\dev\GraphSentinal` | `/mnt/c/dev/GraphSentinal` |
| `C:\dev\GraphSentinal\backend` | `/mnt/c/dev/GraphSentinal/backend` |
| `C:\dev\GraphSentinal\frontend` | `/mnt/c/dev/GraphSentinal/frontend` |
| `C:\dev\GraphSentinal\blockchain` | `/mnt/c/dev/GraphSentinal/blockchain` |

---

## Part 6 — Troubleshooting

| Issue | Cause | Fix |
|---|---|---|
| `0x80080005` on WSL install | Virtualization disabled or WSL service not running | Enable Intel VT-x/AMD-V in BIOS, install kernel from https://aka.ms/wsl2kernel |
| `.venv/bin/activate: No such file or directory` | venv was created on Windows (wrong Python) | Delete `.venv`, recreate with WSL2's python3 in `~/graphsentinel-venv` |
| `externally-managed-environment` pip error | pip resolving to system pip instead of venv | Run `which pip` — if not pointing to venv, deactivate and re-activate from `~/graphsentinel-venv` |
| `ModuleNotFoundError: No module named 'mininet'` | Mininet not installed, or venv python can't see it | Run `sudo apt install mininet -y`, use `--system-site-packages` when creating venv |
| `Cannot find required executable controller` | OpenFlow controller not installed | Run `sudo apt install openvswitch-testcontroller -y` |
| `Blockchain connection failed` | Ganache started after the backend | Always start Ganache (Step 4.1) before uvicorn (Step 4.3). Restart the backend terminal. |
| `AF_UNIX socket exceptions` | Windows does not support UNIX sockets for OVS daemon | Safe — backend auto-falls back to `simulated` mode without crashing |
| CORS / Network errors on frontend | Port binding conflict | Backend accepts ports 5173, 5174, and 3000. Restart the Vite server to clear port bindings. |
| `UnicodeEncodeError` on backend startup | Console encoding conflict with status icons | Fixed in current codebase — ASCII status labels are used instead |

---

## Part 7 — Prerequisites Checklist

Before running the startup sequence, verify:

- [ ] Node.js `20.x LTS` installed on Windows Host
- [ ] WSL2 with Ubuntu 22.04 set up and running
- [ ] Python 3.12 installed inside WSL2
- [ ] `~/graphsentinel-venv` created with `--system-site-packages`
- [ ] `pip install -r requirements.txt` completed successfully
- [ ] Mininet installed (`sudo apt install mininet -y`)
- [ ] OpenFlow controller installed (`sudo apt install openvswitch-testcontroller -y`)
- [ ] Hardhat & Ganache installed in `blockchain/` folder
- [ ] `graphsage_weights.pt` placed inside `ML/GraphSage-model/` (or path set in `backend/.env`)
