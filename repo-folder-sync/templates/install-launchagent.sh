#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.env"

PLIST_TARGET="$HOME/Library/LaunchAgents/$LAUNCH_AGENT_LABEL.plist"
OLD_LABEL="com.user.$(basename "$SRC_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9.-' '-')-dropbox-sync"
OLD_PLIST_TARGET="$HOME/Library/LaunchAgents/$OLD_LABEL.plist"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
chmod +x "$SCRIPT_DIR/repo-folder-sync" "$SCRIPT_DIR/watch.sh"

# Best effort cleanup from old naming to avoid stale background items.
launchctl bootout "gui/$(id -u)/$OLD_LABEL" >/dev/null 2>&1 || true
launchctl unload "$OLD_PLIST_TARGET" >/dev/null 2>&1 || true
rm -f "$OLD_PLIST_TARGET"

cat > "$PLIST_TARGET" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LAUNCH_AGENT_LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>$SCRIPT_DIR/repo-folder-sync</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/launchd.out.log</string>

  <key>StandardErrorPath</key>
  <string>$LOG_DIR/launchd.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_TARGET" >/dev/null 2>&1 || true
launchctl load "$PLIST_TARGET"

echo "LaunchAgent installed and started: $PLIST_TARGET"
