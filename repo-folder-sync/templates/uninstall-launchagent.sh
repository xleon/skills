#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.env"

PLIST_TARGET="$HOME/Library/LaunchAgents/$LAUNCH_AGENT_LABEL.plist"
OLD_LABEL="com.user.$(basename "$SRC_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9.-' '-')-dropbox-sync"
OLD_PLIST_TARGET="$HOME/Library/LaunchAgents/$OLD_LABEL.plist"

if [[ -f "$PLIST_TARGET" ]]; then
  launchctl unload "$PLIST_TARGET" >/dev/null 2>&1 || true
  rm -f "$PLIST_TARGET"
  echo "LaunchAgent removed: $PLIST_TARGET"
else
  echo "LaunchAgent not found: $PLIST_TARGET"
fi

# Also remove legacy dropbox-sync label/plist if present.
launchctl bootout "gui/$(id -u)/$OLD_LABEL" >/dev/null 2>&1 || true
launchctl unload "$OLD_PLIST_TARGET" >/dev/null 2>&1 || true
rm -f "$OLD_PLIST_TARGET"
