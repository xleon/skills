#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$SCRIPT_DIR/config.env"

mkdir -p "$STATE_DIR"

CANDIDATES_FILE="$STATE_DIR/candidates.txt"
IGNORED_FILE="$STATE_DIR/dynamic-ignored-paths.txt"
OUTPUT_FILE="$STATE_DIR/dynamic-unison-ignores.txt"

# Check only top-level entries (.venv, __pycache__, .DS_Store, etc.) instead
# of every file inside ignored trees — avoids "Argument list too long" in
# unison when .venv/ contains thousands of files.
cd "$SRC_ROOT"
> "$IGNORED_FILE"
for entry in * .*; do
  [[ "$entry" == "." || "$entry" == ".." ]] && continue
  git check-ignore -q "$entry" 2>/dev/null && echo "$entry" >> "$IGNORED_FILE"
done
sort -u -o "$IGNORED_FILE" "$IGNORED_FILE"
: > "$CANDIDATES_FILE"

{
  while IFS= read -r relpath; do
    [[ -n "$relpath" ]] || continue
    printf 'Path %s\n' "$relpath"
  done < "$IGNORED_FILE"
} > "$OUTPUT_FILE"

printf '%s\n' "$OUTPUT_FILE"
