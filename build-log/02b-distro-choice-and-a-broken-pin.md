# Phase 02b — The distro I never chose, and the pin that would have broken

**Status:** done — the repair worked; a one-hour outage the same night turned out to have a different cause (see What broke 7)
**Date:** 2026-09-18 to 2026-09-19
**Elapsed:** ~2 h verification, ~1 h outage, and a misdiagnosis before the real cause surfaced
**Cost:** $0

## Goal

Someone asked why this machine runs Ubuntu and not Debian or Fedora. I went to answer and found I couldn't — nothing in the record had ever compared them. Answering the question properly turned up a second thing: the driver pin that [phase 02](02-linux-box-driver-containers.md) certified as passing would have taken the GPU out the next time the kernel moved.

## Hardware touched

The phase 02 box: RTX 4070 12 GB, 64 GB, Ubuntu 24.04.4 LTS on HWE kernel 7.0.0-31-generic, Docker + NVIDIA Container Toolkit, Ollama serving models. Both the owner's daily desktop and the always-on endpoint.

## What I ran

First, a grep of the entire private build record — guide, handoff, hardware capture, raw command transcript, every script:

```sh
grep -rniE 'debian|fedora|rhel|rocky|arch linux|opensuse|nixos' --include='*.md' --include='*.txt' --include='*.sh' .
```

Nothing. Ubuntu 24.04 appears in build-guide **revision 1** — the original dual-boot plan — and survives revisions 2 and 3 untouched. Revision 3 opens with a table of six defects it fixed and three dropped steps it restored; the distribution isn't among them. The decision log has four numbered entries plus an explicitly-flagged open decision about LUKS. The only distro-adjacent justification in the whole guide is "the Desktop image, not Server" — a choice *within* Ubuntu.

So the honest answer to "why Ubuntu" was: **nobody chose it.** It was assumed in a first draft and never revisited.

Then I checked whether it was right anyway, against primary sources rather than memory — debian.org, packages.debian.org, the Debian BTS and security tracker, Fedora docs, RPM Fusion, NVIDIA's and Docker's install guides, and the READMEs of the tools this box actually runs. Then three adversarial passes: steelman Debian, steelman Fedora, and a critic told to find what Ubuntu costs here.

## Output

**The container layer is Ubuntu-first, and that's the layer this machine is.**

| | Ubuntu | Debian | Fedora |
|---|---|---|---|
| NVIDIA Container Toolkit *tested platforms* | 22.04, 24.04, 26.04 | **11 only** (two stables behind) | **not listed** |
| Official CUDA base images (1,930 tags) | yes | **zero** | **zero** |
| CUDA Toolkit itself | first-class | first-class, no lag | first-class, no lag |
| Docker Engine | first-class | first-class | first-class |

Docker isn't a differentiator. The CUDA *toolkit* isn't either — Debian 13 and Fedora 44 get the same CUDA 13.4.2 and driver branch 615 with no delay. The toolkit-plus-images layer is, and `nvidia/cuda:12.6.3-base-ubuntu24.04` sits on it. Underneath all of it: **DGX OS is Ubuntu** — DGX OS 7 is 24.04, DGX OS 8 is 26.04, with a kernel co-engineered by NVIDIA and Canonical. NVIDIA has that relationship with no other distribution.

**Debian came out worse than I expected, and I went in sympathetic.** Debian 13 "trixie" ships NVIDIA 550.163.01. It supports the RTX 4070 — but the **`-open` flavour does not compile against Debian 13's own kernel**: bug #1143204, `pci_resize_resource` API change at 6.12.100, filed 31 July 2026, still open, and trixie runs 6.12.107. `trixie-backports` isn't an escape hatch — same upstream 550.163.01, and broken against the current backports kernel too. Nine CVEs sit "vulnerable (no DSA)" on it. And **Debian's own wiki** recommends, for Turing-and-newer, "NV DC driver v595 or the most recent, open flavor" — use NVIDIA's repo, not Debian's. The Debian path converges on a vendor repo anyway, which throws away Debian's packaging advantage and lands you on a distro NVIDIA tests less.

**Fedora fails on role, not technology.** Fedora 44 with RPM Fusion's `akmod-nvidia` at 615.71.09 is technically the best of the three for a three-monitor desktop that also games. But: ~13-month support, no LTS, Fedora 45 beta already out with GA a month away, and akmods *compiles the driver at boot*, ordered `Before=display-manager.service`. A box that has to come back unattended after a power cut doesn't want a forced in-place distro upgrade twice a year.

Worth noting for anyone assuming the whole ecosystem is Ubuntu-locked: llama.cpp's prebuilt Linux binaries are literally named `ubuntu` and built in an Ubuntu 24.04 CUDA container (a glibc 2.39 floor, which Debian 12 sits below); NVIDIA PAIR ships exactly one Linux package format, a `.deb`; LM Studio's published requirement names Ubuntu and nothing else. But **Ollama is built on AlmaLinux 8 on purpose**, so its binaries are portable, and it's genuinely distro-agnostic. The lock-in is real but not uniform.

## What broke

**1. An acceptance test passed on a configuration with a latent failure.**

Phase 02's A2.4 was `apt-mark showhold | grep -c nvidia`, expecting ≥ 1. It got 1. It passed. Here is what it couldn't see:

```
$ apt-cache policy nvidia-driver-595-open
  Installed: 595.84-0ubuntu0.24.04.1
  Candidate: 595.91.07-0ubuntu0.24.04.1        ← blocked by the hold

$ apt-cache show linux-modules-nvidia-595-open-7.0.0-31-generic
Depends: linux-image-7.0.0-31-generic | linux-image-unsigned-7.0.0-31-generic,
         nvidia-kernel-common-595 (<= 595.91.07-1), nvidia-kernel-common-595 (>= 595.91.07)

$ apt-get -s dist-upgrade | grep -c nvidia     # kept back
17

$ systemctl is-enabled unattended-upgrades
enabled
```

The kernel-ABI module package is version-locked to **both** the kernel image *and* the driver. `linux-image-generic-hwe-24.04` has no NVIDIA dependency and upgrades freely — and `unattended-upgrades` is on, so it moves without anyone typing a command. At the next HWE ABI bump the kernel installs, the module is kept back because the hold blocks its `nvidia-kernel-common-595` dependency, and the machine boots into a kernel with **no NVIDIA module**. No GPU for the model containers; desktop on llvmpipe.

The hold protected against nothing it was supposed to, and broke the kernel↔module lockstep that was the actual safety mechanism.

I first wrote that the package *name* pinned the branch — that `nvidia-driver-595-open` can't walk to 610 because 610 is a differently-named package. **That is wrong**, and it's worth stating plainly because it's the kind of thing that sounds obviously true:

```
$ apt-cache show nvidia-driver-535-open | grep -E 'Depends|Description-en'
Depends: nvidia-driver-580-open
Description-en: NVIDIA driver (open kernel) metapackage (transitional package)
```

At branch EOL Ubuntu converts the metapackage into a transitional one pointing at the successor, inside the stable release, from `noble-updates` *and* `noble-security`. What actually blocks an unattended branch move is `unattended-upgrades` refusing any transaction containing a removal — `/usr/bin/unattended-upgrade` line 1114, `sanity_problem()`: `"pkg %s is marked to be deleted"` — and a branch move always removes the old stack. A *manual* `apt full-upgrade` would take it.

The unhold still stands, on severity rather than on the claim I got wrong: the hold's failure is *no module at all*, certain at the next ABI bump, on a machine with one kernel and no reachable boot menu. A branch transition brings its matching modules, so the GPU keeps working — a CUDA-compatibility risk, distant, recoverable, and refused unattended.

**2. There was no recovery path.** One kernel installed. `GRUB_TIMEOUT=0` with `GRUB_TIMEOUT_STYLE=hidden`, so the boot menu is unreachable without knowing to hold Shift. No SSH (deferred in phase 02). A machine in that state has exactly one way to boot and no way to choose another.

**3. The fix for the defect had the same class of defect.** The repair script's first revision was ordered "safety net first, driver last": GRUB, then the fallback kernel *and its NVIDIA module*, then the driver. That ordering is impossible, not merely suboptimal:

```
$ apt-get -s install --no-install-recommends linux-image-generic \
      linux-headers-generic linux-modules-nvidia-595-open-generic
E: Error, pkgProblemResolver::Resolve generated breaks, this may be caused by held packages.
```

The fallback's GPU module `Depends: nvidia-kernel-common-595 (>= 595.91.07)` — the *new* driver, which the hold forbids. The fallback kernel's module and the driver upgrade are necessarily one apt transaction and cannot be ordered apart. Run for real, the script would have died having rewritten `/etc/default/grub` without regenerating `grub.cfg`, leaving a machine whose boot configuration disagreed with itself and nothing fixed.

**4. `--dry-run` gave a clean all-clear on the one command that fails.** The wrapper printed `[dry-run] apt-get install ...` instead of simulating it. A cautious operator doing the responsible thing would have been told everything was fine, then watched it die for real. A rehearsal that doesn't exercise the failing path is worse than none, because it converts caution into confidence.

**5. `lsmod | grep -q` fails every time under `set -o pipefail`.** Revision 2 of the repair script refused to start — "the nvidia kernel module is not loaded" — two lines after printing `NVIDIA GeForce RTX 4070, 595.84`. `grep -q` exits at the first match, `lsmod` takes SIGPIPE (141), `pipefail` propagates it:

```
pipefail ON : 40/40 spurious failures
pipefail OFF: 0/40 spurious failures
grep -q '^nvidia ' /proc/modules (no pipeline): 0/40
```

Fixed by reading `/proc/modules`, which is what `lsmod` reads anyway.

**The adversarial review missed it.** One of the five lenses was specifically shell correctness — "find every place where a legitimately-empty result would abort" — and it returned five real `set -e` hazards. None of them was the one that made the script refuse to run on every single invocation. **Running the rehearsal found it in one command.** A review of a rehearsal is not a substitute for running it, which is the same lesson as finding 4 arriving from the opposite direction.

**6. The rehearsal required root, so nobody would have run it.** `--dry-run` was gated behind `id -u -eq 0` along with everything else, despite touching nothing privileged. A dry run you need sudo for is a dry run people skip.

**7. I blamed the repair for an outage it didn't cause — from data that couldn't tell.** After the repair ran, every normal boot reached a grey screen and never offered a login. Nine failed boots, about an hour at the physical keyboard in recovery mode. The package side was clean on every one: right kernel, module loaded with zero errors, X up with the right driver, and the login-screen process logging *identically* to the boot that eventually worked. The difference was which monitors were attached:

| Boots | Driver | Monitors | Reached login? |
|---|---|---|---|
| 4 before the repair | 595.84 | 1440p LG + 4K Samsung | 4 of 4 |
| 8 after | 595.91.07 | 1440p LG + 4K Samsung | 0 of 8 |
| the one that worked | 595.91.07 | 1440p LG only | yes |

I read that as "the driver point release broke the login screen with the 4K monitor", wrote it into three records as the root cause, and explained at some length why none of the repair's checks could have seen a runtime display regression.

**It was wrong.** Hot-plugging the Samsung into the running session on the *new* driver:

```
DP-2 connected 3840x2160+2560+0      <- the 4K Samsung, lit and fine on 595.91.07
```

The missing variable: the Samsung has several inputs, and **it was switched to a PS5 for the whole outage.** Its DisplayPort link stayed live, so the PC still counted it as a monitor and the login screen laid out two displays. The prompt most likely landed on the Samsung — behind the console picture — and the LG showed only the greeter's grey background. It cleared when the Samsung dropped off; it never happened on the old driver because those days the Samsung was on the PC input.

The driver and the monitor input changed **the same night**. My table compares drivers, but it's confounded: the data cannot separate the two variables, and I attributed the cause to the one I'd changed and could see. The tell was already in the evidence — logs *identical* between grey and working boots is what a fault outside the machine looks like. **When the logs can't tell success from failure, look outside the logs.**

What survives from the incident: the repair script offered an immediate reboot on the owner's only workstation before anyone had confirmed a way back. That's the wrong default regardless of what the cause turned out to be. The way back did exist — every 595.84 package was cached offline — and was checked afterwards.

The real remaining hazard is small and has nothing to do with drivers: if the 4K monitor is on another input at boot, the login prompt can be invisible. The fix is to make the login screen put its prompt on the other monitor.

Findings 3 and 4 were caught by adversarial review before the script was run — five independent lenses over it (boot safety, apt semantics, GRUB, rollback, shell correctness), every finding then handed to a separate agent told to refute it. 14 findings survived refutation; three were this blocker approached from different angles.

**5. A fact in the record was an inference.** The hardware record said the driver was "installed automatically by the Ubuntu installer's third-party-drivers option". What the apt log actually shows is `apt-get install -y nvidia-driver-595-open linux-modules-nvidia-595-open-generic-hwe-24.04` at 21:14:56 on install day — consistent with the installer checkbox, with `ubuntu-drivers autoinstall`, or with the Software & Updates GUI. I wrote down the inference as a fact. Now recorded as unknown.

## What I would do differently

**Write acceptance checks against outcomes, not commands.** A2.4 asked "is something held?" The question was "will the GPU still work after the next kernel update?" Every check in phase 02 that tested a *command having run* rather than an *outcome being safe* deserves re-reading in that light. [Phase 03](03-local-model-endpoint.md) had the same shape of bug from the other direction — `docker info` reported the right directory while the bytes went elsewhere — and the fix there was the same: test the thing you actually care about.

**Record the decisions nobody remembers making.** The distro was a load-bearing choice made by inertia. A decision log that contains only the decisions someone recalls deliberating is a partial log, and the gaps are exactly where the unexamined assumptions live.

**Ask what the pin is protecting against before pinning.** "Pin the driver" is folklore that's correct on distros where the driver and kernel are packaged independently. On Ubuntu the LRM packaging deliberately couples them, so a hold fights the mechanism instead of using it.

**Make the rehearsal exercise the thing that can fail.** The dry run and the acceptance test failed the same way: both reported on a proxy rather than the outcome. If `--dry-run` doesn't run the real resolver, it isn't a dry run — it's a listing of intentions.

## Acceptance check

| | Check | Result |
|---|---|---|
| A2b.1 | The distro choice is examined against alternatives on primary sources | pass — Debian 13 and Fedora 44, with dates and URLs |
| A2b.2 | The choice is ratified or reversed, with the costs recorded either way | pass — ratified; four costs recorded, not glossed |
| A2b.3 | Every installed kernel has a matching NVIDIA module | pass — `6.8.0-139-generic` and `7.0.0-31-generic`, both `installed` |
| A2b.4 | A second bootable kernel exists and the boot menu can reach it | pass — **proven in use**: the owner booted `6.8.0-139-generic` from the menu during the outage |
| A2b.5 | No NVIDIA package is kept back | pass — none kept back, no holds |
| A2b.6 | GPU survives a reboot after the repair, verified in a container | pass — `NVIDIA GeForce RTX 4070, 595.91.07` from `nvidia/cuda` |
| A2b.7 | The desktop reaches the login screen after a reboot with every monitor connected | pass, with a caveat — the 4K monitor works on the new driver; the 0-of-8 run was that monitor showing a PS5. Open robustness item: pin the login prompt to the other monitor so another input can't hide it |

A2.4 from phase 02 is **retired**. "The driver is held" was the wrong check. It is replaced by A2b.3 and A2b.5, which ask whether the GPU will survive the next kernel rather than whether a command was typed.
