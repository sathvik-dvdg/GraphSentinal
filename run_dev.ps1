# Starts the local services, each in its own PowerShell window.
#
#   .\run_dev.ps1                     # inference (8081), ganache (8545), backend (8001), frontend (5173)
#   .\run_dev.ps1 -NoFrontend         # skip the frontend
#   .\run_dev.ps1 -BackendPort 8000   # run the backend on another port
#
# Everything uses backend\.venv: the system Python's torch fails to load
# fbgemm.dll on this machine. The backend reads its GS2_* settings from
# backend\.env; the inference service only reads GRAPHSENTINEL_MODEL_DIR from
# the environment, so it is set here.
param([switch]$NoFrontend, [int]$BackendPort = 8001)

$root = $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "backend\.venv not found at $py" }

# Single-quote a value for the child PowerShell's -Command string. Doubling any
# ' keeps a clone path like C:\Users\O'Brien\GraphSentinal from ending the quote.
function Quote([string]$s) { "'" + ($s -replace "'", "''") + "'" }

function Start-Window($title, $dir, $command) {
    $wrapped = "`$Host.UI.RawUI.WindowTitle = $(Quote $title); Set-Location -LiteralPath $(Quote $dir); $command"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $wrapped
}

Start-Window "GS inference :8081" (Join-Path $root "ML\graphsentinel_v2") `
    "`$env:GRAPHSENTINEL_MODEL_DIR = $(Quote "$root\ML"); & $(Quote $py) -m uvicorn graphsentinel.inference.service:app --host 127.0.0.1 --port 8081"

Start-Window "Ganache :8545" (Join-Path $root "blockchain") `
    "npx ganache --host 127.0.0.1 --port 8545 --deterministic --accounts 5 --db ./ganache-data"

# The backend connects to Ganache once at startup and never retries, and Ganache
# can take 30s to listen (npx falls back to a slower NodeJS build). Wait for it,
# or the backend starts with the blockchain disconnected.
Write-Host "Waiting for Ganache on :8545..."
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline -and -not (Test-NetConnection 127.0.0.1 -Port 8545 -WarningAction SilentlyContinue).TcpTestSucceeded) { Start-Sleep 2 }
if ((Get-Date) -ge $deadline) { Write-Warning "Ganache did not answer within 90s; starting the backend anyway (blockchain will be disconnected)." }

Start-Window "GS backend :$BackendPort" (Join-Path $root "backend") `
    "& $(Quote $py) -m uvicorn app.main:socket_app --host 127.0.0.1 --port $BackendPort"

# The frontend calls the backend at VITE_BACKEND_URL, and frontend\.env sets it
# to :8000. A VITE_* variable already in the environment takes priority over
# .env files, so set it here; otherwise every request goes to a port nothing
# listens on (ERR_CONNECTION_REFUSED, dashboard stuck OFFLINE).
if (-not $NoFrontend) {
    Start-Window "GS frontend :5173" (Join-Path $root "frontend") `
        "`$env:VITE_BACKEND_URL = 'http://localhost:$BackendPort'; npm run dev"
}

Write-Host "Started. Inference answers /health in ~12s, backend (:$BackendPort) in ~16s. Then: python ML\verify_stack.py (set GS_BACKEND_URL if -BackendPort is not 8001)"
