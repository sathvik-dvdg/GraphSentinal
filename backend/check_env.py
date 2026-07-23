"""
GraphSentinel — Teammate Environment Diagnostic & Auto-Fix Script
=================================================================
Run this on your laptop BEFORE starting the backend for the first time.
It checks your Python version, installed packages, GPU/CUDA, WSL, and more.

HOW TO RUN:
    cd d:/GraphSentinal/backend    (or wherever your repo is cloned)
    python check_env.py

This will print a full report and automatically attempt to fix common issues.
"""

import sys
import os
import subprocess
import platform
import importlib
import json

# ─── ANSI Colors ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}[OK]{RESET}  {msg}")
def err(msg):  print(f"  {RED}[ERR]{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}[WARN]{RESET} {msg}")
def info(msg): print(f"  {CYAN}[INFO]{RESET} {msg}")
def header(msg): print(f"\n{BOLD}{CYAN}{'='*60}{RESET}\n{BOLD}  {msg}{RESET}\n{'='*60}")


# ────────────────────────────────────────────────────────────────────────────
# 1. Python Version
# ────────────────────────────────────────────────────────────────────────────
header("1. Python Environment")

py = sys.version_info
info(f"Python {py.major}.{py.minor}.{py.micro}  at  {sys.executable}")

if py.major == 3 and py.minor >= 11:
    ok("Python version is compatible (3.11+)")
elif py.major == 3 and py.minor == 10:
    warn("Python 3.10 detected — should work, but 3.11+ is recommended")
else:
    err(f"Python {py.major}.{py.minor} is too old. Install Python 3.11 or 3.12.")


# ────────────────────────────────────────────────────────────────────────────
# 2. Virtual Environment Check
# ────────────────────────────────────────────────────────────────────────────
header("2. Virtual Environment")

in_venv = sys.prefix != sys.base_prefix
if in_venv:
    ok(f"Running inside venv: {sys.prefix}")
else:
    warn("NOT inside a virtual environment.")
    warn("Create one with:  python -m venv .venv")
    warn("Then activate:    .venv\\Scripts\\activate  (Windows) or  source .venv/bin/activate  (WSL)")


# ────────────────────────────────────────────────────────────────────────────
# 3. Required Packages
# ────────────────────────────────────────────────────────────────────────────
header("3. Required Package Versions")

REQUIRED = {
    "fastapi":          "0.115.6",
    "uvicorn":          "0.35.0",
    "socketio":         None,
    "dotenv":           None,       # python-dotenv — module name is 'dotenv'
    "sqlalchemy":       "2.0.36",
    "pydantic":         "2.10.4",
    "pydantic_settings": "2.7.0",
    "networkx":         "3.3",
    "pandas":           "2.2.0",
    "numpy":            "1.26.0",
    "sklearn":          "1.5.0",    # scikit-learn
    "scapy":            "2.5.0",
    "web3":             "7.4.0",
    "torch":            None,       # >=2.4.1, checked separately
    "torch_geometric":  "2.5.0",
    "pytest":           "8.0.0",
    "httpx":            "0.26.0",
    "cachetools":       "5.3.3",
}

missing_packages = []

for pkg, expected_ver in REQUIRED.items():
    try:
        mod = importlib.import_module(pkg)
        ver = getattr(mod, "__version__", "?")
        if expected_ver and ver != expected_ver:
            warn(f"{pkg}: installed={ver}  expected={expected_ver}  (minor mismatch, may still work)")
        else:
            ok(f"{pkg}: {ver}")
    except ImportError:
        err(f"{pkg}: NOT INSTALLED")
        # Map module name back to pip package name
        pip_name = {
            "dotenv": "python-dotenv",
            "sklearn": "scikit-learn",
            "socketio": "python-socketio",
            "pydantic_settings": "pydantic-settings",
            "torch_geometric": "torch-geometric",
        }.get(pkg, pkg.replace("_", "-"))
        missing_packages.append(pip_name)

if missing_packages:
    print()
    warn(f"Missing packages: {', '.join(missing_packages)}")
    ans = input(f"\n  Install them now? [y/N]: ").strip().lower()
    if ans == "y":
        subprocess.run([sys.executable, "-m", "pip", "install"] + missing_packages)
        ok("Install attempted. Re-run this script to verify.")


# ────────────────────────────────────────────────────────────────────────────
# 4. PyTorch + CUDA (Critical for RTX GPU)
# ────────────────────────────────────────────────────────────────────────────
header("4. PyTorch & CUDA / GPU")

try:
    import torch
    ver = torch.__version__
    info(f"Torch version: {ver}")

    # Check minimum version 2.4.1
    parts = ver.split("+")[0].split(".")
    try:
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2].split("a")[0].split("b")[0].split("rc")[0])
        if (major, minor, patch) >= (2, 4, 1):
            ok("PyTorch >= 2.4.1  (libomp140 DLL fix included)")
        else:
            err(f"PyTorch {ver} is older than 2.4.1")
            err("On Windows, torch 2.4.0 is missing libomp140.x86_64.dll and will crash!")
            print()
            info("Fix: run this command to upgrade PyTorch with CUDA 12.4 support:")
            print(f"\n    {BOLD}pip install 'torch>=2.4.1' --index-url https://download.pytorch.org/whl/cu124{RESET}\n")
    except (ValueError, IndexError):
        warn(f"Could not parse torch version string: {ver}")

    # CUDA availability
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        cuda_ver = torch.version.cuda
        ok(f"GPU detected: {gpu_name}")
        ok(f"CUDA version: {cuda_ver}")
    else:
        warn("CUDA not available — running on CPU only (ML inference will be slower)")
        info("If you have an Nvidia GPU, install PyTorch with CUDA support:")
        print(f"\n    {BOLD}pip install 'torch>=2.4.1' --index-url https://download.pytorch.org/whl/cu124{RESET}\n")

except ImportError:
    err("PyTorch is NOT installed!")
    print()
    info("Install PyTorch with CUDA 12.4 support (for Nvidia GPUs):")
    print(f"\n    {BOLD}pip install 'torch>=2.4.1' --index-url https://download.pytorch.org/whl/cu124{RESET}\n")
    info("Or CPU-only PyTorch:")
    print(f"\n    {BOLD}pip install 'torch>=2.4.1'{RESET}\n")


# ────────────────────────────────────────────────────────────────────────────
# 5. DLL check (Windows only)
# ────────────────────────────────────────────────────────────────────────────
if platform.system() == "Windows":
    header("5. Windows DLL Check")

    dll_name = "libomp140.x86_64.dll"
    dll_found = False

    search_paths = [
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32"),
        os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "SysWOW64"),
        *os.environ.get("PATH", "").split(os.pathsep),
    ]

    # Also check inside the torch package lib directory
    try:
        import torch
        torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        search_paths.insert(0, torch_lib)
    except ImportError:
        pass

    for path in search_paths:
        full = os.path.join(path, dll_name)
        if os.path.isfile(full):
            dll_found = True
            ok(f"libomp140.x86_64.dll found at: {full}")
            break

    if not dll_found:
        try:
            import torch
            ok("libomp140.x86_64.dll check skipped (PyTorch imported successfully)")
        except ImportError:
            err("libomp140.x86_64.dll NOT FOUND")
            err("This will cause PyTorch to crash when imported!")
            info("Fix: Upgrade PyTorch to >= 2.4.1 (it bundles the DLL):")
            print(f"\n    {BOLD}pip install 'torch>=2.4.1' --index-url https://download.pytorch.org/whl/cu124{RESET}\n")

    # Visual C++ Redistributable
    header("5b. Visual C++ Redistributable")
    try:
        result = subprocess.run(
            ["reg", "query", r"HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            ok("Visual C++ 2015-2022 Redistributable (x64) is installed")
        else:
            warn("Visual C++ 2015-2022 Redistributable (x64) may be missing")
            info("Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe")
    except Exception:
        warn("Could not check for Visual C++ Redistributable")


# ────────────────────────────────────────────────────────────────────────────
# 6. WSL Check (needed for Mininet/OVS network traffic)
# ────────────────────────────────────────────────────────────────────────────
header("6. WSL (Windows Subsystem for Linux)")

if platform.system() == "Windows":
    try:
        result = subprocess.run(["wsl", "--status"], capture_output=True, text=True, timeout=8)
        if result.returncode == 0 or "WSL" in (result.stdout + result.stderr):
            ok("WSL is installed and available")
            result2 = subprocess.run(["wsl", "-l", "-v"], capture_output=True, timeout=8)
            try:
                stdout = result2.stdout.decode("utf-16-le", errors="replace").strip()
            except Exception:
                stdout = result2.stdout.decode("utf-8", errors="replace").strip()
            if stdout:
                info("Installed WSL distros:")
                for line in stdout.splitlines():
                    if line.strip():
                        print(f"    {line}")
        else:
            warn("WSL does not appear to be installed or running")
            info("Install WSL2 with: wsl --install")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        warn("WSL command not found or timed out")
        info("Install WSL2 from Microsoft Store or run: wsl --install")

    header("6b. Ganache URL (Blockchain) — WSL IP Warning")
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            content = f.read()
        if "127.0.0.1:8545" in content:
            warn("GANACHE_URL in .env uses 127.0.0.1")
            warn("If you run the backend INSIDE WSL, Ganache (on Windows) won't be reachable!")
            info("WSL users: find your Windows host IP and update .env:")
            print(f"\n    Run on Windows:  {BOLD}ipconfig{RESET}  — look for 'vEthernet (WSL)' adapter IP")
            print(f"    Then set in .env:  {BOLD}GANACHE_URL=http://<windows-ip>:8545{RESET}\n")
        else:
            ok("GANACHE_URL is configured (not using localhost 127.0.0.1)")
else:
    # Linux/WSL
    info(f"Platform: {platform.system()} — Mininet/OVS runs natively here")
    ok("No WSL required (you are already on Linux)")


# ────────────────────────────────────────────────────────────────────────────
# 7. SQLite / Database Check
# ────────────────────────────────────────────────────────────────────────────
header("7. SQLite & Database")

try:
    import sqlite3
    ok(f"sqlite3 available — version {sqlite3.sqlite_version}")

    test_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_env_check_test.db")
    try:
        conn = sqlite3.connect(test_db)
        conn.execute("CREATE TABLE IF NOT EXISTS _test (id INTEGER PRIMARY KEY)")
        conn.close()
        os.remove(test_db)
        ok("SQLite write test passed (no disk I/O errors)")
    except sqlite3.OperationalError as e:
        err(f"SQLite write test FAILED: {e}")
        if "disk I/O" in str(e):
            err("This is the WSL + Windows-mounted drive bug!")
            info("Fix options:")
            info("  Option A: Run the backend on Windows natively (recommended)")
            info("  Option B: Move the project to a native Linux path (e.g. ~/graphsentinel)")
except ImportError:
    err("sqlite3 is not available — reinstall Python")


# ────────────────────────────────────────────────────────────────────────────
# 8. Node.js / Frontend
# ────────────────────────────────────────────────────────────────────────────
header("8. Node.js & Frontend (npm)")

try:
    node_result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
    npm_result  = subprocess.run(["npm",  "--version"], capture_output=True, text=True, timeout=5)
    node_ver = node_result.stdout.strip()
    npm_ver  = npm_result.stdout.strip()
    major = int(node_ver.lstrip("v").split(".")[0])
    if major >= 18:
        ok(f"Node.js {node_ver}  (>= v18, compatible)")
    else:
        warn(f"Node.js {node_ver}  — v18 or newer is recommended")
        info("Download from: https://nodejs.org")
    ok(f"npm {npm_ver}")
except FileNotFoundError:
    err("Node.js or npm not found")
    info("Install from: https://nodejs.org")
except subprocess.TimeoutExpired:
    warn("Node.js check timed out")


# ────────────────────────────────────────────────────────────────────────────
# 9. Ganache / Blockchain
# ────────────────────────────────────────────────────────────────────────────
header("9. Ganache (Blockchain) Connectivity")

env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
ganache_candidates = ["http://127.0.0.1:8545", "http://172.18.112.1:8545"]

if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            if line.strip().startswith("GANACHE_URL="):
                url = line.strip().split("=", 1)[1].split("#")[0].strip()
                if url and url not in ganache_candidates:
                    ganache_candidates.insert(0, url)

ganache_reachable = False
for url in ganache_candidates:
    try:
        import urllib.request, urllib.error
        req = urllib.request.Request(
            url,
            data=b'{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}',
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = json.loads(resp.read())
            if "result" in body:
                ok(f"Ganache is reachable at {url}  (block #{int(body['result'], 16)})")
                ganache_reachable = True
                break
    except Exception:
        info(f"Ganache not reachable at {url}")

if not ganache_reachable:
    warn("Ganache is NOT reachable on any known address")
    info("Start Ganache CLI:  npx ganache --chain.chainId 1337 --port 8545")
    info("Or download Ganache Desktop: https://trufflesuite.com/ganache/")


# ────────────────────────────────────────────────────────────────────────────
# 10. ML Model Weights
# ────────────────────────────────────────────────────────────────────────────
header("10. ML Model Weights (GraphSAGE)")

base = os.path.dirname(os.path.abspath(__file__))
weights_candidates = [
    os.path.normpath(os.path.join(base, "..", "ML", "GraphSage-model", "graphsage_weights.pt")),
    os.path.normpath(os.path.join(base, "..", "ml", "GraphSage-model", "graphsage_weights.pt")),
]

if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            if line.strip().startswith("WEIGHTS_PATH="):
                rel = line.strip().split("=", 1)[1].split("#")[0].strip()
                abs_path = os.path.normpath(os.path.join(base, rel))
                if abs_path not in weights_candidates:
                    weights_candidates.insert(0, abs_path)

weights_found = False
for path in weights_candidates:
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / 1024 / 1024
        ok(f"Model weights found: {path}  ({size_mb:.1f} MB)")
        weights_found = True
        break

if not weights_found:
    err("graphsage_weights.pt NOT FOUND")
    info("Make sure the ML/ folder was pulled from Git")
    info("If using Git LFS: run  git lfs pull")
    info("Or ask your teammate who trained the model to share the .pt file")


# ────────────────────────────────────────────────────────────────────────────
# 11. .env Config File
# ────────────────────────────────────────────────────────────────────────────
header("11. .env Configuration File")

if os.path.exists(env_file):
    ok(".env file exists")
    required_keys = [
        "SQLITE_PATH", "GANACHE_URL", "CONTRACT_ADDRESS",
        "WEIGHTS_PATH", "ENFORCEMENT_MODE", "DEMO_FALLBACK_FLOWS"
    ]
    with open(env_file) as f:
        env_content = f.read()
    for key in required_keys:
        if key + "=" in env_content:
            ok(f"  {key} is configured")
        else:
            warn(f"  {key} is MISSING from .env — add it!")
else:
    err(".env file MISSING!")
    example = os.path.join(base, ".env.example")
    if os.path.exists(example):
        info("Create it from the example:")
        print(f"\n    {BOLD}copy .env.example .env   (Windows PowerShell){RESET}")
        print(f"    {BOLD}cp .env.example .env     (Linux/WSL){RESET}\n")
    else:
        err(".env.example is also missing — re-clone the repository")


# ────────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────────
header("DIAGNOSTIC COMPLETE — Quick Fix Reference")

print(f"""
{BOLD}If anything above failed, here are the fix commands:{RESET}

  {CYAN}Step 1 — Activate venv:{RESET}
    Windows:   {BOLD}.venv\\Scripts\\activate{RESET}
    WSL/Linux: {BOLD}source .venv/bin/activate{RESET}

  {CYAN}Step 2 — Install all packages:{RESET}
    {BOLD}pip install -r requirements.txt{RESET}

  {CYAN}Step 3 — Install PyTorch with GPU (Nvidia RTX):{RESET}
    {BOLD}pip install "torch>=2.4.1" --index-url https://download.pytorch.org/whl/cu124{RESET}

  {CYAN}Step 4 — Configure .env:{RESET}
    {BOLD}copy .env.example .env{RESET}   (then edit GANACHE_URL and CONTRACT_ADDRESS)

  {CYAN}Step 5 — Start backend (Windows):{RESET}
    {BOLD}python -m uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload{RESET}

  {CYAN}Step 5 — Start backend (WSL — needs sudo for OVS/Mininet):{RESET}
    {BOLD}sudo -E .venv/bin/uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload{RESET}

  {CYAN}Step 6 — Start frontend:{RESET}
    {BOLD}cd ../frontend && npm install && npm run dev{RESET}

  {CYAN}Step 7 — Run Mininet attacks (WSL only):{RESET}
    {BOLD}cd ../mininet/topologies/attack_scripts && sudo python3 demo_controller.py{RESET}

{'='*60}
""")
