#!/usr/bin/env python3
"""
Pokemon Buddy for Claude — Cross-platform installer
Supports Windows, macOS, and Linux.

Usage:
  python install.py          # Windows / macOS / Linux
  python3 install.py         # macOS / Linux alternative
"""

import sys
import os
import json
import shutil
import stat
from pathlib import Path
from datetime import date

# ── Require Python 3.6+ ───────────────────────────────────────────────────────

if sys.version_info < (3, 6):
    print("Error: Python 3.6 or newer is required.")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────

CLAUDE_DIR  = Path.home() / ".claude"
SCRIPT_DIR  = Path(__file__).parent.resolve()
TODAY       = date.today().strftime("%Y-%m-%d")

# ── Color helpers (ANSI; works on macOS, Linux, Windows 10+) ──────────────────

def _enable_win_ansi():
    """Enable ANSI escape codes on Windows (no-op on other platforms)."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

_enable_win_ansi()

# ── Windows UTF-8 stdout (emoji safe) ────────────────────────────────────────
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_use_color = sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False

def bold(s):   return f"\033[1m{s}\033[0m"  if _use_color else s
def green(s):  return f"\033[32m{s}\033[0m" if _use_color else s
def yellow(s): return f"\033[33m{s}\033[0m" if _use_color else s
def cyan(s):   return f"\033[36m{s}\033[0m" if _use_color else s

# ── Banner ────────────────────────────────────────────────────────────────────

print()
print(cyan("╔══════════════════════════════════════════════════╗"))
print(cyan("║") + f"  🎮  {bold('Pokemon Buddy for Claude')}  —  Setup Wizard     " + cyan("║"))
print(cyan("╚══════════════════════════════════════════════════╝"))
print()

# ── Trainer name ──────────────────────────────────────────────────────────────

default_name = os.environ.get("USER") or os.environ.get("USERNAME") or "Trainer"
trainer_input = input(f"{bold('Your trainer name')} [{default_name}]: ").strip()
TRAINER_NAME = trainer_input if trainer_input else default_name

# ── Starter choice ────────────────────────────────────────────────────────────

print()
print(bold("Choose your starter Pokemon:"))
print()
print(f"  {yellow('[1]')} 🔥 {bold('Charmander')}  — Fire type    · Frontend / JavaScript")
print(f"  {yellow('[2]')} 🌿 {bold('Bulbasaur')}   — Grass type   · Backend / Python")
print(f"  {yellow('[3]')} 💧 {bold('Squirtle')}    — Water type   · Database / SQL")
print()
starter_choice = input(f"{bold('Pick starter')} [1/2/3]: ").strip()

STARTERS = {
    "2": dict(
        name="Bulbasaur",   stype="Grass",  semoji="🌿",
        specialty="Backend / Python",
        evo1="Ivysaur",   evo1_lv=16,
        evo2="Venusaur",  evo2_lv=36,
        hp=45, atk=49, defense=49, spa=65, spd=65, spe=45,
        moves=[
            ("Tackle",    "Normal", "Lv.1",  "Server basics"),
            ("Vine Whip", "Grass",  "Lv.1",  "API endpoints"),
            ("???",       "???",    "Lv.5",  "Learn more to unlock!"),
            ("???",       "???",    "Lv.10", "Learn more to unlock!"),
        ],
    ),
    "3": dict(
        name="Squirtle",  stype="Water",  semoji="💧",
        specialty="Database / SQL",
        evo1="Wartortle", evo1_lv=16,
        evo2="Blastoise", evo2_lv=36,
        hp=44, atk=48, defense=65, spa=50, spd=64, spe=43,
        moves=[
            ("Tackle",    "Normal", "Lv.1",  "SQL basics"),
            ("Water Gun", "Water",  "Lv.1",  "First queries"),
            ("???",       "???",    "Lv.5",  "Learn more to unlock!"),
            ("???",       "???",    "Lv.10", "Learn more to unlock!"),
        ],
    ),
}
# Default to Charmander for any other input
STARTERS["1"] = dict(
    name="Charmander", stype="Fire",  semoji="🔥",
    specialty="Frontend / JavaScript",
    evo1="Charmeleon", evo1_lv=16,
    evo2="Charizard",  evo2_lv=36,
    hp=39, atk=52, defense=43, spa=60, spd=50, spe=65,
    moves=[
        ("Scratch", "Normal", "Lv.1",  "JS fundamentals"),
        ("Ember",   "Fire",   "Lv.1",  "First components/UI"),
        ("???",     "???",    "Lv.5",  "Learn more to unlock!"),
        ("???",     "???",    "Lv.10", "Learn more to unlock!"),
    ],
)

s = STARTERS.get(starter_choice, STARTERS["1"])
if starter_choice not in STARTERS:
    print(f"  (defaulting to {bold('Charmander')})")
STARTER   = s["name"]
STYPE     = s["stype"]
SEMOJI    = s["semoji"]
SPECIALTY = s["specialty"]
EVO1      = s["evo1"];  EVO1_LV = s["evo1_lv"]
EVO2      = s["evo2"];  EVO2_LV = s["evo2_lv"]
HP = s["hp"]; ATK = s["atk"]; DEF = s["defense"]
SPA = s["spa"]; SPD = s["spd"]; SPE = s["spe"]
MOVES_ROWS = "\n".join(
    f"| {m[0]:<9} | {m[1]:<6} | {m[2]:<5} | {m[3]} |"
    for m in s["moves"]
)

# ── Role / domain ─────────────────────────────────────────────────────────────

print()
print(bold("Choose your trainer role:"))
print()
print(f"  {yellow('[1]')} ⚡ Frontend      {yellow('[2]')} 🪨 Backend       {yellow('[3]')} 💧 Database")
print(f"  {yellow('[4]')} ⚙️  DevOps        {yellow('[5]')} 🌑 Security      {yellow('[6]')} 🥊 Testing")
print(f"  {yellow('[7]')} 🧠 AI / ML       {yellow('[8]')} ⭐ Full-stack     {yellow('[9]')} 🐛 QA Engineer")
print()
role_choice = input(f"{bold('Pick role')} [1-9]: ").strip()

ROLES = {
    "2": ("Backend",     "Rock 🪨"),
    "3": ("Database",    "Water 💧"),
    "4": ("DevOps",      "Steel ⚙️"),
    "5": ("Security",    "Dark 🌑"),
    "6": ("Testing",     "Fighting 🥊"),
    "7": ("AI / ML",     "Psychic 🧠"),
    "8": ("Full-stack",  "Normal ⭐"),
    "9": ("QA Engineer", "Bug 🐛"),
}
ROLE, ROLE_TYPE = ROLES.get(role_choice, ("Frontend", "Electric ⚡"))
if role_choice not in ROLES:
    print(f"  (defaulting to {bold('Frontend')})")

# ── Create ~/.claude ──────────────────────────────────────────────────────────

CLAUDE_DIR.mkdir(parents=True, exist_ok=True)

# ── Overwrite guard ───────────────────────────────────────────────────────────

if (CLAUDE_DIR / "buddy-pokemon.md").exists():
    print()
    print(f"  {yellow('Warning:')} An existing buddy was found at ~/.claude/buddy-pokemon.md")
    print(f"  Re-installing will {bold('reset your buddy')} (level, XP, badges, journey log).")
    print()
    confirm = input("  Overwrite and start fresh? [y/N]: ").strip().lower()
    if confirm != "y":
        print()
        print("  Aborted. Your buddy is safe.")
        print()
        sys.exit(0)

# ── Write buddy-pokemon.md ────────────────────────────────────────────────────

buddy_md = f"""\
# Buddy Pokemon: {STARTER} {SEMOJI}

**Name**: {STARTER}
**Type**: {STYPE} {SEMOJI}
**Trainer**: {TRAINER_NAME}
**Specialty**: {SPECIALTY}
**Level**: 1
**XP**: 0 / 100
**Stage**: {STARTER} {SEMOJI}

## Evolution Path

**Current Stage**: {STARTER} {SEMOJI}

```
{STARTER} Lv.1-{EVO1_LV - 1} → {EVO1} Lv.{EVO1_LV}-{EVO2_LV - 1} → {EVO2} Lv.{EVO2_LV}+
```

## Stats

| Stat | Value |
|---|---|
| HP | {HP} |
| Attack | {ATK} |
| Defense | {DEF} |
| Special Atk | {SPA} |
| Special Def | {SPD} |
| Speed | {SPE} |

## Moves

| Move | Type | Unlocked At | Description |
|---|---|---|---|
{MOVES_ROWS}

## Badges Earned

*No badges yet — the journey begins now!*

## Journey Log

| Date | Event | XP Gained |
|---|---|---|
| {TODAY} | Journey began! {STARTER} chosen as buddy | — |

## Trainer Info

- **Trainer**: {TRAINER_NAME}
- **Role**: {ROLE} ({ROLE_TYPE} domain)
- **Journey Started**: {TODAY}
"""

(CLAUDE_DIR / "buddy-pokemon.md").write_text(buddy_md, encoding="utf-8")

# ── Write pokemon-collection.md ───────────────────────────────────────────────

collection_md = f"""\
# Pokemon Collection

**Active**: {STARTER}

| Name | Type | Emoji | Level | XP | Caught | Rarity |
|---|---|---|---|---|---|---|
| {STARTER} | {STYPE} | {SEMOJI} | 1 | 0 | {TODAY} | starter |
"""

(CLAUDE_DIR / "pokemon-collection.md").write_text(collection_md, encoding="utf-8")

# ── Copy scripts ──────────────────────────────────────────────────────────────

def copy_exec(src_name, dst_name=None):
    """Copy a file and mark it executable on Unix."""
    dst_name = dst_name or src_name
    src = SCRIPT_DIR / src_name
    dst = CLAUDE_DIR / dst_name
    shutil.copy2(src, dst)
    if sys.platform != "win32":
        dst.chmod(dst.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

copy_exec("buddy-update.py")
copy_exec("statusline-buddy.sh")

# ── Copy commands ─────────────────────────────────────────────────────────────

(CLAUDE_DIR / "commands").mkdir(exist_ok=True)
for cmd in ("buddy.md", "buddy-xp.md", "buddy-badge.md", "buddy-card.md", "pokemon-switch.md"):
    src = SCRIPT_DIR / "commands" / cmd
    if src.exists():
        shutil.copy2(src, CLAUDE_DIR / "commands" / cmd)

# ── Copy persona ──────────────────────────────────────────────────────────────

copy_exec("pokemon-persona.md")

# ── Patch CLAUDE.md ───────────────────────────────────────────────────────────

claude_md_path = CLAUDE_DIR / "CLAUDE.md"
if not claude_md_path.exists():
    claude_md_path.write_text("", encoding="utf-8")

existing = claude_md_path.read_text(encoding="utf-8")
if "buddy-pokemon.md" not in existing:
    patch = """
@buddy-pokemon.md

Speak as a Pokemon Master Coach (see ~/.claude/pokemon-persona.md for full persona).

## Buddy XP Auto-Award

After completing a task, automatically run `/buddy-xp <brief description>` — no need to ask.
Triggers: bug fix, UI component, new concept, feature, production ship, new framework, hard problem, tests, refactor.
Award highest applicable category only. Never award the same task twice.
"""
    claude_md_path.write_text(existing + patch, encoding="utf-8")

# ── Patch settings.json ───────────────────────────────────────────────────────

settings_path = CLAUDE_DIR / "settings.json"
if not settings_path.exists():
    settings_path.write_text("{}", encoding="utf-8")

try:
    data = json.loads(settings_path.read_text(encoding="utf-8"))
except json.JSONDecodeError:
    data = {}

# Always write correct statusLine format (type + command)
if sys.platform == "win32":
    cmd = f'python "{CLAUDE_DIR / "buddy-update.py"}" statusline'
else:
    cmd = str(CLAUDE_DIR / "statusline-buddy.sh")
data["statusLine"] = {"type": "command", "command": cmd}
settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

# ── Stamp installed version ──────────────────────────────────────────────────

version_src = SCRIPT_DIR / "VERSION"
if version_src.exists():
    shutil.copy2(version_src, CLAUDE_DIR / "buddy-version")

# ── Done ──────────────────────────────────────────────────────────────────────

print()
print(green("✓ Installation complete!"))
print()
print(f"  Trainer : {bold(TRAINER_NAME)}")
print(f"  Starter : {SEMOJI} {bold(STARTER)}  ({STYPE} type)")
print(f"  Role    : {bold(ROLE)}  ({ROLE_TYPE})")
print()
print("  Commands available:")
print(f"    {cyan('/buddy')}            — Show full status")
print(f"    {cyan('/buddy-card')}       — Shareable trainer card")
print(f"    {cyan('/buddy-xp')}         — Award XP")
print(f"    {cyan('/buddy-badge')}      — Award a badge")
print(f"    {cyan('/pokemon-switch')}   — Switch active buddy")
print()
print("  Restart Claude Code to activate the status bar.")
print()
print(f"  {yellow('Your journey begins now, Trainer!')}  🔥")
print()
