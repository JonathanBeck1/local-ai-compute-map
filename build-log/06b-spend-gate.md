# Phase 06b — Spend gate

**Status:** not started **Date:** **Elapsed:** **Cost:**

## Goal

Put a human approval step in front of any agent-initiated paid GPU launch. As the map notes, the coding agent's own safety classifier has no dollar criterion, so this seam is the one thing on this list that genuinely does not exist yet as a first-party feature.

## Hardware touched

Development console; Linux workstation as launch host

## Planned steps

- Add an explicit ask rule on the launch command.
- Add a pre-execution hook that reads the dry-run cost, compares it to a declared budget, and asks or denies with the dollar figure in the reason.
- Log every launch, estimated and actual, to an append-only ledger.
- Confirm the gate still prompts under the agent's automatic permission mode.

## What I ran

_Not started._

## Output

_Pasted verbatim when the phase runs._

## What broke

_An empty section here after the phase is done would be suspicious, not impressive._

## What I would do differently

_Filled in after._

## Acceptance check

_The phase is done when this section holds pasted output, not when the commands have been typed._
