#!/usr/bin/env bash
set -euo pipefail

# When run via bash <(curl ...) stdin is not the terminal — fix it
[[ ! -t 0 ]] && exec </dev/tty

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
RED='\033[0;31m';    GREEN='\033[0;32m';    YELLOW='\033[1;33m'
CYAN='\033[0;36m';   MAGENTA='\033[0;35m';  BLUE='\033[0;34m'
BOLD='\033[1m';      DIM='\033[2m';          RESET='\033[0m'

info()    { echo -e "${CYAN}🔹 →${RESET}  $*"; }
success() { echo -e "${GREEN}✅${RESET}  $*"; }
warn()    { echo -e "${YELLOW}⚠️  ${RESET}  $*"; }
error()   { echo -e "${RED}❌${RESET}  $*" >&2; exit 1; }
divider() { echo -e "${DIM}  ────────────────────────────────────────${RESET}"; }
banner()  {
  echo ""
  echo -e "${BOLD}${MAGENTA}  ╭──────────────────────────────────────╮${RESET}"
  echo -e "${BOLD}${MAGENTA}  │${RESET}   ${BOLD}${CYAN}🚀  Skills Installer  ✨${RESET}           ${BOLD}${MAGENTA}│${RESET}"
  echo -e "${BOLD}${MAGENTA}  ╰──────────────────────────────────────╯${RESET}"
  echo ""
}

usage() {
  echo ""
  echo -e "  ${BOLD}${CYAN}Usage:${RESET}"
  echo -e "  ${BOLD}install.sh${RESET}                          ${DIM}# interactive mode${RESET}"
  echo -e "  ${BOLD}install.sh ${YELLOW}--all${RESET}                    ${DIM}# install all skills${RESET}"
  echo -e "  ${BOLD}install.sh ${MAGENTA}<skill> [<skill>…]${RESET}       ${DIM}# install specific skills${RESET}"
  echo ""
  echo -e "  ${BOLD}${CYAN}Options:${RESET}"
  echo -e "  ${YELLOW}--dir${RESET} ${MAGENTA}<path>${RESET}  Installation path (skips the prompt)"
  echo -e "  ${YELLOW}--list${RESET}        List available skills in the repo"
  echo -e "  ${YELLOW}--help${RESET}        Show this help"
  echo ""
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
  divider
  echo -e "  ${BOLD}${CYAN}📂  Where do you want to install the skills?${RESET}"
  divider
  echo ""
  for i in "${!dirs[@]}"; do
    local label="${dirs[$i]}"
    [[ "$label" == "$PWD" ]] && label="$label  ${YELLOW}(current directory)${RESET}"
    echo -e "  ${CYAN}$((i+1)))${RESET}  $label"
  done
  echo -e "  ${CYAN}c)${RESET}  Custom path"
  echo ""
  read -rp "$(echo -e "  ${BOLD}Select option${RESET} ${DIM}[1]${RESET}: ")" choice
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

skill_description() {
  local skill="$1"
  local file="$TMP_DIR/repo/$skill/$SKILL_MARKER"
  local desc=""

  [[ -f "$file" ]] || {
    echo "No description available."
    return
  }

  # Read YAML frontmatter description from SKILL.md when present.
  desc=$(awk '
    $0=="---" {
      if (!frontmatter_started) {
        frontmatter_started=1
        next
      }
      exit
    }
    frontmatter_started && /^[[:space:]]*description:[[:space:]]*/ {
      line=$0
      sub(/^[[:space:]]*description:[[:space:]]*/, "", line)
      gsub(/^"|"$/, "", line)
      print line
      exit
    }
  ' "$file")

  if [[ -z "$desc" ]]; then
    echo "No description available."
  else
    echo "$desc"
  fi
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
SELECTED_SKILLS=()

interactive_select() {
  SELECTED_SKILLS=()
  local skills=("$@")
  echo ""
  divider
  echo -e "  ${BOLD}${CYAN}📦  Available skills:${RESET}"
  divider
  echo ""
  for i in "${!skills[@]}"; do
    local skill="${skills[$i]}"
    local desc
    desc="$(skill_description "$skill")"
    echo -e "  ${CYAN}$((i+1)))${RESET}  ${BOLD}${skill}${RESET} ${DIM}- ${desc}${RESET}"
  done
  echo -e "  ${CYAN}a)${RESET}  ${BOLD}All${RESET}"
  echo ""
  read -rp "$(echo -e "  ${BOLD}Select number(s)${RESET} ${DIM}separated by spaces (or 'a' for all)${RESET}: ")" input

  if [[ "$input" == "a" ]]; then
    SELECTED_SKILLS=("${skills[@]}")
    return
  fi

  for token in $input; do
    if [[ "$token" =~ ^[0-9]+$ ]] && (( token >= 1 && token <= ${#skills[@]} )); then
      SELECTED_SKILLS+=("${skills[$((token-1))]}")
    else
      warn "Invalid option ignored: $token"
    fi
  done
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

  banner
  fetch_repo
  available=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && available+=("$line")
  done < <(list_skills)

  if [[ ${#available[@]} -eq 0 ]]; then
    error "No skills found in the repository."
  fi

  if [[ "$mode" == "list" ]]; then
    echo ""
    divider
    echo -e "  ${BOLD}${CYAN}📦  Available skills in the repo:${RESET}"
    divider
    echo ""
    for skill in "${available[@]}"; do
      local desc
      desc="$(skill_description "$skill")"
      echo -e "  ${CYAN}•${RESET}  ${BOLD}${skill}${RESET} ${DIM}- ${desc}${RESET}"
    done
    echo ""
    return
  fi

  [[ -z "$INSTALL_DIR" ]] && prompt_install_dir
  mkdir -p "$INSTALL_DIR"

  case "$mode" in
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
      interactive_select "${available[@]}"
      if [[ ${#SELECTED_SKILLS[@]} -gt 0 ]]; then
        for skill in "${SELECTED_SKILLS[@]}"; do
          install_skill "$skill"
        done
      fi
      ;;
  esac

  echo ""
  divider
  success "${BOLD}Done!${RESET}  Skills installed in: ${CYAN}${INSTALL_DIR}${RESET}  🎉"
  divider
  echo ""
}

main "$@"
