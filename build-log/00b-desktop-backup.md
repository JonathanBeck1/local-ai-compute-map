# Phase 00b — What on the workstation exists nowhere else

**Status:** part 1 done: the irreplaceable set is backed up daily and a restore is tested. Part 2, the NAS, is deferred and has turned out to be a convenience rather than the backup.
**Date:** 2026-09-19
**Elapsed:** ~40 min
**Cost:** $0

## Goal

When the [roles were corrected](README.md), the desktop became where the work lives, on a disk that nothing copied. The plan called this phase "desktop backup, the NAS is the target." But the NAS isn't connected yet, and [phase 00](00-protect-and-inventory.md)'s first lesson was to count before planning. So: inventory first. What on this machine would actually be lost if the disk died?

## Hardware touched

The workstation. Read-only until the backup ran.

## What I ran

Phase 00's repo sweep, adapted: every git repo, and whether it has a remote, unpushed commits or uncommitted work. Then the home directory and the bulk disk by size, and each item classified by one question: *does this re-download?*

## Output

```
every git repo on this machine: remote? unpushed? uncommitted?
  origin   ahead=0   dirty=0    ~/Desktop/<private build record>
  origin   ahead=0   dirty=0    ~/repos/local-ai-compute-map
```

Both clean and pushed. After classifying the rest:

| | Size | Re-downloads? |
|---|---|---|
| Models | 32 GB | yes: `ollama pull` |
| Steam library | 64 GB | yes |
| Steam client, Claude Code install, tool binaries, container images | ~6 GB | yes |
| **Claude Code session transcripts and memory** | **29 MB** | **no** |
| **Claude settings, the [spend gate](06b-spend-gate.md), its policy and audit log** | **< 1 MB** | **no** |
| **The system config files this build changed** (fstab, GRUB, Docker, containerd, systemd guards, apt sources) | **tiny** | **no**, though the build log documents every change |

**What would actually be lost if the disk died is about 45 MB.** The other ~100 GB re-downloads. That reframes the phase. The NAS doesn't protect the work, it saves a long re-download. So the backup that matters can happen today, without it.

The most irreplaceable item is one I hadn't counted: **the session transcripts.** This build log's first rule is "paste real output, not a description of it," and the transcripts are where the real output lives, holding every command and every result. The entries are written from them.

The backup is a script, [`scripts/backup-machine-state.sh`](scripts/backup-machine-state.sh). It copies that set into a private GitHub repo, runs a credential scan, and commits and pushes. **It refuses to commit** if anything credential-shaped turns up: GitHub, Anthropic, AWS, Google and Slack tokens, private keys, OAuth tokens.

One deliberate exclusion: `etckeeper` keeps a full git history of `/etc`, and that history includes **`/etc/shadow`, the password hashes.** Those don't go to GitHub, even a private repo. The history stays local; the files this build changed are copied as they currently stand, all world-readable and none secret, so the backup needs no root.

**Restore test**, because Phase 00's rule is that *a backup that has never been restored is a hypothesis*: a fresh clone from GitHub, checksummed against the live originals, and the restored spend gate run straight from the clone:

```
fresh clone from GitHub: ok (29M)
  DIFFERS: ~/.claude/projects/.../memory/MEMORY.md
byte-identical to the live originals: 79   differ: 1

restored gate says: deny
```

The one difference was an edit made *after* the backup ran. So was a new memory file that wasn't in the backup at all. **Three minutes after the first backup, it was already out of date.** Re-running it brought it current. A backup you run by hand is a backup of one moment.

## What broke

**1. The credential scan fired on a fake token I had typed.** To prove the scan refuses, I planted a fake GitHub token and expected a refusal. It refused before the test even ran, and it named *the session transcript*, not the planted file. **Claude Code records a command in the transcript before running it**, so the fake token I typed into the command was already in the transcript, and it will be there permanently. Every future backup of that session would have been refused.

The fix redacts that one known fake in the *copy*, never the original. The fake's value is built at runtime, so the literal string never appears in the script or the repo. The refusal was then proven properly with a token assembled at runtime, which never touched a transcript.

The general lesson for anyone backing up agent sessions: **the transcript contains everything you typed, including the things you typed to test the thing that scans the transcript.**

**2. The inventory found a local agent writing outside its directory.** A stray test file sat in the home directory. Its timestamp put it inside the [phase 03b](03b-coding-agent-on-the-workstation.md) local-model trial: an early draft the agent wrote to the wrong path before writing the real one in the folder it had been given. It was harmless here, but it's exactly what makes an unattended local agent risky, and the check at the time missed it by only looking inside the working directory. It's now recorded in 03b.

## What I would do differently

**Count before buying.** This is phase 00's lesson again. Two weeks ago I'd assumed the desktop backup meant "connect the NAS." Counting showed 45 MB that matters and 100 GB that doesn't.

**Schedule it, or it's stale.** The restore test found the backup already out of date three minutes after it ran. That settled the question of scheduling it. Scheduling was still asked rather than assumed, because a daily job pushes session transcripts to GitHub unattended, and that's a decision for the person whose sessions they are. The answer was yes.

It runs as a systemd *user* timer, so no root is needed. It runs daily at 23:00, and `Persistent=true` means a run missed while the machine was off fires at the next login. It runs at low CPU and I/O priority, so it can't disturb a game or a model. An `OnFailure=` unit raises a desktop notification if the credential scan refuses or the push fails, so a broken backup can't fail silently for weeks.

It was verified the way it will actually run, not from a terminal. The real service, started under systemd, made its own push, which proves the GitHub login held in the desktop keyring is reachable from a scheduled job. That's the part most likely to break silently. The alarm was proven by a deliberately failing job wired to the same `OnFailure=`, and the notification fired.

## Acceptance check

| | Check | Result |
|---|---|---|
| A0b.1 | Everything on the machine classified as re-downloadable or not | pass: ~45 MB irreplaceable, ~100 GB re-downloadable |
| A0b.2 | The irreplaceable set is off the machine | pass: private repo, verified from the remote |
| A0b.3 | Nothing credential-shaped leaves the machine | pass: scan clean, refusal proven with a planted token |
| A0b.4 | A restore has been tested | pass: fresh clone, 79/80 byte-identical, the one difference explained, the restored gate runs |
| A0b.5 | The backup stays current | pass: daily systemd user timer, proven to push from inside systemd; failures notify |

Part 2, the NAS, waits for the network rebuild and is now about saving a 100 GB re-download.
