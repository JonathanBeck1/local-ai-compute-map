#!/usr/bin/env bash
#
# backup-machine-state.sh -- back up what on a workstation exists nowhere else
#
# Copies the small set of things on this machine that exist nowhere else into
# this private repo, then commits and pushes. Re-run it any time; a backup you
# ran once is stale the next day.
#
# What exists only on this disk (inventoried 2026-09-19): about 45 MB.
# Everything large -- models, the Steam library, container images, tool
# installs -- re-downloads, and is deliberately NOT copied.
#
#   ~/.claude/projects/          session transcripts + memory  (the raw record of the build)
#   ~/.claude/settings.json      Claude Code settings, incl. the spend-gate hook registration
#   ~/.claude/hooks/             the spend gate
#   ~/.config/spend-gate/        the spend policy
#   ~/.local/state/spend-gate/   the spend audit log
#   /etc/...                     the current state of every system file this build changed
#
# Deliberately NOT copied: etckeeper's full /etc history (/etc/.git). It contains
# /etc/shadow -- password hashes -- which do not go to GitHub, even privately.
# That history stays local; the files it tracks for this build are copied as-is.
#
# Refuses to commit if a credential-shaped string turns up anywhere in the copy.
#
# Usage:  bash backup-machine-state.sh          # copy, scan, commit, push
#         bash backup-machine-state.sh --dry    # copy and scan only

set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
DEST="$REPO/machine-state"
DRY=0; [ "${1:-}" = "--dry" ] && DRY=1

ETC_FILES=(
    /etc/fstab
    /etc/hosts
    /etc/default/grub
    /etc/docker/daemon.json
    /etc/containerd/config.toml
    /etc/systemd/system/docker.service.d/10-require-ai-lab.conf
    /etc/systemd/system/containerd.service.d/10-require-ai-lab.conf
    /etc/apt/sources.list.d/docker.sources
    /etc/apt/sources.list.d/nvidia-container-toolkit.list
)

CRED='gh[opusr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|"(access|refresh)_token"[[:space:]]*:[[:space:]]*"[^"*]{20,}'

echo "==> copying into $DEST"
mkdir -p "$DEST/claude" "$DEST/config" "$DEST/state" "$DEST/etc"
rsync -a --delete ~/.claude/projects/        "$DEST/claude/projects/"
rsync -a --delete ~/.claude/hooks/           "$DEST/claude/hooks/"
cp -a ~/.claude/settings.json                "$DEST/claude/settings.json"
rsync -a --delete ~/.config/spend-gate/      "$DEST/config/spend-gate/"
rsync -a --delete ~/.local/state/spend-gate/ "$DEST/state/spend-gate/"
for f in "${ETC_FILES[@]}"; do
    if [ -r "$f" ]; then
        mkdir -p "$DEST/etc$(dirname "$f")"
        cp -a "$f" "$DEST/etc$f"
    else
        echo "   skipped (unreadable or absent): $f"
    fi
done
echo "   $(du -sh "$DEST" | cut -f1) total, $(find "$DEST" -type f | wc -l) files"

# One known fake: a test token typed into a command on 2026-09-19 to prove this
# scan refuses. Claude Code records a command in the transcript before running
# it, so the fake is permanently in that session's transcript and would block
# every backup. Redact exactly that string in the COPY (never the original).
# Built at runtime so the literal never appears in this script or the repo.
KNOWN_FAKE="gh""p_$(printf 'FAKE%.0s' 1 2 3 4 5 6 7 8 9)12"
grep -rlF "$KNOWN_FAKE" "$DEST" 2>/dev/null | while read -r f; do
    sed -i "s/$KNOWN_FAKE/[REDACTED-TEST-CANARY]/g" "$f"
done

echo "==> credential scan"
HITS="$(grep -rElc -E "$CRED" "$DEST" 2>/dev/null || true)"
if [ -n "$HITS" ]; then
    echo "REFUSING TO COMMIT: credential-shaped content found in:" >&2
    echo "$HITS" | sed 's/^/   /' >&2
    echo "Nothing was committed. Inspect those files; the copy is left in place for that." >&2
    exit 1
fi
echo "   clean"

if [ "$DRY" -eq 1 ]; then
    echo "==> dry run: copied and scanned, not committed"
    exit 0
fi

echo "==> commit and push"
cd "$REPO"
git add machine-state
if git diff --cached --quiet; then
    echo "   nothing changed since the last backup"
    exit 0
fi
git commit -q -m "machine-state backup $(date +%F\ %H:%M)

Session transcripts, memory, Claude settings, the spend gate and its log,
and the system config files this build changed. Credential scan: clean."
git push -q
echo "   pushed: $(git log --oneline -1)"
