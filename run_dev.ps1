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
    # The daemon must be given exactly the token the backend uses. The backend
    # reads the DAEMON_TOKEN environment variable first, then backend\.env (with
    # any quotes around the value removed), then its built-in default.
    $daemonToken = $env:DAEMON_TOKEN
    $envFile = Join-Path $root "backend\.env"
    if (-not $daemonToken -and (Test-Path $envFile)) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*DAEMON_TOKEN\s*=\s*(.*)$') {
                $daemonToken = $Matches[1].Trim().Trim('"').Trim("'")
                break
            }
        }
    }

    if (-not $daemonToken) {
        # The daemon exits at startup without a token, and the backend falls back to
        # this one, so using it on both sides keeps them matching.
        $daemonToken = "test-token"
        Write-Warning "DAEMON_TOKEN is not set (environment or backend\.env): using the backend's built-in default for the daemon too."
    }
    if ($daemonToken.Contains("'")) {
        Write-Error "DAEMON_TOKEN contains a single quote, which this script cannot pass to WSL safely. Use a token without one."
        exit 1
    }

    $driveLetter = $root.Substring(0, 1).ToLower()
    $wslRoot     = "/mnt/$driveLetter" + ($root.Substring(2) -replace '\\', '/')

    $distroQ = Quote $WslDistro

    # The distribution must exist and start. A wrong -WslDistro name makes
    # wsl.exe print an error and exit non-zero; without this check the three
    # WSL windows below would each fail on their own.
    & wsl.exe -d $WslDistro -u root -- true 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "WSL distribution '$WslDistro' was not found or would not start. Run 'wsl -l -v' to see the names, then pass one with -WslDistro."
        exit 1
    }

    # Mininet, Open vSwitch and an OpenFlow controller must be installed in it.
    # Without a controller binary the topology dies at "*** Starting controller",
    # switch s1 is never created, and every poll of the switch fails with
    # "s1 is not a bridge or a socket".
    $missing = @()
    foreach ($tool in @("mn", "ovs-vsctl", "ovs-ofctl")) {
        & wsl.exe -d $WslDistro -u root -- which $tool 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { $missing += $tool }
    }
    $hasController = $false
    foreach ($tool in @("ovs-controller", "ovs-testcontroller", "test-controller")) {
        & wsl.exe -d $WslDistro -u root -- which $tool 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $hasController = $true; break }
    }
    if (-not $hasController) { $missing += "an OpenFlow controller (openvswitch-testcontroller)" }
    if ($missing.Count -gt 0) {
        Write-Error ("Missing in WSL ($WslDistro): " + ($missing -join ", ") + ". Install them once with:`n" +
                     "  wsl -d $WslDistro -u root -- apt-get install -y mininet openvswitch-switch openvswitch-testcontroller`n" +
                     "then run this script again.")
        exit 1
    }

    $ovsCmd  = Quote "service openvswitch-switch start && echo OVS started && bash"
    Start-Window "GS OVS (WSL)" $root "wsl -d $distroQ -u root -- bash -c $ovsCmd"
    
    Start-Sleep 2

    # The packaged openvswitch-testcontroller service listens on 6653, the port
    # Mininet's own controller wants, and `mn -c` clears what an earlier run left
    # behind (a stale s1, hosts, controllers), so every start is a clean one.
    $mininetCmd  = Quote ("systemctl stop openvswitch-testcontroller 2>/dev/null; service openvswitch-testcontroller stop 2>/dev/null; mn -c >/dev/null 2>&1; cd '" + $wslRoot + "' && python3 mininet/topologies/base_topology_headless.py")
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

# With real Mininet traffic the backend must never fill in for a failed switch
# poll with made-up flows (DEMO_FALLBACK_FLOWS). The variable overrides backend\.env.
# GS_WSL_DISTRO tells the Simulate button's attack scripts which distribution to
# enter: it must be the one running the topology (-WslDistro), not the default.
# It is also set when -WslDistro is given without -WithMininet (Mininet started by hand).
$envPrefix = ""
if ($WithMininet) { $envPrefix += '$env:DEMO_FALLBACK_FLOWS = ''false''; ' }
if ($WithMininet -or $PSBoundParameters.ContainsKey('WslDistro')) { $envPrefix += '$env:GS_WSL_DISTRO = ' + (Quote $WslDistro) + '; ' }
$backendCmd = $envPrefix + "& " + (Quote $py) + " -m uvicorn app.main:socket_app --host 127.0.0.1 --port $BackendPort"
Start-Window "GS backend :$BackendPort" (Join-Path $root "backend") $backendCmd

if (-not $NoFrontend) {
    $frontendCmd = '$env:VITE_BACKEND_URL = ''http://localhost:' + $BackendPort + '''; npm run dev'
    Start-Window "GS frontend :5173" (Join-Path $root "frontend") $frontendCmd
}

if ($WithMininet) {
    Write-Host "Waiting for switch s1 in WSL..."
    $s1Up = $false
    $s1Deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $s1Deadline) {
        & wsl.exe -d $WslDistro -u root -- ovs-vsctl br-exists s1 2>$null
        if ($LASTEXITCODE -eq 0) { $s1Up = $true; break }
        Start-Sleep 3
    }
    if ($s1Up) {
        Write-Host "Switch s1 is up. Simulate Attack can run." -ForegroundColor Green
    } else {
        Write-Warning ("Switch s1 did not appear within 60s, so the topology is not running. " +
                       "Read the 'GS Mininet (WSL)' window for the error; the console's preflight stays red until s1 exists.")
    }
}

Write-Host "Started. Inference answers /health in ~12s, backend in ~16s."
