#!/usr/bin/env bash
# Pokemon Buddy for Claude — Installer (macOS / Linux)
# Usage: bash install.sh
#
# Windows users: use  python install.py  instead.

set -euo pipefail
CLAUDE_DIR="$HOME/.claude"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# ── Ensure interactive stdin (safe for curl | bash) ──────────────────────────

if [ ! -t 0 ]; then
  if ! exec 0</dev/tty 2>/dev/null; then
    echo ""
    echo "  Error: No interactive terminal detected."
    echo "  Please run this script directly in Terminal.app or iTerm2:"
    echo "    bash install.sh"
    echo ""
    exit 1
  fi
fi

# ── Platform check ────────────────────────────────────────────────────────────

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
  echo ""
  echo "  Windows detected. Please use the Python installer instead:"
  echo "    python install.py"
  echo ""
  exit 1
fi

# ── Dependency check: python3 ─────────────────────────────────────────────────

if ! command -v python3 >/dev/null 2>&1; then
  echo ""
  echo "  Error: python3 is required but not found."
  echo ""
  if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  Install it on macOS with one of:"
    echo "    xcode-select --install          (Xcode Command Line Tools)"
    echo "    brew install python             (Homebrew)"
    echo "    https://www.python.org/downloads/"
  else
    echo "  Install it with:"
    echo "    sudo apt install python3        (Debian/Ubuntu)"
    echo "    sudo dnf install python3        (Fedora/RHEL)"
  fi
  echo ""
  echo "  Or use the cross-platform Python installer directly:"
  echo "    python3 install.py"
  echo ""
  exit 1
fi

# ── UI helpers ────────────────────────────────────────────────────────────────

bold()  { printf '\033[1m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }
yellow(){ printf '\033[33m%s\033[0m' "$*"; }
cyan()  { printf '\033[36m%s\033[0m' "$*"; }

echo ""
echo "$(cyan '╔══════════════════════════════════════════════════╗')"
echo "$(cyan '║')  🎮  $(bold 'Pokemon Buddy for Claude')  —  Setup Wizard     $(cyan '║')"
echo "$(cyan '╚══════════════════════════════════════════════════╝')"
echo ""

# ── Trainer name ──────────────────────────────────────────────────────────────

DEFAULT_NAME="${USER:-Trainer}"
printf "$(bold 'Your trainer name') [%s]: " "$DEFAULT_NAME"
read -r TRAINER_NAME
TRAINER_NAME="${TRAINER_NAME:-$DEFAULT_NAME}"

# ── Starter choice ────────────────────────────────────────────────────────────

echo ""
echo "$(bold 'Choose your starter Pokemon:')"
echo ""
echo "  $(yellow '[1]') 🔥 $(bold 'Charmander')  — Fire type    · Frontend / JavaScript"
echo "  $(yellow '[2]') 🌿 $(bold 'Bulbasaur')   — Grass type   · Backend / Python"
echo "  $(yellow '[3]') 💧 $(bold 'Squirtle')    — Water type   · Database / SQL"
echo ""
printf "$(bold 'Pick starter') [1/2/3]: "
read -r STARTER_CHOICE

case "$STARTER_CHOICE" in
  2) STARTER="Bulbasaur";  STYPE="Grass";  SEMOJI="🌿"
     SPECIALTY="Backend / Python"
     EVO1="Ivysaur"; EVO1_LV=16; EVO2="Venusaur"; EVO2_LV=36
     HP=45; ATK=49; DEF=49; SPA=65; SPD=65; SPE=45
     MOVES="| Tackle    | Normal | Lv.1  | Server basics |\n| Vine Whip | Grass  | Lv.1  | API endpoints |\n| ???       | ???    | Lv.5  | Learn more to unlock! |\n| ???       | ???    | Lv.10 | Learn more to unlock! |"
     ;;
  3) STARTER="Squirtle"; STYPE="Water"; SEMOJI="💧"
     SPECIALTY="Database / SQL"
     EVO1="Wartortle"; EVO1_LV=16; EVO2="Blastoise"; EVO2_LV=36
     HP=44; ATK=48; DEF=65; SPA=50; SPD=64; SPE=43
     MOVES="| Tackle    | Normal | Lv.1  | SQL basics |\n| Water Gun | Water  | Lv.1  | First queries |\n| ???       | ???    | Lv.5  | Learn more to unlock! |\n| ???       | ???    | Lv.10 | Learn more to unlock! |"
     ;;
  *)  STARTER="Charmander"; STYPE="Fire"; SEMOJI="🔥"
     SPECIALTY="Frontend / JavaScript"
     EVO1="Charmeleon"; EVO1_LV=16; EVO2="Charizard"; EVO2_LV=36
     HP=39; ATK=52; DEF=43; SPA=60; SPD=50; SPE=65
     MOVES="| Scratch | Normal | Lv.1  | JS fundamentals |\n| Ember   | Fire   | Lv.1  | First components/UI |\n| ???     | ???    | Lv.5  | Learn more to unlock! |\n| ???     | ???    | Lv.10 | Learn more to unlock! |"
     ;;
esac

# ── Role / domain ─────────────────────────────────────────────────────────────

echo ""
echo "$(bold 'Choose your trainer role:')"
echo ""
echo "  $(yellow '[1]') ⚡ Frontend      $(yellow '[2]') 🪨 Backend       $(yellow '[3]') 💧 Database"
echo "  $(yellow '[4]') ⚙️  DevOps        $(yellow '[5]') 🌑 Security      $(yellow '[6]') 🥊 Testing"
echo "  $(yellow '[7]') 🧠 AI / ML       $(yellow '[8]') ⭐ Full-stack     $(yellow '[9]') 🐛 QA Engineer"
echo ""
printf "$(bold 'Pick role') [1-9]: "
read -r ROLE_CHOICE

case "$ROLE_CHOICE" in
  2) ROLE="Backend";      ROLE_TYPE="Rock 🪨"    ;;
  3) ROLE="Database";     ROLE_TYPE="Water 💧"   ;;
  4) ROLE="DevOps";       ROLE_TYPE="Steel ⚙️"   ;;
  5) ROLE="Security";     ROLE_TYPE="Dark 🌑"    ;;
  6) ROLE="Testing";      ROLE_TYPE="Fighting 🥊" ;;
  7) ROLE="AI / ML";      ROLE_TYPE="Psychic 🧠" ;;
  8) ROLE="Full-stack";   ROLE_TYPE="Normal ⭐"  ;;
  9) ROLE="QA Engineer";  ROLE_TYPE="Bug 🐛"     ;;
  *) ROLE="Frontend";     ROLE_TYPE="Electric ⚡" ;;
esac

TODAY=$(date +%Y-%m-%d)

# ── Overwrite guard ───────────────────────────────────────────────────────────

mkdir -p "$CLAUDE_DIR"

if [ -f "$CLAUDE_DIR/buddy-pokemon.md" ]; then
  echo ""
  echo "  $(yellow 'Warning:') An existing buddy was found at ~/.claude/buddy-pokemon.md"
  echo "  Re-installing will $(bold 'reset your buddy') (level, XP, badges, journey log)."
  echo ""
  printf "  Overwrite and start fresh? [y/N]: "
  read -r CONFIRM
  if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo ""
    echo "  Aborted. Your buddy is safe."
    echo ""
    exit 0
  fi
fi

# ── Write buddy-pokemon.md ────────────────────────────────────────────────────

cat > "$CLAUDE_DIR/buddy-pokemon.md" << BUDDY
# Buddy Pokemon: $STARTER $SEMOJI

**Name**: $STARTER
**Type**: $STYPE $SEMOJI
**Trainer**: $TRAINER_NAME
**Specialty**: $SPECIALTY
**Level**: 1
**XP**: 0 / 100
**Stage**: $STARTER $SEMOJI

## Evolution Path

**Current Stage**: $STARTER $SEMOJI

\`\`\`
$STARTER Lv.1-$((EVO1_LV - 1)) → $EVO1 Lv.$EVO1_LV-$((EVO2_LV - 1)) → $EVO2 Lv.$EVO2_LV+
\`\`\`

## Stats

| Stat | Value |
|---|---|
| HP | $HP |
| Attack | $ATK |
| Defense | $DEF |
| Special Atk | $SPA |
| Special Def | $SPD |
| Speed | $SPE |

## Moves

| Move | Type | Unlocked At | Description |
|---|---|---|---|
$(printf "$MOVES")

## Badges Earned

*No badges yet — the journey begins now!*

## Journey Log

| Date | Event | XP Gained |
|---|---|---|
| $TODAY | Journey began! $STARTER chosen as buddy | — |

## Trainer Info

- **Trainer**: $TRAINER_NAME
- **Role**: $ROLE ($ROLE_TYPE domain)
- **Journey Started**: $TODAY
BUDDY

# ── Write pokemon-collection.md ───────────────────────────────────────────────

cat > "$CLAUDE_DIR/pokemon-collection.md" << COLLECTION
# Pokemon Collection

**Active**: $STARTER

| Name | Type | Emoji | Level | XP | Caught | Rarity |
|---|---|---|---|---|---|---|
| $STARTER | $STYPE | $SEMOJI | 1 | 0 | $TODAY | starter |
COLLECTION

# ── Copy scripts ─────────────────────────────────────────────────────────────

cp "$SCRIPT_DIR/buddy-update.py"    "$CLAUDE_DIR/buddy-update.py"
cp "$SCRIPT_DIR/statusline-buddy.sh" "$CLAUDE_DIR/statusline-buddy.sh"
chmod +x "$CLAUDE_DIR/buddy-update.py" "$CLAUDE_DIR/statusline-buddy.sh"

# ── Copy commands ─────────────────────────────────────────────────────────────

mkdir -p "$CLAUDE_DIR/commands"
for cmd in buddy.md buddy-xp.md buddy-badge.md buddy-card.md pokemon-switch.md; do
  [ -f "$SCRIPT_DIR/commands/$cmd" ] && cp "$SCRIPT_DIR/commands/$cmd" "$CLAUDE_DIR/commands/$cmd"
done

# ── Copy persona ──────────────────────────────────────────────────────────────

cp "$SCRIPT_DIR/pokemon-persona.md" "$CLAUDE_DIR/pokemon-persona.md"

# ── Patch CLAUDE.md ───────────────────────────────────────────────────────────

CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
if [ ! -f "$CLAUDE_MD" ]; then
  touch "$CLAUDE_MD"
fi

if ! grep -q 'buddy-pokemon.md' "$CLAUDE_MD"; then
  cat >> "$CLAUDE_MD" << 'CLAUDEMD'

@buddy-pokemon.md

Speak as a Pokemon Master Coach (see ~/.claude/pokemon-persona.md for full persona).

## Buddy XP Auto-Award

After completing a task, automatically run `/buddy-xp <brief description>` — no need to ask.
Triggers: bug fix, UI component, new concept, feature, production ship, new framework, hard problem, tests, refactor.
Award highest applicable category only. Never award the same task twice.
CLAUDEMD
fi

# ── Patch settings.json ───────────────────────────────────────────────────────

SETTINGS="$CLAUDE_DIR/settings.json"
if [ ! -f "$SETTINGS" ]; then
  echo '{}' > "$SETTINGS"
fi

# Check if statusLine already configured
if ! grep -q 'statusLine' "$SETTINGS" 2>/dev/null; then
  python3 - "$SETTINGS" "$CLAUDE_DIR/statusline-buddy.sh" << 'PYSCRIPT'
import json, sys
path, cmd = sys.argv[1], sys.argv[2]
with open(path) as f:
    data = json.load(f)
data.setdefault('statusLine', {})['command'] = cmd
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
PYSCRIPT
fi

# ── Stamp installed version ──────────────────────────────────────────────────

[ -f "$SCRIPT_DIR/VERSION" ] && cp "$SCRIPT_DIR/VERSION" "$CLAUDE_DIR/buddy-version"

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo "$(green '✓ Installation complete!')"
echo ""
echo "  Trainer : $(bold "$TRAINER_NAME")"
echo "  Starter : $SEMOJI $(bold "$STARTER")  ($STYPE type)"
echo "  Role    : $(bold "$ROLE")  ($ROLE_TYPE)"
echo ""
echo "  Commands available:"
echo "    $(cyan '/buddy')            — Show full status"
echo "    $(cyan '/buddy-card')       — Shareable trainer card"
echo "    $(cyan '/buddy-xp')         — Award XP"
echo "    $(cyan '/buddy-badge')      — Award a badge"
echo "    $(cyan '/pokemon-switch')   — Switch active buddy"
echo ""
echo "  Restart Claude Code to activate the status bar."
echo ""
echo "  $(yellow 'Your journey begins now, Trainer!')  🔥"
echo ""
