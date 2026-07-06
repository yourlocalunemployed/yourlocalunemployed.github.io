#!/usr/bin/env bash
#
# backup-blog.sh — local safety-net backup for the Hugo blog.
#
# GitHub already holds full committed history offsite. This adds a
# self-contained, timestamped snapshot of the WHOLE repo (source + .git
# history + any uncommitted/untracked work), copied to every available
# off-VM target, keeping the most recent $RETAIN archives on each.
#
# Regenerable build output (public/) is excluded — rebuild it with
# `hugo --minify` after a restore.
#
# Run by hand any time:   ~/blog/scripts/backup-blog.sh
# Restore:                tar -xzf blog-<ts>.tar.gz -C /some/dir && cd blog && hugo --minify
#
set -euo pipefail

REPO="${BLOG_REPO:-/home/student/blog}"
RETAIN="${BLOG_BACKUP_RETAIN:-7}"          # archives to keep per target
LOG="${HOME}/.local/state/blog-backup/backup.log"

# Off-VM destinations. Missing/unmounted ones are skipped, not fatal.
TARGETS=(
  "${HOME}/OneDrive/blog-backups"                # offsite via OneDrive sync
  "/mnt/hgfs/ClaudeDIrecotryVM/blog-backups"     # VMware host shared folder
)

mkdir -p "$(dirname "$LOG")"
log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG" >&2; }

[ -d "$REPO/.git" ] || { log "ERROR: $REPO is not a git repo — aborting"; exit 1; }

ts="$(date '+%Y%m%d-%H%M%S')"
stage="$(mktemp -d)"
archive="${stage}/blog-${ts}.tar.gz"
trap 'rm -rf "$stage"' EXIT

log "backup start (repo=$REPO)"

tar -czf "$archive" \
  --exclude='blog/public' \
  --exclude='blog/.hugo_build.lock' \
  --exclude='blog/resources/_gen' \
  -C "$(dirname "$REPO")" "$(basename "$REPO")"

log "archive built: blog-${ts}.tar.gz ($(du -h "$archive" | cut -f1))"

copied=0
for dest in "${TARGETS[@]}"; do
  if [ ! -d "$(dirname "$dest")" ]; then
    log "skip (unavailable): $dest"
    continue
  fi
  mkdir -p "$dest"
  cp "$archive" "$dest/"
  # prune: keep newest $RETAIN by mtime
  find "$dest" -maxdepth 1 -name 'blog-*.tar.gz' -printf '%T@ %p\n' \
    | sort -rn | tail -n +"$((RETAIN + 1))" | cut -d' ' -f2- \
    | while read -r old; do rm -f "$old"; log "pruned: $(basename "$old") @ $dest"; done
  log "copied -> $dest (keeping newest $RETAIN)"
  copied=$((copied + 1))
done

if [ "$copied" -eq 0 ]; then
  log "WARNING: no targets available — snapshot NOT stored off-VM"
  exit 1
fi
log "backup done ($copied target(s))"
