# Phase 02 — Linux box, driver, containers

**Status:** done, two checks deferred by decision (SSH, rescue boot)
**Date:** 2026-09-07 install, 2026-09-08 setup
**Elapsed:** ~1.5 h. Install ~25 min from USB boot to first desktop; setup ~1 h. ~0.5 h of that lost to failures, itemised below
**Cost:** $0

## Goal

Turn the Windows gaming PC into the lab's CUDA node: Ubuntu 24.04 LTS, single boot, NVIDIA driver pinned, GPU visible inside a container, models and images on a separate disk so a runaway download can't fill root. Done when a container prints the GPU's name and the acceptance checks below have pasted output.

## Hardware touched

Self-built desktop: Ryzen 9 5900XT, 64 GB, RTX 4070 12 GB, ASUS X570 board. Two internal disks: a 2 TB Crucial NVMe (was Windows 11) and a 1 TB Samsung 860 EVO SATA (was blank). One 29 GB USB stick as installer.

Windows was wiped, not dual-booted. Phase 00's README said dual boot; that was the plan before the inventory. Dual boot means the model endpoint is down whenever the machine is in Windows, which defeats "always-on". Roughly 700 GB on the Windows disk was reviewed, judged not worth keeping, and accepted as lost. No evacuation.

## What I ran

Firmware first: SATA to AHCI, NVMe RAID off, CSM off, Secure Boot left off. RAID mode is the one that matters — it hides NVMe drives from the Ubuntu installer entirely, and "installer shows no disks" on an X570 board is almost always this.

Install: Ubuntu 24.04.4 desktop, "erase disk" default onto the NVMe, third-party drivers box ticked. The Samsung untouched during install.

Bulk disk, by its `by-id` path so `/dev/sdX` letter drift can't hit the wrong disk:

```bash
DISK=/dev/disk/by-id/ata-Samsung_SSD_860_EVO_1TB_<serial>
echo "DISK=$DISK"; lsblk -o NAME,SIZE,MODEL,SERIAL "$DISK"     # look before continuing

sudo parted -a optimal "$DISK" mklabel gpt
sudo parted -a optimal "$DISK" mkpart primary ext4 0% 100%
sudo udevadm settle
sudo mkfs.ext4 -m 1 -L ai-lab "${DISK}-part1"

UUID=$(sudo blkid -s UUID -o value "${DISK}-part1")
sudo mkdir -p /srv/ai-lab
echo "UUID=$UUID /srv/ai-lab ext4 defaults,noatime,nofail,x-systemd.device-timeout=15 0 2" | sudo tee -a /etc/fstab
sudo systemctl daemon-reload && sudo mount -a
```

`nofail` so a dead SATA disk or loose cable doesn't strand a headless box at an emergency shell. The cost is that it then boots *quietly* without the disk, which is why Docker and containerd get `RequiresMountsFor=/srv/ai-lab` below: they refuse to start rather than silently recreate their stores on root.

Driver: nothing by hand. The installer's third-party option installed `nvidia-driver-595-open`, which is also what `ubuntu-drivers devices` marks `recommended`. Held afterwards so an `apt upgrade` can't move it under a working CUDA container stack:

```bash
sudo apt-mark hold nvidia-driver-595-open
```

Docker Engine from Docker's repo, NVIDIA Container Toolkit pinned to 1.20.0-1, Docker's `data-root` on the bulk disk, guard drop-in on `docker.service`. Then the correction in *What broke* item 1: containerd's `root` on the bulk disk too, and the same guard on `containerd.service`. Scripts: [`scripts/docker-on-bulk-disk.sh`](scripts/docker-on-bulk-disk.sh) and [`scripts/containerd-root-on-bulk-disk.sh`](scripts/containerd-root-on-bulk-disk.sh).

Housekeeping: `git`, `gh`, `uv`, `etckeeper`.

Checks: [`scripts/first-boot-capture.sh`](scripts/first-boot-capture.sh) prints a markdown record; [`scripts/acceptance-tests.sh`](scripts/acceptance-tests.sh) runs the nine checks and says pass or fail.

## Output

```
$ lsb_release -ds; uname -r
Ubuntu 24.04.4 LTS
7.0.0-31-generic

$ lsblk -o NAME,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINT          (snap loops omitted)
NAME          SIZE MODEL                   SERIAL    FSTYPE   MOUNTPOINT
sda         931.5G Samsung SSD 860 EVO 1TB <serial>
└─sda1      931.5G                                   ext4     /srv/ai-lab
nvme0n1       1.8T CT2000P310SSD8          <serial>
├─nvme0n1p1     1G                                   vfat     /boot/efi
└─nvme0n1p2   1.8T                                   ext4     /

$ ethtool enp4s0 | grep -iE "speed|link detected"
	Speed: 2500Mb/s
	Link detected: yes

$ ubuntu-drivers devices | grep recommended
driver   : nvidia-driver-595-open - distro non-free recommended

$ nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
NVIDIA GeForce RTX 4070, 12282 MiB, 595.84

$ apt-mark showhold
nvidia-driver-595-open

$ df -h /srv/ai-lab                                    (fresh, before Docker)
/dev/sda1       916G   48K  907G   1% /srv/ai-lab

$ docker info | grep -E 'Server Version|Docker Root Dir|driver-type'
 Server Version: 29.8.0
  driver-type: io.containerd.snapshotter.v1
 Docker Root Dir: /srv/ai-lab/docker

$ grep ^root /etc/containerd/config.toml
root = "/srv/ai-lab/containerd"

$ systemctl show containerd docker -p Id -p RequiresMountsFor
Id=containerd.service
RequiresMountsFor=/srv/ai-lab
Id=docker.service
RequiresMountsFor=/srv/ai-lab

$ docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi -L
GPU 0: NVIDIA GeForce RTX 4070 (UUID: GPU-<uuid>)

$ docker run --rm --gpus all pytorch/pytorch:2.14.0-cuda12.6-cudnn9-runtime \
    python -c "import torch;print(torch.cuda.get_device_name(0))"
NVIDIA GeForce RTX 4070
```

The 2.5 GbE Realtek port came up on the in-tree `r8169` driver at full speed. The vendor `r8125` fallback that Realtek 2.5G parts sometimes need was not needed here.

## What broke

Install: nothing. Firmware settings were right first time, the installer saw the NVMe, the network came up. 25 minutes.

**1. Docker 29 puts image layers on root no matter what `data-root` says.** The guide I was following sets `"data-root": "/srv/ai-lab/docker"` and verifies it with `docker info | grep "Docker Root Dir"`. That check passed. The image still went to the NVMe:

```
$ journalctl -u docker -b | grep -i snapshotter
dockerd: msg="Starting daemon with containerd snapshotter integration enabled"
dockerd: msg="Docker daemon" containerd-snapshotter=true storage-driver=overlayfs version=29.8.0

$ df -h / /srv/ai-lab          # after pulling a 100 MB CUDA image
/dev/nvme0n1p2  1.8T   17G  1.7T   1% /            # was 16G
/dev/sda1       916G  284K  907G   1% /srv/ai-lab  # not here

$ sudo du -sh /var/lib/containerd
338M    /var/lib/containerd
```

Since Docker 28 the default image store is containerd's snapshotter, and its root is `/var/lib/containerd`, set by `root =` in `/etc/containerd/config.toml`. Docker's `data-root` still governs containers, volumes and metadata, which is why `Docker Root Dir` looked right while the bytes went elsewhere. Fix: `root = "/srv/ai-lab/containerd"`, a `RequiresMountsFor` drop-in on `containerd.service`, delete the misplaced store, re-pull. Same pull afterwards moved `/srv/ai-lab` from 380K to 338M and left `/` at 17G.

The lesson is about the check, not the setting: `df` on both disks before and after a pull is the test. `docker info` was answering a different question.

**2. An empty variable reached `parted`.** The block above was pasted with the `DISK=` line first; the terminal dropped it.

```
$ lsblk -o NAME,SIZE,MODEL,SERIAL "$DISK"
lsblk: : not a block device
$ sudo parted -a optimal "$DISK" mklabel gpt
Error: Could not stat device  - No such file or directory.
Retry/Cancel?
```

Nothing written. An empty path can't address a disk, which is the by-id design working. Cancelled, set the variable on its own line, echoed it, re-ran. The `echo "DISK=$DISK"` line in the block above is there because of this.

**3. A 40-line paste with two heredocs garbled.** A fragment of the last line got spliced into the middle (`daemon.jso -Ludo docker run …`) and left bash at a `>` prompt. Two harmless commands had run. Ctrl+C, then every privileged step after that went into a script file run with `sudo bash`. That's the right default anyway; a script can be read before it runs and re-run when it fails.

**4. Rule broken: Phase 00 isn't closed.** The [build-log rules](README.md) say nothing downstream starts until the laptop has a tested backup. It doesn't, and this phase happened anyway. Recorded rather than hidden. The exposure is unchanged: this machine had nothing on it worth keeping, and nothing from the laptop touched it.

**5. Guide errors found in use.** The written guide assumed a separate `/boot` partition, so its rescue-boot step said to mount `nvme0n1p3`; the installer default has no separate `/boot` and root is `p2`. Fixed before the test ran. A typo cost a minute: `apt install ectkeeper`.

## What I would do differently

Test where the bytes land, not what the config says. Item 1 passed its own check and was wrong. `df` before and after is cheap and doesn't lie.

Scripts, not pastes, for anything with `sudo` in it. Two of the three failures were paste corruption.

Skip the separate `/boot`. The guide had one because the LUKS decision was open; on an unencrypted root it does nothing, and the installer default is simpler.

Decide the hostname before writing the guide. The guide said `ai-main`; the machine is named something else; every document now has to say which it means.

## Deferred, by decision

- **SSH.** `openssh-server` not installed; nothing on port 22. Ubuntu 24.04 ships the client only. The machine is keyboard-only until this changes, and phase 04 (remote workflow from the laptop) can't start before it does.
- **Rescue boot.** Booting the installer stick and mounting root from it, to prove the recovery path works before it's needed. Needs the stick and ten minutes.

## Acceptance check

Nine checks from the guide, run 2026-09-08. Output above; the full log is in the private record.

| | Check | Result |
|---|---|---|
| A2.1 | driver and GPU visible on the host | pass |
| A2.2 | GPU visible inside a container | pass |
| A2.3 | CUDA usable from PyTorch | pass |
| A2.4 | driver package held | pass (after `apt-mark hold`, same day) |
| A2.5 | driver survives a reboot | pass — A2.1 output identical before and after a real reboot |
| A2.6 | zero nvidia lines in `journalctl -p err -b` | pass, 0 |
| A2.7 | rescue media boots and mounts root | **deferred** |
| A2.8 | port 22 listening | **fail, accepted** — SSH deferred |
| A2.9 | bulk disk is a real mount after reboot, with `nofail` | pass |

Phase closes on A2.7 and A2.8. The CUDA node works; the *reachable* CUDA node doesn't exist yet.
