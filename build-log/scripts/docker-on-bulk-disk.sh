#!/usr/bin/env bash
#
# docker-on-bulk-disk.sh -- Docker Engine + NVIDIA Container Toolkit, stores on a bulk disk
#
# Docker Engine + NVIDIA Container Toolkit, with Docker's data-root on the
# bulk disk and a systemd guard so Docker refuses to start if /srv/ai-lab
# is not really mounted.
#
# Run as:   sudo bash docker-on-bulk-disk.sh
#
# Safe to re-run. Resumes cleanly from a partial earlier attempt.

set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
TARGET_USER="${SUDO_USER:?run with sudo from your normal user}"
TOOLKIT_VERSION="1.20.0-1"

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

# ---------------------------------------------------------------- 1. Docker Engine
step "Docker apt source"
install -m 0755 -d /etc/apt/keyrings
[ -s /etc/apt/keyrings/docker.asc ] || curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

. /etc/os-release
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
cat /etc/apt/sources.list.d/docker.sources

# ---------------------------------------------------------------- 2. data-root + guard, BEFORE first start
# Written before Docker is installed so the daemon never creates /var/lib/docker on the NVMe.
step "data-root on /srv/ai-lab and RequiresMountsFor guard"
findmnt /srv/ai-lab >/dev/null || { echo "/srv/ai-lab is not mounted -- refusing to continue"; exit 1; }
mkdir -p /srv/ai-lab/docker /etc/docker /etc/systemd/system/docker.service.d
[ -s /etc/docker/daemon.json ] || echo '{ "data-root": "/srv/ai-lab/docker" }' > /etc/docker/daemon.json
cat > /etc/systemd/system/docker.service.d/10-require-ai-lab.conf <<'EOF'
[Unit]
RequiresMountsFor=/srv/ai-lab
EOF
systemctl daemon-reload

step "install Docker Engine"
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker "$TARGET_USER"

# ---------------------------------------------------------------- 3. NVIDIA Container Toolkit
step "NVIDIA Container Toolkit ${TOOLKIT_VERSION}"
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update
apt-get install -y \
    nvidia-container-toolkit="${TOOLKIT_VERSION}" \
    nvidia-container-toolkit-base="${TOOLKIT_VERSION}" \
    libnvidia-container-tools="${TOOLKIT_VERSION}" \
    libnvidia-container1="${TOOLKIT_VERSION}"

nvidia-ctk runtime configure --runtime=docker
systemctl daemon-reload
systemctl restart docker

# ---------------------------------------------------------------- 4. verify
step "verify"
echo "--- /etc/docker/daemon.json ---"
cat /etc/docker/daemon.json
echo "--- docker info ---"
docker info 2>/dev/null | grep -E 'Server Version|Docker Root Dir|Runtimes'
echo "--- /var/lib/docker should NOT exist (nothing on the NVMe) ---"
ls -d /var/lib/docker 2>&1 || true
echo "--- A2.2: GPU visible inside a container ---"
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi -L

printf '\nDone. Log out and back in so %s picks up the docker group.\n' "$TARGET_USER"
