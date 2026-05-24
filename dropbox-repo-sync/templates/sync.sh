#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.env"

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

mkdir -p "$STATE_DIR" "$LOG_DIR" "$DST_ROOT"

LOCK_DIR="$STATE_DIR/lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  printf 'Another sync is already running, skipping this cycle.\n'
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
LOG_FILE="$LOG_DIR/sync-$TIMESTAMP.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting sync" | tee -a "$LOG_FILE"

if ! command -v unison >/dev/null 2>&1; then
  echo "Error: unison is not installed. Install with: brew install unison" | tee -a "$LOG_FILE"
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Error: git is not installed or not in PATH." | tee -a "$LOG_FILE"
  exit 1
fi

DYNAMIC_IGNORE_FILE="$($SCRIPT_DIR/build-dynamic-ignores.sh)"

FIXED_EXCLUDES=()
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -n "$line" ]] || continue
  FIXED_EXCLUDES+=("$line")
done < "$SCRIPT_DIR/fixed-excludes.txt"

DYNAMIC_EXCLUDES=()
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -n "$line" ]] || continue
  DYNAMIC_EXCLUDES+=("$line")
done < "$DYNAMIC_IGNORE_FILE"

UNISON_CMD=(
  unison
  "$SRC_ROOT"
  "$DST_ROOT"
  -ui text
  -batch
  -auto
  -copyonconflict
  -times
  -perms 0
)

if [[ "$DRY_RUN" -eq 1 ]]; then
  # This Unison build has no -dryrun flag; block all mutations for a safe preview run.
  UNISON_CMD+=(
    -noupdate "$SRC_ROOT"
    -noupdate "$DST_ROOT"
    -nocreation "$SRC_ROOT"
    -nocreation "$DST_ROOT"
    -nodeletion "$SRC_ROOT"
    -nodeletion "$DST_ROOT"
  )
fi

for relpath in "${FIXED_EXCLUDES[@]}"; do
  [[ -n "$relpath" ]] || continue
  UNISON_CMD+=(-ignore "Path $relpath")
done

for rule in "${DYNAMIC_EXCLUDES[@]}"; do
  [[ -n "$rule" ]] || continue
  UNISON_CMD+=(-ignore "$rule")
done

{
  printf 'Source: %s\n' "$SRC_ROOT"
  printf 'Destination: %s\n' "$DST_ROOT"
  printf 'Dry-run: %s\n' "$DRY_RUN"
  printf 'Fixed excludes: %s\n' "${#FIXED_EXCLUDES[@]}"
  printf 'Dynamic excludes from .gitignore: %s\n' "${#DYNAMIC_EXCLUDES[@]}"
  printf 'Command: '
  printf '%q ' "${UNISON_CMD[@]}"
  printf '\n\n'
} >> "$LOG_FILE"

"${UNISON_CMD[@]}" | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

if [[ "$EXIT_CODE" -eq 0 ]]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sync finished successfully" | tee -a "$LOG_FILE"
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sync failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
fi

exit "$EXIT_CODE"
