param(
    [switch]$NoFrontend,
    [int]$BackendPort = 8001,
    [switch]$WithMininet,
    [string]$WslDistro = "Ubuntu"
)

$root = $PSScriptRoot
$py   = Join-Path $root "backend\.venv\Scripts\python.exe"

function Quote([string]$s) {
    "'" + ($s -replace "'", "''") + "'"
}

function Start-Window([string]$title, [string]$dir, [string]$command) {
    $q    = Quote $title
    $dq   = Quote $dir
    $body = '$Host.UI.RawUI.WindowTitle = ' + $q + '; Set-Location -LiteralPath ' + $dq + '; ' + $command
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $body
}

if ($WithMininet) {
    $daemonToken = ""
    $envFile = Join-Path $root "backend\.env"
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match "^DAEMON_TOKEN=(.*)") {
                $daemonToken = $Matches[1]
                break
            }
        }
    }

    if (-not $daemonToken) {
        Write-Warning "DAEMON_TOKEN not found in backend\.env"
    }

    $driveLetter = $root.Substring(0, 1).ToLower()
    $wslRoot     = "/mnt/$driveLetter" + ($root.Substring(2) -replace '\\', '/')

    $distroQ = Quote $WslDistro
    
    $ovsCmd  = Quote "service openvswitch-switch start && echo OVS started && bash"
    Start-Window "GS OVS (WSL)" $root "wsl -d $distroQ -u root -- bash -c $ovsCmd"
    
    Start-Sleep 2

    $mininetCmd  = Quote ("cd '" + $wslRoot + "' && python3 mininet/topologies/base_topology_headless.py")
    Start-Window "GS Mininet (WSL)" $root "wsl -d $distroQ -u root -- bash -c $mininetCmd"

    $daemonCmd   = Quote ("cd '" + $wslRoot + "' && DAEMON_TOKEN='" + $daemonToken + "' python3 backend/scripts/enforcement_daemon.py")
    Start-Window "GS daemon (WSL)" $root "wsl -d $distroQ -u root -- bash -c $daemonCmd"
}

$mlDir   = Join-Path $root "ML"
$infCmd  = '$env:GRAPHSENTINEL_MODEL_DIR = ' + (Quote $mlDir) + '; & ' + (Quote $py) + ' -m uvicorn graphsentinel.inference.service:app --host 127.0.0.1 --port 8081'
Start-Window "GS inference :8081" (Join-Path $root "ML\graphsentinel_v2") $infCmd

$ganacheCmd = "npx ganache --host 127.0.0.1 --port 8545 --deterministic --accounts 5 --db ./ganache-data"
Start-Window "Ganache :8545" (Join-Path $root "blockchain") $ganacheCmd

Write-Host "Waiting for Ganache on :8545..."
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline -and -not (Test-NetConnection 127.0.0.1 -Port 8545 -WarningAction SilentlyContinue).TcpTestSucceeded) {
    Start-Sleep 2
}

$backendCmd = "& " + (Quote $py) + " -m uvicorn app.main:socket_app --host 127.0.0.1 --port $BackendPort"
Start-Window "GS backend :$BackendPort" (Join-Path $root "backend") $backendCmd

if (-not $NoFrontend) {
    $frontendCmd = '$env:VITE_BACKEND_URL = ''http://localhost:' + $BackendPort + '''; npm run dev'
    Start-Window "GS frontend :5173" (Join-Path $root "frontend") $frontendCmd
}

Write-Host "Started. Inference answers /health in ~12s, backend in ~16s."
