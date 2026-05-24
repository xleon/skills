#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <repo-path> <destination-path> [launchagent-label]"
  exit 1
fi

REPO_ROOT="$(cd "$1" && pwd)"
DEST_ROOT="$2"
LAUNCH_LABEL="${3:-com.user.$(basename "$REPO_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9.-' '-')-folder-sync}"

RAW_FOLDER_NAME="$(basename "$REPO_ROOT")"
SANITIZED_FOLDER_NAME="$(printf '%s' "$RAW_FOLDER_NAME" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-')"
SANITIZED_FOLDER_NAME="${SANITIZED_FOLDER_NAME#-}"
SANITIZED_FOLDER_NAME="${SANITIZED_FOLDER_NAME%-}"
if [[ -z "$SANITIZED_FOLDER_NAME" ]]; then
  SANITIZED_FOLDER_NAME="repo"
fi

SHORT_FOLDER_NAME="${SANITIZED_FOLDER_NAME:0:20}"
SHORT_FOLDER_NAME="${SHORT_FOLDER_NAME%-}"
if [[ -z "$SHORT_FOLDER_NAME" ]]; then
  SHORT_FOLDER_NAME="repo"
fi

LAUNCHER_NAME="repo-folder-sync-$SHORT_FOLDER_NAME"

SKILL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SKILL_ROOT/templates"
TARGET_DIR="$REPO_ROOT/.tools/repo-folder-sync"

if [[ ! -d "$REPO_ROOT/.git" ]]; then
  echo "Error: $REPO_ROOT does not look like a git repository (.git not found)."
  exit 1
fi

mkdir -p "$TARGET_DIR"

ensure_gitignore_entry() {
  local entry="$1"
  local gitignore_path="$REPO_ROOT/.gitignore"

  touch "$gitignore_path"
  if ! grep -Fxq "$entry" "$gitignore_path"; then
    printf '%s\n' "$entry" >> "$gitignore_path"
  fi
}

copy_template() {
  local src="$1"
  local dst="$2"
  sed \
    -e "s#__REPO_ROOT__#$REPO_ROOT#g" \
    -e "s#__DEST_ROOT__#$DEST_ROOT#g" \
    -e "s#__LAUNCH_LABEL__#$LAUNCH_LABEL#g" \
    -e "s#__LAUNCHER_NAME__#$LAUNCHER_NAME#g" \
    "$src" > "$dst"
}

copy_template "$TEMPLATES_DIR/config.env.template" "$TARGET_DIR/config.env"
copy_template "$TEMPLATES_DIR/fixed-excludes.txt" "$TARGET_DIR/fixed-excludes.txt"
copy_template "$TEMPLATES_DIR/build-dynamic-ignores.sh" "$TARGET_DIR/build-dynamic-ignores.sh"
copy_template "$TEMPLATES_DIR/sync.sh" "$TARGET_DIR/sync.sh"
copy_template "$TEMPLATES_DIR/watch.sh" "$TARGET_DIR/watch.sh"
copy_template "$TEMPLATES_DIR/repo-folder-sync" "$TARGET_DIR/$LAUNCHER_NAME"
copy_template "$TEMPLATES_DIR/status.sh" "$TARGET_DIR/status.sh"
copy_template "$TEMPLATES_DIR/install-launchagent.sh" "$TARGET_DIR/install-launchagent.sh"
copy_template "$TEMPLATES_DIR/uninstall-launchagent.sh" "$TARGET_DIR/uninstall-launchagent.sh"
copy_template "$TEMPLATES_DIR/README.md" "$TARGET_DIR/README.md"
copy_template "$TEMPLATES_DIR/com.user.repo-folder-sync.plist.template" "$TARGET_DIR/com.user.repo-folder-sync.plist.template"

chmod +x "$TARGET_DIR"/*.sh
chmod +x "$TARGET_DIR/$LAUNCHER_NAME"

# Keep runtime artifacts out of git by default.
ensure_gitignore_entry ".tools/repo-folder-sync/state/"
ensure_gitignore_entry ".tools/repo-folder-sync/logs/"

echo "Installed sync toolkit at: $TARGET_DIR"
echo "LaunchAgent label: $LAUNCH_LABEL"
echo "Launcher name: $LAUNCHER_NAME"
echo "Updated .gitignore with runtime paths for .tools/repo-folder-sync"
echo "Next steps:"
echo "  1) brew install unison fswatch"
echo "  2) cd $REPO_ROOT && .tools/repo-folder-sync/sync.sh --dry-run"
echo "  3) cd $REPO_ROOT && .tools/repo-folder-sync/status.sh"
echo "  4) cd $REPO_ROOT && .tools/repo-folder-sync/install-launchagent.sh"
echo "  5) (optional) disable auto-sync: cd $REPO_ROOT && .tools/repo-folder-sync/uninstall-launchagent.sh"
