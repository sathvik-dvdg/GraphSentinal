#!/usr/bin/env bash
# GraphSentinel environment check. Run from the repository root on Ubuntu/Debian
# (WSL or native):
#
#     bash scripts/check_env.sh [--no-install] [--no-build] [--verify]
#
# Checks that this machine can run the stack, installs what it safely can, and
# says exactly how to fix the rest. Exits 0 only if nothing is left broken.
# Versions are read from the project's own files, not written here.
set -euo pipefail

# ── flags ────────────────────────────────────────────────────────────────────
NO_INSTALL=0
NO_BUILD=0
VERIFY=0

usage() {
    cat <<'EOF'
Usage: bash scripts/check_env.sh [options]

  --no-install   Run checks only; print install commands but do not run them.
  --no-build     Skip the frontend build smoke-test.
  --verify       After all checks pass, run ML/verify_stack.py (needs the
                 backend and inference service running).
  --help         Print this and exit.

Run from the repository root. Exits 0 only if every check passed.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --no-install) NO_INSTALL=1 ;;
        --no-build)   NO_BUILD=1 ;;
        --verify)     VERIFY=1 ;;
        --help|-h)    usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

# ── output helpers ───────────────────────────────────────────────────────────
if [ -t 1 ]; then
    C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_FAIL=$'\033[31m'; C_INST=$'\033[36m'
    C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
    C_OK=''; C_WARN=''; C_FAIL=''; C_INST=''; C_DIM=''; C_OFF=''
fi

PASSED=()
WARNED=()
FAILED=()
LAST_OUT=''          # last lines of the most recent failed install

ok()         { PASSED+=("$1"); printf '%s[  OK  ]%s %s\n' "$C_OK" "$C_OFF" "$1"; }
warn()       { WARNED+=("$1"); printf '%s[ WARN ]%s %s%s\n' "$C_WARN" "$C_OFF" "$1" "${2:+ -- $2}"; }
fail()       { FAILED+=("$1"); printf '%s[ FAIL ]%s %s%s\n' "$C_FAIL" "$C_OFF" "$1" "${2:+ -- $2}"; }
installing() { printf '%s[INSTALL]%s %s\n' "$C_INST" "$C_OFF" "$1"; }
skip()       { printf '%s[ SKIP ]%s %s\n' "$C_DIM" "$C_OFF" "$1"; }
note()       { printf '         %s\n' "$1"; }
section()    { printf '\n%s── %s%s\n' "$C_DIM" "$1" "$C_OFF"; }

# ── small tools ──────────────────────────────────────────────────────────────
have() { command -v "$1" >/dev/null 2>&1; }

# ver_ge A B: true when version A >= version B
ver_ge() { [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]; }

SUDO_OK=0
run_priv() {
    if [ "$(id -u)" -eq 0 ]; then "$@"; return; fi
    if [ "$SUDO_OK" -eq 1 ]; then sudo -n "$@"; return; fi
    return 126
}

# apt_install PKG: 0 if installed now, 1 otherwise (LAST_OUT says why)
apt_install() {
    local pkg="$1" out
    if [ "$NO_INSTALL" -eq 1 ]; then
        LAST_OUT="not installed (--no-install). Run: sudo apt-get install -y $pkg"
        return 1
    fi
    installing "$pkg not found -- installing with apt-get..."
    if out=$(DEBIAN_FRONTEND=noninteractive run_priv apt-get install -y "$pkg" 2>&1); then
        return 0
    fi
    if [ "$(id -u)" -ne 0 ] && [ "$SUDO_OK" -eq 0 ]; then
        LAST_OUT="needs root. Run: sudo apt-get install -y $pkg"
    else
        LAST_OUT=$(printf '%s' "$out" | tail -n 3 | tr '\n' ' ')
    fi
    return 1
}

PIP_FLAGS=()
pip_install() {
    local out
    if out=$(python3 -m pip install "${PIP_FLAGS[@]+"${PIP_FLAGS[@]}"}" "$@" 2>&1); then
        return 0
    fi
    LAST_OUT=$(printf '%s' "$out" | tail -n 3 | tr '\n' ' ')
    return 1
}

# Reads requirement lines on stdin; prints  status|requirement|name|installed
# status: ok | missing | mismatch | bad
PYREQ=$(cat <<'PY'
import sys
try:
    from packaging.requirements import Requirement
except Exception:
    from pip._vendor.packaging.requirements import Requirement
from importlib import metadata
for raw in sys.stdin:
    line = raw.split('#', 1)[0].strip()
    if not line or line.startswith('-'):
        continue
    try:
        r = Requirement(line)
    except Exception:
        print('bad|%s||' % line)
        continue
    try:
        v = metadata.version(r.name)
    except metadata.PackageNotFoundError:
        print('missing|%s|%s|' % (line, r.name))
        continue
    good = r.specifier.contains(v, prereleases=True)
    print('%s|%s|%s|%s' % ('ok' if good else 'mismatch', line, r.name, v))
PY
)

req_status() { printf '%s\n' "$1" | python3 -c "$PYREQ" 2>/dev/null || true; }

# The requirement line for one package, as its file states it (CRLF-safe).
req_line() {  # req_line FILE NAME
    tr -d '\r' <"$1" | sed 's/#.*//' | grep -iE "^[[:space:]]*$2([[:space:]]*[=<>!~\[]|[[:space:]]*$)" | head -n1 | tr -d ' ' || true
}

# check_requirements LABEL FILE SKIP_REGEX
check_requirements() {
    local label="$1" file="$2" skip_re="$3" status req name ver again
    if [ ! -f "$file" ]; then
        fail "$label: $file not found"
        return 0
    fi
    if ! printf 'pip\n' | python3 -c "$PYREQ" >/dev/null 2>&1; then
        fail "$label: cannot inspect installed packages" "python3 with pip is required first"
        return 0
    fi
    while IFS='|' read -r status req name ver <&3; do
        if printf '%s' "$name" | grep -qiE "$skip_re"; then continue; fi
        case "$status" in
            ok) ok "$label: $name $ver ($req)" ;;
            bad) warn "$label: could not parse requirement '$req'" ;;
            missing|mismatch)
                if [ "$NO_INSTALL" -eq 1 ]; then
                    fail "$label: $name ${ver:-not installed}, need $req" "python3 -m pip install ${PIP_FLAGS[*]:-} \"$req\""
                    continue
                fi
                installing "$label: $name ${ver:-not installed}, need $req -- installing..."
                if pip_install --upgrade "$req"; then
                    again=$(req_status "$req")
                    if [ "${again%%|*}" = "ok" ]; then
                        ok "$label: $name $(printf '%s' "$again" | cut -d'|' -f4) ($req)"
                    else
                        fail "$label: $name still not $req after install"
                    fi
                else
                    fail "$label: $name install failed ($req)" "$LAST_OUT"
                fi
                ;;
        esac
    done 3< <(tr -d '\r' <"$file" | python3 -c "$PYREQ" 2>/dev/null)
}

# ── paths (all relative to the repository root) ──────────────────────────────
BACKEND_REQ="backend/requirements.txt"
ML_REQ="ML/graphsentinel_v2/requirements.txt"
[ -f ML/graphsentinel_v2/pyproject.toml ] && ML_REQ="ML/graphsentinel_v2/pyproject.toml"

if [ ! -f "$BACKEND_REQ" ] || [ ! -d frontend ] || [ ! -d ML ]; then
    echo "Run this from the GraphSentinel repository root (backend/, frontend/, ML/ not found here)." >&2
    exit 2
fi

# ═════════════════════════════════════════════════════════════════════════════
section "SYSTEM"

# 1. Linux
if [ "$(uname -s)" != "Linux" ]; then
    fail "Not running on Linux ($(uname -s))" \
         "This project runs in WSL or native Linux. On Windows, open a WSL terminal first."
    exit 1
fi
ok "Linux $(uname -r)"

# 2. bash >= 4
if [ "${BASH_VERSINFO[0]}" -ge 4 ]; then
    ok "bash ${BASH_VERSION%%(*} (>= 4 required)"
else
    warn "bash ${BASH_VERSION} is below 4" "sudo apt-get install -y --only-upgrade bash"
fi

# 3. sudo
if [ "$(id -u)" -eq 0 ]; then
    SUDO_OK=1
    ok "running as root"
elif sudo -n true 2>/dev/null; then
    SUDO_OK=1
    ok "sudo available without a password"
else
    warn "sudo not available without a password" \
         "Some installs below need sudo. Re-run with sudo or grant passwordless sudo for this session."
fi

# ═════════════════════════════════════════════════════════════════════════════
section "PYTHON"

# Required Python: backend/pyproject.toml's requires-python if there is one, else 3.10.
PY_MIN="3.10"; PY_MIN_SRC="default (backend states none)"
if [ -f backend/pyproject.toml ]; then
    found=$(grep -E '^[[:space:]]*requires-python' backend/pyproject.toml | grep -oE '[0-9]+\.[0-9]+' | head -n1 || true)
    if [ -n "$found" ]; then PY_MIN="$found"; PY_MIN_SRC="backend/pyproject.toml"; fi
fi

PY_OK=0
check_python() {
    # 4. python3 present
    if ! have python3; then
        if ! apt_install python3 || ! have python3; then
            fail "python3 not found" "${LAST_OUT:-sudo apt-get install -y python3}"
            return 0
        fi
    fi
    # 5. version
    local v img
    v=$(python3 --version 2>&1 | awk '{print $2}')
    if ver_ge "$v" "$PY_MIN"; then
        ok "Python $v (>= $PY_MIN required; $PY_MIN_SRC)"
        PY_OK=1
        # The pins in backend/requirements.txt were installed on the image's
        # Python; a newer interpreter may have no wheels for them.
        img=$(grep -oE '^FROM python:[0-9]+\.[0-9]+' backend/Dockerfile 2>/dev/null | head -n1 | grep -oE '[0-9]+\.[0-9]+' || true)
        if [ -n "$img" ] && ! ver_ge "$img.99" "$v"; then
            warn "Python $v is newer than the $img the backend image uses"                  "pinned packages (numpy, pandas, pydantic) may have no wheels for it; a python$img venv is the safe route"
        fi
    else
        fail "Python $v is below $PY_MIN" \
             "sudo add-apt-repository -y ppa:deadsnakes/ppa && sudo apt-get update && sudo apt-get install -y python${PY_MIN} python${PY_MIN}-venv  (not installed automatically)"
        return 0
    fi
    # 6. pip
    if ! python3 -m pip --version >/dev/null 2>&1; then
        if ! apt_install python3-pip || ! python3 -m pip --version >/dev/null 2>&1; then
            fail "pip for python3 not found" "${LAST_OUT:-sudo apt-get install -y python3-pip}"
            PY_OK=0
            return 0
        fi
    fi
    ok "pip $(python3 -m pip --version | awk '{print $2}')"
    # --break-system-packages exists from pip 23.0.1; older pips reject the flag.
    if python3 -m pip install --help 2>/dev/null | grep -q -- '--break-system-packages'; then
        PIP_FLAGS=(--break-system-packages)
    fi
    # 7. venv
    if python3 -m venv --help >/dev/null 2>&1; then
        ok "python3 venv module"
    elif apt_install python3-venv && python3 -m venv --help >/dev/null 2>&1; then
        ok "python3 venv module"
    else
        fail "python3 venv module missing" "${LAST_OUT:-sudo apt-get install -y python3-venv}"
    fi
}
check_python || true

# ═════════════════════════════════════════════════════════════════════════════
section "PYTHON PACKAGES -- BACKEND ($BACKEND_REQ)"
# torch and torch-geometric are checked together below (check 10).
if [ "$PY_OK" -eq 1 ]; then
    check_requirements "backend" "$BACKEND_REQ" '^(torch|torch[-_]geometric)$' || true
else
    fail "backend packages not checked" "fix Python first"
fi

section "PYTHON PACKAGES -- ML / v2 ($ML_REQ)"
if [ "$PY_OK" -eq 1 ]; then
    if [ "${ML_REQ##*.}" = "toml" ]; then
        # pyproject: pull the dependency strings out and check them the same way
        tmp_req=$(mktemp)
        python3 - "$ML_REQ" >"$tmp_req" 2>/dev/null <<'PY' || true
import sys
try:
    import tomllib
except Exception:
    import pip._vendor.tomli as tomllib
with open(sys.argv[1], 'rb') as fh:
    for dep in tomllib.load(fh).get('project', {}).get('dependencies', []):
        print(dep)
PY
        check_requirements "ml-v2" "$tmp_req" '^(torch|torch[-_]geometric)$' || true
        rm -f "$tmp_req"
    else
        check_requirements "ml-v2" "$ML_REQ" '^(torch|torch[-_]geometric)$' || true
    fi
else
    fail "ML packages not checked" "fix Python first"
fi

# 10. torch, CUDA, torch_geometric
section "TORCH"
check_torch() {
    [ "$PY_OK" -eq 1 ] || { fail "torch not checked" "fix Python first"; return 0; }
    local specs=() f line st tv cuda card_torch pyg_req bad=0
    for f in "$BACKEND_REQ" "$ML_REQ"; do
        [ "${f##*.}" = "txt" ] || continue
        line=$(req_line "$f" torch)
        [ -n "$line" ] && specs+=("$line")
    done
    [ "${#specs[@]}" -gt 0 ] || specs=("torch")
    card_torch=$(python3 -c "import json;print(json.load(open('ML/model_card.json'))['framework']['torch'])" 2>/dev/null || true)

    if ! python3 -c "import torch" >/dev/null 2>&1; then
        # CPU wheel: the default index pulls a multi-GB CUDA build.
        if [ "$NO_INSTALL" -eq 1 ]; then
            fail "torch not installed (need ${specs[*]})" \
                 "python3 -m pip install ${PIP_FLAGS[*]:-} \"${specs[0]}\" --index-url https://download.pytorch.org/whl/cpu"
            return 0
        fi
        installing "torch not found -- installing the CPU wheel (${specs[0]})..."
        if ! pip_install "${specs[0]}" --index-url https://download.pytorch.org/whl/cpu; then
            fail "torch install failed" "$LAST_OUT"
            return 0
        fi
    fi
    tv=$(python3 -c "import torch;print(torch.__version__)" 2>/dev/null || true)
    if [ -z "$tv" ]; then
        fail "torch is installed but does not import" "python3 -c 'import torch' shows the error"
        return 0
    fi
    for line in "${specs[@]}"; do
        st=$(req_status "$line")
        [ "${st%%|*}" = "ok" ] || { bad=1; fail "torch $tv does not satisfy $line" "python3 -m pip install ${PIP_FLAGS[*]:-} --upgrade \"$line\" --index-url https://download.pytorch.org/whl/cpu"; }
    done
    [ "$bad" -eq 0 ] && ok "torch $tv (${specs[*]}; model trained on ${card_torch:-unknown})"

    # CUDA is optional: CPU inference works.
    if [ "$(python3 -c 'import torch;print(torch.cuda.is_available())' 2>/dev/null)" = "True" ]; then
        ok "CUDA available"
        cuda="cu$(python3 -c 'import torch;print((torch.version.cuda or "").replace(".",""))' 2>/dev/null)"
    else
        warn "CUDA not available (CPU inference will be used)" \
             "if wanted: python3 -m pip install ${PIP_FLAGS[*]:-} torch==${tv%%+*} --index-url https://download.pytorch.org/whl/cu121"
        cuda="cpu"
    fi

    pyg_req=$(req_line "$BACKEND_REQ" 'torch[-_]geometric')
    [ -n "$pyg_req" ] || pyg_req="torch-geometric"
    if ! python3 -c "import torch_geometric" >/dev/null 2>&1; then
        if [ "$NO_INSTALL" -eq 1 ]; then
            fail "torch_geometric not installed (need $pyg_req)" \
                 "python3 -m pip install ${PIP_FLAGS[*]:-} \"$pyg_req\""
            note "optional compiled extras: python3 -m pip install pyg_lib torch_scatter torch_sparse -f https://data.pyg.org/whl/torch-${tv%%+*}+${cuda}.html"
            return 0
        fi
        installing "torch_geometric not found -- installing $pyg_req..."
        if ! pip_install "$pyg_req" || ! python3 -c "import torch_geometric" >/dev/null 2>&1; then
            fail "torch_geometric install failed ($pyg_req)" "$LAST_OUT"
            return 0
        fi
    fi
    for f in "$BACKEND_REQ" "$ML_REQ"; do
        [ "${f##*.}" = "txt" ] || continue
        line=$(req_line "$f" 'torch[-_]geometric')
        [ -n "$line" ] || continue
        st=$(req_status "$line")
        if [ "${st%%|*}" = "ok" ]; then
            ok "torch_geometric $(printf '%s' "$st" | cut -d'|' -f4) ($line, $f)"
        elif [ "$NO_INSTALL" -eq 1 ]; then
            fail "torch_geometric $(printf '%s' "$st" | cut -d'|' -f4) does not satisfy $line ($f)" \
                 "python3 -m pip install ${PIP_FLAGS[*]:-} --upgrade \"$line\""
        else
            installing "torch_geometric does not satisfy $line -- installing..."
            if pip_install --upgrade "$line" && [ "$(req_status "$line" | cut -d'|' -f1)" = "ok" ]; then
                ok "torch_geometric ($line, $f)"
            else
                fail "torch_geometric still not $line" "$LAST_OUT"
            fi
        fi
    done
}
check_torch || true

# ═════════════════════════════════════════════════════════════════════════════
section "NODE / FRONTEND"

# Required Node: engines.node in frontend/package.json; if it has none, what the
# installed/locked Vite demands; if neither says, 18.
NODE_MIN="18.0.0"; NODE_REQ=">=18"; NODE_SRC="default (no engines.node)"
if have python3; then
    node_info=$(python3 - <<'PY' 2>/dev/null || true
import json, re
req, src = None, None
try:
    req = json.load(open('frontend/package.json')).get('engines', {}).get('node')
    src = 'frontend/package.json engines.node'
except Exception:
    pass
if not req:
    for path, key in (('frontend/node_modules/vite/package.json', None),
                      ('frontend/package-lock.json', 'node_modules/vite')):
        try:
            d = json.load(open(path))
            d = d['packages'][key] if key else d
            req = d.get('engines', {}).get('node')
            if req:
                src = path + ' (vite engines.node)'
                break
        except Exception:
            pass
if not req:
    req, src = '>=18', 'default (no engines.node)'
vers = [tuple(int(x) for x in (m + '.0.0').split('.')[:3]) for m in re.findall(r'\d+(?:\.\d+){0,2}', req)]
print('%d.%d.%d	%s	%s' % (min(vers) + (req, src)))
PY
)
    if [ -n "$node_info" ]; then
        NODE_MIN=$(printf '%s' "$node_info" | cut -f1)
        NODE_REQ=$(printf '%s' "$node_info" | cut -f2)
        NODE_SRC=$(printf '%s' "$node_info" | cut -f3)
    fi
fi
NODE_MAJOR=${NODE_MIN%%.*}

NODE_OK=0
check_node() {
    local v how
    if [ -f "$HOME/.nvm/nvm.sh" ]; then
        how="nvm install $NODE_MAJOR && nvm use $NODE_MAJOR"
    else
        how="curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | sudo -E bash - && sudo apt-get install -y nodejs"
    fi
    # 11. node
    if ! have node; then
        fail "node not found (need $NODE_REQ)" "$how  (not installed automatically)"
        return 0
    fi
    v=$(node --version | sed 's/^v//')
    if ver_ge "$v" "$NODE_MIN"; then
        ok "node $v ($NODE_REQ required; $NODE_SRC)"
    else
        fail "node $v is below $NODE_MIN ($NODE_REQ; $NODE_SRC)" "$how  (not installed automatically)"
        return 0
    fi
    # 12. npm
    if ! have npm; then
        fail "npm not found although node is present" "sudo apt-get install -y npm, or reinstall node: $how"
        return 0
    fi
    ok "npm $(npm --version 2>/dev/null)"
    NODE_OK=1
}
check_node || true

check_frontend() {
    local out
    [ "$NODE_OK" -eq 1 ] || { fail "frontend dependencies not checked" "fix node first"; return 0; }
    # 13. node_modules
    if [ -d frontend/node_modules ] && [ -n "$(ls -A frontend/node_modules 2>/dev/null)" ]; then
        ok "frontend/node_modules present"
    elif [ "$NO_INSTALL" -eq 1 ]; then
        fail "frontend/node_modules missing" "cd frontend && npm install"
        return 0
    else
        installing "frontend/node_modules missing -- running npm install..."
        if out=$(cd frontend && npm install 2>&1); then
            ok "frontend/node_modules installed"
        else
            fail "npm install failed in frontend/" "$(printf '%s' "$out" | tail -n 3 | tr '\n' ' ')"
            return 0
        fi
    fi
    # 14. build smoke-test
    if [ "$NO_BUILD" -eq 1 ]; then
        skip "frontend build (--no-build)"
    elif out=$(cd frontend && npm run build 2>&1); then
        ok "frontend build"
    else
        fail "frontend build failed" "cd frontend && npm run build"
        printf '%s\n' "$out" | tail -n 5 | sed 's/^/         /'
    fi
}
check_frontend || true

# ═════════════════════════════════════════════════════════════════════════════
section "OPEN VSWITCH / MININET"

# check_tool LABEL TEST_COMMAND APT_PACKAGE
check_tool() {
    local label="$1" test_cmd="$2" pkg="$3"
    if eval "$test_cmd" >/dev/null 2>&1; then ok "$label"; return 0; fi
    if apt_install "$pkg" && eval "$test_cmd" >/dev/null 2>&1; then ok "$label (installed)"; return 0; fi
    fail "$label missing" "${LAST_OUT:-sudo apt-get install -y $pkg}"
    return 1
}

ovs_running() { pgrep -x ovs-vswitchd >/dev/null 2>&1; }

check_ovs() {
    # 15. package   16. ovs-ofctl
    check_tool "openvswitch-switch package" "dpkg -s openvswitch-switch" openvswitch-switch || return 0
    if have ovs-ofctl; then
        ok "ovs-ofctl $(ovs-ofctl --version 2>/dev/null | head -n1 | awk '{print $NF}')"
    else
        fail "ovs-ofctl not found although openvswitch-switch is installed" "sudo apt-get install -y --reinstall openvswitch-switch"
    fi
    # 17. service
    if ovs_running; then
        ok "Open vSwitch running"
    elif [ "$NO_INSTALL" -eq 1 ]; then
        fail "Open vSwitch not running" "sudo service openvswitch-switch start"
    else
        installing "Open vSwitch not running -- starting it..."
        run_priv service openvswitch-switch start >/dev/null 2>&1 || true
        sleep 1
        if ovs_running; then ok "Open vSwitch running (started)"
        else fail "Open vSwitch not running" "sudo service openvswitch-switch start"; fi
    fi
}
check_ovs || true

# 18. mininet   19. mn
if check_tool "mininet (python3 module)" "python3 -c 'import mininet'" mininet; then
    if have mn; then ok "mn $(mn --version 2>&1 | tail -n1)"; else fail "mn command not found" "sudo apt-get install -y --reinstall mininet"; fi
fi
if have mnexec; then ok "mnexec (used by mininet/demo attacks)"
else warn "mnexec not found" "it ships with mininet; the demo attacks need it"; fi

# 20. nmap   21. net-tools
check_tool "nmap" "command -v nmap" nmap || true
check_tool "net-tools (ifconfig)" "command -v ifconfig" net-tools || true

# ═════════════════════════════════════════════════════════════════════════════
section "BLOCKCHAIN"

check_ganache() {
    local spec="" want="" bin="" v out
    if [ -f blockchain/package.json ] && have python3; then
        spec=$(python3 -c "
import json
d=json.load(open('blockchain/package.json'))
print(d.get('devDependencies',{}).get('ganache') or d.get('dependencies',{}).get('ganache') or '')" 2>/dev/null || true)
    fi
    want=$(printf '%s' "$spec" | grep -oE '[0-9]+(\.[0-9]+){0,2}' | head -n1 || true)

    # 22. the project runs `npx ganache` from blockchain/, so a local install counts
    if [ -x blockchain/node_modules/.bin/ganache ]; then bin="blockchain/node_modules/.bin/ganache"
    elif have ganache; then bin="ganache"
    elif have ganache-cli; then bin="ganache-cli"
    fi
    if [ -z "$bin" ]; then
        if [ "$NODE_OK" -ne 1 ]; then
            fail "ganache not found" "fix node first, then: npm install -g \"ganache${spec:+@$spec}\""
            return 0
        fi
        if [ "$NO_INSTALL" -eq 1 ]; then
            fail "ganache not found" "npm install -g \"ganache${spec:+@$spec}\"  (or: cd blockchain && npm ci)"
            return 0
        fi
        installing "ganache not found -- npm install -g ganache${spec:+@$spec}..."
        if out=$(npm install -g "ganache${spec:+@$spec}" 2>&1) && have ganache; then
            bin="ganache"
        else
            fail "ganache install failed" "$(printf '%s' "$out" | tail -n 3 | tr '\n' ' ') Try: sudo npm install -g \"ganache${spec:+@$spec}\""
            return 0
        fi
    fi
    v=$("$bin" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1 || true)
    if [ -z "$want" ] || [ -z "$v" ]; then
        ok "ganache ${v:-present} ($bin)"
    elif [ "${v%%.*}" = "${want%%.*}" ] && ver_ge "$v" "$want"; then
        ok "ganache $v ($spec required by blockchain/package.json; $bin)"
    elif [ "$NO_INSTALL" -eq 1 ] || [ "$NODE_OK" -ne 1 ]; then
        fail "ganache $v does not satisfy $spec (blockchain/package.json)" "npm install -g \"ganache@$spec\""
    else
        installing "ganache $v does not satisfy $spec -- installing..."
        if npm install -g "ganache@$spec" >/dev/null 2>&1; then ok "ganache $(ganache --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1) ($spec)"
        else fail "ganache still does not satisfy $spec" "sudo npm install -g \"ganache@$spec\""; fi
    fi
    # Not on the list, but the deploy step needs Hardhat from here.
    if [ -d blockchain ] && [ ! -d blockchain/node_modules ]; then
        warn "blockchain/node_modules missing" "cd blockchain && npm ci  (needed to deploy the contract)"
    fi
}
check_ganache || true

# 23. web3 is in backend/requirements.txt and was checked (and installed) above;
#     shown again here because the chain depends on it.
if [ "$PY_OK" -eq 1 ]; then
    web3_req=$(req_line "$BACKEND_REQ" web3)
    web3_st=$(req_status "${web3_req:-web3}")
    if [ "${web3_st%%|*}" = "ok" ]; then
        ok "web3 $(printf '%s' "$web3_st" | cut -d'|' -f4) (${web3_req:-any}; $BACKEND_REQ)"
    elif printf '%s
' "${FAILED[@]+"${FAILED[@]}"}" | grep -q 'backend: web3'; then
        note "web3 (${web3_req:-web3}) already reported above; chain writes need it"
    else
        fail "web3 does not satisfy ${web3_req:-web3}" "python3 -m pip install ${PIP_FLAGS[*]:-} \"${web3_req:-web3}\""
    fi
fi

# ═════════════════════════════════════════════════════════════════════════════
section "BACKEND ENVIRONMENT FILE"

env_value() {  # env_value KEY -> value from backend/.env (empty if absent)
    tr -d '\r' <backend/.env 2>/dev/null | grep -E "^[[:space:]]*$1[[:space:]]*=" | tail -n1 | cut -d= -f2- | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' || true
}

describe_key() {
    case "$1" in
        DAEMON_TOKEN) echo "shared secret with enforcement_daemon.py; every switch poll fails without the same value on both sides" ;;
        CONTRACT_ADDRESS) echo "the deployed IncidentLogger address; written by blockchain/scripts/deploy.js; no chain writes without it" ;;
        THREAT_THRESHOLD) echo "v1's block threshold" ;;
        ENFORCEMENT_MODE) echo "simulated or ovs; keep simulated for the demo" ;;
        BLOCKCHAIN_PRIVATE_KEY) echo "optional signer key; leave unset to use Ganache's first account" ;;
        BLOCKCHAIN_EXPECTED_CHAIN_ID) echo "optional; refuse to connect to any other chain id" ;;
        *) echo "see backend/app/config.py" ;;
    esac
}

check_env_file() {
    local key keys
    # 24. the file
    if [ -f backend/.env ]; then
        ok "backend/.env present"
    elif [ -f backend/.env.example ]; then
        if [ "$NO_INSTALL" -eq 1 ]; then
            warn "backend/.env missing" "cp backend/.env.example backend/.env, then edit it"
            return 0
        fi
        cp backend/.env.example backend/.env
        warn "backend/.env was missing" "Copied .env.example to .env -- edit it before starting."
    else
        warn "backend/.env is missing and no .env.example found" \
             "Create it with at least THREAT_THRESHOLD, ENFORCEMENT_MODE, DAEMON_TOKEN."
        return 0
    fi
    # 25. keys with no usable default: Settings fields whose default is absent,
    #     empty or None (read from config.py), plus keys .env.example leaves empty.
    keys=$( {
        python3 - <<'PY' 2>/dev/null || true
import ast
tree = ast.parse(open('backend/app/config.py', encoding='utf-8').read())
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == 'Settings':
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                v = item.value
                if v is None or (isinstance(v, ast.Constant) and v.value in ('', None)):
                    print(item.target.id.upper())
PY
        if [ -f backend/.env.example ]; then
            tr -d '\r' <backend/.env.example | grep -E '^[A-Z_]+=[[:space:]]*$' | cut -d= -f1 || true
        fi
    } | sort -u )
    for key in $keys; do
        if [ -n "$(env_value "$key")" ]; then
            ok "backend/.env sets $key"
        else
            warn "backend/.env missing $key" "$(describe_key "$key")"
        fi
    done
}
check_env_file || true

# ═════════════════════════════════════════════════════════════════════════════
section "ML MODEL FILES"

need_file() {  # need_file PATH MESSAGE
    if [ -s "$1" ]; then ok "$1"; else fail "$1 missing" "$2"; fi
}
need_file ML/GraphSage-model/graphsage_weights.pt "v1 model checkpoint missing. Place the trained weights at ML/GraphSage-model/graphsage_weights.pt."
need_file ML/GraphSage-model/inference_stats.pt   "v1 scaling statistics missing. Place them at ML/GraphSage-model/inference_stats.pt."
need_file ML/weights.pt        "v2 checkpoint missing (it is gitignored). Place it at ML/weights.pt."
need_file ML/model_card.json   "v2 model card missing; the backend refuses to start v2 without it."
need_file ML/named_figures.json "required by the figures guard (ML/graphsentinel_v2/tests/test_figures_guard.py)."

# ═════════════════════════════════════════════════════════════════════════════
section "PORTS"

# Backend port: BACKEND_PORT in backend/.env, else the port RUN_GUIDE.md starts it on.
BACKEND_PORT=""
[ -f backend/.env ] && BACKEND_PORT=$(env_value BACKEND_PORT)
if [ -z "$BACKEND_PORT" ] && [ -f RUN_GUIDE.md ]; then
    BACKEND_PORT=$(grep -E 'app\.main:socket_app.*--port' RUN_GUIDE.md | grep -oE -- '--port [0-9]+' | awk '{print $2}' | head -n1 || true)
fi
[ -n "$BACKEND_PORT" ] || BACKEND_PORT=8000
INFER_PORT=""
[ -f RUN_GUIDE.md ] && INFER_PORT=$(grep -E 'inference\.service:app.*--port' RUN_GUIDE.md | grep -oE -- '--port [0-9]+' | awk '{print $2}' | head -n1 || true)
GANACHE_PORT=$(grep -oE 'ganache_url: str = "[^"]*:([0-9]+)"' backend/app/config.py | grep -oE '[0-9]+"$' | tr -d '"' || true)
DAEMON_PORT=$(grep -oE 'daemon_port: int = [0-9]+' backend/app/config.py | grep -oE '[0-9]+$' || true)
VITE_PORT=$(grep -oE 'port:[[:space:]]*[0-9]+' frontend/vite.config.js 2>/dev/null | grep -oE '[0-9]+' | head -n1 || true)

port_owner() {  # prints "PID name" of the listener on port $1, or nothing
    local line=""
    if have ss; then
        line=$(ss -ltnpH 2>/dev/null | awk -v p=":$1" '$4 ~ p"$" {print; exit}' || true)
        [ -n "$line" ] || return 0
        printf '%s' "$line" | sed -n 's/.*users:(("\([^"]*\)",pid=\([0-9]*\).*/PID \2 \1/p' | grep . || echo "owner not visible (try sudo)"
    elif have netstat; then
        line=$(netstat -ltnp 2>/dev/null | awk -v p=":$1" '$4 ~ p"$" {print $NF; exit}' || true)
        [ -n "$line" ] && echo "$line"
    fi
    return 0
}

check_port() {  # check_port PORT WHAT
    local owner
    [ -n "$1" ] || return 0
    owner=$(port_owner "$1")
    if [ -z "$owner" ]; then ok "port $1 free ($2)"
    else warn "port $1 in use ($owner)" "$2 needs it; nothing was stopped"; fi
}
if have ss || have netstat; then
    check_port "$BACKEND_PORT"        "backend"
    check_port "${VITE_PORT:-5173}"   "Vite dev server"
    check_port "${GANACHE_PORT:-8545}" "Ganache"
    check_port "${DAEMON_PORT:-50051}" "enforcement daemon"
    check_port "$INFER_PORT"          "v2 inference service"
else
    warn "cannot check ports" "neither ss nor netstat found: sudo apt-get install -y iproute2"
fi

# ═════════════════════════════════════════════════════════════════════════════
# 32. optional: the project's own ten-check verifier (needs the stack running)
if [ "$VERIFY" -eq 1 ]; then
    section "VERIFY STACK"
    if [ "${#FAILED[@]}" -gt 0 ]; then
        skip "ML/verify_stack.py (blocking checks failed above)"
    elif out=$(python3 ML/verify_stack.py 2>&1); then
        ok "ML/verify_stack.py"
    else
        fail "ML/verify_stack.py reported failures" "python3 ML/verify_stack.py"
        printf '%s\n' "$out" | grep -iE 'FAIL|UNVERIFIABLE|Error' | tail -n 12 | sed 's/^/         /' || true
    fi
fi

# ── summary ──────────────────────────────────────────────────────────────────
W=54
row() {  # one table row, padded or cut to the box width
    local text="$1"
    [ "${#text}" -le "$W" ] || text="${text:0:$((W - 1))}…"
    printf '║%s%*s║\n' "$text" "$((W - ${#text}))" ''
}
rule() { local l="$1" r="$2" i; printf '%s' "$l"; for ((i = 0; i < W; i++)); do printf '═'; done; printf '%s\n' "$r"; }

n_pass=${#PASSED[@]}; n_warn=${#WARNED[@]}; n_fail=${#FAILED[@]}
total=$((n_pass + n_fail)); cells=20; filled=$cells
[ "$total" -gt 0 ] && filled=$((n_pass * cells / total))
bar=''
for ((i = 0; i < cells; i++)); do if [ "$i" -lt "$filled" ]; then bar+='█'; else bar+='░'; fi; done

echo
rule '╔' '╗'
row "         GraphSentinel — Environment Check"
rule '╠' '╣'
row "$(printf '  PASSED %4d   %s   FAILED %3d' "$n_pass" "$bar" "$n_fail")"
row "$(printf '  WARNED %4d' "$n_warn")"
if [ "$n_fail" -gt 0 ]; then
    rule '╠' '╣'
    row "  FAILED:"
    for item in "${FAILED[@]}"; do row "    ✗ $item"; done
fi
if [ "$n_warn" -gt 0 ]; then
    rule '╠' '╣'
    row "  WARNED:"
    for item in "${WARNED[@]}"; do row "    ⚠ $item"; done
fi
rule '╚' '╝'

if [ "$n_fail" -gt 0 ]; then
    echo
    echo "Still wrong ($n_fail):"
    for item in "${FAILED[@]}"; do echo "  - $item"; done
    exit 1
fi
exit 0
