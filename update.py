#!/usr/bin/env python3
"""
Pokemon Buddy for Claude — Cross-platform updater
Supports Windows, macOS, and Linux.

Updates engine/persona/commands to the latest version WITHOUT touching
your buddy data (buddy-pokemon.md, pokemon-collection.md, buddy-log-archive.md).

Usage (from cloned repo):  python update.py
Usage (remote):            python update.py --remote
"""

import sys
import os
import stat
import shutil
import argparse
from pathlib import Path
from urllib import request, error as url_error

# ── Require Python 3.6+ ───────────────────────────────────────────────────────

if sys.version_info < (3, 6):
    print("Error: Python 3.6 or newer is required.")
    sys.exit(1)

# ── Paths & constants ─────────────────────────────────────────────────────────

CLAUDE_DIR  = Path.home() / ".claude"
SCRIPT_DIR  = Path(__file__).parent.resolve()
REPO_URL    = "https://raw.githubusercontent.com/andriar/pokemon-buddy-claude/main"

# Files to update — NEVER overwrite user data
UPDATABLE_FILES = [
    "buddy-update.py",
    "statusline-buddy.sh",
    "pokemon-persona.md",
]
UPDATABLE_COMMANDS = [
    "commands/buddy.md",
    "commands/buddy-xp.md",
    "commands/buddy-badge.md",
    "commands/pokemon-switch.md",
]

# ── Color helpers ─────────────────────────────────────────────────────────────

def _enable_win_ansi():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

_enable_win_ansi()
_use_color = sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False

def bold(s):   return f"\033[1m{s}\033[0m"  if _use_color else s
def green(s):  return f"\033[32m{s}\033[0m" if _use_color else s
def yellow(s): return f"\033[33m{s}\033[0m" if _use_color else s
def cyan(s):   return f"\033[36m{s}\033[0m" if _use_color else s
def red(s):    return f"\033[31m{s}\033[0m" if _use_color else s

# ── CLI args ──────────────────────────────────────────────────────────────────

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--remote", action="store_true",
                    help="Force download from GitHub even if local repo is present")
args, _ = parser.parse_known_args()

# ── Detect mode: local repo or remote ────────────────────────────────────────

USE_LOCAL = (not args.remote) and (SCRIPT_DIR / "VERSION").exists()

print()
print(cyan("🔄 Pokemon Buddy for Claude — Updater"))
print()

if USE_LOCAL:
    NEW_VERSION = (SCRIPT_DIR / "VERSION").read_text().strip()
    print(f"  Source : {bold('local repo')}  ({SCRIPT_DIR})")
else:
    print(f"  Source : {bold('remote')}  ({REPO_URL})")
    try:
        with request.urlopen(f"{REPO_URL}/VERSION", timeout=10) as r:
            NEW_VERSION = r.read().decode().strip()
    except url_error.URLError as e:
        print()
        print(red(f"  Error: could not reach GitHub — {e}"))
        print("  Check your internet connection or clone the repo and run locally.")
        print()
        sys.exit(1)

# ── Check installed version ───────────────────────────────────────────────────

version_file = CLAUDE_DIR / "buddy-version"
INSTALLED_VERSION = version_file.read_text().strip() if version_file.exists() else "(none)"

print(f"  Installed : {bold(INSTALLED_VERSION)}")
print(f"  Available : {bold(NEW_VERSION)}")
print()

if INSTALLED_VERSION == NEW_VERSION:
    print(green("✓ Already up to date.")  + "  Nothing to do.")
    print()
    sys.exit(0)

# ── Update files ──────────────────────────────────────────────────────────────

def mark_exec(path: Path):
    """Mark a file executable on Unix (no-op on Windows)."""
    if sys.platform != "win32":
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

def update_file(rel_path: str):
    dst = CLAUDE_DIR / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    if USE_LOCAL:
        shutil.copy2(SCRIPT_DIR / rel_path, dst)
    else:
        url = f"{REPO_URL}/{rel_path}"
        try:
            with request.urlopen(url, timeout=15) as r:
                dst.write_bytes(r.read())
        except url_error.URLError as e:
            print(f"    {red('✗')} {rel_path}  ({e})")
            return
    mark_exec(dst)
    print(f"    {green('✓')} {rel_path}")

print("  Updating files...")
print()
for f in UPDATABLE_FILES + UPDATABLE_COMMANDS:
    update_file(f)

# ── Bump installed version ────────────────────────────────────────────────────

version_file.write_text(NEW_VERSION + "\n")

# ── Done ──────────────────────────────────────────────────────────────────────

print()
print(green(f"✓ Updated {INSTALLED_VERSION} → {NEW_VERSION}"))
print()
print(f"  {yellow('Your buddy data is untouched:')}  buddy-pokemon.md, pokemon-collection.md")
print("  Restart Claude Code to apply changes.")
print()
