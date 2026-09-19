#!/usr/bin/env bash
#
# maintenance.sh -- maintenance pass, part 1 of 3 (packages)
#
# Upgrades OS + Docker + NVIDIA Container Toolkit packages, then proves the
# machine still works the way this build left it.
#
#   sudo bash maintenance.sh --plan     # show what apt would do, change nothing
#   sudo bash maintenance.sh --apply    # do it, then verify
#
# Both modes run `apt-get update` (that needs root), which is why --plan is
# also run with sudo. --plan installs, upgrades and removes nothing.
#
# It REFUSES to apply when the plan contains:
#   * any package removal          -- the shape of a branch transition, which is
#                                     what broke unattended-upgrades on this box
#   * any kernel or NVIDIA driver  -- those two are a matched pair on this
#                                     machine and are changed deliberately,
#                                     with the GA fallback kernel verified
#                                     first, never as part of routine upgrades
#
# NOT covered here: the Ollama container image (pinned by tag in compose.yaml)
# is part 2, and the acceptance tests are part 3.
#
# What it verifies after upgrading, by running things rather than reading config:
#   1. docker + containerd are up, and both REALLY store data on /srv/ai-lab
#      (checked with df on the live directories, not by trusting daemon.json --
#      Docker 29 ignored data-root for images once already)
#   2. a container can see the GPU through the freshly upgraded toolkit
#   3. Ollama answers on loopback, still has 64k context, and can actually
#      generate a token with weights in VRAM
#
# Rollback: every version in use is recorded to the log below before anything
# changes, so any package can be put back with
#     sudo apt-get install --allow-downgrades <name>=<version>

set -euo pipefail

MODE="${1:-}"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="/var/log/ai-lab-maintenance-$STAMP.log"
LAB="/srv/ai-lab"
OLLAMA_URL="http://127.0.0.1:11434"
SMOKE_MODEL="qwen3.5:0.8b"        # smallest installed model, fastest honest GPU proof

case "$MODE" in
    --plan|--apply) ;;
    *) echo "usage: sudo bash $0 --plan | --apply" >&2; exit 2 ;;
esac
if [ "$(id -u)" -ne 0 ]; then
    echo "run this with sudo: sudo bash $0 $MODE" >&2
    exit 2
fi

exec > >(tee -a "$LOG") 2>&1
echo "=== ai-lab maintenance $STAMP  mode=$MODE"
echo "=== log: $LOG"
echo

# ---------------------------------------------------------------- before state
echo "==> state before"
echo "    kernel:  $(uname -r)"
echo "    driver:  $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo '(nvidia-smi failed)')"
echo "    holds:   $(apt-mark showhold | tr '\n' ' ')(none expected)"
printf '    versions recorded for rollback:\n'
for p in docker-ce docker-ce-cli containerd.io nvidia-container-toolkit libnvidia-container1; do
    v="$(dpkg-query -W -f='${Version}' "$p" 2>/dev/null || true)"
    [ -n "$v" ] && printf '      %-28s %s\n' "$p" "$v"
done
dpkg -l > "/var/log/ai-lab-dpkg-before-$STAMP.txt"
echo "    full package list: /var/log/ai-lab-dpkg-before-$STAMP.txt"
echo "    $LAB usage: $(df -h --output=used,avail,pcent "$LAB" | tail -1)"
echo

# ---------------------------------------------------------------------- plan
echo "==> apt-get update"
apt-get update -qq

echo "==> plan (simulation, nothing installed)"
PLAN="$(mktemp)"
# --with-new-pkgs lets an upgrade pull in a new dependency (docker splits packages
# this way) while still never removing anything.
apt-get -s --with-new-pkgs upgrade > "$PLAN"

REMOVALS="$(grep -E '^(Remv|Purg) ' "$PLAN" | awk '{print $2}' | tr '\n' ' ' || true)"
KERNEL_DRIVER="$(grep -E '^(Inst|Conf) ' "$PLAN" | awk '{print $2}' \
                 | grep -E '^(linux-image|linux-headers|linux-modules|nvidia-driver|nvidia-dkms|nvidia-kernel)' \
                 | tr '\n' ' ' || true)"
HELD_BACK="$(awk '/kept back/{f=1;next} f&&/^[[:space:]]/{print;next} f{exit}' "$PLAN" | tr -s ' \n' ' ' || true)"

grep -E '^(Inst|Remv|Purg) ' "$PLAN" | sed 's/^/    /' || echo "    (nothing to do)"
echo
grep -E '^[0-9]+ upgraded' "$PLAN" | sed 's/^/    /'
echo

REFUSE=0
if [ -n "$REMOVALS" ]; then
    echo "!!  PLAN REMOVES PACKAGES: $REMOVALS"
    echo "!!  A removal in a routine upgrade is the shape of a branch transition."
    echo "!!  Stopping. Look at what is being removed before going further."
    REFUSE=1
fi
if [ -n "$KERNEL_DRIVER" ]; then
    echo "!!  PLAN TOUCHES KERNEL OR NVIDIA DRIVER: $KERNEL_DRIVER"
    echo "!!  On this machine those move together, with the GA fallback kernel"
    echo "!!  checked first. Not as part of a package sweep. Stopping."
    REFUSE=1
fi
[ -n "$HELD_BACK" ] && echo "note: kept back (not an error): $HELD_BACK"
rm -f "$PLAN"

if [ "$REFUSE" -eq 1 ]; then
    echo
    echo "==> refused. Nothing was changed. Send me this log."
    exit 1
fi

if [ "$MODE" = "--plan" ]; then
    echo "==> plan looks clean. Nothing was changed."
    echo "==> to apply:  sudo bash $0 --apply"
    exit 0
fi

# --------------------------------------------------------------------- apply
echo "==> upgrading"
DEBIAN_FRONTEND=noninteractive apt-get -y --with-new-pkgs \
    -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold upgrade
echo

echo "==> restarting docker + containerd"
systemctl restart containerd
systemctl restart docker
sleep 5
systemctl is-active containerd docker | sed 's/^/    /'
echo

# --------------------------------------------------------------------- verify
FAIL=0
fail() { echo "    FAIL: $*"; FAIL=$((FAIL + 1)); }
pass() { echo "    pass: $*"; }

echo "==> check 1: docker and containerd really store data on $LAB"
LABSRC="$(df --output=source "$LAB" | tail -1)"
DROOT="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo '')"
CROOT="$(awk -F'"' '/^[[:space:]]*root[[:space:]]*=/ {print $2; exit}' /etc/containerd/config.toml 2>/dev/null || echo '')"
for pair in "docker:$DROOT" "containerd:$CROOT"; do
    name="${pair%%:*}"; dir="${pair#*:}"
    if [ -z "$dir" ] || [ ! -d "$dir" ]; then
        fail "$name root is '$dir' -- missing or unreadable"
        continue
    fi
    src="$(df --output=source "$dir" | tail -1)"
    if [ "$src" = "$LABSRC" ]; then
        pass "$name root $dir is on $LABSRC ($(df -h --output=used "$dir" | tail -1 | tr -d ' ') used)"
    else
        fail "$name root $dir is on $src, NOT $LABSRC -- image store escaped to the NVMe again"
    fi
done
echo

echo "==> check 2: a container can see the GPU through the upgraded toolkit"
GPUIMG=""
for img in nvidia/cuda:12.6.3-base-ubuntu24.04 ollama/ollama:0.33.3; do
    docker image inspect "$img" >/dev/null 2>&1 && { GPUIMG="$img"; break; }
done
if [ -z "$GPUIMG" ]; then
    fail "no local image to test the GPU with (expected the cuda base or the ollama image)"
else
    if GPUOUT="$(docker run --rm --gpus all --entrypoint nvidia-smi "$GPUIMG" -L 2>&1)"; then
        echo "$GPUOUT" | sed 's/^/      /'
        echo "$GPUOUT" | grep -q 'GPU 0' && pass "container saw the GPU (via $GPUIMG)" \
                                         || fail "nvidia-smi ran in the container but listed no GPU"
    else
        echo "$GPUOUT" | sed 's/^/      /'
        fail "container could not use --gpus all -- check the toolkit upgrade"
    fi
fi
echo

echo "==> check 3: Ollama is back, loopback-only, 64k context, generating on the GPU"
if ! docker ps --format '{{.Names}}' | grep -qx ollama; then
    echo "    ollama container is not running; starting it"
    docker start ollama >/dev/null 2>&1 || true
    sleep 5
fi
for i in $(seq 1 30); do
    curl -fsS -m 3 "$OLLAMA_URL/api/version" >/dev/null 2>&1 && break
    sleep 2
done
VER="$(curl -fsS -m 5 "$OLLAMA_URL/api/version" 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin)["version"])' 2>/dev/null || echo '')"
if [ -n "$VER" ]; then
    pass "Ollama answering on loopback, version $VER"
else
    fail "Ollama did not answer on $OLLAMA_URL"
fi

# loopback-only: the published port must be bound to 127.0.0.1, not 0.0.0.0
PORTS="$(docker port ollama 2>/dev/null | tr '\n' ' ' || echo '')"
case "$PORTS" in
    *0.0.0.0*|*:::*) fail "ollama port is exposed beyond loopback: $PORTS" ;;
    *127.0.0.1*)     pass "port binding is loopback-only: $PORTS" ;;
    *)               fail "unexpected port binding: '$PORTS'" ;;
esac

CTX="$(docker inspect ollama --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null \
        | awk -F= '$1=="OLLAMA_CONTEXT_LENGTH"{print $2}' || echo '')"
[ "$CTX" = "65536" ] && pass "OLLAMA_CONTEXT_LENGTH=$CTX" || fail "OLLAMA_CONTEXT_LENGTH is '$CTX', expected 65536"

if [ -n "$VER" ]; then
    echo "    generating one token with $SMOKE_MODEL ..."
    GEN="$(curl -fsS -m 300 "$OLLAMA_URL/api/generate" \
            -d "{\"model\":\"$SMOKE_MODEL\",\"prompt\":\"say ok\",\"stream\":false,\"options\":{\"num_predict\":8}}" \
            2>/dev/null || echo '')"
    if [ -n "$GEN" ] && printf '%s' "$GEN" | python3 -c 'import sys,json;sys.exit(0 if json.load(sys.stdin).get("done") else 1)' 2>/dev/null; then
        pass "generation completed"
        VRAM="$(curl -fsS -m 5 "$OLLAMA_URL/api/ps" | python3 -c '
import sys, json
for m in json.load(sys.stdin).get("models", []):
    pct = m.get("size_vram", 0) / max(m.get("size", 1), 1) * 100
    print(m["name"], "%.0f" % pct)
' 2>/dev/null | head -1)"
        pct="${VRAM##* }"
        if [ -n "$pct" ] && [ "${pct%.*}" -gt 0 ] 2>/dev/null; then
            pass "weights are in VRAM: ${VRAM% *} at ${pct}% GPU"
        else
            fail "model loaded but nothing is in VRAM ('$VRAM') -- it fell back to CPU"
        fi
    else
        fail "$SMOKE_MODEL did not generate"
    fi
fi
echo

# ---------------------------------------------------------------------- after
echo "==> state after"
echo "    kernel:  $(uname -r)"
echo "    driver:  $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo '(nvidia-smi failed)')"
for p in docker-ce containerd.io nvidia-container-toolkit; do
    printf '    %-28s %s\n' "$p" "$(dpkg-query -W -f='${Version}' "$p" 2>/dev/null || echo '-')"
done
if [ -f /var/run/reboot-required ]; then
    echo "    REBOOT REQUESTED by: $(tr '\n' ' ' < /var/run/reboot-required.pkgs 2>/dev/null)"
    echo "    (nothing here needs it immediately; reboot when convenient)"
else
    echo "    no reboot required"
fi
echo

if [ "$FAIL" -eq 0 ]; then
    echo "==> all checks passed. Log: $LOG"
else
    echo "==> $FAIL check(s) FAILED. Log: $LOG"
    echo "==> send me the log. Rollback versions are recorded at the top of it."
    exit 1
fi
