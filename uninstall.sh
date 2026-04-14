#!/usr/bin/env bash
# Pokemon Buddy for Claude — Uninstaller (macOS / Linux)
# Usage:
#   bash uninstall.sh           # remove scripts + un-patch config; keep buddy data
#   bash uninstall.sh --purge   # remove everything, including buddy/collection/stats

set -euo pipefail
CLAUDE_DIR="$HOME/.claude"
PURGE=0

for arg in "$@"; do
  case "$arg" in
    --purge|-p) PURGE=1 ;;
    -h|--help)
      sed -n '2,6p' "$0"; exit 0 ;;
  esac
done

# ── UI helpers ────────────────────────────────────────────────────────────────

bold()  { printf '\033[1m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }
yellow(){ printf '\033[33m%s\033[0m' "$*"; }
red()   { printf '\033[31m%s\033[0m' "$*"; }
cyan()  { printf '\033[36m%s\033[0m' "$*"; }

echo ""
echo "$(cyan '╔══════════════════════════════════════════════════╗')"
echo "$(cyan '║')  🎮  $(bold 'Pokemon Buddy for Claude')  —  Uninstaller    $(cyan '║')"
echo "$(cyan '╚══════════════════════════════════════════════════╝')"
echo ""

if [ ! -d "$CLAUDE_DIR" ]; then
  echo "  Nothing to remove — $CLAUDE_DIR does not exist."
  exit 0
fi

# ── Interactive stdin (safe for curl | bash) ─────────────────────────────────

if [ ! -t 0 ]; then
  if ! exec 0</dev/tty 2>/dev/null; then
    echo "  Error: No interactive terminal. Run directly: bash uninstall.sh"
    exit 1
  fi
fi

# ── Confirm ──────────────────────────────────────────────────────────────────

if [ "$PURGE" -eq 1 ]; then
  echo "  $(red 'PURGE MODE') — this will delete $(bold 'all') buddy data:"
  echo "    • Active buddy  (buddy-pokemon.md)"
  echo "    • Party roster  (pokemon-collection.md)"
  echo "    • Stats / streak (buddy-stats.md)"
  echo "    • Journey log   (buddy-log-archive.md)"
else
  echo "  Standard uninstall — engine + commands will be removed."
  echo "  Your buddy data (party, stats, journey log) will be $(bold 'kept')."
  echo "  Use $(cyan '--purge') to also delete buddy data."
fi
echo ""
printf "  Continue? [y/N]: "
read -r CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo ""
  echo "  Aborted. Nothing was changed."
  exit 0
fi

# ── Files removed in all modes (engine + commands + persona + version) ────────

ENGINE_FILES=(
  "buddy-update.py"
  "statusline-buddy.sh"
  "pokemon-persona.md"
  "buddy-version"
)
COMMAND_FILES=(
  "commands/buddy.md"
  "commands/buddy-xp.md"
  "commands/buddy-badge.md"
  "commands/buddy-card.md"
  "commands/pokemon-switch.md"
)

removed=0
for f in "${ENGINE_FILES[@]}" "${COMMAND_FILES[@]}"; do
  if [ -f "$CLAUDE_DIR/$f" ]; then
    rm -f "$CLAUDE_DIR/$f"
    removed=$((removed + 1))
  fi
done

# Remove commands dir only if empty (user may have other commands)
if [ -d "$CLAUDE_DIR/commands" ] && [ -z "$(ls -A "$CLAUDE_DIR/commands" 2>/dev/null)" ]; then
  rmdir "$CLAUDE_DIR/commands"
fi

# ── Purge-mode: also remove user buddy data ───────────────────────────────────

if [ "$PURGE" -eq 1 ]; then
  USER_DATA=(
    "buddy-pokemon.md"
    "pokemon-collection.md"
    "buddy-stats.md"
    "buddy-log-archive.md"
    "buddy-state.md"
  )
  for f in "${USER_DATA[@]}"; do
    if [ -f "$CLAUDE_DIR/$f" ]; then
      rm -f "$CLAUDE_DIR/$f"
      removed=$((removed + 1))
    fi
  done
fi

# ── Un-patch CLAUDE.md (remove the buddy block added by installer) ────────────

CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$CLAUDE_MD" ] && grep -q '@buddy-pokemon.md' "$CLAUDE_MD"; then
  backup="$CLAUDE_MD.bak.$(date +%Y%m%d%H%M%S)"
  cp "$CLAUDE_MD" "$backup"
  python3 - "$CLAUDE_MD" << 'PYSCRIPT'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
text = p.read_text(encoding='utf-8')
# Remove the installer's block: from "@buddy-pokemon.md" through the Buddy XP Auto-Award section
pattern = re.compile(
    r'\n*@buddy-pokemon\.md\s*\n.*?Never award the same task twice\.\s*',
    re.DOTALL,
)
new_text = pattern.sub('\n', text).rstrip() + '\n'
p.write_text(new_text, encoding='utf-8')
PYSCRIPT
  echo "  $(green '✓') Un-patched CLAUDE.md (backup: $(basename "$backup"))"
fi

# ── Un-patch settings.json (remove statusLine if it points to our script) ─────

SETTINGS="$CLAUDE_DIR/settings.json"
if [ -f "$SETTINGS" ]; then
  python3 - "$SETTINGS" << 'PYSCRIPT'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
try:
    data = json.loads(p.read_text(encoding='utf-8') or '{}')
except Exception:
    sys.exit(0)
sl = data.get('statusLine')
if isinstance(sl, dict) and 'statusline-buddy.sh' in str(sl.get('command', '')):
    data.pop('statusLine', None)
    p.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print("  \033[32m✓\033[0m Removed statusLine from settings.json")
PYSCRIPT
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "$(green '✓ Uninstall complete.')  Removed $removed file(s)."
if [ "$PURGE" -eq 0 ]; then
  echo "  Your buddy data was $(bold 'preserved') in $CLAUDE_DIR."
  echo "  To also delete it, re-run with $(cyan '--purge')."
fi
echo "  Restart Claude Code to clear the status bar."
echo ""
