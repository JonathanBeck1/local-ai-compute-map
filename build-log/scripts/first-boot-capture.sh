#!/usr/bin/env bash
#
# first-boot-capture.sh -- phase 02 first-boot record
#
# Runs the recording commands from the build guide and prints a markdown block
# ready to paste into HARDWARE.md.
#
# READ-ONLY. It changes nothing. Every command here only reports state.
#
# Usage:
#     bash first-boot-capture.sh                 # print to stdout
#     bash first-boot-capture.sh > capture.md    # save it
#
# Some sections need root for full detail (dmidecode). Run with sudo for those,
# or accept the gaps -- the script says which it skipped and why.

set -uo pipefail

have() { command -v "$1" >/dev/null 2>&1; }

section() { printf '\n## %s\n' "$1"; }

# run <label> <command...>  -- prints the command and its output in a fenced block
run() {
    local label="$1"; shift
    printf '\n**%s**\n\n```\n$ %s\n' "$label" "$*"
    if have "${1}"; then
        "$@" 2>&1 || printf '(command exited %s)\n' "$?"
    else
        printf '(not installed: %s)\n' "${1}"
    fi
    printf '```\n'
}

printf '# phase 02 -- first boot capture\n'
printf '\n**Captured:** %s\n' "$(date -u '+%Y-%m-%d %H:%M:%SZ')"
printf '**Host:** %s\n' "$(hostname 2>/dev/null || echo unknown)"
printf '**Run as:** %s\n' "$(id -un 2>/dev/null || echo unknown)"

section "Identity and distro"
run "hostname" hostnamectl
run "distro" lsb_release -a
run "kernel" uname -a

section "CPU and memory"
run "cpu" lscpu
run "memory total" free -h
if [ "$(id -u)" -eq 0 ] && have dmidecode; then
    run "memory modules" dmidecode -t memory
else
    printf '\n**memory modules**\n\n```\n(skipped: dmidecode needs root -- re-run with sudo for DIMM detail)\n```\n'
fi

section "Firmware"
if [ -d /sys/firmware/efi ]; then
    printf '\n**boot mode**\n\n```\n/sys/firmware/efi exists -> booted in UEFI mode\n```\n'
else
    printf '\n**boot mode**\n\n```\n/sys/firmware/efi missing -> NOT booted in UEFI mode (unexpected)\n```\n'
fi
run "secure boot" mokutil --sb-state

section "Storage"
run "block devices" lsblk -o NAME,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINT
run "nvme" nvme list
printf '\n**disks by id**\n\n```\n$ ls -l /dev/disk/by-id/\n'
ls -l /dev/disk/by-id/ 2>&1 | grep -vE 'part[0-9]+$' || true
printf '```\n'
run "mounts" findmnt -t ext4,vfat -o TARGET,SOURCE,FSTYPE,OPTIONS
run "free space" df -h
run "bulk disk mount" findmnt /srv/ai-lab
run "bulk disk space" df -h /srv/ai-lab
run "fstab" cat /etc/fstab

section "Network"
run "interfaces" ip -br a
IFACE="$(ip -o -4 route show to default 2>/dev/null | awk '{print $5}' | head -1)"
if [ -n "${IFACE:-}" ]; then
    printf '\n**link speed (%s)**\n\n```\n$ ethtool %s | grep -iE "speed|duplex|link detected"\n' "$IFACE" "$IFACE"
    if have ethtool; then
        ethtool "$IFACE" 2>&1 | grep -iE 'speed|duplex|link detected' || printf '(no matching lines)\n'
    else
        printf '(ethtool not installed: sudo apt install -y ethtool)\n'
    fi
    printf '```\n'
    printf '\n> Expected: 2500Mb/s on the Realtek 2.5GbE port.\n'
else
    printf '\n**link speed**\n\n```\n(no default route -- network is not up)\n```\n'
fi

section "GPU"
run "nvidia-smi" nvidia-smi
run "gpu query" nvidia-smi --query-gpu=name,memory.total,driver_version,uuid --format=csv,noheader
printf '\n> Expected: NVIDIA GeForce RTX 4070, 12282 MiB.\n'
run "driver packages" bash -c "dpkg -l 'nvidia*' 2>/dev/null | grep '^ii' | awk '{print \$2, \$3}'"
run "held packages" apt-mark showhold
run "recommended driver" ubuntu-drivers devices

section "Docker"
run "docker version" docker --version
run "docker root dir" bash -c "docker info 2>/dev/null | grep 'Docker Root Dir'"
printf '\n> Expected: /srv/ai-lab/docker\n'
run "nvidia container toolkit" bash -c "dpkg -l 'nvidia-container*' 'libnvidia-container*' 2>/dev/null | grep '^ii' | awk '{print \$2, \$3}'"

section "Services and listeners"
run "listening sockets" ss -tlnp
printf '\n> Port 22 owned by systemd rather than sshd is correct: Ubuntu uses socket activation.\n'

section "Boot log errors"
run "nvidia errors this boot" bash -c "journalctl -p err -b 2>/dev/null | grep -i nvidia | head -20; echo '--- count ---'; journalctl -p err -b 2>/dev/null | grep -ci nvidia || true"
printf '\n> Expected count: 0\n'

printf '\n---\n\nPaste the relevant parts into HARDWARE.md, replacing the VERIFY markers.\n'
