#!/usr/bin/env python3
"""Stop hook: award XP from token usage of the just-completed turn.

Reads transcript_path from stdin, scans the JSONL for assistant entries with
usage data, and awards XP for the tokens produced since the last processed
turn (tracked per session_id in pokemon-buddy-plugin.json).

Tier formula:
  output       : 1 XP / 100  tokens
  input        : 1 XP / 1000 tokens
  cache write  : 1 XP / 500  tokens
  cache read   : 1 XP / 5000 tokens
"""
import json, os, sys, subprocess, traceback
from datetime import datetime
from pathlib import Path

if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOME         = Path.home()
CLAUDE_DIR   = HOME / '.claude'
BUDDY_FILE   = CLAUDE_DIR / 'buddy-pokemon.md'
PLUGIN_STATE = CLAUDE_DIR / 'pokemon-buddy-plugin.json'
ERROR_LOG    = CLAUDE_DIR / 'pokemon-buddy-error.log'
PLUGIN_ROOT  = Path(os.environ.get('CLAUDE_PLUGIN_ROOT', Path(__file__).resolve().parent.parent))

# Tokens-per-XP (integer divisor per tier — lower = more generous)
TIERS = {
    'output':       100,
    'input':        1000,
    'cache_write':  500,
    'cache_read':   5000,
}


def log_err(msg):
    try:
        with open(ERROR_LOG, 'a', encoding='utf-8') as f:
            f.write(f'\n[{datetime.now().isoformat()}] stop-xp: {msg}\n')
    except Exception:
        pass


def load_state():
    if PLUGIN_STATE.exists():
        try: return json.loads(PLUGIN_STATE.read_text(encoding='utf-8'))
        except Exception: return {}
    return {}


def save_state(state):
    PLUGIN_STATE.write_text(json.dumps(state, indent=2), encoding='utf-8')


def extract_usage(entry):
    """Pull token counts from an assistant JSONL entry. Returns dict or None."""
    msg = entry.get('message') or {}
    u   = msg.get('usage') or {}
    if not u:
        return None
    return {
        'output':      int(u.get('output_tokens', 0) or 0),
        'input':       int(u.get('input_tokens', 0) or 0),
        'cache_write': int(u.get('cache_creation_input_tokens', 0) or 0),
        'cache_read':  int(u.get('cache_read_input_tokens', 0) or 0),
    }


def collect_new_usage(transcript_path, last_uuid):
    """Walk transcript; return (summed_usage, last_assistant_uuid_seen, turns_counted).

    Only assistant entries AFTER last_uuid are counted. If last_uuid is not
    found in the file (fresh session, compacted, etc.), count all entries.
    """
    totals = {k: 0 for k in TIERS}
    latest_uuid = last_uuid
    turns = 0
    seen_anchor = (last_uuid is None)

    with open(transcript_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get('type') != 'assistant':
                continue
            uuid = entry.get('uuid')
            if not seen_anchor:
                if uuid == last_uuid:
                    seen_anchor = True
                continue
            u = extract_usage(entry)
            if u is None:
                continue
            for k in TIERS:
                totals[k] += u[k]
            turns += 1
            if uuid:
                latest_uuid = uuid

    # If anchor was never found, bail on counting — treat it as a reset
    if not seen_anchor:
        return None, None, 0

    return totals, latest_uuid, turns


def compute_xp(totals):
    xp = 0
    for k, divisor in TIERS.items():
        xp += totals.get(k, 0) // divisor
    return xp


def main():
    # Skip entirely if no buddy chosen yet
    if not BUDDY_FILE.exists():
        return

    raw = sys.stdin.read().strip()
    if not raw:
        return
    try:
        payload = json.loads(raw)
    except Exception as e:
        log_err(f'stdin parse: {e}')
        return

    transcript = payload.get('transcript_path')
    session_id = payload.get('session_id') or 'default'
    if not transcript or not Path(transcript).exists():
        return

    state    = load_state()
    sessions = state.setdefault('xp_sessions', {})
    sess     = sessions.setdefault(session_id, {})
    last_uuid = sess.get('last_uuid')

    totals, latest_uuid, turns = collect_new_usage(transcript, last_uuid)

    if totals is None:
        # Anchor missing — record current tail uuid without awarding
        # (prevents back-filling a huge cumulative batch on resume)
        _, tail_uuid, _ = collect_new_usage(transcript, None)
        if tail_uuid:
            sess['last_uuid'] = tail_uuid
            save_state(state)
        return

    if turns == 0:
        return

    xp_amount = compute_xp(totals)

    # Always advance anchor so we don't re-count these turns
    sess['last_uuid'] = latest_uuid
    save_state(state)

    if xp_amount <= 0:
        return

    tok_summary = (f'{totals["output"]}o+{totals["input"]}i'
                   f'+{totals["cache_write"]}cw+{totals["cache_read"]}cr')

    # Fire-and-forget: buddy-update.py prints its full announcement to stdout.
    # We print that too so the user sees XP feedback after each turn.
    try:
        result = subprocess.run(
            ['python3', str(PLUGIN_ROOT / 'buddy-update.py'),
             'xp-auto', str(xp_amount), tok_summary],
            capture_output=True, text=True, timeout=8,
        )
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.returncode != 0 and result.stderr:
            log_err(f'buddy-update xp-auto failed: {result.stderr.strip()}')
    except subprocess.TimeoutExpired:
        log_err('buddy-update xp-auto timeout')
    except Exception as e:
        log_err(f'buddy-update xp-auto exception: {e}')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        log_err(traceback.format_exc())
