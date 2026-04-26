#!/usr/bin/env python3
"""SessionStart hook for Pokemon Buddy plugin.

Runs once per Claude Code session:
  1. If legacy v1.x install detected → print migration nudge (once)
  2. If no buddy state yet            → print welcome + starter prompt
  3. Always: ensure statusline is wired in ~/.claude/settings.json
"""
import json, os, sys
from pathlib import Path

if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOME          = Path.home()
CLAUDE_DIR    = HOME / '.claude'
BUDDY_FILE    = CLAUDE_DIR / 'buddy-pokemon.md'
LEGACY_ENGINE = CLAUDE_DIR / 'buddy-update.py'
PLUGIN_ROOT   = Path(os.environ.get('CLAUDE_PLUGIN_ROOT', Path(__file__).resolve().parent.parent))
PLUGIN_STATE  = CLAUDE_DIR / 'pokemon-buddy-plugin.json'
SETTINGS_FILE = CLAUDE_DIR / 'settings.json'


def load_plugin_state():
    if PLUGIN_STATE.exists():
        try: return json.loads(PLUGIN_STATE.read_text(encoding='utf-8'))
        except Exception: pass
    return {}

def save_plugin_state(state):
    PLUGIN_STATE.write_text(json.dumps(state, indent=2), encoding='utf-8')


def ensure_statusline():
    """Register the plugin's statusline command in ~/.claude/settings.json if not already.
    Backs up any existing statusLine to _statusLineBackup so uninstall can restore it."""
    engine = PLUGIN_ROOT / 'buddy-update.py'
    desired = f'python3 "{engine}" statusline --plugin'

    settings = {}
    if SETTINGS_FILE.exists():
        try: settings = json.loads(SETTINGS_FILE.read_text(encoding='utf-8'))
        except Exception: settings = {}

    current = settings.get('statusLine')
    current_cmd = current.get('command') if isinstance(current, dict) else None

    if current_cmd == desired:
        return False  # already wired

    if current and 'pokemon-buddy-plugin' not in json.dumps(current) and 'buddy-update.py' not in (current_cmd or ''):
        settings['_statusLineBackup'] = current

    settings['statusLine'] = {'type': 'command', 'command': desired, 'padding': 0}
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding='utf-8')
    return True


def detect_legacy():
    return LEGACY_ENGINE.exists()


def has_buddy():
    return BUDDY_FILE.exists()


def fire_update_check():
    """Background fire-and-forget GitHub release poll. Never blocks session."""
    try:
        import subprocess
        engine = PLUGIN_ROOT / 'buddy-update.py'
        if not engine.exists():
            return
        subprocess.Popen(
            ['python3', str(engine), 'update-check'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def main():
    state = load_plugin_state()
    first_run = not state.get('welcomed')
    fire_update_check()
    statusline_new = ensure_statusline()
    legacy = detect_legacy()

    lines = []

    if legacy and not state.get('migration_nudged'):
        lines.append('')
        lines.append('⚡ Pokémon Buddy v2.0 detected legacy v1.x install')
        lines.append('   Your existing buddy can be migrated with: /poke:migrate')
        lines.append('   (Run once — carries over XP, level, streak, collection)')
        lines.append('')
        state['migration_nudged'] = True

    elif first_run and has_buddy():
        lines.append('')
        lines.append('⚡ Pokémon Buddy reinstalled — welcome back, Trainer!')
        lines.append('   Your buddy, collection, and streak were restored.')
        lines.append('   Run /poke:status to see them.')
        lines.append('')

    elif first_run and not has_buddy():
        lines.append('')
        lines.append('╔══════════════════════════════════════════════════════════╗')
        lines.append('║  ⚡ Pokémon Buddy for Claude — welcome, Trainer!         ║')
        lines.append('╚══════════════════════════════════════════════════════════╝')
        lines.append('')
        lines.append('  Pick your starter:         /poke:choose')
        lines.append('  Enable Coach persona:      /poke:persona on  (opt-in, costs tokens)')
        lines.append('  Check current status:      /poke:status')
        lines.append('')
        lines.append('  The status bar will animate after you pick a starter.')
        lines.append('')

    if first_run:
        state['welcomed'] = True

    if statusline_new:
        save_plugin_state(state)  # save even if no lines, to persist the install
    elif lines or state != load_plugin_state():
        save_plugin_state(state)

    if lines:
        print('\n'.join(lines))


if __name__ == '__main__':
    try: main()
    except Exception as e:
        # Never fail session start — log to file for later diagnosis
        import traceback
        log_path = CLAUDE_DIR / 'pokemon-buddy-error.log'
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                from datetime import datetime
                f.write(f'\n[{datetime.now().isoformat()}] session-start error:\n')
                f.write(traceback.format_exc())
        except Exception:
            pass
        print(f'[pokemon-buddy] session-start error logged to {log_path}', file=sys.stderr)
