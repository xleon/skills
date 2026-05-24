#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.env"

mkdir -p "$STATE_DIR"

CANDIDATES_FILE="$STATE_DIR/candidates.txt"
IGNORED_FILE="$STATE_DIR/dynamic-ignored-paths.txt"
OUTPUT_FILE="$STATE_DIR/dynamic-unison-ignores.txt"

{
  cd "$SRC_ROOT"
  find . -mindepth 1 -print 2>/dev/null | sed 's#^\./##' || true

  if [[ -d "$DST_ROOT" ]]; then
    cd "$DST_ROOT"
    find . -mindepth 1 -print 2>/dev/null | sed 's#^\./##' || true
  fi
} | awk 'NF' | sort -u > "$CANDIDATES_FILE"

if [[ -s "$CANDIDATES_FILE" ]]; then
  git -C "$SRC_ROOT" check-ignore --no-index --stdin < "$CANDIDATES_FILE" | sort -u > "$IGNORED_FILE" || true
else
  : > "$IGNORED_FILE"
fi

{
  while IFS= read -r relpath; do
    [[ -n "$relpath" ]] || continue
    printf 'Path %s\n' "$relpath"
  done < "$IGNORED_FILE"
} > "$OUTPUT_FILE"

printf '%s\n' "$OUTPUT_FILE"
