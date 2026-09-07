# Build log

One worked example of the setup the [map](../README.md) describes, on hardware I actually own, written as it happens.

The map is general — it's about the tools, not about my machines. This part isn't, deliberately. Most published guides in this space run on 4×4090 rigs or vendor-loaned DGX boxes, which is not what most people reading them have. This runs on an 18 GB laptop, a 16 GB Mac mini and a 12 GB GPU, which is closer to ordinary. Where a tool in the map won't run on hardware this size, I say so rather than quietly skipping it.

Guides are usually written afterwards, by someone who already knows the answer, with the failures cut. Here what breaks stays in.

## Hardware

| Role | Machine | Spec that matters |
|---|---|---|
| Development console | MacBook Pro M3 Pro | 18 GB unified |
| Always-on | Mac mini M4 | 16 GB unified |
| Local model endpoint (planned) | Self-built desktop, currently Windows | RTX 4070, 12 GB VRAM, 64 GB RAM |
| Archive | NAS | — |
| Burst | Rented cloud GPUs | bounded |

12 GB is the real ceiling, so anything bigger is a cloud job or doesn't happen. Both Macs are under the 24 GB Perplexity's Mac product needs, so some tools in the map get documented but not run.

The desktop is a gaming PC running Windows, not a Linux box yet. Converting it — wiping Windows, dual-booting it onto its own SSD, and putting Ubuntu on the big one — is phase 02, and it hasn't happened. That starting point is probably more common than the one most guides assume: if you own a 4070, it's likely running Windows right now.

## Entries

- [00 — Protect and inventory](00-protect-and-inventory.md) — inventory done, backup not yet configured

Planned, in order. Each becomes a file when it has output in it, not before:

01 naming and access · 02 Linux box, driver, containers · 03 local model endpoint · 04 MacBook remote workflow · 05 always-on services and archive · 06a cloud burst, bounded · 06b spend gate

## Rules

Paste real output, not a description of it and not a cleaned-up version.

Record what broke. An empty "what broke" section reads as suspicious, not impressive.

Record the money and the hours, including hours lost.

Sanitize, don't fictionalize. Hostnames, IPs, mesh names and serials become placeholders like `<linux-box>`. Repo and client names come out. Nothing else gets edited.

A phase is done when its acceptance check has produced pasted output. Not when the commands were typed.

Date everything. These tools change weekly and an undated setup guide is a trap.

## Template

```markdown
# Phase NN — <name>

**Status:** in progress | done | blocked
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
