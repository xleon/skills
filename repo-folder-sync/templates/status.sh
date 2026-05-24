#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.env"

mkdir -p "$LOG_DIR" "$STATE_DIR"

echo "== Repository Folder Sync Status =="
echo "Repo:           $SRC_ROOT"
echo "Destination:    $DST_ROOT"
echo "Launch label:   $LAUNCH_AGENT_LABEL"
echo

if command -v launchctl >/dev/null 2>&1; then
  echo "[launchd]"
  if launchctl print "gui/$(id -u)/$LAUNCH_AGENT_LABEL" >/dev/null 2>&1; then
    launchctl print "gui/$(id -u)/$LAUNCH_AGENT_LABEL" \
      | awk '/state =|last exit code|pid =/{print "  " $0}'
  else
    echo "  Not loaded"
  fi
else
  echo "[launchd] launchctl command not available"
fi

echo
if command -v unison >/dev/null 2>&1; then
  echo "[dependencies] unison: $(command -v unison)"
else
  echo "[dependencies] unison: MISSING"
fi

if command -v fswatch >/dev/null 2>&1; then
  echo "[dependencies] fswatch: $(command -v fswatch)"
else
  echo "[dependencies] fswatch: MISSING"
fi

LAST_SYNC_LOG="$(ls -1t "$LOG_DIR"/sync-*.log 2>/dev/null | head -n 1 || true)"
echo
if [[ -n "$LAST_SYNC_LOG" ]]; then
  echo "[last sync log] $LAST_SYNC_LOG"
  tail -n 20 "$LAST_SYNC_LOG"
else
  echo "[last sync log] no sync logs found"
fi

echo
if [[ -f "$LOG_DIR/launchd.out.log" ]]; then
  echo "[launchd out] $LOG_DIR/launchd.out.log"
  tail -n 10 "$LOG_DIR/launchd.out.log"
else
  echo "[launchd out] no log file"
fi

echo
if [[ -f "$LOG_DIR/launchd.err.log" ]]; then
  echo "[launchd err] $LOG_DIR/launchd.err.log"
  tail -n 10 "$LOG_DIR/launchd.err.log"
else
  echo "[launchd err] no log file"
fi
