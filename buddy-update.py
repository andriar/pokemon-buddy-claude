#!/usr/bin/env python3
"""
buddy-update.py — Pokemon Buddy engine for Claude Code.

Commands:
  status                       Full status card (read-only)
  statusline                   Compact one-liner for status bar
  card                         Shareable ASCII trainer card
  xp "<description>"           Award XP (auto-detects amount), may trigger catch
  badge "<emoji>" "<n>" "<d>"  Award badge + 50 XP
  switch "<name>"              Switch active buddy
  catch "<name>"               Manually add a Pokemon to collection
"""

import sys, re, random, unicodedata, json
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.data import (
    STARTER_DATA, MOVE_UNLOCKS, RARITY_START_LEVEL, BUDDY_RARITY_BOOST,
    ENCOUNTER_RATES, POKEMON_POOL, XP_RULES, MILESTONES, TITLE_RULES, BUDDY_TEMPLATE,
    POKEBALL_TYPES, BALL_BY_RARITY, BALL_EARN_BY_XP,
    BERRY_TYPES, BERRY_DROP_RATES,
    WILD_LEVELS, BASE_CATCH_RATES, TYPE_ADVANTAGE,
    COMBO_MULTIPLIERS, COMBO_WINDOW_SECS, LEVEL_UP_MILESTONE_REWARDS,
    DAILY_QUESTS,
)

# ── Windows UTF-8 stdout (emoji safe) ────────────────────────────────────────
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Terminal width helper ─────────────────────────────────────────────────────

def visual_len(s):
    """Return the visible terminal width of a string.
    Emoji and East-Asian wide chars occupy 2 columns; everything else 1.
    """
    width = 0
    for ch in s:
        cp  = ord(ch)
        eaw = unicodedata.east_asian_width(ch)
        if eaw in ('W', 'F') or 0x2600 <= cp <= 0x27BF or 0x2B00 <= cp <= 0x2BFF or cp >= 0x1F000:
            width += 2
        else:
            width += 1
    return width

BUDDY_FILE      = Path.home() / '.claude' / 'buddy-pokemon.md'
COLLECTION_FILE = Path.home() / '.claude' / 'pokemon-collection.md'
STATS_FILE      = Path.home() / '.claude' / 'buddy-stats.md'
STATE_FILE      = Path.home() / '.claude' / 'buddy-state.txt'
ENCOUNTER_FILE  = Path.home() / '.claude' / 'buddy-encounter.json'
TODAY           = date.today().strftime('%Y-%m-%d')
LOG_CAP         = 15
ARCHIVE_FILE    = Path.home() / '.claude' / 'buddy-log-archive.md'

SHINY_RATE        = 1 / 200   # 0.5%
STREAK_BONUS_XP   = 20        # bonus XP for first award of the day
STATS_SCHEMA_VER  = 2         # bumped: added inventory, combo, daily quest

RARITY_TIER_ORDER = ['mythical', 'legendary', 'rare', 'uncommon', 'common', 'starter']
RARITY_LABELS_ASCII = {
    'mythical':  '★  MYTHICAL',
    'legendary': '★  LEGENDARY',
    'rare':      '◆  RARE',
    'uncommon':  '◈  UNCOMMON',
    'common':    '◌  COMMON',
    'starter':   '◌  STARTER',
}

def _pokemon_tier(p):
    r = p.get('rarity', '')
    for t in RARITY_TIER_ORDER:
        if t in r:
            return t
    return 'common'

def _group_by_tier(pokemon):
    grouped = {}
    for p in pokemon:
        grouped.setdefault(_pokemon_tier(p), []).append(p)
    return grouped

# ── Pokemon data, XP rules — see lib/data.py ──────────────────────────────────

def detect_xp(description):
    m = re.search(r'\b(\d+)\s*xp\b', description.lower())
    if m: return int(m.group(1))
    desc = description.lower()
    for rule in XP_RULES:
        xp, en_keywords, id_keywords = rule
        if any(k in desc for k in en_keywords) or any(k in desc for k in id_keywords):
            return xp
    return 10

# ── Milestone & title data — see lib/data.py ───────────────────────────────────

# ── Level / XP math ───────────────────────────────────────────────────────────

def xp_for_level(n):
    if n <= 1:  return 0
    if n <= 15: return (n - 1) * 100
    if n <= 35: return 1400 + (n - 15) * 150
    return 4400 + (n - 35) * 200

def level_from_xp(xp):
    lv = 1
    while lv < 100 and xp >= xp_for_level(lv + 1):
        lv += 1
    return lv

# ── Bars ─────────────────────────────────────────────────────────────────────

def bar(cur, max_val, width):
    filled = min(width, int(cur * width / max_val)) if max_val > 0 else 0
    return '█' * filled + '░' * (width - filled)

def stat_bar(val, width=10):
    return bar(val, 100, width)

def colored_bar(cur, max_val, width=10):
    """XP bar with ANSI color: green < 70%, yellow 70–90%, red >= 90%."""
    filled = min(width, int(cur * width / max_val)) if max_val > 0 else 0
    pct    = int(cur * 100 / max_val) if max_val > 0 else 0
    if pct >= 90:   color = '\033[31m'   # red   — almost level up!
    elif pct >= 70: color = '\033[33m'   # yellow — getting close
    else:           color = '\033[32m'   # green  — steady grind
    reset = '\033[0m'
    blocks = color + '█' * filled + reset + '░' * (width - filled)
    return f'[{blocks}]'

def get_chatter(xp_pct=0):
    """Return buddy chatter for statusline. Reads STATE_FILE if fresh (< 5 min)."""
    now = datetime.now().timestamp()
    if STATE_FILE.exists():
        age = now - STATE_FILE.stat().st_mtime
        if age < 300:
            msg = STATE_FILE.read_text(encoding='utf-8').strip()
            if msg:
                return msg
    # XP-percentage-aware idle messages
    if xp_pct >= 90: return 'Almost there! 😤'
    if xp_pct >= 70: return 'Getting close! ⚡'
    # Time-of-day fallback
    hour = datetime.now().hour
    if hour < 9:   return 'Early bird! 🌅'
    if hour < 12:  return 'Morning grind! ☕'
    if hour < 17:  return 'What are we building? 🎯'
    if hour < 21:  return 'Evening session! 🌙'
    return 'Late night coding! 🦉'

# ── Stats I/O ─────────────────────────────────────────────────────────────────

def read_stats():
    defaults = {
        'schema_version': STATS_SCHEMA_VER,
        'streak': 0, 'last_xp_date': '', 'longest_streak': 0,
        'total_xp_ever': 0, 'bug_fixes': 0, 'features': 0, 'ships': 0,
        'caught_legendary': False, 'caught_mythical': False, 'caught_shiny': False,
        'milestones': set(),
        # Inventory (new trainers start with 5 Poké Balls)
        'balls_poke': 5, 'balls_great': 0, 'balls_ultra': 0, 'balls_master': 0,
        'master_shards': 0,
        'berry_razz': 0, 'berry_nanab': 0, 'berry_pinap': 0, 'berry_golden': 0,
        # Combo
        'combo': 0, 'combo_ts': '',
        # Daily quest
        'daily_quest_date': '', 'daily_quest_id': '', 'daily_quest_done': False,
        'tasks_today': 0,
    }
    if not STATS_FILE.exists():
        return defaults
    text = STATS_FILE.read_text(encoding='utf-8')
    def gi(key):
        m = re.search(rf'\*\*{key}\*\*:\s*(-?\d+)', text)
        return int(m.group(1)) if m else defaults.get(key, 0)
    def gb(key):
        m = re.search(rf'\*\*{key}\*\*:\s*(true|false)', text)
        return (m.group(1) == 'true') if m else defaults.get(key, False)
    def gs(key):
        m = re.search(rf'\*\*{key}\*\*:\s*(.+)', text)
        return m.group(1).strip() if m else defaults.get(key, '')
    ms_section = re.search(r'## Milestones Awarded\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    milestones = set(re.findall(r'^- (\S+)', ms_section.group(1), re.MULTILINE)) if ms_section else set()
    stats = {
        'schema_version':    gi('schema_version') or STATS_SCHEMA_VER,
        'streak':            gi('streak'),
        'last_xp_date':      gs('last_xp_date'),
        'longest_streak':    gi('longest_streak'),
        'total_xp_ever':     gi('total_xp_ever'),
        'bug_fixes':         gi('bug_fixes'),
        'features':          gi('features'),
        'ships':             gi('ships'),
        'caught_legendary':  gb('caught_legendary'),
        'caught_mythical':   gb('caught_mythical'),
        'caught_shiny':      gb('caught_shiny'),
        'milestones':        milestones,
        'balls_poke':        gi('balls_poke') if '**balls_poke**' in text else defaults['balls_poke'],
        'balls_great':       gi('balls_great'),
        'balls_ultra':       gi('balls_ultra'),
        'balls_master':      gi('balls_master'),
        'master_shards':     gi('master_shards'),
        'berry_razz':        gi('berry_razz'),
        'berry_nanab':       gi('berry_nanab'),
        'berry_pinap':       gi('berry_pinap'),
        'berry_golden':      gi('berry_golden'),
        'combo':             gi('combo'),
        'combo_ts':          gs('combo_ts'),
        'daily_quest_date':  gs('daily_quest_date'),
        'daily_quest_id':    gs('daily_quest_id'),
        'daily_quest_done':  gb('daily_quest_done'),
        'tasks_today':       gi('tasks_today'),
    }
    return stats

def write_stats(s):
    b = lambda v: 'true' if v else 'false'
    ms_lines = '\n'.join(f'- {m}' for m in sorted(s['milestones'])) or '*(none yet)*'
    STATS_FILE.write_text(
        f'# Trainer Stats\n\n'
        f'**schema_version**: {STATS_SCHEMA_VER}\n'
        f'**streak**: {s["streak"]}\n'
        f'**last_xp_date**: {s["last_xp_date"]}\n'
        f'**longest_streak**: {s["longest_streak"]}\n'
        f'**total_xp_ever**: {s["total_xp_ever"]}\n'
        f'**bug_fixes**: {s["bug_fixes"]}\n'
        f'**features**: {s["features"]}\n'
        f'**ships**: {s["ships"]}\n'
        f'**caught_legendary**: {b(s["caught_legendary"])}\n'
        f'**caught_mythical**: {b(s["caught_mythical"])}\n'
        f'**caught_shiny**: {b(s["caught_shiny"])}\n'
        f'**balls_poke**: {s.get("balls_poke", 0)}\n'
        f'**balls_great**: {s.get("balls_great", 0)}\n'
        f'**balls_ultra**: {s.get("balls_ultra", 0)}\n'
        f'**balls_master**: {s.get("balls_master", 0)}\n'
        f'**master_shards**: {s.get("master_shards", 0)}\n'
        f'**berry_razz**: {s.get("berry_razz", 0)}\n'
        f'**berry_nanab**: {s.get("berry_nanab", 0)}\n'
        f'**berry_pinap**: {s.get("berry_pinap", 0)}\n'
        f'**berry_golden**: {s.get("berry_golden", 0)}\n'
        f'**combo**: {s.get("combo", 0)}\n'
        f'**combo_ts**: {s.get("combo_ts", "")}\n'
        f'**daily_quest_date**: {s.get("daily_quest_date", "")}\n'
        f'**daily_quest_id**: {s.get("daily_quest_id", "")}\n'
        f'**daily_quest_done**: {b(s.get("daily_quest_done", False))}\n'
        f'**tasks_today**: {s.get("tasks_today", 0)}\n\n'
        f'## Milestones Awarded\n\n'
        f'{ms_lines}\n'
    )

# ── Streak logic ──────────────────────────────────────────────────────────────

def update_streak(stats):
    """Returns (bonus_xp, new_streak, is_new_day)."""
    last = stats.get('last_xp_date', '')
    if last == TODAY:
        return 0, stats['streak'], False
    yesterday = (datetime.strptime(TODAY, '%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
    new_streak = (stats['streak'] + 1) if last == yesterday else 1
    stats['streak'] = new_streak
    stats['last_xp_date'] = TODAY
    if new_streak > stats.get('longest_streak', 0):
        stats['longest_streak'] = new_streak
    return STREAK_BONUS_XP, new_streak, True

# ── Milestone & title logic ───────────────────────────────────────────────────

def get_trainer_title(stats, col):
    n = len(col['pokemon'])
    checks = {
        'caught_mythical':  stats.get('caught_mythical'),
        'caught_legendary': stats.get('caught_legendary'),
        'caught_shiny':     stats.get('caught_shiny'),
        'dex_30':           n >= 30,
        'ships_3':          stats.get('ships', 0) >= 3,
        'ships_1':          stats.get('ships', 0) >= 1,
        'streak_30':        stats.get('streak', 0) >= 30,
        'streak_7':         stats.get('streak', 0) >= 7,
        'bug_20':           stats.get('bug_fixes', 0) >= 20,
        'features_10':      stats.get('features', 0) >= 10,
        'dex_10':           n >= 10,
    }
    for key, title in TITLE_RULES:
        if checks.get(key):
            return title
    return 'Rookie Trainer'

def check_milestones(stats, col, old_level, new_level, catch_result, evolved):
    """Returns list of (emoji, name, desc) for newly triggered milestones."""
    new_ms = []
    awarded = stats['milestones']

    def maybe(key):
        if key not in awarded and key in MILESTONES:
            awarded.add(key)
            return [MILESTONES[key]]
        return []

    n_caught = len(col['pokemon'])

    # Dex milestones
    if n_caught >= 1:  new_ms += maybe('first_catch')
    if n_caught >= 10: new_ms += maybe('dex_10')
    if n_caught >= 20: new_ms += maybe('dex_20')
    if n_caught >= 30: new_ms += maybe('dex_30')

    # Catch tier milestones
    if catch_result:
        base_tier = catch_result[0].replace('-shiny', '')
        if base_tier == 'legendary': new_ms += maybe('legendary_catch')
        if base_tier == 'mythical':  new_ms += maybe('mythical_catch')
        if catch_result[4]:          new_ms += maybe('shiny_catch')  # is_shiny flag

    # Evolution milestones
    if evolved:
        new_ms += maybe('first_evolution')
        if new_level >= 36: new_ms += maybe('final_evolution')

    # Level milestones
    for lv, key in [(10,'level_10'),(20,'level_20'),(30,'level_30'),(50,'level_50')]:
        if old_level < lv <= new_level: new_ms += maybe(key)

    # Streak milestones
    streak = stats.get('streak', 0)
    if streak >= 7:  new_ms += maybe('streak_7')
    if streak >= 30: new_ms += maybe('streak_30')

    stats['milestones'] = awarded
    return new_ms

def append_badge(badge_line):
    """Append a badge line to buddy file."""
    text = BUDDY_FILE.read_text(encoding='utf-8')
    if '*No badges yet' in text:
        text = text.replace('*No badges yet — the journey begins now!*', badge_line)
    else:
        lines = text.splitlines(keepends=True)
        for i in range(len(lines) - 1, -1, -1):
            if re.match(r'- .* \*\*.*\*\*', lines[i]):
                lines.insert(i + 1, badge_line + '\n')
                text = ''.join(lines)
                break
        else:
            text = text  # no-op if pattern not found
    BUDDY_FILE.write_text(text, encoding='utf-8')

# ── Collection I/O ────────────────────────────────────────────────────────────

def parse_int(text):
    m = re.search(r'\d+', str(text))
    return int(m.group()) if m else 0

def read_collection():
    if not COLLECTION_FILE.exists():
        return {'active': None, 'pokemon': []}
    text = COLLECTION_FILE.read_text(encoding='utf-8')
    active_m = re.search(r'\*\*Active\*\*:\s*(\S+)', text)
    active = active_m.group(1).strip() if active_m else None
    pokemon = []
    for line in text.splitlines():
        if not line.startswith('|'): continue
        cols = [c.strip() for c in line.split('|')]
        cols = [c for c in cols if c]
        if len(cols) < 6 or cols[0] == 'Name': continue
        try:
            rarity = cols[6] if len(cols) > 6 else 'caught'
            pokemon.append({
                'name':    cols[0],
                'type':    cols[1],
                'emoji':   cols[2],
                'level':   int(cols[3]),
                'xp':      int(cols[4]),
                'caught':  cols[5],
                'rarity':  rarity,
                'shiny':   rarity.endswith('-shiny'),
            })
        except (ValueError, IndexError):
            continue
    return {'active': active, 'pokemon': pokemon}

def write_collection(active, pokemon_list):
    lines = [
        '# Pokemon Collection\n\n',
        f'**Active**: {active}\n\n',
        '| Name | Type | Emoji | Level | XP | Caught | Rarity |\n',
        '|---|---|---|---|---|---|---|\n',
    ]
    for p in pokemon_list:
        lines.append(
            f"| {p['name']} | {p['type']} | {p['emoji']} | "
            f"{p['level']} | {p['xp']} | {p['caught']} | {p['rarity']} |\n"
        )
    COLLECTION_FILE.write_text(''.join(lines), encoding='utf-8')

def sync_active_to_collection(name, level, xp):
    col = read_collection()
    for p in col['pokemon']:
        if p['name'] == name:
            p['level'] = level
            p['xp']    = xp
            write_collection(col['active'], col['pokemon'])
            return
    # Missing from collection — append rather than silently dropping the update.
    starter = STARTER_DATA.get(name, {})
    col['pokemon'].append({
        'name':   name,
        'type':   starter.get('type', '?'),
        'emoji':  starter.get('emoji', '?'),
        'level':  level,
        'xp':     xp,
        'caught': TODAY,
        'rarity': 'starter',
    })
    write_collection(col['active'], col['pokemon'])

# ── Catch system ──────────────────────────────────────────────────────────────

def get_role_type():
    """Parse trainer's Pokemon type from buddy-pokemon.md role line.
    e.g. '- **Role**: Frontend (Electric ⚡ domain)' → 'Electric'
    """
    if not BUDDY_FILE.exists():
        return None
    m = re.search(r'\*\*Role\*\*:.*?\(([A-Za-z]+)', BUDDY_FILE.read_text(encoding='utf-8'))
    return m.group(1) if m else None

def get_buddy_rarity():
    """Return the active buddy's rarity tier (strips -shiny suffix). Returns None if unknown."""
    col = read_collection()
    active_name = col.get('active')
    if not active_name:
        return None
    active = next((p for p in col['pokemon'] if p['name'] == active_name), None)
    if not active:
        return None
    return active.get('rarity', '').replace('-shiny', '') or None

def _roll_encounter_tier(base_xp, buddy_rarity):
    """Roll which tier of wild Pokémon appears, or None if no encounter."""
    rates  = ENCOUNTER_RATES.get(base_xp, [('common', 0.25)])
    boosts = BUDDY_RARITY_BOOST.get(buddy_rarity, {}) if buddy_rarity else {}
    found  = None
    for tier, prob in sorted(rates, key=lambda x: list(POKEMON_POOL.keys()).index(x[0])):
        if random.random() < min(1.0, prob * boosts.get(tier, 1.0)):
            found = tier
    return found

def _pick_wild(tier, owned_names, role_type):
    """Pick a wild Pokémon from the pool, preferring unseen and role-type matches."""
    pool      = POKEMON_POOL[tier]
    available = [p for p in pool if p[0] not in owned_names] or pool
    if role_type:
        weights = [3 if p[1] == role_type else 1 for p in available]
        return random.choices(available, weights=weights, k=1)[0]
    return random.choice(available)

def run_battle(buddy_level, buddy_type, wild_level, wild_type):
    """Returns (won: bool, win_pct: int)."""
    advantage = wild_type in TYPE_ADVANTAGE.get(buddy_type or '', [])
    base = buddy_level / max(1, wild_level) * 70
    if advantage:
        base += 20
    win_pct = max(20, min(95, int(base)))
    return random.randint(1, 100) <= win_pct, win_pct

def attempt_catch(tier, ball_key, stats):
    """Roll the catch. Returns (caught: bool, catch_pct: int). Uses best berry automatically."""
    if ball_key == 'master':
        return True, 100
    base = BASE_CATCH_RATES.get(tier, 0.5)
    mult = POKEBALL_TYPES.get(ball_key, {}).get('multiplier', 1.0)
    # Auto-use best available berry
    berry_used = None
    if stats.get('berry_golden', 0) > 0:
        mult *= BERRY_TYPES['golden']['catch_boost']
        stats['berry_golden'] -= 1
        berry_used = 'golden'
    elif stats.get('berry_razz', 0) > 0:
        mult *= BERRY_TYPES['razz']['catch_boost']
        stats['berry_razz'] -= 1
        berry_used = 'razz'
    catch_pct = min(95, int(base * mult * 100))
    return random.randint(1, 100) <= catch_pct, catch_pct

def earn_inventory(base_xp, is_badge, stats):
    """Add balls and berries earned from the task. Returns description string."""
    earned = []
    ball_gains = BALL_EARN_BY_XP.get(base_xp, {'poke': 1})
    if is_badge:
        ball_gains = {'poke': 1}  # badge gives shard separately
    for ball, qty in ball_gains.items():
        key = f'balls_{ball}'
        stats[key] = stats.get(key, 0) + qty
        info = POKEBALL_TYPES.get(ball, {})
        earned.append(f'{info.get("emoji","🔴")} {info.get("name","Ball")} ×{qty}')
    # Roll berries
    for berry, chance in BERRY_DROP_RATES.get(base_xp, []):
        if random.random() < chance:
            key = f'berry_{berry}'
            stats[key] = stats.get(key, 0) + 1
            info = BERRY_TYPES.get(berry, {})
            earned.append(f'{info.get("emoji","🍓")} {info.get("name","Berry")} ×1')
            break  # max 1 berry per task
    if is_badge:
        stats['master_shards'] = stats.get('master_shards', 0) + 1
        if stats['master_shards'] >= 3:
            stats['master_shards'] -= 3
            stats['balls_master'] = stats.get('balls_master', 0) + 1
            earned.append('🟣 Master Ball ×1 (3 shards!)')
        else:
            earned.append(f'💠 Master Shard ×1 ({stats["master_shards"]}/3)')
    return '  '.join(earned) if earned else ''

def update_combo(stats):
    """Update combo counter. Returns (combo_count: int, xp_multiplier: float)."""
    now = datetime.now()
    ts_str = stats.get('combo_ts', '')
    if ts_str:
        try:
            last = datetime.fromisoformat(ts_str)
            elapsed = (now - last).total_seconds()
        except ValueError:
            elapsed = COMBO_WINDOW_SECS + 1
    else:
        elapsed = COMBO_WINDOW_SECS + 1
    if elapsed > COMBO_WINDOW_SECS:
        stats['combo'] = 1
    else:
        stats['combo'] = stats.get('combo', 0) + 1
    stats['combo_ts'] = now.isoformat()
    combo = stats['combo']
    mult = next((m for min_c, m in COMBO_MULTIPLIERS if combo >= min_c), 1.0)
    return combo, mult

def get_daily_quest(stats):
    """Return today's quest dict (resets each day)."""
    if stats.get('daily_quest_date') != TODAY:
        idx = hash(TODAY) % len(DAILY_QUESTS)
        stats['daily_quest_date'] = TODAY
        stats['daily_quest_id']   = DAILY_QUESTS[idx]['id']
        stats['daily_quest_done'] = False
        stats['tasks_today']      = 0
    return next((q for q in DAILY_QUESTS if q['id'] == stats['daily_quest_id']), None)

def check_daily_quest(stats, desc, did_catch):
    """Check if daily quest completed. Returns reward description or ''."""
    if stats.get('daily_quest_done'):
        return ''
    quest = get_daily_quest(stats)
    if not quest:
        return ''
    dl = desc.lower()
    completed = False
    if quest['id'] == 'catch':
        completed = did_catch
    elif quest['id'] == 'three_tasks':
        completed = stats.get('tasks_today', 0) >= 3
    elif quest['keywords']:
        completed = any(k in dl for k in quest['keywords'])
    if not completed:
        return ''
    stats['daily_quest_done'] = True
    reward = quest['reward']
    qty    = quest['qty']
    if reward == 'ultra':
        stats['balls_ultra'] = stats.get('balls_ultra', 0) + qty
        return f'📋 Quest "{quest["desc"]}" done! → 🟡 Ultra Ball ×{qty}'
    elif reward == 'great':
        stats['balls_great'] = stats.get('balls_great', 0) + qty
        return f'📋 Quest "{quest["desc"]}" done! → 🔵 Great Ball ×{qty}'
    elif reward == 'xp':
        return f'📋 Quest "{quest["desc"]}" done! → +{qty} bonus XP'
    elif reward == 'shard':
        stats['master_shards'] = stats.get('master_shards', 0) + 1
        if stats['master_shards'] >= 3:
            stats['master_shards'] -= 3
            stats['balls_master']   = stats.get('balls_master', 0) + 1
            return f'📋 Quest "{quest["desc"]}" done! → 🟣 Master Ball ×1 (3 shards!)'
        return f'📋 Quest "{quest["desc"]}" done! → 💠 Master Shard ({stats["master_shards"]}/3)'
    elif reward == 'razz':
        stats['berry_razz'] = stats.get('berry_razz', 0) + qty
        return f'📋 Quest "{quest["desc"]}" done! → 🍓 Razz Berry ×{qty}'
    elif reward == 'pinap':
        stats['berry_pinap'] = stats.get('berry_pinap', 0) + qty
        return f'📋 Quest "{quest["desc"]}" done! → 🍍 Pinap Berry ×{qty}'
    return ''

def level_up_rewards(old_level, new_level, stats):
    """Award balls for levels gained. Returns description or ''."""
    parts = []
    for lv in range(old_level + 1, new_level + 1):
        stats['balls_poke'] = stats.get('balls_poke', 0) + 2
        if lv % 10 == 0:
            stats['balls_ultra'] = stats.get('balls_ultra', 0) + 1
            parts.append(f'🟡 Lv.{lv}: Ultra Ball +1')
        elif lv % 5 == 0:
            stats['balls_great'] = stats.get('balls_great', 0) + 1
            parts.append(f'🔵 Lv.{lv}: Great Ball +1')
        if lv in LEVEL_UP_MILESTONE_REWARDS:
            ms = LEVEL_UP_MILESTONE_REWARDS[lv]
            for ball, qty in ms.items():
                if ball == 'msg':
                    continue
                key = f'balls_{ball}'
                stats[key] = stats.get(key, 0) + qty
            parts.append(ms.get('msg', ''))
    return '  '.join(p for p in parts if p)

def run_encounter(base_xp, owned_names, role_type, buddy_rarity,
                  buddy_level, buddy_type, stats):
    """Full adventure flow: spawn → battle → ball throws until caught or empty.

    Returns (catch_result, encounter_info) where:
      catch_result = (tier, name, type, emoji, is_shiny) or None  (for milestone compat)
      encounter_info = dict with full battle/catch details
    """
    tier = _roll_encounter_tier(base_xp, buddy_rarity)
    if not tier:
        return None, {'encountered': False}

    wild_name, wild_type, wild_emoji = _pick_wild(tier, owned_names, role_type)
    lv_min, lv_max = WILD_LEVELS.get(tier, (1, 5))
    wild_level = random.randint(lv_min, lv_max)
    is_shiny   = random.random() < SHINY_RATE

    battle_won, win_pct = run_battle(buddy_level, buddy_type, wild_level, wild_type)

    info = {
        'encountered':  True,
        'wild_name':    wild_name,
        'wild_emoji':   wild_emoji,
        'wild_tier':    tier,
        'wild_level':   wild_level,
        'wild_type':    wild_type,
        'is_shiny':     is_shiny,
        'battle_won':   battle_won,
        'win_pct':      win_pct,
        'throws':       [],
        'caught':       False,
        'no_balls':     False,
        'combo':        stats.get('combo', 1),
        'balls_poke':   stats.get('balls_poke', 0),
        'balls_great':  stats.get('balls_great', 0),
        'balls_ultra':  stats.get('balls_ultra', 0),
        'balls_master': stats.get('balls_master', 0),
    }

    if not battle_won:
        return None, info

    caught = False
    for ball in BALL_BY_RARITY.get(tier, ['poke']):
        key       = f'balls_{ball}'
        ball_info = POKEBALL_TYPES.get(ball, {})
        while stats.get(key, 0) > 0:
            stats[key] -= 1
            c, catch_pct = attempt_catch(tier, ball, stats)
            info['throws'].append({
                'ball_key':   ball,
                'ball_emoji': ball_info.get('emoji', '🔴'),
                'ball_name':  ball_info.get('name', 'Ball'),
                'catch_pct':  catch_pct,
                'caught':     c,
                'rem_poke':   stats.get('balls_poke', 0),
                'rem_great':  stats.get('balls_great', 0),
                'rem_ultra':  stats.get('balls_ultra', 0),
            })
            if c:
                caught = True
                break
        if caught:
            break

    if not info['throws']:
        info['no_balls'] = True
        return None, info

    info['caught'] = caught
    info['balls_poke']   = stats.get('balls_poke', 0)
    info['balls_great']  = stats.get('balls_great', 0)
    info['balls_ultra']  = stats.get('balls_ultra', 0)
    info['balls_master'] = stats.get('balls_master', 0)

    if caught:
        add_to_collection(wild_name, wild_type, wild_emoji, tier, is_shiny)
        stored_tier  = (tier + '-shiny') if is_shiny else tier
        catch_result = (stored_tier, wild_name, wild_type, wild_emoji, is_shiny)
        return catch_result, info

    return None, info

def add_to_collection(name, ptype, emoji, rarity, is_shiny=False):
    col = read_collection()
    stored_rarity = (rarity + '-shiny') if is_shiny else rarity
    start_level = RARITY_START_LEVEL.get(rarity, 1)
    col['pokemon'].append({
        'name': name, 'type': ptype, 'emoji': emoji,
        'level': start_level, 'xp': 0, 'caught': TODAY,
        'rarity': stored_rarity, 'shiny': is_shiny,
    })
    write_collection(col['active'], col['pokemon'])

# ── Buddy file I/O ────────────────────────────────────────────────────────────

def read_buddy():
    if not BUDDY_FILE.exists():
        print(f' ❌ No buddy found at {BUDDY_FILE}')
        print(f'    Run /poke:choose to pick a starter first.')
        sys.exit(1)
    lines = BUDDY_FILE.read_text(encoding='utf-8').splitlines(keepends=True)
    text  = ''.join(lines)
    level = parse_int(next((l for l in lines if l.startswith('**Level**:')), '1'))
    xp    = parse_int(next((l for l in lines if l.startswith('**XP**:')), '0'))
    stage_m = re.search(r'\*\*Stage\*\*:\s*(\w+)', text)
    name_m  = re.search(r'\*\*Name\*\*:\s*(\w+)', text)
    stage = stage_m.group(1) if stage_m else 'Charmander'
    name  = name_m.group(1)  if name_m  else 'Charmander'
    return lines, text, level, xp, stage, name

def cap_journal(out):
    log_rows = [(i, l) for i, l in enumerate(out)
                if re.match(r'\| \d{4}-\d{2}-\d{2} \|', l)]
    if len(log_rows) <= LOG_CAP:
        return out
    overflow = log_rows[:-LOG_CAP]
    with open(ARCHIVE_FILE, 'a') as f:
        f.writelines(row for _, row in overflow)
    remove = {i for i, _ in overflow}
    return [l for i, l in enumerate(out) if i not in remove]

def patch_buddy(lines, new_level, new_xp, new_max, new_stage,
                stat_boost, new_moves_data, mode, badge_line):
    out = []
    last_log_idx = -1
    for line in lines:
        if   line.startswith('**Level**:'):      line = f'**Level**: {new_level}  \n'
        elif line.startswith('**XP**:'):         line = f'**XP**: {new_xp} / {new_max}  \n'
        elif line.startswith('**Stage**:'):      line = f'**Stage**: {new_stage} 🔥  \n'
        elif line.startswith('**Current Stage**:'): line = f'**Current Stage**: {new_stage} 🔥\n'

        if stat_boost > 0:
            m = re.match(r'\| (HP|Attack|Speed|Special Atk|Defense|Special Def) \| (\d+) \|', line)
            if m:
                new_val = int(m.group(2)) + stat_boost
                line = line.replace(f'| {m.group(1)} | {m.group(2)} |',
                                    f'| {m.group(1)} | {new_val} |', 1)

        for lv, name, mtype, desc in new_moves_data:
            if f'| ??? | ??? | Lv.{lv} |' in line:
                line = line.replace(f'| ??? | ??? | Lv.{lv} | Learn more to unlock! |',
                                    f'| {name} | {mtype} | Lv.{lv} | {desc} |')

        if mode == 'badge' and badge_line and '*No badges yet' in line:
            line = badge_line + '\n'

        out.append(line)
        if re.match(r'\| \d{4}-\d{2}-\d{2} \|', line):
            last_log_idx = len(out) - 1

    if mode == 'badge' and badge_line and '*No badges yet' not in BUDDY_FILE.read_text(encoding='utf-8'):
        for i in range(len(out) - 1, -1, -1):
            if re.match(r'- .* \*\*.*Badge', out[i]):
                out.insert(i + 1, badge_line + '\n')
                break

    return out, last_log_idx

# ── Encounter display constants ───────────────────────────────────────────────

_ENC_DIV  = ' ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
_ENC_DIV2 = ' ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─  ─'
_TIER_BADGE = {
    'common':    '◌  COMMON',
    'uncommon':  '◈  UNCOMMON',
    'rare':      '◆  RARE',
    'legendary': '★  LEGENDARY',
    'mythical':  '✦  MYTHICAL',
}
_TIER_FLAVOR = {
    'common':    'A wild Pokémon crossed your path!',
    'uncommon':  'Something unusual stirs nearby...',
    'rare':      'A powerful presence emerges from the shadows!',
    'legendary': 'THE GROUND TREMBLES — A LEGEND APPEARS!',
    'mythical':  '✨  A MYTHICAL BEING DESCENDS FROM BEYOND!  ✨',
}

# ── Renderers ─────────────────────────────────────────────────────────────────

def render_status(text):
    def g(pat, default='?'):
        m = re.search(pat, text)
        return m.group(1).strip() if m else default

    name    = g(r'\*\*Name\*\*:\s*(\S+)')
    level   = g(r'\*\*Level\*\*:\s*(\d+)')
    trainer = g(r'\*\*Trainer\*\*:\s*(.+)')
    stage   = g(r'\*\*Stage\*\*:\s*(\w+)')
    xp_cur  = int(g(r'\*\*XP\*\*:\s*(\d+)', '0'))
    xp_max  = int(g(r'\*\*XP\*\*:\s*\d+\s*/\s*(\d+)', '100'))
    xp_floor    = xp_for_level(int(level) if str(level).isdigit() else 1)
    xp_disp     = xp_cur - xp_floor
    xp_max_disp = xp_max - xp_floor

    stats = {}
    for stat in ('HP', 'Attack', 'Speed', 'Special Atk', 'Defense', 'Special Def'):
        m = re.search(rf'\| {re.escape(stat)} \| (\d+) \|', text)
        stats[stat] = int(m.group(1)) if m else 0

    moves  = re.findall(r'\| ([^|?]+) \| ([^|?]+) \| Lv\.(\d+) \| ([^|]+) \|', text)
    locked = re.findall(r'\| \?\?\? \| \?\?\? \| Lv\.(\d+) \|', text)

    badges_section = re.search(r'## Badges Earned\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    badges_raw = re.findall(r'^- (.+)$', badges_section.group(1), re.MULTILINE) if badges_section else []
    badges = [b for b in badges_raw if 'No badges yet' not in b]

    # Trainer stats for title & dex
    trainer_stats = read_stats()
    col   = read_collection()
    title = get_trainer_title(trainer_stats, col)
    n_dex = len(col['pokemon'])
    n_total = sum(len(v) for v in POKEMON_POOL.values())
    streak  = trainer_stats.get('streak', 0)
    longest = trainer_stats.get('longest_streak', 0)

    xp_b = bar(xp_disp, xp_max_disp, 24)
    sep  = '─' * 52

    streak_icon = '🔥' if streak >= 7 else '📅'
    out = [
        f' 🔥 {stage.upper():<12} Lv.{level:<4}      Trainer: {trainer}',
        f'    · {title} ·',
        f' {sep}',
        f' XP  [{xp_b}]  {xp_disp} / {xp_max_disp}',
        '',
    ]

    move_list  = [(m[0].strip(), m[1].strip(), m[3].strip()) for m in moves]
    right_items = []
    for nm, mt, desc in move_list:
        right_items.append(f'  {nm:<10} [{mt[0].upper()}]  {desc}')
    for lv in locked:
        right_items.append(f'  ? ???        [?]  unlock Lv.{lv}')

    stat_keys   = ['HP', 'Attack', 'Defense', 'Special Atk', 'Special Def', 'Speed']
    stat_labels = ['HP ', 'ATK', 'DEF', 'SPA', 'SPD', 'SPE']
    for i, (key, label) in enumerate(zip(stat_keys, stat_labels)):
        val   = stats.get(key, 0)
        b_bar = stat_bar(val)
        right = right_items[i] if i < len(right_items) else ''
        if i == 5 and badges:
            badge_names = ', '.join(
                re.search(r'\*\*(.+?)\*\*', b2).group(1)
                for b2 in badges if re.search(r'\*\*(.+?)\*\*', b2)
            )
            right = f'  BADGES: {len(badges)}  ({badge_names})'
        out.append(f' {label}  {b_bar}  {val:<3}    {right}')

    out += [
        f' {sep}',
        f' PATH: {stage} ──> (Lv.16) ──> (Lv.36)',
        f' DEX: {n_dex}/{n_total} caught   {streak_icon} Streak: {streak} days (best: {longest})',
    ]

    if col['pokemon']:
        party_str = '  '.join(
            f"{'✨' if p.get('shiny') else ''}{p['emoji']}{p['name']}{'*' if p['name'] == col['active'] else ''} Lv.{p['level']}"
            for p in col['pokemon']
        )
        out += ['', f' PARTY: {party_str}']

    return '\n'.join(out)

def get_plugin_version():
    plugin_json = Path(__file__).parent / '.claude-plugin' / 'plugin.json'
    try:
        return json.loads(plugin_json.read_text(encoding='utf-8')).get('version', '2.x')
    except Exception:
        return '2.x'

def render_statusline(plugin_mode=False):
    col = read_collection()
    prefix = f'⚡v{get_plugin_version()}  ' if plugin_mode else ''
    if not col['pokemon']:
        return f'{prefix}🎮 No buddy yet'

    # ── Section 1: Active buddy ──────────────────────────────────────────────
    active     = next((p for p in col['pokemon'] if p['name'] == col['active']), col['pokemon'][0])
    shiny_mark = '✨' if active.get('shiny') else ''
    buddy_str  = f"{shiny_mark}{active['emoji']} {active['name']} Lv.{active['level']}"

    # ── Section 2: Colored XP bar ────────────────────────────────────────────
    if not BUDDY_FILE.exists():
        return f'{prefix}{buddy_str}'
    lines    = BUDDY_FILE.read_text(encoding='utf-8').splitlines()
    xp_line  = next((l for l in lines if l.startswith('**XP**:')), '')
    xp_cur   = parse_int(xp_line)
    xp_max_m = re.search(r'\*\*XP\*\*:\s*\d+\s*/\s*(\d+)', xp_line)
    xp_max   = int(xp_max_m.group(1)) if xp_max_m else 100
    xp_floor    = xp_for_level(active['level'])
    xp_disp     = xp_cur - xp_floor
    xp_max_disp = xp_max - xp_floor
    pct      = int(xp_disp * 100 / xp_max_disp) if xp_max_disp else 0
    xp_str   = f'{colored_bar(xp_disp, xp_max_disp, 10)} {xp_disp}/{xp_max_disp}'

    # ── Section 3: Stats (streak · badges · party) ───────────────────────────
    buddy_text  = BUDDY_FILE.read_text(encoding='utf-8')
    badges_sec  = re.search(r'## Badges Earned\n(.*?)(?=\n##|\Z)', buddy_text, re.DOTALL)
    badges_raw  = re.findall(r'^- (.+)$', badges_sec.group(1), re.MULTILINE) if badges_sec else []
    badge_count = sum(1 for b in badges_raw if 'No badges yet' not in b)
    tr_stats    = read_stats()
    streak      = tr_stats.get('streak', 0)
    party_count = len(col['pokemon'])
    stats_str   = f'🔥 ×{streak}   🏅 {badge_count}   👥 {party_count}'

    # ── Section 4: Contextual display or chatter ────────────────────────────
    sep = '  ┃  ' if plugin_mode else '  │  '

    enc = None
    if ENCOUNTER_FILE.exists():
        try:
            age = datetime.now().timestamp() - ENCOUNTER_FILE.stat().st_mtime
            if age < 300:
                enc = json.loads(ENCOUNTER_FILE.read_text(encoding='utf-8'))
        except Exception:
            enc = None

    if enc and enc.get('encountered'):
        pb = enc.get("balls_poke", 0)
        gb = enc.get("balls_great", 0)
        ub = enc.get("balls_ultra", 0)
        mb = enc.get("balls_master", 0)
        balls_str = f'🔴 {pb}  🔵 {gb}  🟡 {ub}  🟣 {mb}'
        combo     = enc.get('combo', 1)
        combo_str = f'{sep}🔥 ×{combo}' if combo >= 2 else ''
        wname     = enc["wild_name"]
        wemoji    = enc["wild_emoji"]
        throws    = enc.get("throws", [])
        last_ball = throws[-1]["ball_emoji"] if throws else "🔴"
        if not enc.get('battle_won'):
            result = f'⚔️  {wemoji} {wname} fled'
        elif enc.get('no_balls'):
            result = f'⚔️  WIN  ·  no balls!  {wemoji} {wname} escaped'
        elif enc.get('caught'):
            result = f'⚔️  WIN  ·  {last_ball} caught {wemoji} {wname}!'
        else:
            result = f'⚔️  WIN  ·  {last_ball} {wemoji} {wname} broke free!'
        return f'{prefix}{buddy_str}{sep}{result}{sep}{balls_str}{combo_str}'

    chatter_str = f'💭 {get_chatter(pct)}'
    return f'{prefix}{buddy_str}{sep}{xp_str}{sep}{stats_str}{sep}{chatter_str}'

def render_card():
    """Render a shareable ASCII trainer card."""
    text     = BUDDY_FILE.read_text(encoding='utf-8')
    col      = read_collection()
    tr_stats = read_stats()

    def g(pat, default='?'):
        m = re.search(pat, text)
        return m.group(1).strip() if m else default

    stage    = g(r'\*\*Stage\*\*:\s*(\w+)')
    level    = g(r'\*\*Level\*\*:\s*(\d+)')
    trainer  = g(r'\*\*Trainer\*\*:\s*(.+)')
    xp_cur   = int(g(r'\*\*XP\*\*:\s*(\d+)', '0'))
    xp_max   = int(g(r'\*\*XP\*\*:\s*\d+\s*/\s*(\d+)', '100'))
    xp_floor    = xp_for_level(int(level) if str(level).isdigit() else 1)
    xp_disp     = xp_cur - xp_floor
    xp_max_disp = xp_max - xp_floor
    specialty = g(r'\*\*Specialty\*\*:\s*(.+)')

    title = get_trainer_title(tr_stats, col)

    # Rarest catch (highest tier first)
    rarity_order = ['mythical', 'legendary', 'rare', 'uncommon', 'common']
    rarest = None
    for tier in rarity_order:
        for p in col['pokemon']:
            if tier in p.get('rarity', ''):
                rarest = p
                break
        if rarest: break

    badges_section = re.search(r'## Badges Earned\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    badges_raw = re.findall(r'^- (.+)$', badges_section.group(1), re.MULTILINE) if badges_section else []
    badges = [b for b in badges_raw if 'No badges yet' not in b]
    badge_names = [re.search(r'\*\*(.+?)\*\*', b).group(1) for b in badges if re.search(r'\*\*(.+?)\*\*', b)]

    n_caught = len(col['pokemon'])
    n_total  = sum(len(v) for v in POKEMON_POOL.values())
    streak   = tr_stats.get('streak', 0)
    longest  = tr_stats.get('longest_streak', 0)

    emoji_map = {
        'Charmander':'🔥','Charmeleon':'🔥','Charizard':'🐉',
        'Bulbasaur':'🌿','Ivysaur':'🌿','Venusaur':'🌺',
        'Squirtle':'💧','Wartortle':'💧','Blastoise':'💦',
    }
    buddy_emoji = emoji_map.get(stage, '🎮')
    xp_b = bar(xp_disp, xp_max_disp, 20)

    W   = 54
    SEP = f' ╠{"═" * (W + 3)}╣'

    def row(content=''):
        pad = W - 1 - visual_len(content)
        return f' ║  {content}{" " * max(0, pad)}  ║'

    rarest_str = (
        f'{"✨" if rarest.get("shiny") else ""}{rarest["emoji"]} {rarest["name"]}'
        f' ({rarest["rarity"].upper().replace("-SHINY", " ✨")})'
        if rarest else 'None yet'
    )
    shiny_str = '  ✨ Shiny Caught' if tr_stats.get('caught_shiny') else ''

    grouped = _group_by_tier(col['pokemon'])

    balls_parts = []
    for emoji, key in [('🔴','balls_poke'),('🔵','balls_great'),('🟡','balls_ultra'),('🟣','balls_master')]:
        n = tr_stats.get(key, 0)
        if n: balls_parts.append(f'{emoji}×{n}')
    balls_str = '  '.join(balls_parts) if balls_parts else 'No balls'

    active_quest = get_daily_quest(tr_stats)
    quest_done   = tr_stats.get('daily_quest_done', False)
    quest_line   = (f'Quest: {active_quest["desc"]}  {"✓ DONE" if quest_done else "[active]"}'
                    if active_quest else '')

    out = [
        f' ╔{"═" * (W + 3)}╗',
        row(f'🏆  TRAINER CARD  ·  {trainer}'),
        row(f'     · {title} ·'),
        SEP,
        row('ACTIVE BUDDY'),
        row(f'{buddy_emoji} {stage.upper():<14} Lv.{level}'),
        row(f'[{xp_b}]  {xp_disp}/{xp_max_disp} XP'),
        row(f'Specialty: {specialty}'),
        SEP,
        row('ACHIEVEMENTS'),
        row(f'Badges: {len(badges)}   Dex: {n_caught}/{n_total} caught'),
        row(f'Streak: 🔥{streak} days  (best: {longest}){shiny_str}'),
        row(f'Rarest: {rarest_str}'),
        row(f'Balls:  {balls_str}'),
    ]
    if quest_line:
        out.append(row(f'📋 {quest_line}'))
    out.append(SEP)

    if badge_names:
        out.append(row('BADGES'))
        line = ''
        for bn in badge_names:
            candidate = (line + '  ·  ' + bn).lstrip(' ·  ')
            if visual_len(candidate) > W - 2:
                out.append(row(line))
                line = bn
            else:
                line = candidate
        if line:
            out.append(row(line))
        out.append(SEP)

    out += [
        row(f'Total XP earned: {tr_stats.get("total_xp_ever", 0)}'),
        row(f'Bugs fixed: {tr_stats.get("bug_fixes",0)}   '
            f'Features: {tr_stats.get("features",0)}   '
            f'Ships: {tr_stats.get("ships",0)}'),
        f' ╚{"═" * (W + 3)}╝',
    ]

    if col['pokemon']:
        TW = W + 3
        NC, LC = 24, 5
        RC = TW - NC - LC - 6

        def trow(name='', lv='', rar=''):
            n_pad = NC - visual_len(name)
            l_pad = LC - visual_len(str(lv))
            r_pad = RC - visual_len(rar)
            return (f' ║ {name}{" "*max(0,n_pad)} │ '
                    f'{lv}{" "*max(0,l_pad)} │ '
                    f'{rar}{" "*max(0,r_pad)} ║')

        tsep = f' ╠{"═"*(NC+2)}╪{"═"*(LC+2)}╪{"═"*(RC+2)}╣'
        tdiv = f' ╟{"─"*(NC+2)}┼{"─"*(LC+2)}┼{"─"*(RC+2)}╢'
        ttop = f' ╔{"═"*(NC+2)}╤{"═"*(LC+2)}╤{"═"*(RC+2)}╗'
        tbot = f' ╚{"═"*(NC+2)}╧{"═"*(LC+2)}╧{"═"*(RC+2)}╝'

        party_lines = ['', ttop, trow('  POKEMON', ' LV.', ' RARITY'), tsep]
        first_tier = True
        for tier in RARITY_TIER_ORDER:
            members = grouped.get(tier)
            if not members:
                continue
            if not first_tier:
                party_lines.append(tdiv)
            first_tier = False
            for p in members:
                mark = '✨' if p.get('shiny') else ''
                name = f'  {mark}{p["emoji"]} {p["name"]}{"*" if p["name"] == col["active"] else ""}'
                party_lines.append(trow(name, f'  {p["level"]}', f' {RARITY_LABELS_ASCII.get(tier, tier.upper())}'))
        party_lines.append(tbot)
        out += party_lines

    return '\n'.join(out)

# ── HTML trainer card (shareable — full-page interactive Pokemon theme) ────────

def _he(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
                  .replace('>', '&gt;').replace('"', '&quot;'))

def render_html_card():
    """Render a full-page interactive Pokemon-themed HTML trainer card."""
    text     = BUDDY_FILE.read_text(encoding='utf-8')
    col      = read_collection()
    tr_stats = read_stats()

    def g(pat, default='?'):
        m = re.search(pat, text)
        return m.group(1).strip() if m else default

    stage    = g(r'\*\*Stage\*\*:\s*(\w+)')
    level    = int(g(r'\*\*Level\*\*:\s*(\d+)', '1'))
    trainer  = g(r'\*\*Trainer\*\*:\s*(.+)')
    xp_cur   = int(g(r'\*\*XP\*\*:\s*(\d+)', '0'))
    xp_max   = int(g(r'\*\*XP\*\*:\s*\d+\s*/\s*(\d+)', '100'))
    xp_floor    = xp_for_level(level)
    xp_disp     = xp_cur - xp_floor
    xp_max_disp = xp_max - xp_floor
    specialty   = g(r'\*\*Specialty\*\*:\s*(.+)')
    title       = get_trainer_title(tr_stats, col)

    badges_section = re.search(r'## Badges Earned\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    badges_raw = re.findall(r'^- (.+)$', badges_section.group(1), re.MULTILINE) if badges_section else []
    badge_entries = []
    for b in badges_raw:
        if 'No badges yet' in b: continue
        nm = re.search(r'\*\*(.+?)\*\*', b)
        em = re.match(r'^\s*([^\w\s])', b)
        if nm:
            badge_entries.append((em.group(1) if em else '🏅', nm.group(1)))

    rarity_labels_html = {
        'mythical':  ('★ Mythical',  '#c084fc', '#2d1b69'),
        'legendary': ('★ Legendary', '#ffd700', '#3d2e00'),
        'rare':      ('◆ Rare',      '#60a5fa', '#1a2f5a'),
        'uncommon':  ('◈ Uncommon',  '#4ade80', '#143322'),
        'common':    ('◌ Common',    '#94a3b8', '#1e2433'),
        'starter':   ('◌ Starter',   '#fb923c', '#3d1f0a'),
    }

    grouped = _group_by_tier(col['pokemon'])
    rarest  = next((grouped[t][0] for t in RARITY_TIER_ORDER if grouped.get(t)), None)

    n_caught = len(col['pokemon'])
    n_total  = sum(len(v) for v in POKEMON_POOL.values())
    streak   = tr_stats.get('streak', 0)
    longest  = tr_stats.get('longest_streak', 0)
    total_xp = tr_stats.get('total_xp_ever', 0)
    pct = min(100, int(xp_disp / xp_max_disp * 100)) if xp_max_disp else 0

    balls_poke  = tr_stats.get('balls_poke', 0)
    balls_great = tr_stats.get('balls_great', 0)
    balls_ultra = tr_stats.get('balls_ultra', 0)
    balls_mast  = tr_stats.get('balls_master', 0)

    active_quest = get_daily_quest(tr_stats)
    quest_done   = tr_stats.get('daily_quest_done', False)

    party_rows_html = []
    for tier in RARITY_TIER_ORDER:
        members = grouped.get(tier)
        if not members:
            continue
        label, color, bg = rarity_labels_html.get(tier, ('?', '#fff', '#222'))
        for p in members:
            is_active = p['name'] == col['active']
            shiny     = '✨ ' if p.get('shiny') else ''
            mark      = ' ★' if is_active else ''
            row_cls   = 'active-row' if is_active else ''
            party_rows_html.append(
                f'<tr class="{row_cls}">'
                f'<td>{_he(shiny)}{_he(p["emoji"])} {_he(p["name"])}{_he(mark)}</td>'
                f'<td class="center">{p["level"]}</td>'
                f'<td><span class="rarity-badge" style="color:{color};background:{bg}">'
                f'{_he(label)}</span></td>'
                f'</tr>'
            )

    badge_chips = ''.join(
        f'<span class="badge-chip">{_he(em)} {_he(nm)}</span>'
        for em, nm in badge_entries
    ) or '<span class="muted">No badges yet</span>'

    def ball_item(emoji, count, label):
        if count == 0:
            return ''
        return (f'<div class="ball-item">'
                f'<span class="ball-emoji">{emoji}</span>'
                f'<span class="ball-count">×{count}</span>'
                f'<span class="ball-label">{label}</span>'
                f'</div>')

    balls_html = (
        ball_item('🔴', balls_poke,  'Poké') +
        ball_item('🔵', balls_great, 'Great') +
        ball_item('🟡', balls_ultra, 'Ultra') +
        ball_item('🟣', balls_mast,  'Master')
    ) or '<span class="muted">No balls</span>'

    rarest_str = (
        f'{rarest.get("emoji","")} {rarest["name"]} '
        f'({rarest["rarity"].upper().replace("-SHINY"," ✨")})'
        if rarest else 'None yet'
    )

    quest_html = ''
    if active_quest:
        done_badge = ('<span class="quest-done">✓ DONE</span>' if quest_done
                      else '<span class="quest-active">● Active</span>')
        quest_html = (
            f'<div class="quest-card">'
            f'<span class="quest-icon">📋</span>'
            f'<div class="quest-body">'
            f'<div class="quest-label">Daily Quest</div>'
            f'<div class="quest-desc">{_he(active_quest["desc"])}</div>'
            f'</div>'
            f'{done_badge}'
            f'</div>'
        )

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trainer Card — {_he(trainer)}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Nunito:wght@400;700;900&display=swap');
  :root {{
    --red:   #CC0000; --red2:  #ff1a1a;
    --yel:   #FFDE00; --yel2:  #ffe94d;
    --blue:  #3B4CCA; --blue2: #5b6fea;
    --dark:  #0d0e1a; --card:  #181929;
    --card2: #1f2136; --card3: #252641;
    --text:  #e8ecff; --muted: #7a82a8;
    --gold:  #FFD700;
    --glow-red: 0 0 20px rgba(204,0,0,.4);
    --glow-yel: 0 0 20px rgba(255,222,0,.4);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--dark);
    color: var(--text);
    font-family: 'Nunito', system-ui, sans-serif;
    min-height: 100vh;
    background-image:
      radial-gradient(ellipse at 20% 10%, rgba(59,76,202,.15) 0%, transparent 60%),
      radial-gradient(ellipse at 80% 90%, rgba(204,0,0,.12) 0%, transparent 60%);
  }}
  .page {{ max-width: 900px; margin: 0 auto; padding: 24px 16px 60px; }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(135deg, #1a0000 0%, #3d0000 40%, #1a0012 100%);
    border: 2px solid var(--red);
    border-radius: 20px;
    padding: 28px 32px;
    position: relative;
    overflow: hidden;
    margin-bottom: 20px;
    box-shadow: var(--glow-red), inset 0 1px 0 rgba(255,255,255,.08);
  }}
  .header::before {{
    content: '';
    position: absolute; right: -60px; top: -60px;
    width: 220px; height: 220px;
    border-radius: 50%;
    border: 40px solid rgba(204,0,0,.18);
  }}
  .header::after {{
    content: '';
    position: absolute; right: -10px; top: -10px;
    width: 100px; height: 100px;
    border-radius: 50%;
    border: 16px solid rgba(255,255,255,.06);
  }}
  .header-top {{ display: flex; align-items: center; gap: 16px; margin-bottom: 6px; }}
  .pokeball-icon {{
    width: 52px; height: 52px; border-radius: 50%;
    background: linear-gradient(180deg, var(--red) 50%, #fff 50%);
    border: 3px solid #fff;
    position: relative; flex-shrink: 0;
    box-shadow: 0 0 0 3px var(--red);
    animation: spin-slow 8s linear infinite;
  }}
  .pokeball-icon::after {{
    content: '';
    position: absolute; top: 50%; left: 50%;
    transform: translate(-50%,-50%);
    width: 14px; height: 14px; border-radius: 50%;
    background: #fff; border: 3px solid #333;
  }}
  @keyframes spin-slow {{ to {{ transform: rotate(360deg); }} }}
  .header-trainer {{ font-size: 28px; font-weight: 900; color: var(--yel); text-shadow: 0 0 12px rgba(255,222,0,.6); }}
  .header-title {{ font-size: 13px; color: var(--muted); margin-top: 2px; letter-spacing: 1px; }}
  .header-badge {{
    display: inline-block; margin-top: 10px;
    background: rgba(255,222,0,.1); border: 1px solid rgba(255,222,0,.3);
    color: var(--yel); border-radius: 20px; padding: 3px 14px; font-size: 12px; font-weight: 700;
  }}

  /* ── Grid layout ── */
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
  @media(max-width:600px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}

  /* ── Cards ── */
  .card {{
    background: var(--card); border: 1px solid rgba(255,255,255,.07);
    border-radius: 16px; padding: 20px;
    transition: transform .15s, box-shadow .15s;
  }}
  .card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,.4); }}
  .card-title {{
    font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
    color: var(--muted); margin-bottom: 14px;
    display: flex; align-items: center; gap: 8px;
  }}
  .card-title::after {{
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(90deg, rgba(255,255,255,.1), transparent);
  }}

  /* ── Buddy card ── */
  .buddy-name {{ font-size: 30px; font-weight: 900; margin-bottom: 2px; }}
  .buddy-level {{ color: var(--blue2); font-size: 16px; font-weight: 700; }}
  .buddy-spec {{ color: var(--muted); font-size: 13px; margin: 6px 0 16px; }}
  .xp-label {{
    display: flex; justify-content: space-between;
    font-size: 12px; color: var(--muted); margin-bottom: 6px;
  }}
  .xp-track {{
    height: 12px; border-radius: 6px;
    background: rgba(255,255,255,.08); overflow: hidden;
  }}
  .xp-fill {{
    height: 100%; border-radius: 6px;
    background: linear-gradient(90deg, #4ade80, #22c55e);
    box-shadow: 0 0 8px rgba(74,222,128,.5);
    transition: width 1s cubic-bezier(.4,0,.2,1);
  }}

  /* ── Stats grid ── */
  .stats-grid {{ display: grid; grid-template-columns: repeat(2,1fr); gap: 12px; }}
  .stat-item {{ background: var(--card2); border-radius: 12px; padding: 12px 14px; }}
  .stat-val {{ font-size: 22px; font-weight: 900; }}
  .stat-lbl {{ font-size: 11px; color: var(--muted); margin-top: 2px; }}
  .stat-val.gold {{ color: var(--gold); }}
  .stat-val.blue {{ color: var(--blue2); }}
  .stat-val.red  {{ color: #f87171; }}

  /* ── Party table ── */
  .party-wrap {{ margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead th {{
    font-size: 10px; letter-spacing: 2px; text-transform: uppercase;
    color: var(--muted); padding: 0 12px 10px; text-align: left;
  }}
  tbody tr {{
    border-top: 1px solid rgba(255,255,255,.05);
    transition: background .15s;
  }}
  tbody tr:hover {{ background: rgba(255,255,255,.04); }}
  tbody tr.active-row {{ background: rgba(255,222,0,.06); }}
  tbody td {{ padding: 10px 12px; font-size: 14px; }}
  tbody td.center {{ text-align: center; color: var(--blue2); font-weight: 700; }}
  .rarity-badge {{
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: 11px; font-weight: 700; letter-spacing: .5px;
  }}

  /* ── Balls ── */
  .balls-row {{ display: flex; gap: 12px; flex-wrap: wrap; }}
  .ball-item {{ display: flex; flex-direction: column; align-items: center; gap: 4px; }}
  .ball-emoji {{ font-size: 28px; }}
  .ball-count {{ font-size: 16px; font-weight: 900; }}
  .ball-label {{ font-size: 10px; color: var(--muted); }}

  /* ── Badges ── */
  .badge-chip {{
    display: inline-block; background: var(--card2);
    border: 1px solid rgba(255,255,255,.1);
    border-radius: 20px; padding: 5px 14px;
    font-size: 13px; margin: 4px;
    transition: background .15s;
  }}
  .badge-chip:hover {{ background: var(--card3); }}

  /* ── Quest card ── */
  .quest-card {{
    display: flex; align-items: center; gap: 14px;
    background: linear-gradient(135deg, rgba(59,76,202,.15), rgba(59,76,202,.05));
    border: 1px solid rgba(59,76,202,.3);
    border-radius: 14px; padding: 14px 18px; margin-bottom: 16px;
  }}
  .quest-icon {{ font-size: 24px; }}
  .quest-body {{ flex: 1; }}
  .quest-label {{ font-size: 10px; letter-spacing: 2px; color: var(--blue2); margin-bottom: 3px; }}
  .quest-desc {{ font-size: 15px; font-weight: 700; }}
  .quest-done  {{
    background: rgba(74,222,128,.15); color: #4ade80;
    border: 1px solid rgba(74,222,128,.3);
    border-radius: 20px; padding: 3px 12px; font-size: 12px; font-weight: 700; white-space: nowrap;
  }}
  .quest-active {{
    background: rgba(251,191,36,.12); color: #fbbf24;
    border: 1px solid rgba(251,191,36,.3);
    border-radius: 20px; padding: 3px 12px; font-size: 12px; font-weight: 700; white-space: nowrap;
  }}

  /* ── Rarest ── */
  .rarest-str {{ font-size: 18px; font-weight: 700; color: var(--gold); }}

  /* ── Footer ── */
  .footer {{ text-align: center; color: var(--muted); font-size: 12px; margin-top: 32px; }}
  .footer a {{ color: var(--blue2); text-decoration: none; }}
  .muted {{ color: var(--muted); font-size: 13px; }}
</style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="header">
    <div class="header-top">
      <div class="pokeball-icon"></div>
      <div>
        <div class="header-trainer">{_he(trainer)}</div>
        <div class="header-title">TRAINER CARD</div>
      </div>
    </div>
    <span class="header-badge">· {_he(title)} ·</span>
  </div>

  <!-- Quest -->
  {quest_html}

  <!-- Top grid: Buddy + Stats -->
  <div class="grid-2">
    <!-- Active Buddy -->
    <div class="card">
      <div class="card-title">Active Buddy</div>
      <div class="buddy-name">{_he(stage)}</div>
      <div class="buddy-level">Level {level}</div>
      <div class="buddy-spec">{_he(specialty)}</div>
      <div class="xp-label">
        <span>XP</span>
        <span>{xp_disp} / {xp_max_disp}</span>
      </div>
      <div class="xp-track">
        <div class="xp-fill" style="width:{pct}%"></div>
      </div>
    </div>

    <!-- Stats -->
    <div class="card">
      <div class="card-title">Stats</div>
      <div class="stats-grid">
        <div class="stat-item"><div class="stat-val gold">{streak}</div><div class="stat-lbl">🔥 Day Streak</div></div>
        <div class="stat-item"><div class="stat-val blue">{n_caught}<span style="font-size:14px;color:var(--muted)">/{n_total}</span></div><div class="stat-lbl">📖 Pokédex</div></div>
        <div class="stat-item"><div class="stat-val">{total_xp}</div><div class="stat-lbl">⚡ Total XP</div></div>
        <div class="stat-item"><div class="stat-val red">{_he(rarest_str)}</div><div class="stat-lbl">💎 Rarest</div></div>
      </div>
    </div>
  </div>

  <!-- Balls inventory -->
  <div class="card" style="margin-bottom:16px">
    <div class="card-title">Ball Inventory</div>
    <div class="balls-row">{balls_html}</div>
  </div>

  <!-- Party table -->
  <div class="card party-wrap">
    <div class="card-title">Party ({n_caught} Pokémon)</div>
    <table>
      <thead><tr><th>Pokémon</th><th style="text-align:center">Lv.</th><th>Rarity</th></tr></thead>
      <tbody>{''.join(party_rows_html) or '<tr><td colspan="3" class="muted">No Pokémon yet</td></tr>'}</tbody>
    </table>
  </div>

  <!-- Badges -->
  <div class="card" style="margin-bottom:16px">
    <div class="card-title">Badges ({len(badge_entries)})</div>
    <div>{badge_chips}</div>
  </div>

  <!-- Footer -->
  <div class="footer">
    pokemon-buddy-claude · powered by
    <a href="https://github.com/anthropics/claude-code">Claude Code</a>
  </div>

</div>
<script>
  // Animate XP bar on load
  document.querySelectorAll('.xp-fill').forEach(el => {{
    const w = el.style.width;
    el.style.width = '0';
    requestAnimationFrame(() => requestAnimationFrame(() => {{ el.style.width = w; }}));
  }});
</script>
</body>
</html>'''
    return html


def render_readme_snippet(html_path='trainer-card.html'):
    """Markdown snippet for pasting into a GitHub profile README."""
    col = read_collection()
    text = BUDDY_FILE.read_text(encoding='utf-8')
    trainer = re.search(r'\*\*Trainer\*\*:\s*(.+)', text)
    trainer = trainer.group(1).strip() if trainer else 'Trainer'
    stage = re.search(r'\*\*Stage\*\*:\s*(\w+)', text)
    stage = stage.group(1) if stage else '?'
    level = re.search(r'\*\*Level\*\*:\s*(\d+)', text)
    level = level.group(1) if level else '?'
    return (
        f'<!-- Pokemon Buddy for Claude — trainer card -->\n'
        f'<p align="center">\n'
        f'  <a href="./{html_path}">'
        f'<img src="./{html_path}" alt="{trainer} — {stage} Lv.{level}"/></a>\n'
        f'</p>\n'
        f'<p align="center">\n'
        f'  <sub>Powered by '
        f'<a href="https://github.com/anthropics/claude-code">Claude Code</a> · '
        f'<a href="https://github.com/andriar/pokemon-buddy-claude">pokemon-buddy-claude</a></sub>\n'
        f'</p>\n'
    )


def render_dex():
    """Render Pokédex — all caught Pokémon grouped by rarity."""
    col = read_collection()
    if not col['pokemon']:
        return ' No Pokémon caught yet. Earn XP to encounter wild Pokémon!'

    n_total  = sum(len(v) for v in POKEMON_POOL.values())
    n_caught = len(col['pokemon'])
    grouped  = _group_by_tier(col['pokemon'])

    W = 54
    SEP = f' ╠{"═" * (W + 3)}╣'

    def row(content=''):
        pad = W - 1 - visual_len(content)
        return f' ║  {content}{" " * max(0, pad)}  ║'

    out = [
        f' ╔{"═" * (W + 3)}╗',
        row(f'📖  POKÉDEX  ·  {n_caught} / {n_total} caught'),
        SEP,
    ]

    for tier in RARITY_TIER_ORDER:
        members = grouped.get(tier)
        if not members:
            continue
        out.append(row(RARITY_LABELS_ASCII.get(tier, tier.upper())))
        row_buf = []
        for p in members:
            mark  = '✨' if p.get('shiny') else ''
            entry = f'{mark}{p["emoji"]} {p["name"]}{"*" if p["name"] == col["active"] else ""} Lv.{p["level"]}'
            row_buf.append(entry)
            if len(row_buf) == 3:
                out.append(row(f'{row_buf[0]:<20}{row_buf[1]:<20}{row_buf[2]}'))
                row_buf = []
        if row_buf:
            out.append(row(''.join(f'{e:<20}' for e in row_buf).rstrip()))
        out.append(row())

    out[-1] = SEP  # replace trailing blank row with separator
    out += [
        row(f'Use /poke:switch <name> to change your active buddy'),
        f' ╚{"═" * (W + 3)}╝',
    ]
    return '\n'.join(out)

def render_announcement(mode, add_xp, old_level, new_level, new_xp, new_max,
                        new_stage, stat_boost, new_moves_data, evolved,
                        catch_result=None, b_emoji='', b_name='', b_desc='',
                        streak_bonus=0, streak_count=0, new_badges=None,
                        buddy_rarity=None, buddy_name='',
                        inventory_msg='', combo=1, combo_mult=1.0,
                        quest_msg='', lv_reward_msg='',
                        encounter_info=None, active_quest=None, quest_done=False):
    xp_floor    = xp_for_level(new_level)
    xp_disp     = new_xp - xp_floor
    xp_max_disp = new_max - xp_floor
    xp_b  = bar(xp_disp, xp_max_disp, 24)
    lines = []

    if mode == 'badge':
        inner = max(len(b_name) + 13, 41)
        lines += [
            f' ┌{"─" * inner}┐',
            f' │  {b_emoji}  {b_name} OBTAINED!{" " * (inner - len(b_name) - 12)}│',
            f' │  "{b_desc}"{" " * (inner - len(b_desc) - 3)}│',
            f' └{"─" * inner}┘', '',
        ]

    parts = [f'+{add_xp} XP!']
    if combo_mult > 1.0: parts.append(f'🔥 Combo ×{combo} ({combo_mult:.1f}× XP)!')
    if streak_bonus and streak_count:
        parts.append(f'🔥 Day {streak_count} streak (+{streak_bonus} bonus)!')
    if new_level > old_level: parts.append(f'★ LEVEL UP! Lv.{old_level} → Lv.{new_level}')
    if evolved:               parts.append(f'✨ EVOLVED into {evolved}!')
    lines.append(' ' + '   '.join(parts))
    if inventory_msg:
        lines.append(f' 🎁 Earned: {inventory_msg}')
    if lv_reward_msg:
        lines.append(f' 🎁 Level reward: {lv_reward_msg}')
    lines += [
        f' 🔥 {new_stage.upper():<12} Lv.{new_level:<4}',
        ' ' + '─' * 52,
        f' XP  [{xp_b}]  {xp_disp} / {xp_max_disp}',
    ]
    if stat_boost > 0:
        lines.append(f' All stats +{stat_boost}!')
    for _, name, mtype, desc in new_moves_data:
        lines.append(f' New move: {name} [{mtype}] — {desc}')
    if quest_msg:
        lines.append(f' {quest_msg}')
    elif active_quest:
        status = '✓ DONE' if quest_done else '…'
        lines.append(f' 📋 Quest: {active_quest["desc"]}  [{status}]')

    # Auto-milestone badges announcement
    if new_badges:
        for ms_emoji, ms_name, ms_desc in new_badges:
            inner = max(len(ms_name) + 13, 44)
            lines += [
                '',
                f' ┌{"─" * inner}┐',
                f' │  {ms_emoji}  {ms_name} UNLOCKED!{" " * (inner - len(ms_name) - 12)}│',
                f' │  "{ms_desc}"{" " * (inner - len(ms_desc) - 3)}│',
                f' └{"─" * inner}┘',
            ]

    if encounter_info and encounter_info.get('encountered'):
        ei       = encounter_info
        wname    = ei['wild_name']
        wemoji   = ei['wild_emoji']
        wtier    = ei['wild_tier']
        wlv      = ei['wild_level']
        is_shiny = ei.get('is_shiny', False)

        lines += ['', _ENC_DIV]

        boosted_tiers = set(BUDDY_RARITY_BOOST.get(buddy_rarity, {}).keys())
        if buddy_rarity in BUDDY_RARITY_BOOST and wtier in boosted_tiers:
            aura_msgs = {
                'mythical':  f'✦  {buddy_name.upper()}\'S AURA CALLED ACROSS DIMENSIONS!',
                'legendary': f'★  {buddy_name.upper()}\'S POWER SHOOK THE WILD!',
                'rare':      f'◆  {buddy_name.upper()}\'S PRESENCE DREW IT NEAR!',
            }
            lines.append(f' {aura_msgs.get(wtier, "")}')

        shiny_tag = '  ✨ SHINY' if is_shiny else ''
        lines += [
            f' {_TIER_BADGE.get(wtier, wtier.upper())}{shiny_tag}',
            f' {_TIER_FLAVOR.get(wtier, "")}',
            '',
            f'   {wemoji}  {wname}  ·  Lv.{wlv}',
            _ENC_DIV2,
        ]

        win_pct = ei["win_pct"]
        lines += [
            ' ⚔️   BATTLE',
            f'     {buddy_name} Lv.{new_level}  vs  {wname} Lv.{wlv}',
            f'     [{stat_bar(win_pct, 20)}]  {win_pct}% win chance',
        ]

        if not ei['battle_won']:
            lines += [
                f'     ✗  DEFEAT — {wname} fled into the wild!',
                _ENC_DIV,
            ]
        else:
            lines += ['     ✓  VICTORY!', '']

            if ei.get('no_balls'):
                lines += [
                    ' 🎯  CATCH PHASE',
                    f'     No Pokéballs left!  {wname} slipped away...',
                    _ENC_DIV,
                ]
            else:
                lines.append(' 🎯  CATCH PHASE')
                throws = ei.get('throws', [])
                for i, t in enumerate(throws):
                    lines.append(f'     Throw #{i+1}  {t["ball_emoji"]}  {t["ball_name"]}')
                    lines.append(f'               [{stat_bar(t["catch_pct"], 20)}]  {t["catch_pct"]}% catch rate')
                    if t['caught']:
                        if is_shiny:
                            w = max(len(wname) + 28, 50)
                            lines += [
                                '',
                                f' ╔{"═" * w}╗',
                                f' ║   ✨✨✨  SHINY {wemoji} {wname.upper()} CAUGHT!  ✨✨✨{" " * max(0, w - len(wname) - 27)}║',
                                f' ║   AN INCREDIBLY RARE SHINY — 1 in 200 ODDS!{" " * max(0, w - 44)}║',
                                f' ╚{"═" * w}╝',
                            ]
                        else:
                            lines += [
                                f'               ★  GOTCHA!  {wname} was caught!',
                                '               → /poke:switch to make them your buddy',
                            ]
                        break
                    else:
                        lines.append(
                            f'               💨  Broke free!  '
                            f'(🔴×{t["rem_poke"]} 🔵×{t["rem_great"]} 🟡×{t["rem_ultra"]} left)'
                        )

                if not ei['caught']:
                    lines += ['', f'     😔  Every Pokéball was used — {wname} escaped!']
                lines.append(_ENC_DIV)

        lines.append(
            f' Balls remaining:  🔴×{ei.get("balls_poke",0)}  🔵×{ei.get("balls_great",0)}'
            f'  🟡×{ei.get("balls_ultra",0)}  🟣×{ei.get("balls_master",0)}'
        )

    elif catch_result:
        # Legacy path (manual /catch command)
        tier, cname, ctype, cemoji, is_shiny = catch_result
        lines += [
            '',
            _ENC_DIV,
            f' {"✨ SHINY " if is_shiny else ""}🎉 {cemoji} {cname} added to party!',
            _ENC_DIV,
        ]

    return '\n'.join(lines)

# ── Switch buddy ─────────────────────────────────────────────────────────────

# BUDDY_TEMPLATE — see lib/data.py

def do_switch(target_name):
    col = read_collection()
    match = next((p for p in col['pokemon'] if p['name'].lower() == target_name.lower()), None)
    if not match:
        print(f"❌ {target_name} not found in your party.")
        print(f"   Party: {', '.join(p['name'] for p in col['pokemon'])}")
        sys.exit(1)

    lines, _, cur_level, cur_xp, _, cur_name = read_buddy()
    sync_active_to_collection(cur_name, cur_level, cur_xp)

    name    = match['name']
    ptype   = match['type']
    emoji   = match['emoji']
    level   = match['level']
    xp      = match['xp']
    xp_max  = xp_for_level(level + 1)

    starter = STARTER_DATA.get(name)
    trainer = re.search(r'\*\*Trainer\*\*:\s*(.+)', BUDDY_FILE.read_text(encoding='utf-8'))
    trainer = trainer.group(1).strip() if trainer else 'Trainer'

    # Stat boosts accumulate at every level divisible by 5 (+5 each time)
    total_stat_boost = sum(5 for lv in range(1, level + 1) if lv % 5 == 0)

    if starter:
        base_stats = starter['stats']
        stats = {k: v + total_stat_boost for k, v in base_stats.items()}
        evos      = starter['evolutions']
        evo_parts = [f'{name} Lv.1-{evos[0][1]-1}'] + \
                    [f'{e[0]} Lv.{evos[i][1]}-{evos[i+1][1]-1 if i+1 < len(evos) else "∞"}'
                     for i, e in enumerate(evos)]
        evo_line  = ' → '.join(evo_parts)
        specialty = starter['specialty']
        # Unlock moves already reached at the pokemon's current level
        move_defs = MOVE_UNLOCKS.get(name, {})
        moves = []
        for m in starter['moves']:
            if m[0] == '???' and m[2].startswith('Lv.'):
                lv_num = int(m[2][3:])
                if lv_num in move_defs and level >= lv_num:
                    mn, mt, md = move_defs[lv_num]
                    moves.append((mn, mt, m[2], md))
                else:
                    moves.append(m)
            else:
                moves.append(m)
    else:
        base_stats = {'HP': 40, 'Attack': 50, 'Defense': 50,
                      'Special Atk': 50, 'Special Def': 50, 'Speed': 50}
        stats    = {k: v + total_stat_boost for k, v in base_stats.items()}
        evo_line = f'{name} Lv.1+ → ???'
        moves    = [('Tackle', 'Normal', 'Lv.1', 'Basic attack'),
                    ('???',    '???',    'Lv.5',  'Learn more to unlock!')]
        specialty = ptype + ' specialist'

    moves_rows = '\n'.join(f'| {m[0]} | {m[1]} | {m[2]} | {m[3]} |' for m in moves)

    content = BUDDY_TEMPLATE.format(
        name=name, emoji=emoji, ptype=ptype, trainer=trainer,
        specialty=specialty, level=level, xp=xp, xp_max=xp_max,
        evo_line=evo_line,
        hp=stats['HP'], atk=stats['Attack'], def_=stats['Defense'],
        spa=stats['Special Atk'], spd=stats['Special Def'], spe=stats['Speed'],
        moves_rows=moves_rows, today=TODAY,
    )
    BUDDY_FILE.write_text(content, encoding='utf-8')

    col['active'] = name
    write_collection(col['active'], col['pokemon'])

    STATE_FILE.write_text(f'Switched to {name}! 🔄\n', encoding='utf-8')

    prev = cur_name
    print(f' 🔄 Switched buddy: {prev} → {emoji} {name}')
    print(f'    {name} is now your active buddy! (Lv.{level}, {xp} XP)')

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: buddy-update.py status|statusline|card|html|readme|dex|backup|import|xp|badge|switch|catch")
        sys.exit(1)

    mode = args[0]

    if mode in ('status', 'card', 'html', 'svg', 'readme', 'dex', 'switch', 'xp', 'badge') and not BUDDY_FILE.exists():
        print(f' ❌ No buddy found at {BUDDY_FILE}')
        print(f'    Run /poke:choose to pick a starter first.')
        sys.exit(1)

    if mode == 'status':
        print(render_status(BUDDY_FILE.read_text(encoding='utf-8')))
        sys.exit(0)

    if mode == 'statusline':
        plugin_mode = '--plugin' in args
        print(render_statusline(plugin_mode=plugin_mode))
        sys.exit(0)

    if mode == 'card':
        print(render_card())
        sys.exit(0)

    if mode == 'dex':
        print(render_dex())
        sys.exit(0)

    if mode in ('html', 'svg'):
        out_path = Path(args[1]) if len(args) > 1 else Path.cwd() / 'trainer-card.html'
        out_path.write_text(render_html_card(), encoding='utf-8')
        print(f' ✅ Trainer card saved: {out_path}')
        print(f'    Open in a browser — full-page interactive Pokemon-themed card.')
        sys.exit(0)

    if mode == 'readme':
        html_rel = args[1] if len(args) > 1 else 'trainer-card.html'
        print(render_readme_snippet(html_rel))
        sys.exit(0)

    if mode == 'backup':
        out_path = Path(args[1]) if len(args) > 1 else Path.cwd() / 'buddy-export.json'
        payload = {'schema': 'pokemon-buddy-export/1', 'exported_at': TODAY}
        for key, p in [('buddy', BUDDY_FILE), ('stats', STATS_FILE), ('collection', COLLECTION_FILE)]:
            payload[key] = p.read_text(encoding='utf-8') if p.exists() else None
        try:
            _, _, lvl, xp, stage, name = read_buddy()
            payload['summary'] = {'name': name, 'level': lvl, 'xp': xp, 'stage': stage}
        except Exception:
            pass
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f' ✅ Buddy backed up: {out_path}')
        print(f'    Share this file to transfer your party — restore with /poke:import.')
        sys.exit(0)

    if mode == 'import':
        import shutil
        src = Path(args[1]) if len(args) > 1 else Path.cwd() / 'buddy-export.json'
        if not src.exists():
            print(f' ❌ File not found: {src}')
            sys.exit(1)
        try:
            payload = json.loads(src.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            print(f' ❌ Invalid JSON: {e}')
            sys.exit(1)
        if payload.get('schema') != 'pokemon-buddy-export/1':
            print(f' ❌ Unknown schema: {payload.get("schema")!r} (expected pokemon-buddy-export/1)')
            sys.exit(1)
        for key, p in [('buddy', BUDDY_FILE), ('stats', STATS_FILE), ('collection', COLLECTION_FILE)]:
            if p.exists():
                shutil.copy(p, p.with_suffix(p.suffix + '.bak'))
            if payload.get(key) is not None:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(payload[key], encoding='utf-8')
        s = payload.get('summary') or {}
        when = payload.get('exported_at', '?')
        print(f' ✅ Imported {s.get("name","buddy")} (Lv {s.get("level","?")}, {s.get("xp","?")} XP, stage {s.get("stage","?")})')
        print(f'    Exported {when}. Previous party saved as *.bak — run /poke:status to verify.')
        sys.exit(0)

    if mode == 'switch':
        do_switch(args[1] if len(args) > 1 else '')
        sys.exit(0)

    if mode == 'catch':
        cname  = args[1] if len(args) > 1 else 'Pikachu'
        ctype  = args[2] if len(args) > 2 else 'Normal'
        cemoji = args[3] if len(args) > 3 else '🎮'
        rarity = args[4] if len(args) > 4 else 'caught'
        add_to_collection(cname, ctype, cemoji, rarity)
        print(f' ★ {cemoji} {cname} added to your party!')
        sys.exit(0)

    # ── xp / badge ────────────────────────────────────────────────────────────
    lines, text, old_level, old_xp, old_stage, buddy_name = read_buddy()

    add_xp = 0; log_desc = ''; badge_line = ''
    b_emoji = b_name = b_desc = ''
    streak_bonus = 0; streak_count = 0
    inventory_msg = ''; combo = 1; combo_mult = 1.0
    quest_msg = ''; lv_reward_msg = ''

    # Load stats early — needed for streak and milestone tracking
    tr_stats = read_stats()

    if mode == 'xp':
        desc    = args[1] if len(args) > 1 else ''
        base_xp = detect_xp(desc)
        log_desc = desc or 'XP awarded'

        # Combo multiplier
        combo, combo_mult = update_combo(tr_stats)

        # Streak: bonus XP for first award of the day
        bonus, streak_count, is_new_day = update_streak(tr_stats)
        if is_new_day:
            streak_bonus = bonus

        add_xp = int(base_xp * combo_mult) + streak_bonus

        # Track achievement counters + daily task count
        dl = desc.lower()
        if any(k in dl for k in ['ship','deploy','production','prod','release']):
            tr_stats['ships'] = tr_stats.get('ships', 0) + 1
        if any(k in dl for k in ['feature','complete','implement','finish']):
            tr_stats['features'] = tr_stats.get('features', 0) + 1
        if any(k in dl for k in ['bug','fix','error','issue','patch']):
            tr_stats['bug_fixes'] = tr_stats.get('bug_fixes', 0) + 1
        tr_stats['tasks_today'] = tr_stats.get('tasks_today', 0) + 1

        tr_stats['total_xp_ever'] = tr_stats.get('total_xp_ever', 0) + add_xp

        # Earn balls & berries
        inventory_msg = earn_inventory(base_xp, False, tr_stats)

    elif mode == 'badge':
        add_xp  = 50
        b_emoji = args[1] if len(args) > 1 else '🏅'
        b_name  = args[2] if len(args) > 2 else 'New Badge'
        b_desc  = args[3] if len(args) > 3 else 'Achievement unlocked'
        log_desc  = f'Earned {b_emoji} {b_name}'
        badge_line = f'- {b_emoji} **{b_name}** — *{b_desc}* `{TODAY}`'
        tr_stats['total_xp_ever'] = tr_stats.get('total_xp_ever', 0) + add_xp
        inventory_msg = earn_inventory(add_xp, True, tr_stats)

    new_xp    = old_xp + add_xp
    new_level = level_from_xp(new_xp)
    # At level cap, hold XP just shy of the next-level threshold so the bar
    # displays near-full instead of runaway numbers past the bar max.
    if new_level >= 100:
        new_level = 100
        new_xp = min(new_xp, xp_for_level(101) - 1)
    new_max   = xp_for_level(new_level + 1)
    stat_boost = sum(5 for lv in range(old_level + 1, new_level + 1) if lv % 5 == 0)

    # Evolution: pick the highest-threshold form the new level qualifies for,
    # across whatever evolution chain the buddy's starter defines.
    evolutions = STARTER_DATA.get(buddy_name, {}).get('evolutions', [])
    target_stage = buddy_name
    for evo_name, threshold, _ in evolutions:
        if new_level >= threshold:
            target_stage = evo_name
    evolved = target_stage if target_stage != old_stage else ''
    new_stage = evolved or old_stage

    move_defs      = MOVE_UNLOCKS.get(buddy_name, MOVE_UNLOCKS.get('Charmander', {}))
    new_moves_data = [(lv, *move_defs[lv]) for lv in sorted(move_defs) if old_level < lv <= new_level]

    out, last_log_idx = patch_buddy(lines, new_level, new_xp, new_max, new_stage,
                                    stat_boost, new_moves_data, mode, badge_line)

    if last_log_idx >= 0:
        out.insert(last_log_idx + 1, f'| {TODAY} | {log_desc} | +{add_xp} XP |\n')

    out = cap_journal(out)
    BUDDY_FILE.write_text(''.join(out), encoding='utf-8')

    # Sync collection
    sync_active_to_collection(buddy_name, new_level, new_xp)

    # Run wild encounter (battle + ball throw)
    base_xp_for_enc = detect_xp(args[1] if len(args) > 1 and mode == 'xp' else '') if mode == 'xp' else add_xp
    col          = read_collection()
    owned        = {p['name'] for p in col['pokemon']}
    buddy_rarity = get_buddy_rarity()
    buddy_type   = STARTER_DATA.get(buddy_name, {}).get('type', 'Normal')

    catch_result, encounter_info = run_encounter(
        base_xp_for_enc, owned, get_role_type(), buddy_rarity,
        new_level, buddy_type, tr_stats,
    )

    if catch_result:
        # Update stats flags (collection already updated inside run_encounter)
        base_tier = catch_result[0].replace('-shiny', '')
        if base_tier == 'legendary': tr_stats['caught_legendary'] = True
        if base_tier == 'mythical':  tr_stats['caught_mythical']  = True
        if catch_result[4]:          tr_stats['caught_shiny']      = True
        col = read_collection()

    # Level-up rewards (after XP resolved)
    if new_level > old_level:
        lv_reward_msg = level_up_rewards(old_level, new_level, tr_stats)

    # Daily quest check
    did_catch = catch_result is not None
    quest_msg    = check_daily_quest(tr_stats, desc if mode == 'xp' else '', did_catch)
    active_quest = get_daily_quest(tr_stats)
    quest_done   = tr_stats.get('daily_quest_done', False)

    # Write ENCOUNTER_FILE for contextual statusline
    if encounter_info.get('encountered'):
        encounter_info['combo'] = combo
        ENCOUNTER_FILE.write_text(json.dumps(encounter_info), encoding='utf-8')

    # Check and award auto milestone badges
    new_badges = check_milestones(tr_stats, col, old_level, new_level, catch_result, evolved)
    for ms_emoji, ms_name, ms_desc in new_badges:
        ms_badge_line = f'- {ms_emoji} **{ms_name}** — *{ms_desc}* `{TODAY}`'
        append_badge(ms_badge_line)

    # Persist updated stats
    write_stats(tr_stats)

    # Write chatter message for statusline (expires after 5 min)
    if mode == 'xp':
        if evolved:
            chatter_msg = f'Evolved to {new_stage}! 🎉'
        elif new_level > old_level:
            chatter_msg = f'Level {new_level}! Growing strong 💪'
        elif catch_result and catch_result[4]:
            chatter_msg = f'✨ Shiny {catch_result[1]}! 1 in 200!'
        elif catch_result and catch_result[0] in ('mythical', 'legendary'):
            chatter_msg = f'Caught {catch_result[1]}! 🧬'
        else:
            chatter_msg = f'+{add_xp} XP! Back to work ⚡'
        STATE_FILE.write_text(chatter_msg + '\n', encoding='utf-8')
    elif mode == 'badge':
        STATE_FILE.write_text(f'Badge earned! {b_emoji} {b_name} 🏅\n', encoding='utf-8')

    print(render_announcement(
        mode, add_xp, old_level, new_level, new_xp, new_max,
        new_stage, stat_boost, new_moves_data, evolved,
        catch_result, b_emoji, b_name, b_desc,
        streak_bonus, streak_count, new_badges,
        buddy_rarity, buddy_name,
        inventory_msg, combo, combo_mult,
        quest_msg, lv_reward_msg,
        encounter_info, active_quest, quest_done,
    ))

if __name__ == '__main__':
    main()
