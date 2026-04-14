#!/usr/bin/env python3
"""
Pokemon Buddy for Claude — Cross-platform uninstaller
Supports Windows, macOS, and Linux.

Usage:
  python uninstall.py           # remove scripts + un-patch config; keep buddy data
  python uninstall.py --purge   # remove everything, including buddy/collection/stats
"""

import sys
import re
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime

if sys.version_info < (3, 6):
    print("Error: Python 3.6 or newer is required.")
    sys.exit(1)

CLAUDE_DIR = Path.home() / ".claude"

ENGINE_FILES = [
    "buddy-update.py",
    "statusline-buddy.sh",
    "pokemon-persona.md",
    "buddy-version",
]
COMMAND_FILES = [
    "commands/buddy.md",
    "commands/buddy-xp.md",
    "commands/buddy-badge.md",
    "commands/buddy-card.md",
    "commands/pokemon-switch.md",
]
USER_DATA = [
    "buddy-pokemon.md",
    "pokemon-collection.md",
    "buddy-stats.md",
    "buddy-log-archive.md",
    "buddy-state.md",
]

# Unix-style ANSI colors; on Windows 10+ / Windows Terminal this works out of the box.
def _c(code, s):
    return f"\033[{code}m{s}\033[0m"

def bold(s):   return _c("1",  s)
def green(s):  return _c("32", s)
def yellow(s): return _c("33", s)
def red(s):    return _c("31", s)
def cyan(s):   return _c("36", s)

def banner():
    print()
    print(cyan("╔══════════════════════════════════════════════════╗"))
    print(cyan("║") + "  🎮  " + bold("Pokemon Buddy for Claude") + "  —  Uninstaller    " + cyan("║"))
    print(cyan("╚══════════════════════════════════════════════════╝"))
    print()

def confirm(purge: bool) -> bool:
    if purge:
        print("  " + red("PURGE MODE") + " — this will delete " + bold("all") + " buddy data:")
        print("    • Active buddy   (buddy-pokemon.md)")
        print("    • Party roster   (pokemon-collection.md)")
        print("    • Stats / streak (buddy-stats.md)")
        print("    • Journey log    (buddy-log-archive.md)")
    else:
        print("  Standard uninstall — engine + commands will be removed.")
        print("  Your buddy data (party, stats, journey log) will be " + bold("kept") + ".")
        print("  Use " + cyan("--purge") + " to also delete buddy data.")
    print()
    try:
        ans = input("  Continue? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ans in ("y", "yes")

def remove_files(files) -> int:
    removed = 0
    for rel in files:
        p = CLAUDE_DIR / rel
        if p.is_file():
            try:
                p.unlink()
                removed += 1
            except OSError as e:
                print("  " + yellow(f"Warning:") + f" could not remove {rel}: {e}")
    return removed

def cleanup_commands_dir():
    cmd_dir = CLAUDE_DIR / "commands"
    if cmd_dir.is_dir() and not any(cmd_dir.iterdir()):
        try:
            cmd_dir.rmdir()
        except OSError:
            pass

def unpatch_claude_md():
    claude_md = CLAUDE_DIR / "CLAUDE.md"
    if not claude_md.is_file():
        return
    text = claude_md.read_text(encoding="utf-8")
    if "@buddy-pokemon.md" not in text:
        return
    backup = claude_md.with_suffix(
        claude_md.suffix + ".bak." + datetime.now().strftime("%Y%m%d%H%M%S")
    )
    shutil.copy2(claude_md, backup)
    pattern = re.compile(
        r"\n*@buddy-pokemon\.md\s*\n.*?Never award the same task twice\.\s*",
        re.DOTALL,
    )
    new_text = pattern.sub("\n", text).rstrip() + "\n"
    claude_md.write_text(new_text, encoding="utf-8")
    print(f"  {green('✓')} Un-patched CLAUDE.md (backup: {backup.name})")

def unpatch_settings():
    settings = CLAUDE_DIR / "settings.json"
    if not settings.is_file():
        return
    try:
        data = json.loads(settings.read_text(encoding="utf-8") or "{}")
    except (json.JSONDecodeError, ValueError):
        return
    sl = data.get("statusLine")
    if isinstance(sl, dict) and "statusline-buddy.sh" in str(sl.get("command", "")):
        data.pop("statusLine", None)
        settings.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  {green('✓')} Removed statusLine from settings.json")

def main():
    parser = argparse.ArgumentParser(add_help=True, description=__doc__)
    parser.add_argument("--purge", "-p", action="store_true",
                        help="also delete buddy data (buddy-pokemon.md etc.)")
    args = parser.parse_args()

    # Enable ANSI on legacy Windows consoles.
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

    banner()

    if not CLAUDE_DIR.is_dir():
        print(f"  Nothing to remove — {CLAUDE_DIR} does not exist.")
        return

    if not confirm(args.purge):
        print()
        print("  Aborted. Nothing was changed.")
        return

    removed = remove_files(ENGINE_FILES + COMMAND_FILES)
    cleanup_commands_dir()

    if args.purge:
        removed += remove_files(USER_DATA)

    unpatch_claude_md()
    unpatch_settings()

    print()
    print(f"{green('✓ Uninstall complete.')}  Removed {removed} file(s).")
    if not args.purge:
        print(f"  Your buddy data was {bold('preserved')} in {CLAUDE_DIR}.")
        print(f"  To also delete it, re-run with {cyan('--purge')}.")
    print("  Restart Claude Code to clear the status bar.")
    print()

if __name__ == "__main__":
    main()
