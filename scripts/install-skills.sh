#!/bin/bash
# install-skills.sh — mirror skills/ from this repo into ~/.claude/skills/
#
# The skills in this repo (skills/<name>/SKILL.md) are the canonical source.
# Claude Code loads user-global skills from ~/.claude/skills/<name>/SKILL.md.
# This script syncs canonical -> live with rsync.
#
# Usage:
#   bash scripts/install-skills.sh          # sync (additive + overwrite changed)
#   bash scripts/install-skills.sh --prune  # also delete ~/.claude/skills/<name> entries
#                                          # that no longer exist in this repo

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_DIR/skills/"
DST="$HOME/.claude/skills/"

if [ ! -d "$SRC" ]; then
  echo "error: $SRC not found — run from a checkout of AI_skills" >&2
  exit 1
fi

mkdir -p "$DST"

RSYNC_FLAGS=(-av)
if [ "${1:-}" = "--prune" ]; then
  RSYNC_FLAGS+=(--delete)
  echo "[install-skills] PRUNE mode: skills not in repo will be removed from ~/.claude/skills/"
fi

# Mirror, but never touch the live repo's own .git or hidden files
rsync "${RSYNC_FLAGS[@]}" \
  --exclude='.git/' \
  --exclude='.DS_Store' \
  "$SRC" "$DST"

echo
echo "[install-skills] installed skills:"
for d in "$DST"*/; do
  name=$(basename "$d")
  [ -f "$d/SKILL.md" ] && echo "  /$name"
done
