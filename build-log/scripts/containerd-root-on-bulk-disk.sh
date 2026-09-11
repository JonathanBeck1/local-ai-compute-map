#!/usr/bin/env bash
#
# containerd-root-on-bulk-disk.sh -- Docker 29 correction: image store on the bulk disk
#
# Correction to build guide section 9. Docker 29 stores image layers via the
# containerd snapshotter under containerd's root (/var/lib/containerd, on the
# NVMe), NOT under Docker's data-root. So the guide's data-root setting kept
# containers and volumes on /srv/ai-lab but let every image land on root.
#
# This moves containerd's root to the bulk disk and guards containerd.service
# the same way docker.service is guarded. The one image already pulled is
# deleted (re-pullable) rather than migrated; the re-pull is the verification.
#
# Run as:   sudo bash containerd-root-on-bulk-disk.sh
# Safe to re-run.

set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

findmnt /srv/ai-lab >/dev/null || { echo "/srv/ai-lab is not mounted -- refusing to continue"; exit 1; }

step "stop docker and containerd"
systemctl stop docker.socket docker.service containerd.service

step "containerd root -> /srv/ai-lab/containerd"
mkdir -p /srv/ai-lab/containerd
CFG=/etc/containerd/config.toml
cp -n "$CFG" "$CFG.orig" || true
if grep -qE '^\s*#?\s*root\s*=' "$CFG"; then
    sed -i -E 's|^\s*#?\s*root\s*=.*|root = "/srv/ai-lab/containerd"|' "$CFG"
else
    sed -i '1i root = "/srv/ai-lab/containerd"' "$CFG"
fi
grep -nE '^root\s*=' "$CFG"

step "guard containerd.service on the mount"
mkdir -p /etc/systemd/system/containerd.service.d
cat > /etc/systemd/system/containerd.service.d/10-require-ai-lab.conf <<'EOF'
[Unit]
RequiresMountsFor=/srv/ai-lab
EOF
systemctl daemon-reload

step "remove the image store that landed on the NVMe"
du -sh /var/lib/containerd 2>/dev/null || true
rm -rf /var/lib/containerd

step "start containerd and docker"
systemctl start containerd.service docker.service
sleep 2
systemctl is-active containerd docker

step "verify"
echo "--- guards ---"
systemctl show containerd docker -p Id -p RequiresMountsFor
echo "--- docker info ---"
docker info 2>/dev/null | grep -E 'Server Version|Docker Root Dir|Storage Driver|containerd-snapshotter|driver-type'
echo "--- nothing under /var/lib for containerd or docker (expect two 'No such file') ---"
ls -d /var/lib/containerd /var/lib/docker 2>&1 || true
echo "--- disk before pull ---"
df -h / /srv/ai-lab | tail -2
echo "--- A2.2 again: re-pull the CUDA image, GPU visible inside a container ---"
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi -L
echo "--- disk after pull: /srv/ai-lab Used must have grown, / must not ---"
df -h / /srv/ai-lab | tail -2
du -sh /srv/ai-lab/containerd /srv/ai-lab/docker

printf '\nDone.\n'
