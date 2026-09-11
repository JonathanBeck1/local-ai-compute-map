#!/usr/bin/env bash
#
# acceptance-tests.sh -- phase 02 acceptance checks A2.1 - A2.9
#
# "The phase is not done because the commands were typed. It is done when these
#  produce the expected output and you have pasted it into HARDWARE.md."
#
# Read-only, with ONE exception: A2.5 stores a small baseline file under
# ~/.ai-lab/ so that a later run, after a reboot, can compare against it.
# Nothing else is written and nothing is modified.
#
# Usage:
#     bash acceptance-tests.sh              # run everything
#     bash acceptance-tests.sh 2>&1 | tee acceptance-$(date +%F).log
#
# A2.2 and A2.3 pull container images and need network on first run.

set -uo pipefail

STATE_DIR="${HOME}/.ai-lab"
BASELINE="${STATE_DIR}/a2.1-baseline.txt"

CUDA_IMAGE="${CUDA_IMAGE:-nvidia/cuda:12.6.3-base-ubuntu24.04}"
PYTORCH_IMAGE="${PYTORCH_IMAGE:-pytorch/pytorch:2.14.0-cuda12.6-cudnn9-runtime}"

EXPECT_GPU="${EXPECT_GPU:-NVIDIA GeForce RTX 4070}"
EXPECT_VRAM="${EXPECT_VRAM:-12282}"
EXPECT_UUID="${EXPECT_UUID:-}"   # set to your GPU UUID (nvidia-smi --query-gpu=uuid) to check it survives reinstalls

pass=0; fail=0; skip=0; manual=0

c_ok=""; c_no=""; c_sk=""; c_rs=""
if [ -t 1 ]; then
    c_ok="\033[32m"; c_no="\033[31m"; c_sk="\033[33m"; c_rs="\033[0m"
fi

hdr()  { printf '\n\033[1m=== %s ===\033[0m\n' "$1"; }
ok()   { printf "${c_ok}PASS${c_rs}  %s\n" "$1"; pass=$((pass+1)); }
no()   { printf "${c_no}FAIL${c_rs}  %s\n" "$1"; fail=$((fail+1)); }
sk()   { printf "${c_sk}SKIP${c_rs}  %s\n" "$1"; skip=$((skip+1)); }
mn()   { printf "${c_sk}MANUAL${c_rs} %s\n" "$1"; manual=$((manual+1)); }
out()  { printf '      | %s\n' "$@"; }

have() { command -v "$1" >/dev/null 2>&1; }

show() { while IFS= read -r l; do printf '      | %s\n' "$l"; done; }

printf '\033[1mphase 02 acceptance tests\033[0m\n'
printf 'date : %s\n' "$(date -u '+%Y-%m-%d %H:%M:%SZ')"
printf 'host : %s\n' "$(hostname 2>/dev/null || echo unknown)"
printf 'cuda image    : %s\n' "$CUDA_IMAGE"
printf 'pytorch image : %s\n' "$PYTORCH_IMAGE"

# ---------------------------------------------------------------- A2.1
hdr "A2.1  driver and GPU visible to the host"
if ! have nvidia-smi; then
    no "nvidia-smi not installed"
    A21=""
else
    A21="$(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1)"
    printf '%s\n' "$A21" | show
    if printf '%s' "$A21" | grep -q "$EXPECT_GPU" && printf '%s' "$A21" | grep -q "$EXPECT_VRAM"; then
        ok "GPU and VRAM as expected"
    else
        no "expected '$EXPECT_GPU' and '$EXPECT_VRAM' MiB"
    fi
    U="$(nvidia-smi --query-gpu=uuid --format=csv,noheader 2>/dev/null | tr -d ' ')"
    if [ -z "$EXPECT_UUID" ]; then sk "EXPECT_UUID not set; UUID check skipped"
    elif [ "$U" = "$EXPECT_UUID" ]; then ok "GPU UUID matches the recorded one"
    else no "GPU UUID is '$U', expected '$EXPECT_UUID'"; fi
fi

# ---------------------------------------------------------------- A2.2
hdr "A2.2  GPU visible inside a container"
if ! have docker; then
    sk "docker not installed"
elif ! docker info >/dev/null 2>&1; then
    no "cannot talk to the docker daemon (is your user in the docker group? did you log out and back in?)"
else
    R="$(docker run --rm --gpus all "$CUDA_IMAGE" nvidia-smi -L 2>&1)"
    printf '%s\n' "$R" | show
    if printf '%s' "$R" | grep -q "$EXPECT_GPU"; then ok "container sees the 4070"
    else no "container did not report the 4070"; fi
fi

# ---------------------------------------------------------------- A2.3
hdr "A2.3  CUDA usable from PyTorch"
if ! have docker; then
    sk "docker not installed"
elif ! docker info >/dev/null 2>&1; then
    sk "docker daemon unreachable"
else
    R="$(docker run --rm --gpus all "$PYTORCH_IMAGE" \
         python -c "import torch;print(torch.cuda.get_device_name(0))" 2>&1)"
    printf '%s\n' "$R" | show
    if printf '%s' "$R" | grep -q "$EXPECT_GPU"; then ok "PyTorch sees the 4070"
    else no "PyTorch did not report the 4070"; fi
fi

# ---------------------------------------------------------------- A2.4
hdr "A2.4  driver is held"
H="$(apt-mark showhold 2>/dev/null | grep -i nvidia || true)"
if [ -n "$H" ]; then
    printf '%s\n' "$H" | show
    ok "nvidia packages are held"
else
    no "no nvidia package is held -- run: sudo apt-mark hold nvidia-driver-<VERSION>-open"
fi

# ---------------------------------------------------------------- A2.5
hdr "A2.5  survives a reboot"
mkdir -p "$STATE_DIR" 2>/dev/null
if [ -z "${A21:-}" ]; then
    sk "no A2.1 output to compare"
elif [ ! -f "$BASELINE" ]; then
    printf '%s\n' "$A21" > "$BASELINE"
    mn "baseline saved to $BASELINE -- reboot, then re-run this script to complete A2.5"
else
    if [ "$A21" = "$(cat "$BASELINE")" ]; then
        ok "A2.1 output identical to the saved baseline"
        UP="$(uptime -p 2>/dev/null || true)"
        [ -n "$UP" ] && out "uptime: $UP"
    else
        no "A2.1 output changed since the baseline"
        out "baseline: $(cat "$BASELINE")"
        out "now     : $A21"
    fi
fi

# ---------------------------------------------------------------- A2.6
hdr "A2.6  no driver errors in the boot log"
if ! have journalctl; then
    sk "journalctl not available"
else
    N="$(journalctl -p err -b 2>/dev/null | grep -ci nvidia || true)"
    [ -z "$N" ] && N=0
    out "error-level nvidia lines this boot: $N"
    if [ "$N" -eq 0 ]; then ok "clean boot log"
    else
        no "$N nvidia error lines"
        journalctl -p err -b 2>/dev/null | grep -i nvidia | head -10 | show
    fi
fi

# ---------------------------------------------------------------- A2.7
hdr "A2.7  rescue media boots and mounts root"
mn "not automatable -- boot the Ubuntu installer USB, choose Try Ubuntu, then:"
out "sudo mkdir -p /mnt/root && sudo mount /dev/<root-partition> /mnt/root && ls /mnt/root"
out "record the output in HARDWARE.md. Keep that stick; it is the rescue medium."

# ---------------------------------------------------------------- A2.8
hdr "A2.8  what is listening"
if ! have ss; then
    sk "ss not available"
else
    L="$(ss -tlnp 2>/dev/null)"
    printf '%s\n' "$L" | head -15 | show
    if printf '%s' "$L" | grep -qE ':22\b'; then
        ok "something is listening on port 22"
        printf '%s' "$L" | grep -qE ':22\b.*systemd' && out "owner is systemd -- correct, Ubuntu uses socket activation"
    else
        no "nothing on port 22 -- run: sudo apt install -y openssh-server && sudo systemctl enable --now ssh"
    fi
    out "save this list as your baseline of what should be reachable"
fi

# ---------------------------------------------------------------- A2.9
hdr "A2.9  bulk disk mounts on its own"
if findmnt /srv/ai-lab >/dev/null 2>&1; then
    findmnt -o TARGET,SOURCE,FSTYPE,OPTIONS /srv/ai-lab 2>/dev/null | show
    df -h /srv/ai-lab 2>/dev/null | show
    ok "/srv/ai-lab is a real mount"
    SRC="$(findmnt -no SOURCE /srv/ai-lab 2>/dev/null)"
    if printf '%s' "$SRC" | grep -qE 'nvme'; then
        no "it is mounted from an NVMe device ($SRC) -- expected the Samsung SATA disk"
    fi
    grep -q 'ai-lab' /etc/fstab 2>/dev/null && ok "an fstab entry exists" || no "no fstab entry -- it will not survive a reboot"
    grep 'ai-lab' /etc/fstab 2>/dev/null | grep -q 'nofail' && ok "fstab entry has nofail" \
        || no "fstab entry lacks nofail -- a failed disk will strand this machine at an emergency shell"
else
    no "/srv/ai-lab is NOT mounted"
    if [ -d /srv/ai-lab ]; then
        out "the directory exists on the root filesystem, which is what nofail leaves behind."
        out "df alone would look fine here and be wrong. This is the failure findmnt is for."
    fi
fi

# ---------------------------------------------------------------- summary
printf '\n\033[1m=== summary ===\033[0m\n'
printf 'pass %d   fail %d   skip %d   manual %d\n' "$pass" "$fail" "$skip" "$manual"
printf '\nPaste this output into HARDWARE.md. A phase is done when its acceptance\n'
printf 'check has produced pasted output, not when the commands were typed.\n'

[ "$fail" -eq 0 ] || exit 1
