#!/usr/bin/env python3
"""Migrate a legacy v1.x Pokémon Buddy install to the v2.x plugin.

State files (~/.claude/buddy-*.md etc.) stay in place — they're user data
and the plugin reads the same paths. This script only removes v1.x
*install artifacts*: the engine script, statusline wrapper, persona file,
legacy slash commands, and CLAUDE.md import line.
"""
import json, os, sys, shutil
from pathlib import Path

if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')

HOME       = Path.home()
CLAUDE_DIR = HOME / '.claude'

LEGACY_FILES = [
    CLAUDE_DIR / 'buddy-update.py',
    CLAUDE_DIR / 'statusline-buddy.sh',
    CLAUDE_DIR / 'pokemon-persona.md',
    CLAUDE_DIR / 'buddy-pokemon.md.backup',
]
LEGACY_COMMANDS = [
    CLAUDE_DIR / 'commands' / 'buddy.md',
    CLAUDE_DIR / 'commands' / 'buddy-xp.md',
    CLAUDE_DIR / 'commands' / 'buddy-card.md',
    CLAUDE_DIR / 'commands' / 'buddy-badge.md',
    CLAUDE_DIR / 'commands' / 'pokemon-switch.md',
]
BACKUP_DIR = CLAUDE_DIR / 'buddy-v1-backup'
CLAUDE_MD  = CLAUDE_DIR / 'CLAUDE.md'
SETTINGS   = CLAUDE_DIR / 'settings.json'

STATE_FILES = [
    ('Buddy card',        CLAUDE_DIR / 'buddy-pokemon.md'),
    ('Collection (Pokédex)', CLAUDE_DIR / 'pokemon-collection.md'),
    ('Trainer stats',     CLAUDE_DIR / 'buddy-stats.md'),
]


def confirm(prompt, default_yes=True):
    suffix = ' [Y/n] ' if default_yes else ' [y/N] '
    try: ans = input(prompt + suffix).strip().lower()
    except EOFError: ans = ''
    if not ans: return default_yes
    return ans.startswith('y')


def detect_legacy():
    return (CLAUDE_DIR / 'buddy-update.py').exists()


def summarize_state():
    print()
    print('  State files found (will be preserved):')
    for label, p in STATE_FILES:
        mark = '✓' if p.exists() else '–'
        print(f'    {mark} {label:22s}  {p}')
    print()


def clean_claude_md():
    if not CLAUDE_MD.exists(): return False
    content = CLAUDE_MD.read_text(encoding='utf-8')
    targets = ['@buddy-pokemon.md', '@pokemon-persona.md', 'Speak as a Pokemon Master Coach']
    if not any(t in content for t in targets): return False

    if not confirm('  Remove Pokémon persona imports from ~/.claude/CLAUDE.md?'):
        return False

    new_lines = []
    skip_block = False
    for line in content.splitlines():
        low = line.strip()
        if low.startswith('@buddy-pokemon.md') or low.startswith('@pokemon-persona.md'):
            continue
        if '## Buddy XP Auto-Award' in line or '## Active Persona' in line:
            skip_block = True
            continue
        if skip_block and line.startswith('## '):
            skip_block = False
        if skip_block: continue
        if 'Speak as a Pokemon Master Coach' in line: continue
        new_lines.append(line)

    CLAUDE_MD.write_text('\n'.join(new_lines).rstrip() + '\n', encoding='utf-8')
    return True


def clean_settings():
    if not SETTINGS.exists(): return False
    try: data = json.loads(SETTINGS.read_text(encoding='utf-8'))
    except Exception: return False
    sl = data.get('statusLine')
    cmd = sl.get('command') if isinstance(sl, dict) else None
    if not cmd or 'buddy-update.py' not in cmd: return False
    if 'CLAUDE_PLUGIN_ROOT' in cmd: return False  # already plugin-pointed

    if not confirm('  Remove legacy statusline from settings.json? (Plugin will re-register its own)'):
        return False

    data.pop('statusLine', None)
    SETTINGS.write_text(json.dumps(data, indent=2), encoding='utf-8')
    return True


def delete_legacy_files():
    existing = [p for p in LEGACY_FILES + LEGACY_COMMANDS if p.exists()]
    if not existing:
        return 0

    print()
    print('  Legacy install artifacts:')
    for p in existing: print(f'    · {p}')
    print()

    if not confirm(f'  Delete {len(existing)} legacy file(s)? (A backup copy will be saved to {BACKUP_DIR})'):
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    for p in existing:
        try:
            shutil.copy2(p, BACKUP_DIR / p.name)
            p.unlink()
            removed += 1
        except Exception as e:
            print(f'    ! could not remove {p}: {e}')
    return removed


def main():
    print()
    print('═' * 60)
    print('  Pokémon Buddy — Legacy v1.x → Plugin v2.0 Migration')
    print('═' * 60)

    if not detect_legacy():
        print()
        print('  ✓ No legacy install detected. You\'re already clean!')
        print('    Run /poke:choose to pick a starter.')
        return

    summarize_state()

    print('  This migration will:')
    print('    1. Remove v1.x import lines from ~/.claude/CLAUDE.md')
    print('    2. Remove v1.x statusline from ~/.claude/settings.json')
    print('    3. Delete v1.x install files (backup saved)')
    print('    4. Leave your buddy, XP, collection, and stats untouched')
    print()

    if not confirm('  Proceed?'):
        print('\n  Aborted. Nothing changed.')
        return

    md_changed  = clean_claude_md()
    s_changed   = clean_settings()
    n_removed   = delete_legacy_files()

    print()
    print('─' * 60)
    print('  Summary')
    print('─' * 60)
    print(f'    CLAUDE.md cleaned:     {"yes" if md_changed else "skipped"}')
    print(f'    settings.json cleaned: {"yes" if s_changed else "skipped"}')
    print(f'    Legacy files removed:  {n_removed}')
    if n_removed:
        print(f'    Backup location:       {BACKUP_DIR}')
    print()
    print('  ✓ Migration complete.')
    print()
    print('  NEXT STEPS:')
    print('    1. Exit Claude Code and restart to pick up the new plugin statusline.')
    print('    2. (Optional) Enable Coach persona: /poke:persona on')
    print()


if __name__ == '__main__':
    try: main()
    except KeyboardInterrupt:
        print('\n  Cancelled.')
