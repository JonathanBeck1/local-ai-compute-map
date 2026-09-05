# Build log

An actual build of a small heterogeneous AI lab, one entry per phase, written as it happens.

Most setup guides are written after the fact by someone who already knows the answer, on hardware
supplied by a vendor, with the failures edited out. This is the opposite: the hardware is modest and
already owned, the order was decided in advance, and the things that broke stay in.

## The hardware

Deliberately unimpressive, because that is the point — this is the fleet a person actually has rather
than the one a benchmark article assumes.

| Role | Machine | Relevant spec |
|---|---|---|
| Development console | MacBook Pro, M3 Pro | 18 GB unified |
| Always-on services | Mac mini, M4 | 16 GB unified |
| Local model endpoint | Linux workstation | RTX 4070, 12 GB VRAM, 64 GB RAM |
| Archive and backup | NAS | — |
| Elastic capacity | Rented cloud GPUs | as needed, bounded |

Two consequences worth stating up front, since they shape everything below. First, 12 GB of VRAM is
the real ceiling for local work here; anything larger is a cloud job or does not happen. Second, both
Macs are below the 24 GB that Perplexity's Mac product requires, so some of the tools in the
[map](../README.md) are documented here but not runnable on this fleet. Where that happens, it is
noted rather than hidden.

## The phases

| # | Phase | Status |
|---|---|---|
| 00 | [Protect and inventory](00-protect-and-inventory.md) | not started |
| 01 | [Naming and access](01-naming-and-access.md) | not started |
| 02 | [Linux box, driver, containers](02-linux-box-driver-containers.md) | not started |
| 03 | [Local model endpoint](03-local-model-endpoint.md) | not started |
| 04 | [MacBook remote workflow](04-macbook-remote-workflow.md) | not started |
| 05 | [Always-on services and archive discipline](05-always-on-services.md) | not started |
| 06a | [Cloud burst, bounded](06a-cloud-burst-bounded.md) | not started |
| 06b | [Spend gate](06b-spend-gate.md) | not started |

Phases run in order. Phase 00 is backups and inventory and comes first because a lab built on top of
unbacked-up work is not a lab, it is an accident with a schedule.

## Rules for these entries

1. **Paste real output.** Not a description of the output, and not a cleaned-up version of it.
2. **Record what broke.** An entry with an empty "what broke" section is suspicious, not impressive.
3. **Record the cost and the clock.** Both the money and the hours, including the hours lost.
4. **Sanitize, do not fictionalize.** Hostnames, IP addresses, mesh network names, serial numbers,
   and account identifiers are replaced with placeholders like `<linux-box>`. Nothing else is edited.
5. **Do not claim it works until it has been run.** A phase is "done" when its acceptance check has
   produced pasted output, not when the commands have been typed.
6. **Note the date.** Every entry is stamped, because the tools in this space change weekly and an
   undated setup guide is a trap.

## Template

Each phase file follows the same shape:

```markdown
# Phase NN — <name>

**Status:** not started | in progress | done
**Date:**
**Elapsed:**
**Cost:**

## Goal
## Hardware touched
## What I ran
## Output
## What broke
## What I would do differently
## Acceptance check
```
