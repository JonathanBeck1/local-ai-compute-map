# Phase 00 — Protect and inventory

**Status:** in progress — inventory done, backup blocked on hardware
**Date:** 2026-09-07
**Elapsed:** ~40 min for the inventory
**Cost:** $0 so far

## Goal

Know what exists and where, and have a restorable backup, before building anything on top of this machine. Nothing else in the log starts until this closes.

## Hardware touched

MacBook Pro M3 Pro, 18 GB. 388 GB in use on the data volume.

## What I ran

Backup status first, because it's one command and its answer decides how urgent everything else is.

```bash
tmutil destinationinfo
tmutil latestbackup
diskutil list external
```

Then a repo sweep. Depth 7, skipping `node_modules`, `Library` and `.Trash`.

```bash
find ~ -maxdepth 7 -type d -name .git \
  -not -path "*/node_modules/*" -not -path "*/Library/*" -not -path "*/.Trash/*" \
  2>/dev/null | sed 's|/\.git$||' > /tmp/repos.txt
```

For each repo: is there a remote, is it ahead of that remote, how many files are uncommitted.

```bash
while read p; do
  remote=$(git -C "$p" remote -v | head -1)
  dirty=$(git -C "$p" status --porcelain | wc -l | tr -d ' ')
  if [ -n "$remote" ]; then
    ahead=$(git -C "$p" rev-list --count @{u}..HEAD 2>/dev/null || echo "no-upstream")
  else
    ahead=$(git -C "$p" rev-list --count HEAD 2>/dev/null)
  fi
  printf '%s\t%s\t%s\t%s\n' "${remote:+remote}" "$ahead" "$dirty" "$p"
done < /tmp/repos.txt
```

## Output

```
$ tmutil destinationinfo
tmutil: No destinations configured.

$ tmutil latestbackup
Failed to mount backup destination, error: Error Domain=com.apple.backupd.ErrorDomain
Code=17 "Failed to mount destination."

$ diskutil list external
(only iOS simulator disk images — no physical external storage attached)
```

Repo sweep, aggregate:

```
total repos:            50
no remote at all:        9
has remote, unpushed:    7
dirty working tree:     28
```

## What broke

Nothing broke. What the inventory found is worse than a breakage.

**There is no backup.** Not stale, not misconfigured — `No destinations configured`. Every uncommitted file on this machine exists in exactly one place, and has the whole time I've been planning an AI lab to run on it.

**Uncommitted work is the real exposure, not unpushed commits.** I expected unpushed commits to be the headline. They aren't. 7 repos are ahead of their remote; **28** have dirty working trees. Four times as much work is sitting uncommitted as unpushed, and the two aren't equivalent — an unpushed commit still survives a clone from another machine or a disk recovery. An uncommitted edit survives nothing.

**My own numbers were wrong in both directions.** I'd been working from "42 repos, 22 with unpushed work, 7 with no remote." Actual: 50 repos, 7 unpushed, 9 with no remote. Repo count low, unpushed count high by 3x. I'd never counted. I'd remembered.

**Most of the no-remote repos are archive noise.** Five of the nine are duplicate copies of one dead project in an archive folder. Deduplicating before backing up is worth more than backing all of them up.

## Blocked

The backup half needs an external drive and none is attached. 388 GB in use means 1 TB minimum to leave room for history.

Until that drive exists this phase cannot close, and nothing downstream should start.

## What I would do differently

Run `tmutil destinationinfo` first, before any planning. One command, one second, and its answer determines whether the rest is worth doing. I did roughly ten days of architecture work on a machine I hadn't checked was backed up.

Count things instead of remembering them. Two of the three numbers I was carrying were wrong, and the sweep above takes under a minute.

## Acceptance check

Not met. Closes when all four hold:

- [ ] `tmutil destinationinfo` names a destination
- [ ] `tmutil latestbackup` returns a dated snapshot
- [ ] A file is restored from that snapshot and its checksum matches — a backup that has never been restored is a hypothesis
- [ ] Repo sweep shows zero repos whose commits exist only on this disk
