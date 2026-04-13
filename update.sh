#!/usr/bin/env bash
# Pokemon Buddy for Claude — Updater (macOS / Linux)
# Updates installed files to latest version WITHOUT touching your buddy/party data.
#
# Usage (from cloned repo):   bash update.sh
# Usage (remote, one-liner):  curl -sSL https://raw.githubusercontent.com/andriar/pokemon-buddy-claude/main/update.sh | bash
#
# Windows users: use  python update.py  instead.

set -euo pipefail

# ── Platform check ────────────────────────────────────────────────────────────

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  echo ""
  echo "  Windows detected. Please use the Python updater instead:"
  echo "    python update.py"
  echo ""
  exit 1
fi

# ── Dependency check: curl ────────────────────────────────────────────────────

if ! command -v curl >/dev/null 2>&1; then
  echo ""
  echo "  Error: curl is required for remote updates but was not found."
  echo "  Clone the repo locally and run:  bash update.sh"
  echo ""
  exit 1
fi

CLAUDE_DIR="$HOME/.claude"
REPO_URL="https://raw.githubusercontent.com/andriar/pokemon-buddy-claude/main"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-update.sh}")" 2>/dev/null && pwd || echo "")"

bold()  { printf '\033[1m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }
yellow(){ printf '\033[33m%s\033[0m' "$*"; }
cyan()  { printf '\033[36m%s\033[0m' "$*"; }
red()   { printf '\033[31m%s\033[0m' "$*"; }

echo ""
echo "$(cyan '🔄 Pokemon Buddy for Claude — Updater')"
echo ""

# ── Detect mode: local repo or remote ─────────────────────────────────────────

USE_LOCAL=false
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/VERSION" ]; then
  USE_LOCAL=true
  NEW_VERSION=$(cat "$SCRIPT_DIR/VERSION" | tr -d '[:space:]')
  echo "  Source : $(bold 'local repo')  ($SCRIPT_DIR)"
else
  echo "  Source : $(bold 'remote')  ($REPO_URL)"
  NEW_VERSION=$(curl -fsSL "$REPO_URL/VERSION" | tr -d '[:space:]')
fi

# ── Check current installed version ───────────────────────────────────────────

INSTALLED_VERSION="(none)"
if [ -f "$CLAUDE_DIR/buddy-version" ]; then
  INSTALLED_VERSION=$(cat "$CLAUDE_DIR/buddy-version" | tr -d '[:space:]')
fi

echo "  Installed : $(bold "$INSTALLED_VERSION")"
echo "  Available : $(bold "$NEW_VERSION")"
echo ""

if [ "$INSTALLED_VERSION" = "$NEW_VERSION" ]; then
  echo "$(green '✓ Already up to date.')  Nothing to do."
  echo ""
  exit 0
fi

# ── Files to update (NEVER touch user data files) ────────────────────────────
#
# SAFE to overwrite:   buddy-update.py, statusline-buddy.sh, pokemon-persona.md, commands/
# NEVER overwrite:     buddy-pokemon.md, pokemon-collection.md, buddy-log-archive.md

UPDATABLE_FILES=(
  "buddy-update.py"
  "statusline-buddy.sh"
  "pokemon-persona.md"
)

UPDATABLE_COMMANDS=(
  "commands/buddy.md"
  "commands/buddy-xp.md"
  "commands/buddy-badge.md"
  "commands/pokemon-switch.md"
)

echo "  Updating files..."
echo ""

copy_file() {
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ "$USE_LOCAL" = true ]; then
    cp "$SCRIPT_DIR/$src" "$dst"
  else
    curl -fsSL "$REPO_URL/$src" -o "$dst"
  fi
  echo "    $(green '✓') $src"
}

for f in "${UPDATABLE_FILES[@]}";    do copy_file "$f" "$CLAUDE_DIR/$f"; done
for f in "${UPDATABLE_COMMANDS[@]}"; do copy_file "$f" "$CLAUDE_DIR/$f"; done

chmod +x "$CLAUDE_DIR/buddy-update.py" "$CLAUDE_DIR/statusline-buddy.sh"

# ── Bump installed version ────────────────────────────────────────────────────

echo "$NEW_VERSION" > "$CLAUDE_DIR/buddy-version"

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo "$(green "✓ Updated $INSTALLED_VERSION → $NEW_VERSION")"
echo ""
echo "  $(yellow 'Your buddy data is untouched:')  buddy-pokemon.md, pokemon-collection.md"
echo "  Restart Claude Code to apply changes."
echo ""
