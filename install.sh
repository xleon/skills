#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/xleon/skills"
INSTALL_DIR=""
SKILL_MARKER="SKILL.md"

DEFAULT_DIRS=(
  "$HOME/.copilot/skills"
  "$HOME/.cursor/skills"
  "$HOME/.claude/skills"
  "$HOME/.config/opencode/skills"
)

# ── colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${CYAN}→${RESET} $*"; }
success() { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}!${RESET} $*"; }
error()   { echo -e "${RED}✗${RESET} $*" >&2; exit 1; }

usage() {
  echo -e "${BOLD}Usage:${RESET}"
  echo "  install.sh                          # interactive mode"
  echo "  install.sh --all                    # install all skills"
  echo "  install.sh <skill> [<skill>…]       # install specific skills"
  echo ""
  echo -e "${BOLD}Options:${RESET}"
  echo "  --dir <path>  Installation path (skips the prompt)"
  echo "  --list        List available skills in the repo"
  echo "  --help        Show this help"
  exit 0
}

# ── prompt install path ──────────────────────────────────────────────────────
prompt_install_dir() {
  # If the current directory contains skills, add it as an option
  local dirs=("${DEFAULT_DIRS[@]}")
  if find "$PWD" -maxdepth 2 -name "$SKILL_MARKER" -quit 2>/dev/null | grep -q .; then
    dirs=("$PWD" "${dirs[@]}")
  fi

  echo ""
  echo -e "${BOLD}Where do you want to install the skills?${RESET}"
  for i in "${!dirs[@]}"; do
    local label="${dirs[$i]}"
    [[ "$label" == "$PWD" ]] && label="$label  ${YELLOW}(current directory)${RESET}"
    printf "  %d) %s\n" "$((i+1))" "$label"
  done
  echo "   c) Custom path"
  echo ""
  read -rp "Select option [1]: " choice
  choice="${choice:-1}"

  if [[ "$choice" == "c" || "$choice" == "C" ]]; then
    read -rp "Path: " custom
    custom="${custom/#\~/$HOME}"
    INSTALL_DIR="$custom"
  elif [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#dirs[@]} )); then
    INSTALL_DIR="${dirs[$((choice-1))]}"
  else
    warn "Invalid option, using default path."
    INSTALL_DIR="${dirs[0]}"
  fi

  info "Install path: $INSTALL_DIR"
}

# ── dependencies ─────────────────────────────────────────────────────────────
require() {
  command -v "$1" &>/dev/null || error "'$1' is required but not installed."
}
require git

# ── clone repo to tmp ────────────────────────────────────────────────────────
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

fetch_repo() {
  info "Fetching skills from $REPO_URL …"
  git clone --depth 1 --quiet "$REPO_URL.git" "$TMP_DIR/repo" \
    || error "Could not clone the repository."
}

# ── list available skills ────────────────────────────────────────────────────
list_skills() {
  find "$TMP_DIR/repo" -maxdepth 2 -name "$SKILL_MARKER" \
    | sed "s|$TMP_DIR/repo/||;s|/$SKILL_MARKER||" \
    | sort
}

# ── install a skill ──────────────────────────────────────────────────────────
install_skill() {
  local skill="$1"
  local src="$TMP_DIR/repo/$skill"

  if [[ ! -f "$src/$SKILL_MARKER" ]]; then
    warn "Skill '$skill' not found in repo — skipped."
    return
  fi

  local dest="$INSTALL_DIR/$skill"
  mkdir -p "$dest"
  cp -r "$src/." "$dest/"
  success "Installed: $skill  →  $dest"
}

# ── interactive select ───────────────────────────────────────────────────────
interactive_select() {
  local skills=("$@")
  echo ""
  echo -e "${BOLD}Available skills:${RESET}"
  for i in "${!skills[@]}"; do
    printf "  %2d) %s\n" "$((i+1))" "${skills[$i]}"
  done
  echo "   a) All"
  echo ""
  read -rp "Select number(s) separated by spaces (or 'a' for all): " input

  if [[ "$input" == "a" ]]; then
    echo "${skills[@]}"
    return
  fi

  local selected=()
  for token in $input; do
    if [[ "$token" =~ ^[0-9]+$ ]] && (( token >= 1 && token <= ${#skills[@]} )); then
      selected+=("${skills[$((token-1))]}")
    else
      warn "Invalid option ignored: $token"
    fi
  done
  echo "${selected[@]}"
}

# ── main ─────────────────────────────────────────────────────────────────────
main() {
  local mode="interactive"
  local requested=()

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help|-h) usage ;;
      --all)     mode="all" ;;
      --list)    mode="list" ;;
      --dir)     shift; INSTALL_DIR="${1/#\~/$HOME}" ;;
      -*)        error "Unknown option: $1" ;;
      *)         requested+=("$1"); mode="explicit" ;;
    esac
    shift
  done

  fetch_repo
  mapfile -t available < <(list_skills)

  if [[ ${#available[@]} -eq 0 ]]; then
    error "No skills found in the repository."
  fi

  [[ -z "$INSTALL_DIR" ]] && prompt_install_dir
  mkdir -p "$INSTALL_DIR"

  case "$mode" in
    list)
      echo -e "${BOLD}Available skills in the repo:${RESET}"
      printf '  %s\n' "${available[@]}"
      ;;
    all)
      for skill in "${available[@]}"; do
        install_skill "$skill"
      done
      ;;
    explicit)
      for skill in "${requested[@]}"; do
        install_skill "$skill"
      done
      ;;
    interactive)
      read -ra to_install < <(interactive_select "${available[@]}")
      for skill in "${to_install[@]}"; do
        install_skill "$skill"
      done
      ;;
  esac

  echo ""
  success "Done. Skills installed to: $INSTALL_DIR"
}

main "$@"
