# Build log

The same setup on real hardware, written as it happens.

Most setup guides are written afterwards, by someone who already knows the answer, on hardware a
vendor sent them, with the failures cut. This is the opposite. The hardware is what I already own, the
order was fixed in advance, and what breaks stays in.

## Hardware

| Role | Machine | Spec that matters |
|---|---|---|
| Development console | MacBook Pro M3 Pro | 18 GB unified |
| Always-on | Mac mini M4 | 16 GB unified |
| Local model endpoint | Linux workstation | RTX 4070, 12 GB VRAM, 64 GB RAM |
| Archive | NAS | — |
| Burst | Rented cloud GPUs | bounded |

Two things follow from that. 12 GB is the real ceiling here, so anything bigger is a cloud job or
doesn't happen. And both Macs are under the 24 GB that Perplexity's Mac product needs, so some tools
in the [map](../README.md) get documented but not run. Where that happens I say so.

## Phases

| # | Phase | Status |
|---|---|---|
| 00 | [Protect and inventory](00-protect-and-inventory.md) | not started |
| 01 | [Naming and access](01-naming-and-access.md) | not started |
| 02 | [Linux box, driver, containers](02-linux-box-driver-containers.md) | not started |
| 03 | [Local model endpoint](03-local-model-endpoint.md) | not started |
| 04 | [MacBook remote workflow](04-macbook-remote-workflow.md) | not started |
| 05 | [Always-on services and archive](05-always-on-services.md) | not started |
| 06a | [Cloud burst, bounded](06a-cloud-burst-bounded.md) | not started |
| 06b | [Spend gate](06b-spend-gate.md) | not started |

In order. Phase 00 is backups and inventory, first, because a lab on top of unbacked-up work isn't a
lab.

## Rules

Paste real output, not a description of it and not a cleaned-up version.

Record what broke. An empty "what broke" section reads as suspicious, not impressive.

Record the money and the hours, including hours lost.

Sanitize, don't fictionalize. Hostnames, IPs, mesh names and serials become placeholders like
`<linux-box>`. Nothing else gets edited.

A phase is done when its acceptance check has produced pasted output. Not when the commands were
typed.

Date everything. These tools change weekly and an undated setup guide is a trap.

## Template

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
