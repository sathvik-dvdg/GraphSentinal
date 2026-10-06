# Starts the local services, each in its own PowerShell window.
#
#   .\run_dev.ps1                              # inference (8081), ganache (8545), backend (8001), frontend (5173)
#   .\run_dev.ps1 -NoFrontend                  # skip the frontend
#   .\run_dev.ps1 -BackendPort 8000            # run the backend on another port
#   .\run_dev.ps1 -WithMininet                 # also start OVS + Mininet topology + enforcement daemon in WSL
#   .\run_dev.ps1 -WithMininet -WslDistro Debian  # if your WSL distro isn't named Ubuntu
#
# Everything uses backend\.venv: the system Python's torch fails to load
# fbgemm.dll on this machine. The backend reads its GS2_* settings from
# backend\.env; the inference service only reads GRAPHSENTINEL_MODEL_DIR from
# the environment, so it is set here.
param(
    [switch]$NoFrontend,
    [int]$BackendPort = 8001,
    [switch]$WithMininet,
    [string]$WslDistro = "Ubuntu"
)

$root = $PSScriptRoot
$py   = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "backend\.venv not found at $py" }

# Single-quote a value for a child PowerShell -Command string.
# Doubling any ' keeps paths like C:\Users\O'Brien from ending the quote early.
function Quote([string]$s) { "'" + ($s -replace "'", "''") + "'" }

function Start-Window([string]$title, [string]$dir, [string]$command) {
