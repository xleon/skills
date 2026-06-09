#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <repo-path> <dropbox-path> [launchagent-label]"
  exit 1
fi

REPO_ROOT="$(cd "$1" && pwd)"
DROPBOX_ROOT="$2"
LAUNCH_LABEL="${3:-com.user.$(basename "$REPO_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9.-' '-')-dropbox-sync}"

SKILL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SKILL_ROOT/templates"
TARGET_DIR="$REPO_ROOT/.tools/dropbox-sync"

if [[ ! -d "$REPO_ROOT/.git" ]]; then
  echo "Error: $REPO_ROOT does not look like a git repository (.git not found)."
  exit 1
fi

mkdir -p "$TARGET_DIR"

copy_template() {
  local src="$1"
  local dst="$2"
  sed \
    -e "s#__REPO_ROOT__#$REPO_ROOT#g" \
    -e "s#__DROPBOX_ROOT__#$DROPBOX_ROOT#g" \
    -e "s#__LAUNCH_LABEL__#$LAUNCH_LABEL#g" \
    "$src" > "$dst"
}

copy_template "$TEMPLATES_DIR/config.env.template" "$TARGET_DIR/config.env"
copy_template "$TEMPLATES_DIR/fixed-excludes.txt" "$TARGET_DIR/fixed-excludes.txt"
copy_template "$TEMPLATES_DIR/build-dynamic-ignores.sh" "$TARGET_DIR/build-dynamic-ignores.sh"
copy_template "$TEMPLATES_DIR/sync.sh" "$TARGET_DIR/sync.sh"
copy_template "$TEMPLATES_DIR/watch.sh" "$TARGET_DIR/watch.sh"
copy_template "$TEMPLATES_DIR/status.sh" "$TARGET_DIR/status.sh"
copy_template "$TEMPLATES_DIR/install-launchagent.sh" "$TARGET_DIR/install-launchagent.sh"
copy_template "$TEMPLATES_DIR/uninstall-launchagent.sh" "$TARGET_DIR/uninstall-launchagent.sh"
copy_template "$TEMPLATES_DIR/README.md" "$TARGET_DIR/README.md"
copy_template "$TEMPLATES_DIR/com.user.repo-dropbox-sync.plist.template" "$TARGET_DIR/com.user.repo-dropbox-sync.plist.template"

chmod +x "$TARGET_DIR"/*.sh

echo "Installed sync toolkit at: $TARGET_DIR"
echo "LaunchAgent label: $LAUNCH_LABEL"
echo "Next steps:"
echo "  1) brew install unison fswatch"
echo "  2) cd $REPO_ROOT && .tools/dropbox-sync/sync.sh --dry-run"
echo "  3) cd $REPO_ROOT && .tools/dropbox-sync/status.sh"
echo "  4) cd $REPO_ROOT && .tools/dropbox-sync/install-launchagent.sh"
