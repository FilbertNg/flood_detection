#!/usr/bin/env bash
# Daily (floodready-backup.timer): a consistent copy of the app database, gzipped, last 7 kept.
# The database holds what can't be rebuilt from JPS: residents' answers, push subscriptions, admin accounts, reviews.
set -euo pipefail
DIR=/opt/floodready/backups
mkdir -p "$DIR"
out="$DIR/floodready-$(date +%F).db"
sqlite3 /opt/floodready/app/data/floodready.db ".backup '$out'"
gzip -f "$out"
ls -1t "$DIR"/floodready-*.db.gz | tail -n +8 | xargs -r rm --
echo "backup $(du -h "$out.gz" | cut -f1) → $out.gz"
