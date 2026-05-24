#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.env"

if ! command -v fswatch >/dev/null 2>&1; then
  echo "Error: fswatch is not installed. Install with: brew install fswatch"
  exit 1
fi

mkdir -p "$STATE_DIR" "$LOG_DIR"

echo "Watching for changes..."
echo "Repo:    $SRC_ROOT"
echo "Dest:    $DST_ROOT"

fswatch -o -r \
  --latency "$WATCHER_DEBOUNCE_SECONDS" \
  --exclude ".*/\\.tools/repo-folder-sync/state/.*" \
  --exclude ".*/\\.tools/repo-folder-sync/logs/.*" \
  "$SRC_ROOT" "$DST_ROOT" | while read -r _event_count; do
    "$SCRIPT_DIR/sync.sh" || true
  done
