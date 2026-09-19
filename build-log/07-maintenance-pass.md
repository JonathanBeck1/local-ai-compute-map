# Phase 07 — A maintenance pass, and a headline that stopped being true

**Status:** done, except the package upgrade, which needs physical access
**Date:** 2026-09-19
**Elapsed:** ~1.5 h
**Cost:** $0

## Goal

Ten days after the build, check what has moved: Ollama, the driver, Docker, the
container toolkit, the OS. Upgrade what should be upgraded, re-run the
acceptance tests, and confirm the machine still does what the log claims.

What the pass actually produced was a correction. The headline result of
[phase 03](03-local-model-endpoint.md) — *a 30B MoE that doesn't fit the 12 GB
card generates as fast as a 12B dense model that does* — is true at the context
length it was measured at, and false at the context length this machine has been
running since [phase 03c](03c-moe-placement-measured.md).

## What had moved

| Component | Running | Available | Action |
|---|---|---|---|
| Kernel 7.0.0-31, NVIDIA 595.91.07 | current | — | nothing pending, no holds, no reboot waiting |
| Ollama (Docker, pinned tag) | 0.33.3 | 0.34.2 | **upgraded** |
| docker-ce | 29.8.0 | 29.8.1 | deferred, needs root |
| nvidia-container-toolkit | 1.20.0 | 1.20.1 | deferred, needs root |
| Other OS packages | — | 93 upgradable | deferred, needs root |

None of the 93 touch the kernel, the driver or GRUB. `unattended-upgrades`
handles Ubuntu security updates only; Docker and NVIDIA ship from their own
repos, and the Ollama image moves only when its tag is changed here.

The package half is written as [`scripts/maintenance.sh`](scripts/maintenance.sh)
and has not been run. It refuses to proceed if the plan removes any package
(the shape of a branch transition, which is what
[02b](02b-distro-choice-and-a-broken-pin.md) is about) or touches the kernel or
driver, which on this machine move together and deliberately. Afterwards it
verifies by outcome: `df` on the live Docker and containerd directories, a
container actually seeing the GPU, and Ollama actually generating with weights
in VRAM.

## Ollama 0.33.3 → 0.34.2

Nothing in the 0.34 notes affects a Linux CUDA server: the headline items are
macOS, MLX and desktop-app features. The relevant ones are a faster `/api/tags`,
a `typical_p` deprecation that doesn't apply here, and a new first-run sign-in
flow that belongs to the desktop app — worth confirming the server doesn't
inherit it, since this endpoint must work with no account attached.

```
$ docker compose pull && docker compose up -d
 Container ollama Recreated
$ curl -fsS http://127.0.0.1:11434/api/version
{"version":"0.34.2"}
$ docker port ollama
11434/tcp -> 127.0.0.1:11434
$ docker logs ollama 2>&1 | grep -iE 'sign.?in|account|auth|login'
(nothing)
```

All 7 models survived, the 64k context and 30m keep-alive survived, and the
endpoint is still loopback-only. Speed is unchanged — the full context sweep
below was run on both versions and matches at every size within noise.

## The context finding

Phase 03 measured `qwen3-coder:30b` at **53.6 tok/s**, spilling 45/55 into RAM,
and that number is what the log and the map have repeated. Phase 03c then set
`OLLAMA_CONTEXT_LENGTH=65536`, because Claude Code needs 64k. Nobody re-measured
after that change.

Same model, same prompt, same GPU state, one context size per row. Every row
unloads all models first; a cold row is re-run warm, because the first read of
an 18 GB model off the SATA disk depresses the number (see What broke 3).

```
  ctx      tok/s   in VRAM   loaded size
  4096      57.1      57%      19.2 GB
  8192      54.7      55%      19.6 GB
  16384     51.5      53%      20.4 GB
  32768     46.3      49%      22.1 GB
  65536     38.3      43%      25.4 GB     <- the configured default
```

The KV cache at 64k is about 6.8 GB. On a 12 GB card that space comes straight
out of the weights, so more of the model lives in DDR4 and throughput falls
**33%**. The published 53.6 is an 8k-context number for a machine that has been
running at 64k.

The dense models don't move, because their weights never leave VRAM:

```
model            4k tok/s   64k tok/s   in VRAM
gemma4:12b         56.1       55.7       100%
qwen3.5:9b         76.4       76.8       100%
qwen3-coder:30b    57.1       38.2        43%
```

**That inverts the phase 03 headline.** At 4k the claim is exactly right — 57.1
against 56.1, a 30B MoE matching a 12B dense model it has no business matching.
At the 64k this machine actually runs, the MoE is **31% slower** than the 12B.
The physics didn't change; the operating point did. A measurement is only a fact
about the configuration it was taken in, and a configuration change invalidates
every number taken before it.

The 64k default stays. The trade is 8× the context for a third of the
throughput, and the agent workloads this endpoint exists for need the context:
neither Claude Code nor the `claude-local` wrapper sets `num_ctx` per request, so
lowering the default would quietly truncate them instead of speeding them up.
What changes is the documentation, not the setting.

## The acceptance tests were wrong, and passing them would have been worse

Re-running [`scripts/acceptance-tests.sh`](scripts/acceptance-tests.sh) gave
**7 pass, 2 fail**. Both failures were the tests, not the machine.

**A2.4 demanded `apt-mark hold` on the driver.** That was reversed in 02b: a
hold strands the GPU at the next kernel ABI bump, because the package name does
not pin the driver branch. The test still required the thing the log had
rejected, so a correct machine failed. It now fails on a *held* package, and
checks what the hold was meant to protect instead — that the loaded kernel
module and the userspace driver are the same version:

```
=== A2.4  driver and kernel module agree, and nothing is pinned ===
PASS  nothing is held
      | kernel module 595.91.07   |   nvidia-smi 595.91.07   |   kernel 7.0.0-31-generic
PASS  kernel module and userspace driver are the same version
```

**A2.8 failed because nothing was listening on port 22.** SSH is deliberately
absent until the network rebuild, so the check told a correctly configured
machine to install a service it had decided not to run. The outcome worth
testing is the opposite one — that nothing is reachable off the box at all:

```
=== A2.8  nothing is reachable beyond loopback ===
PASS  every listener is bound to loopback
      | SSH is intentionally absent until the network rebuild; the model endpoint is 127.0.0.1 only
```

Before trusting either rewrite, both were fed a synthetic broken configuration
to confirm they can still fail — the loopback check correctly flags
`0.0.0.0:22` and `0.0.0.0:11434`. A check that has only ever been seen passing
has not been tested.

**A2.5 then failed correctly**, on the private copy, and that one was real: its
saved baseline recorded driver 595.84, from before the repair in 02b. The check
caught a genuine change; it just had no way to say "this change was intended."
It now prints how to record the new good state.

```
pass 11   fail 0   skip 1   manual 1
```

The remaining manual check is A2.7, rescue media, which needs a person and the
USB stick.

## What broke

**1. My own sudo check lied to me.** To find out whether the root half could run
unattended I used `sudo -n true 2>&1 | head -2 && echo "passwordless: YES"`. The
pipeline's exit status is `head`'s, not `sudo`'s, so it printed `sudo: a
password is required` and `passwordless sudo: YES` on consecutive lines. The
same class of bug as the `lsmod | grep -q` failure in 02b: **the exit status of
a pipeline belongs to its last command**, and any check built on one is testing
the wrong process.

**2. A verification script that would have reported a false failure.** The
maintenance script's VRAM check embedded Python inside single quotes and escaped
the inner double quotes — `m[\"name\"]` — which bash preserves literally, so
Python got a syntax error and the check would have reported "nothing is in
VRAM," a fabricated regression on a healthy machine. It was caught by running
every check against the current known-good machine first. **A check must be seen
passing on a known-good system before it is trusted to report a failure.** The
same escaping mistake then recurred twice in throwaway commands; the fix that
stuck was to stop embedding Python in shell quotes and put it in a file.

**3. Two wrong numbers from a cold page cache.** The first 0.34.2 sweep reported
35.5 tok/s at 4k against 57.1 on 0.33.3 — a 38% regression, which would have
been a reason to roll back. The load time gives it away: 28.2 s against the
usual 4.3 s, because the container had just restarted and 18 GB was being read
off the SATA disk. Warm, the same row gives 57.0 and 57.6. The same artifact
produced 19.4 tok/s for gemma4 (34 s load) before a warm re-run gave 56.1.
**A number that would change the conclusion gets re-measured before it is
believed** — the same rule 03c arrived at, hit twice more here.

**4. Two acceptance checks that failed on a correct machine.** Covered above.
This is the third time in this log that a check has been wrong rather than the
machine: 02b had one that passed on a configuration that would have lost the
GPU, and now two that fail on a configuration that is right. Both directions
are the same defect — the check encodes a decision that was later superseded and
nobody revisited it.

## Acceptance check

| | Check | Result |
|---|---|---|
| A7.1 | Ollama upgraded, endpoint still loopback-only, 64k, 7 models | pass — 0.34.2, `127.0.0.1:11434`, all 7 present |
| A7.2 | No performance regression from the upgrade | pass — full sweep on both versions, equal within noise at 5 context sizes |
| A7.3 | The server needs no account after the 0.34 sign-in change | pass — no auth lines in the logs, endpoint answers unauthenticated |
| A7.4 | Acceptance tests green, and the checks themselves verified | pass — 11/0/1/1, both rewrites shown failing on a synthetic broken config |
| A7.5 | Spend gate still correct after the upgrades | pass — 87/87, including all 10 regressions |
| A7.6 | Backup still runs and the credential scan is clean | pass — dry run, 36 MB, 180 files, clean |
| A7.7 | Package upgrade applied and verified | **deferred** — needs root; script written, guards and post-checks included |

Phase 07 stays open on A7.7 until the packages go on.
