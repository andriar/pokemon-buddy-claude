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

import os, sys, re, random, time, unicodedata, json
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.data import (
    STARTER_DATA, MOVE_UNLOCKS, RARITY_START_LEVEL, BUDDY_RARITY_BOOST,
    ENCOUNTER_RATES, POKEMON_POOL, XP_RULES, MILESTONES, TITLE_RULES, BUDDY_TEMPLATE,
    POKEBALL_TYPES, BALL_BY_RARITY, BALL_EARN_BY_XP,
    BERRY_TYPES, BERRY_DROP_RATES, POKEDEX_IDS,
    WILD_LEVELS, BASE_CATCH_RATES, TYPE_ADVANTAGE, TYPE_CHART,
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
LEVEL_CAP       = 100         # max Pokémon level; XP past cap → Exp Share
ARCHIVE_FILE    = Path.home() / '.claude' / 'buddy-log-archive.md'

SHINY_RATE        = 1 / 200   # 0.5% base (Cascade badge raises to 1/150)
STREAK_BONUS_XP   = 20        # bonus XP for first award of the day
STATS_SCHEMA_VER  = 4         # bumped: added item_bag

# ── Held items ────────────────────────────────────────────────────────────────
HELD_ITEMS = {
    'lucky_egg':   {'emoji': '🥚', 'name': 'Lucky Egg',   'desc': '+50% XP earned'},
    'choice_band': {'emoji': '🎀', 'name': 'Choice Band', 'desc': '+20% battle win chance'},
    'amulet_coin': {'emoji': '🪙', 'name': 'Amulet Coin', 'desc': '2× catch rate'},
    'shiny_charm': {'emoji': '✨', 'name': 'Shiny Charm',  'desc': '1/100 shiny rate'},
    'everstone':   {'emoji': '🪨', 'name': 'Everstone',   'desc': 'Blocks evolution'},
}
ITEM_IDS = list(HELD_ITEMS)

# Drop chances per wild tier — gated behind Rainbow badge
ITEM_DROP_TABLE = {
    'common':    [('lucky_egg', 0.01),  ('choice_band', 0.01)],
    'uncommon':  [('lucky_egg', 0.015), ('choice_band', 0.015), ('amulet_coin', 0.01)],
    'rare':      [('lucky_egg', 0.02),  ('choice_band', 0.02),  ('amulet_coin', 0.015), ('shiny_charm', 0.005)],
    'legendary': [('shiny_charm', 0.02), ('everstone', 0.02), ('amulet_coin', 0.03)],
    'mythical':  [('shiny_charm', 0.05), ('everstone', 0.03)],
}

# ── Gym badge registry ────────────────────────────────────────────────────────
# Each badge: (id, emoji, name, unlock_feature, hint)
GYM_BADGE_DATA = [
    ('boulder', '🪨', 'Boulder Badge', 'exp_share',      'catch your first Pokémon'),
    ('cascade', '💧', 'Cascade Badge', 'shiny_boost',    'catch 10 Pokémon'),
    ('thunder', '⚡', 'Thunder Badge', 'party_xp',       'reach Level 10'),
    ('rainbow', '🌈', 'Rainbow Badge', 'held_items',     'implement 5 features'),
    ('soul',    '💜', 'Soul Badge',    'breeding',       'maintain a 7-day streak'),
    ('marsh',   '🌿', 'Marsh Badge',   'double_berry',   'catch 20 Pokémon'),
    ('volcano', '🔥', 'Volcano Badge', 'early_evolution','ship 3 times'),
    ('earth',   '🌍', 'Earth Badge',   'raid_battles',   'reach Level 30'),
]
_BADGE_BY_ID    = {b[0]: b for b in GYM_BADGE_DATA}
_BADGE_UNLOCK   = {b[3]: b[0] for b in GYM_BADGE_DATA}  # feature → badge_id
_BADGE_ORDER    = [b[0] for b in GYM_BADGE_DATA]
_MILESTONE_BADGE = {   # existing milestone key → badge_id it grants
    'first_catch':  'boulder',
    'dex_10':       'cascade',
    'level_10':     'thunder',
    'streak_7':     'soul',
    'dex_20':       'marsh',
    'level_30':     'earth',
}

def has_unlock(feature, stats):
    """True if the trainer has earned the badge that unlocks this feature."""
    badge = _BADGE_UNLOCK.get(feature)
    return badge is not None and badge in stats.get('gym_badges', set())

def next_badge_hint(stats):
    """Return hint string for the next unearned badge, or ''."""
    earned = stats.get('gym_badges', set())
    for bid in _BADGE_ORDER:
        if bid not in earned:
            b = _BADGE_BY_ID[bid]
            return f'{b[1]} {b[2]}: {b[4]}'
    return 'All 8 badges earned! 🏆'

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

def displayed_form(p):
    """Return (display_name, display_emoji) for a collection entry, respecting
    evolutions of starter species. Non-starters pass through."""
    starter = STARTER_DATA.get(p['name'])
    if not starter:
        return p['name'], p.get('emoji', '?')
    stage, emj = p['name'], p.get('emoji', '?')
    for evo_name, threshold, evo_emj in starter.get('evolutions', []):
        if p.get('level', 1) >= threshold:
            stage, emj = evo_name, evo_emj
    return stage, emj

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
    while lv < LEVEL_CAP and xp >= xp_for_level(lv + 1):
        lv += 1
    return lv

CAP_XP = xp_for_level(LEVEL_CAP + 1) - 1  # highest XP stored at Lv.cap

def clamp_to_cap(xp_raw):
    """Resolve raw XP to (level, stored_xp, overflow). At cap, stored XP is
    held just shy of the next-level threshold so XP bars render near-full."""
    lv = level_from_xp(xp_raw)
    if lv >= LEVEL_CAP:
        return LEVEL_CAP, min(xp_raw, CAP_XP), max(0, xp_raw - CAP_XP)
    return lv, xp_raw, 0

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
        'gym_badges': set(),
        # Item bag
        **{f'item_{iid}': 0 for iid in ITEM_IDS},
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
    gb_section = re.search(r'## Gym Badges Earned\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    if gb_section:
        gym_badges = set(re.findall(r'^- (\S+)', gb_section.group(1), re.MULTILINE))
    else:
        # Grandfather existing trainers: auto-award badges for milestones already earned
        gym_badges = set()
        for ms_key, badge_id in _MILESTONE_BADGE.items():
            if ms_key in milestones:
                gym_badges.add(badge_id)
        if gi('features') >= 5: gym_badges.add('rainbow')
        if gi('ships')    >= 3: gym_badges.add('volcano')
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
        'gym_badges':        gym_badges,
        **{f'item_{iid}': gi(f'item_{iid}') for iid in ITEM_IDS},
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
    gb_lines = '\n'.join(f'- {bid}' for bid in _BADGE_ORDER if bid in s.get('gym_badges', set())) or '*(none yet)*'
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
        f'**tasks_today**: {s.get("tasks_today", 0)}\n'
        + ''.join(f'**item_{iid}**: {s.get(f"item_{iid}", 0)}\n' for iid in ITEM_IDS)
        + '\n'
        f'## Milestones Awarded\n\n'
        f'{ms_lines}\n\n'
        f'## Gym Badges Earned\n\n'
        f'{gb_lines}\n'
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

def streak_multiplier(streak):
    """XP multiplier from consecutive-day streak. Caps at 30 days (+60%)."""
    return 1.0 + min(streak, 30) * 0.02

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

    # Gym badges — award based on milestone triggers + counter conditions
    gym_badges = stats.get('gym_badges', set())
    for ms_key, badge_id in _MILESTONE_BADGE.items():
        if ms_key in awarded and badge_id not in gym_badges:
            gym_badges.add(badge_id)
    if stats.get('features', 0) >= 5 and 'rainbow'  not in gym_badges: gym_badges.add('rainbow')
    if stats.get('ships',    0) >= 3 and 'volcano'  not in gym_badges: gym_badges.add('volcano')
    stats['gym_badges'] = gym_badges

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

def distribute_overflow_xp(overflow, active_name, stats=None):
    """Exp Share: split overflow XP evenly across non-active party members
    under level 100. Returns list of (name, gained, old_lv, new_lv) for
    announcement. Remainder XP (too small to split) is dropped.
    Requires Boulder Badge (gated by has_unlock)."""
    if overflow <= 0:
        return []
    if stats is not None and not has_unlock('exp_share', stats):
        return []
    col = read_collection()
    eligible = [p for p in col['pokemon']
                if p['name'] != active_name and p.get('level', 1) < LEVEL_CAP]
    if not eligible:
        return []
    share = overflow // len(eligible)
    if share <= 0:
        return []
    results = []
    for p in eligible:
        old_lv = p['level']
        raw_xp = p.get('xp', xp_for_level(old_lv)) + share
        new_lv, new_xp, _ = clamp_to_cap(raw_xp)
        p['level'] = new_lv
        p['xp']    = new_xp
        results.append((p['name'], share, old_lv, new_lv))
    write_collection(col['active'], col['pokemon'])
    return results

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

def run_battle(buddy_level, buddy_type, wild_level, wild_type, choice_band=False):
    """Returns (won: bool, win_pct: int, effectiveness: float)."""
    effectiveness = TYPE_CHART.get(buddy_type or 'Normal', {}).get(wild_type, 1.0)
    base = buddy_level / max(1, wild_level) * 70 * effectiveness
    if choice_band: base += 20
    win_pct = max(5, min(95, int(base)))
    return random.randint(1, 100) <= win_pct, win_pct, effectiveness

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
    if get_held_item() == 'amulet_coin':
        mult *= 2.0
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
    # Roll berries (Marsh badge doubles drop chance)
    berry_mult = 2.0 if has_unlock('double_berry', stats) else 1.0
    for berry, chance in BERRY_DROP_RATES.get(base_xp, []):
        if random.random() < chance * berry_mult:
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
    shiny_rate = (1 / 150) if has_unlock('shiny_boost', stats) else SHINY_RATE
    held = get_held_item()
    if held == 'shiny_charm':
        shiny_rate = min(shiny_rate, 1 / 100)
    is_shiny   = random.random() < shiny_rate

    battle_won, win_pct, effectiveness = run_battle(buddy_level, buddy_type, wild_level, wild_type,
                                                    choice_band=(held == 'choice_band'))

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
        'effectiveness': effectiveness,
        'base_ts':      time.time(),
        'throw_secs':   3.0,
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
        # Item drop (Rainbow badge required)
        item_drop = None
        if has_unlock('held_items', stats):
            for iid, chance in ITEM_DROP_TABLE.get(tier, []):
                if random.random() < chance:
                    stats[f'item_{iid}'] = stats.get(f'item_{iid}', 0) + 1
                    item_drop = iid
                    break
        info['item_drop'] = item_drop
        return catch_result, info

    info['item_drop'] = None
    return None, info

def add_to_collection(name, ptype, emoji, rarity, is_shiny=False):
    col = read_collection()
    stored_rarity = (rarity + '-shiny') if is_shiny else rarity
    start_level = RARITY_START_LEVEL.get(rarity, 1)
    col['pokemon'].append({
        'name': name, 'type': ptype, 'emoji': emoji,
        'level': start_level, 'xp': xp_for_level(start_level), 'caught': TODAY,
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

def get_held_item():
    """Return held item id for active buddy, or None."""
    if not BUDDY_FILE.exists():
        return None
    m = re.search(r'\*\*HeldItem\*\*:\s*(\S+)', BUDDY_FILE.read_text(encoding='utf-8'))
    val = m.group(1) if m else 'none'
    return val if val != 'none' else None

def set_held_item(item_id):
    """Write held item to buddy file. Pass None or 'none' to unequip."""
    text = BUDDY_FILE.read_text(encoding='utf-8')
    val = item_id or 'none'
    if '**HeldItem**:' in text:
        text = re.sub(r'\*\*HeldItem\*\*:\s*\S+', f'**HeldItem**: {val}', text)
    else:
        text = re.sub(r'(\*\*Stage\*\*:.*\n)', r'\1**HeldItem**: ' + val + '\n', text, count=1)
    BUDDY_FILE.write_text(text, encoding='utf-8')

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

def _gym_badges_display(stats):
    """Compact badge row: earned badges + next target hint."""
    earned = stats.get('gym_badges', set())
    n = len(earned)
    if n == 0:
        hint = next_badge_hint(stats)
        return f'0/8 badges  →  {hint}'
    badges_str = '  '.join(
        f'{_BADGE_BY_ID[bid][1]} {_BADGE_BY_ID[bid][2]}'
        for bid in _BADGE_ORDER if bid in earned
    )
    hint = next_badge_hint(stats)
    next_str = f'  →  {hint}' if hint and n < 8 else ''
    return f'{n}/8  {badges_str}{next_str}'

def _held_item_display():
    held = get_held_item()
    if not held or held not in HELD_ITEMS:
        return 'none equipped  (use /poke:item equip <name>)'
    it = HELD_ITEMS[held]
    return f'{it["emoji"]} {it["name"]} — {it["desc"]}'

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
        f' DEX: {n_dex}/{n_total} caught   {streak_icon} Streak: {streak} days (best: {longest})  ×{streak_multiplier(streak):.2f} XP',
        f' GYM: {_gym_badges_display(trainer_stats)}',
        f' ITEM: {_held_item_display()}',
    ]

    if col['pokemon']:
        def _party_entry(p):
            dn, de = displayed_form(p)
            mark = '*' if p['name'] == col['active'] else ''
            shiny = '✨' if p.get('shiny') else ''
            return f"{shiny}{de}{dn}{mark} Lv.{p['level']}"
        party_str = '  '.join(_party_entry(p) for p in col['pokemon'])
        out += ['', f' PARTY: {party_str}']

    return '\n'.join(out)

def get_plugin_version():
    plugin_json = Path(__file__).parent / '.claude-plugin' / 'plugin.json'
    try:
        return json.loads(plugin_json.read_text(encoding='utf-8')).get('version', '2.x')
    except Exception:
        return '2.x'

def render_encounter_state(enc):
    """Timestamp-driven throw wobble. Frame = f(elapsed since base_ts)."""
    wname  = enc["wild_name"]
    wemoji = enc["wild_emoji"]
    throws = enc.get("throws", [])

    if not enc.get('battle_won'):
        return f'⚔️  {wemoji} {wname} fled'
    if enc.get('no_balls'):
        return f'⚔️  WIN  ·  no balls!  {wemoji} {wname} escaped'
    if not throws:
        return f'⚔️  WIN  ·  {wemoji} {wname}'

    base_ts    = enc.get('base_ts', 0)
    throw_secs = enc.get('throw_secs', 3.0)
    elapsed    = max(0.0, time.time() - base_ts) if base_ts else throw_secs * len(throws)
    idx        = int(elapsed // throw_secs)

    if idx < len(throws):
        ball_emj  = throws[idx].get('ball_emoji', '🔴')
        sub       = elapsed - idx * throw_secs
        if   sub < 0.75:        wobble = '·'
        elif sub < 1.5:         wobble = '· ·'
        elif sub < 2.25:        wobble = '· · ·'
        else:                   wobble = '💫'
        prefix = f'{idx+1}/{len(throws)} ' if len(throws) > 1 else ''
        return f'{prefix}{ball_emj} {wemoji} {wname}  {wobble}'

    last_ball = throws[-1]["ball_emoji"]
    if enc.get('caught'):
        return f'⚔️  WIN  ·  {last_ball} caught {wemoji} {wname}!'
    return f'⚔️  WIN  ·  {last_ball} {wemoji} {wname} broke free!'

def is_persona_on():
    """True if Pokémon Master Coach persona block present in ~/.claude/CLAUDE.md."""
    claude_md = Path.home() / '.claude' / 'CLAUDE.md'
    if not claude_md.exists():
        return False
    try:
        return 'Active Persona — Pokémon Master Coach' in claude_md.read_text(encoding='utf-8')
    except Exception:
        return False

def render_statusline(plugin_mode=False):
    col = read_collection()
    prefix = f'⚡v{get_plugin_version()}  ' if plugin_mode else ''
    persona_suffix = '  🎭' if is_persona_on() else ''
    if not col['pokemon']:
        return f'{prefix}🎮 No buddy yet{persona_suffix}'

    # ── Section 1: Active buddy ──────────────────────────────────────────────
    active     = next((p for p in col['pokemon'] if p['name'] == col['active']), col['pokemon'][0])
    shiny_mark = '✨' if active.get('shiny') else ''
    disp_name, disp_emj = displayed_form(active)
    buddy_str  = f"{shiny_mark}{disp_emj} {disp_name} Lv.{active['level']}"

    sep = '  ┃  ' if plugin_mode else '  │  '

    # ── Section 2: Colored XP bar ────────────────────────────────────────────
    if not BUDDY_FILE.exists():
        return f'{prefix}{buddy_str}{persona_suffix}'
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

    # ── Section 3: State (encounter or chatter) ─────────────────────────────
    enc = None
    if ENCOUNTER_FILE.exists():
        try:
            age = datetime.now().timestamp() - ENCOUNTER_FILE.stat().st_mtime
            if age < 300:
                enc = json.loads(ENCOUNTER_FILE.read_text(encoding='utf-8'))
        except Exception:
            enc = None

    if enc and enc.get('encountered'):
        state_str = render_encounter_state(enc)
    else:
        state_str = f'💭 {get_chatter(pct)}'

    tr_stats  = read_stats()
    streak    = tr_stats.get('streak', 0)
    streak_tag = f'  🔥{streak}' if streak >= 3 else ''

    return f'{prefix}{buddy_str}{sep}{xp_str}{sep}{state_str}{streak_tag}{persona_suffix}'

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
                dn, de = displayed_form(p)
                name = f'  {mark}{de} {dn}{"*" if p["name"] == col["active"] else ""}'
                party_lines.append(trow(name, f'  {p["level"]}', f' {RARITY_LABELS_ASCII.get(tier, tier.upper())}'))
        party_lines.append(tbot)
        out += party_lines

    return '\n'.join(out)

# ── HTML trainer card (shareable — full-page interactive Pokemon theme) ────────

def _he(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
                  .replace('>', '&gt;').replace('"', '&quot;'))

_SPRITE_BASE = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon'
_ITEM_BASE   = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items'
_BALL_SPRITES = {
    'Poké':   f'{_ITEM_BASE}/poke-ball.png',
    'Great':  f'{_ITEM_BASE}/great-ball.png',
    'Ultra':  f'{_ITEM_BASE}/ultra-ball.png',
    'Master': f'{_ITEM_BASE}/master-ball.png',
}

def sprite_url(name, shiny=False):
    dex_id = POKEDEX_IDS.get(name)
    if not dex_id:
        return ''
    return f'{_SPRITE_BASE}/shiny/{dex_id}.png' if shiny else f'{_SPRITE_BASE}/{dex_id}.png'

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

    n_caught   = len(col['pokemon'])
    n_total    = sum(len(v) for v in POKEMON_POOL.values())
    streak     = tr_stats.get('streak', 0)
    longest    = tr_stats.get('longest_streak', 0)
    total_xp   = tr_stats.get('total_xp_ever', 0)
    bug_fixes  = tr_stats.get('bug_fixes', 0)
    features   = tr_stats.get('features', 0)
    ships      = tr_stats.get('ships', 0)
    pct = min(100, int(xp_disp / xp_max_disp * 100)) if xp_max_disp else 0

    def _pct(val, cap): return min(100, round(val / cap * 100)) if cap else 0
    _xp_cap   = max(1000, (total_xp // 1000 + 1) * 1000)
    stat_bars = [
        ('🔥', 'Streak',    f'{streak}d',    f'best {longest}d', _pct(streak,    max(longest, 30)),  '#f97316'),
        ('📖', 'Pokédex',   f'{n_caught}',   f'/ {n_total}',     _pct(n_caught,  n_total),           '#22d3ee'),
        ('⚡', 'Total XP',  f'{total_xp:,}', f'/ {_xp_cap:,}',   _pct(total_xp,  _xp_cap),           '#a78bfa'),
        ('🐛', 'Bug Fixes', f'{bug_fixes}',  f'/ 20 goal',       _pct(bug_fixes, 20),                '#4ade80'),
        ('✨', 'Features',  f'{features}',   f'/ 10 goal',       _pct(features,  10),                '#fbbf24'),
        ('🚀', 'Ships',     f'{ships}',      f'/ 5 goal',        _pct(ships,     5),                 '#f472b6'),
    ]
    stats_html = ''.join(
        f'<div class="sbar-row">'
        f'<div class="sbar-meta">'
        f'<span class="sbar-lbl">{icon} {lbl}</span>'
        f'<span class="sbar-val">{val} <span class="sbar-sub">{sub}</span></span>'
        f'</div>'
        f'<div class="sbar-track">'
        f'<div class="sbar-fill" style="width:{pct}%;background:{col}"></div>'
        f'</div>'
        f'</div>'
        for icon, lbl, val, sub, pct, col in stat_bars
    )

    balls_poke  = tr_stats.get('balls_poke', 0)
    balls_great = tr_stats.get('balls_great', 0)
    balls_ultra = tr_stats.get('balls_ultra', 0)
    balls_mast  = tr_stats.get('balls_master', 0)

    active_quest = get_daily_quest(tr_stats)
    quest_done   = tr_stats.get('daily_quest_done', False)

    buddy_spr_url  = sprite_url(stage)
    buddy_img_html = (f'<img src="{buddy_spr_url}" class="buddy-sprite" alt="{_he(stage)}">'
                      if buddy_spr_url else '')

    party_rows_html = []
    for tier in RARITY_TIER_ORDER:
        members = grouped.get(tier)
        if not members:
            continue
        label, color, bg = rarity_labels_html.get(tier, ('?', '#fff', '#222'))
        for p in members:
            is_active = p['name'] == col['active']
            is_shiny  = bool(p.get('shiny'))
            mark      = ' ★' if is_active else ''
            row_cls   = 'active-row' if is_active else ''
            dn, de    = displayed_form(p)
            spr       = sprite_url(dn, shiny=is_shiny)
            shiny_sfx = ' ✨' if is_shiny else ''
            icon      = (f'<img src="{spr}" class="poke-sprite" alt="{_he(dn)}">'
                         if spr else _he(de))
            party_rows_html.append(
                f'<tr class="{row_cls}">'
                f'<td>{icon} {_he(dn)}{_he(shiny_sfx)}{_he(mark)}</td>'
                f'<td class="center">{p["level"]}</td>'
                f'<td><span class="rarity-badge" style="color:{color};background:{bg}">'
                f'{_he(label)}</span></td>'
                f'</tr>'
            )

    badge_chips = ''.join(
        f'<span class="badge-chip">{_he(em)} {_he(nm)}</span>'
        for em, nm in badge_entries
    ) or '<span class="muted">No badges yet</span>'

    def ball_item(label, count):
        if count == 0:
            return ''
        img = f'<img src="{_BALL_SPRITES[label]}" class="ball-sprite" alt="{label} Ball">'
        return (f'<div class="ball-item">'
                f'<div class="ball-img-wrap">{img}'
                f'<span class="ball-count-badge">{count}</span></div>'
                f'<span class="ball-label">{label}</span>'
                f'</div>')

    balls_html = (
        ball_item('Poké',   balls_poke) +
        ball_item('Great',  balls_great) +
        ball_item('Ultra',  balls_ultra) +
        ball_item('Master', balls_mast)
    ) or '<span class="muted">No balls</span>'

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
<meta name="description" content="{_he(trainer)} — {_he(title)} · {_he(stage)} Lv.{level} · {n_caught}/{n_total} Pokédex · {streak}d streak">
<meta property="og:type" content="profile">
<meta property="og:title" content="{_he(trainer)} — Pokémon Trainer Card">
<meta property="og:description" content="{_he(title)} · {_he(stage)} Lv.{level} · {n_caught}/{n_total} Pokédex · {streak}d streak · {total_xp:,} XP">
<meta property="og:image" content="trainer-card-og.svg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{_he(trainer)} — Pokémon Trainer Card">
<meta name="twitter:description" content="{_he(title)} · {_he(stage)} Lv.{level} · {n_caught}/{n_total} Pokédex · {streak}d streak">
<meta name="twitter:image" content="trainer-card-og.svg">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Inter:wght@400;500;600;700&display=swap');
  :root {{
    --bg:    #06070f;
    --s1:    #0b0d1a;
    --s2:    #101220;
    --s3:    #161928;
    --bdr:   rgba(255,255,255,.07);
    --bdrhi: rgba(255,255,255,.14);
    --text:  #dde1f5;
    --muted: #4e5580;
    --acc:   #6366f1;
    --viol:  #a78bfa;
    --red:   #ef4444;
    --gold:  #f59e0b;
    --green: #22c55e;
    --cyan:  #22d3ee;
    --pink:  #f472b6;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg); color: var(--text);
    font-family: 'Inter', system-ui, sans-serif;
    min-height: 100vh;
    background-image:
      radial-gradient(circle, rgba(99,102,241,.035) 1px, transparent 1px),
      radial-gradient(ellipse at 12% 20%, rgba(99,102,241,.09) 0%, transparent 50%),
      radial-gradient(ellipse at 88% 80%, rgba(167,139,250,.06) 0%, transparent 50%);
    background-size: 28px 28px, 100% 100%, 100% 100%;
  }}
  .page {{ max-width: 860px; margin: 0 auto; padding: 32px 20px 72px; }}

  /* ── Header ── */
  .header {{
    position: relative; overflow: hidden;
    border-radius: 24px; margin-bottom: 20px; padding: 36px 40px 32px;
    background: linear-gradient(135deg, #0c0a22 0%, #180a2e 60%, #0c1022 100%);
    border: 1px solid rgba(99,102,241,.22);
    box-shadow: 0 0 48px rgba(99,102,241,.1), inset 0 1px 0 rgba(255,255,255,.07);
  }}
  .header::before {{
    content: ''; position: absolute; inset: 0; pointer-events: none;
    background-image:
      linear-gradient(rgba(99,102,241,.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(99,102,241,.05) 1px, transparent 1px);
    background-size: 36px 36px;
    -webkit-mask-image: radial-gradient(ellipse at 100% 50%, black 20%, transparent 68%);
    mask-image: radial-gradient(ellipse at 100% 50%, black 20%, transparent 68%);
  }}
  .header-inner {{ position: relative; z-index: 1; display: flex; align-items: center; gap: 24px; }}
  .pokeball-svg {{
    width: 56px; height: 56px; flex-shrink: 0;
    animation: spin-slow 10s linear infinite;
    filter: drop-shadow(0 0 10px rgba(239,68,68,.5));
  }}
  @keyframes spin-slow {{ to {{ transform: rotate(360deg); }} }}
  .header-eyebrow {{
    font-size: 9px; letter-spacing: 3px; text-transform: uppercase;
    color: var(--viol); margin-bottom: 8px; font-weight: 600;
  }}
  .header-trainer {{
    font-family: 'Press Start 2P', monospace;
    font-size: 20px; line-height: 1.45; color: #fff;
    text-shadow: 0 0 24px rgba(99,102,241,.55);
    margin-bottom: 14px;
  }}
  .header-meta {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  .chip {{
    display: inline-flex; align-items: center;
    background: rgba(255,255,255,.06); border: 1px solid var(--bdr);
    border-radius: 6px; padding: 3px 10px;
    font-size: 10px; font-weight: 600; letter-spacing: .5px; color: var(--muted);
  }}
  .chip.hi {{ background: rgba(99,102,241,.12); border-color: rgba(99,102,241,.28); color: var(--viol); }}

  /* ── Grid ── */
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
  @media(max-width:600px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}

  /* ── Cards ── */
  .card {{
    background: var(--s1); border: 1px solid var(--bdr);
    border-radius: 20px; padding: 24px; will-change: transform;
  }}
  .sec-lbl {{
    font-size: 9px; letter-spacing: 3px; text-transform: uppercase;
    color: var(--muted); margin-bottom: 16px; font-weight: 600;
    display: flex; align-items: center; gap: 10px;
  }}
  .sec-lbl::after {{
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(90deg, var(--bdr), transparent);
  }}

  /* ── Buddy ── */
  .buddy-sprite-bg {{
    display: flex; justify-content: center; align-items: center;
    background: radial-gradient(circle at 50% 55%, rgba(99,102,241,.1) 0%, transparent 68%);
    border-radius: 14px; padding: 12px; margin-bottom: 16px; min-height: 108px;
  }}
  .buddy-sprite {{
    display: block; width: 96px; height: 96px; image-rendering: pixelated;
    animation: buddy-float 3s ease-in-out infinite;
  }}
  @keyframes buddy-float {{ 0%,100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-7px); }} }}
  .buddy-name {{ font-size: 20px; font-weight: 700; color: #fff; margin-bottom: 6px; }}
  .buddy-lv-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
  .lv-chip {{
    background: rgba(99,102,241,.14); border: 1px solid rgba(99,102,241,.28);
    color: var(--viol); border-radius: 5px; padding: 2px 8px;
    font-size: 10px; font-weight: 700;
  }}
  .buddy-spec {{ color: var(--muted); font-size: 12px; margin-bottom: 16px; }}
  .xp-lbl {{ display: flex; justify-content: space-between; font-size: 10px; color: var(--muted); margin-bottom: 5px; }}
  .xp-track {{ height: 5px; border-radius: 3px; background: rgba(255,255,255,.06); overflow: hidden; }}
  .xp-fill {{
    height: 100%; border-radius: 3px; position: relative; overflow: hidden;
    background: linear-gradient(90deg, var(--acc), var(--viol));
    box-shadow: 0 0 10px rgba(99,102,241,.4);
  }}
  .xp-fill::after {{
    content: ''; position: absolute; top: 0; left: -60%; width: 40%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.4), transparent);
    animation: shimmer 2s ease-in-out infinite;
  }}
  @keyframes shimmer {{ to {{ left: 130%; }} }}

  /* ── Stats bars ── */
  .sbar-row {{ margin-bottom: 11px; }}
  .sbar-row:last-child {{ margin-bottom: 0; }}
  .sbar-meta {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 5px; }}
  .sbar-lbl {{ font-size: 11px; font-weight: 600; }}
  .sbar-val {{ font-size: 11px; font-weight: 700; color: #fff; }}
  .sbar-sub {{ font-size: 10px; color: var(--muted); font-weight: 400; margin-left: 2px; }}
  .sbar-track {{ height: 5px; border-radius: 3px; background: rgba(255,255,255,.06); overflow: hidden; }}
  .sbar-fill {{ height: 100%; border-radius: 3px; position: relative; overflow: hidden; }}
  .sbar-fill::after {{
    content: ''; position: absolute; top: 0; left: -60%; width: 40%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.3), transparent);
    animation: shimmer 2.4s ease-in-out infinite;
  }}

  /* ── Ball inventory ── */
  .balls-row {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .ball-item {{ display: flex; flex-direction: column; align-items: center; gap: 6px; }}
  .ball-img-wrap {{
    position: relative; width: 52px; height: 52px;
    background: rgba(255,255,255,.04); border: 1px solid var(--bdr);
    border-radius: 12px; display: flex; align-items: center; justify-content: center;
  }}
  .ball-sprite {{ width: 32px; height: 32px; image-rendering: pixelated; }}
  .ball-count-badge {{
    position: absolute; top: -7px; right: -7px;
    background: var(--acc); color: #fff; border: 2px solid var(--bg);
    border-radius: 99px; font-size: 9px; font-weight: 700;
    padding: 1px 5px; min-width: 20px; text-align: center;
  }}
  .ball-label {{ font-size: 10px; color: var(--muted); }}

  /* ── Party table ── */
  .party-wrap {{ margin-bottom: 16px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; min-width: 340px; }}
  thead th {{
    font-size: 9px; letter-spacing: 2px; text-transform: uppercase;
    color: var(--muted); padding: 0 14px 12px; text-align: left; font-weight: 600;
  }}
  tbody tr {{ border-top: 1px solid var(--bdr); transition: background .15s; }}
  tbody tr:hover {{ background: rgba(255,255,255,.03); }}
  tbody tr.active-row {{ background: rgba(99,102,241,.07); }}
  tbody td {{ padding: 10px 14px; font-size: 13px; }}
  tbody td.center {{ text-align: center; color: var(--viol); font-weight: 700; }}
  .poke-sprite {{ width: 36px; height: 36px; image-rendering: pixelated; vertical-align: middle; margin-right: 6px; }}
  .rarity-badge {{
    display: inline-block; padding: 2px 9px; border-radius: 5px;
    font-size: 10px; font-weight: 700; letter-spacing: .3px;
  }}

  /* ── Badges ── */
  .badges-wrap {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .badge-chip {{
    display: inline-flex; align-items: center;
    background: rgba(255,255,255,.04); border: 1px solid var(--bdr);
    border-radius: 8px; padding: 6px 14px; font-size: 12px;
    font-weight: 500; cursor: default; will-change: transform;
  }}

  /* ── Quest ── */
  .quest-card {{
    display: flex; align-items: center; gap: 16px;
    background: linear-gradient(135deg, rgba(99,102,241,.08), rgba(99,102,241,.02));
    border: 1px solid rgba(99,102,241,.18); border-radius: 16px;
    padding: 16px 20px; margin-bottom: 16px;
  }}
  .quest-icon {{ font-size: 22px; flex-shrink: 0; }}
  .quest-body {{ flex: 1; }}
  .quest-label {{ font-size: 9px; letter-spacing: 2px; color: var(--viol); margin-bottom: 4px; font-weight: 600; }}
  .quest-desc {{ font-size: 14px; font-weight: 600; }}
  .quest-done {{
    background: rgba(34,197,94,.1); color: #4ade80;
    border: 1px solid rgba(34,197,94,.2);
    border-radius: 6px; padding: 4px 12px; font-size: 11px; font-weight: 700; white-space: nowrap;
  }}
  .quest-active {{
    background: rgba(245,158,11,.1); color: #fbbf24;
    border: 1px solid rgba(245,158,11,.2);
    border-radius: 6px; padding: 4px 12px; font-size: 11px; font-weight: 700; white-space: nowrap;
  }}

  /* ── Misc ── */
  .rarest-sprite {{ width: 22px; height: 22px; image-rendering: pixelated; vertical-align: middle; margin-right: 4px; }}
  .muted {{ color: var(--muted); font-size: 13px; }}
  .footer {{ text-align: center; color: var(--muted); font-size: 11px; margin-top: 40px; letter-spacing: .5px; }}
  .footer a {{ color: var(--acc); text-decoration: none; }}

  /* ── Motion initial states ── */
  .header, .quest-card, .grid-2 .card,
  .card.balls-card, .card.party-card, .card.badges-card,
  .footer, .sbar-row, tbody tr, .badge-chip {{ opacity: 0; }}
  @media (prefers-reduced-motion: reduce) {{
    .header, .quest-card, .grid-2 .card,
    .card.balls-card, .card.party-card, .card.badges-card,
    .footer, .sbar-row, tbody tr, .badge-chip {{ opacity: 1 !important; transform: none !important; }}
    .buddy-sprite {{ animation: none; }}
    .pokeball-svg {{ animation: none; }}
    .xp-fill::after {{ animation: none; }}
  }}
</style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="header">
    <div class="header-inner">
      <svg class="pokeball-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <clipPath id="top-clip"><rect x="0" y="0" width="100" height="50"/></clipPath>
          <clipPath id="bot-clip"><rect x="0" y="50" width="100" height="50"/></clipPath>
        </defs>
        <circle cx="50" cy="50" r="45" fill="#CC0000" clip-path="url(#top-clip)"/>
        <ellipse cx="35" cy="28" rx="14" ry="8" fill="rgba(255,255,255,.18)" clip-path="url(#top-clip)"/>
        <circle cx="50" cy="50" r="45" fill="#f0f0f0" clip-path="url(#bot-clip)"/>
        <path d="M 12 58 Q 50 72 88 58" fill="none" stroke="rgba(0,0,0,.08)" stroke-width="2"/>
        <circle cx="50" cy="50" r="45" fill="none" stroke="#1a1a1a" stroke-width="4.5"/>
        <rect x="5" y="46.5" width="90" height="7" fill="#1a1a1a"/>
        <circle cx="50" cy="50" r="13" fill="#1a1a1a"/>
        <circle cx="50" cy="50" r="9" fill="#ffffff"/>
        <circle cx="47" cy="47" r="2.5" fill="rgba(255,255,255,.6)"/>
      </svg>
      <div>
        <div class="header-eyebrow">Pokémon Trainer</div>
        <div class="header-trainer">{_he(trainer)}</div>
        <div class="header-meta">
          <span class="chip hi">· {_he(title)} ·</span>
          <span class="chip">Trainer Card</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Quest -->
  {quest_html}

  <!-- Top grid: Buddy + Stats -->
  <div class="grid-2">
    <div class="card">
      <div class="sec-lbl">Active Buddy</div>
      <div class="buddy-sprite-bg">{buddy_img_html}</div>
      <div class="buddy-name">{_he(stage)}</div>
      <div class="buddy-lv-row"><span class="lv-chip">Lv. {level}</span></div>
      <div class="buddy-spec">{_he(specialty)}</div>
      <div class="xp-lbl"><span>XP Progress</span><span>{xp_disp} / {xp_max_disp}</span></div>
      <div class="xp-track"><div class="xp-fill" data-xp="{pct}" style="width:0%"></div></div>
    </div>
    <div class="card">
      <div class="sec-lbl">Trainer Stats</div>
      {stats_html}
    </div>
  </div>

  <!-- Balls inventory -->
  <div class="card balls-card" style="margin-bottom:16px">
    <div class="sec-lbl">Ball Inventory</div>
    <div class="balls-row">{balls_html}</div>
  </div>

  <!-- Party table -->
  <div class="card party-card party-wrap">
    <div class="sec-lbl">Party · {n_caught} Pokémon</div>
    <table>
      <thead><tr><th>Pokémon</th><th style="text-align:center">Lv.</th><th>Rarity</th></tr></thead>
      <tbody>{''.join(party_rows_html) or '<tr><td colspan="3" class="muted">No Pokémon yet</td></tr>'}</tbody>
    </table>
  </div>

  <!-- Badges -->
  <div class="card badges-card" style="margin-bottom:16px">
    <div class="sec-lbl">Badges · {len(badge_entries)}</div>
    <div class="badges-wrap">{badge_chips}</div>
  </div>

  <!-- Footer -->
  <div class="footer">
    pokemon-buddy-claude · powered by
    <a href="https://github.com/anthropics/claude-code">Claude Code</a>
  </div>

</div>
<script type="module">
  import {{ animate, stagger, spring }} from 'https://cdn.jsdelivr.net/npm/motion@10.18.0/+esm';
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {{
    document.querySelectorAll('.xp-fill').forEach(el => {{ el.style.width = el.dataset.xp + '%'; }});
  }} else {{
    const ease = [0.22, 1, 0.36, 1];
    animate('.header',   {{ opacity: [0,1], y: [-24,0] }}, {{ easing: spring({{ stiffness:180, damping:22 }}), duration:0.7 }});
    animate('.quest-card', {{ opacity: [0,1], x: [-20,0] }}, {{ easing: ease, duration:0.45, delay:0.18 }});
    animate('.grid-2 .card', {{ opacity: [0,1], y: [20,0] }}, {{ easing: ease, duration:0.4, delay: stagger(0.1, {{ start:0.28 }}) }});
    animate('.sbar-row', {{ opacity: [0,1], x: [-10,0] }}, {{ easing: ease, duration:0.3, delay: stagger(0.06, {{ start:0.42 }}) }});
    const xpFill = document.querySelector('.xp-fill');
    if (xpFill) animate(xpFill, {{ width: ['0%', xpFill.dataset.xp + '%'] }}, {{ easing: spring({{ stiffness:80, damping:18 }}), duration:1.4, delay:0.55 }});
    animate('.card.balls-card, .card.party-card, .card.badges-card', {{ opacity: [0,1], y: [16,0] }}, {{ easing: ease, duration:0.4, delay: stagger(0.1, {{ start:0.5 }}) }});
    animate('tbody tr', {{ opacity: [0,1], x: [-10,0] }}, {{ easing: ease, duration:0.3, delay: stagger(0.035, {{ start:0.65 }}) }});
    animate('.badge-chip', {{ opacity: [0,1], scale: [0.9,1] }}, {{ easing: spring({{ stiffness:300, damping:18 }}), delay: stagger(0.08, {{ start:0.85 }}) }});
    animate('.footer', {{ opacity: [0,1], y: [8,0] }}, {{ easing: ease, duration:0.4, delay:1.1 }});
    document.querySelectorAll('.card').forEach(card => {{
      card.addEventListener('mouseenter', () => animate(card, {{ y:-3, boxShadow:'0 8px 32px rgba(0,0,0,.45)' }}, {{ duration:0.2, easing:ease }}));
      card.addEventListener('mouseleave', () => animate(card, {{ y:0, boxShadow:'none' }}, {{ duration:0.25, easing:ease }}));
    }});
    document.querySelectorAll('.badge-chip').forEach(chip => {{
      chip.addEventListener('mouseenter', () => animate(chip, {{ scale:1.05 }}, {{ duration:0.15, easing:ease }}));
      chip.addEventListener('mouseleave', () => animate(chip, {{ scale:1 }}, {{ duration:0.2,  easing:ease }}));
    }});
  }}
</script>
</body>
</html>'''
    return html


def render_og_svg():
    """Render a 1200x630 OpenGraph social-share SVG of the trainer card.

    SVG is dependency-free and accepted as og:image by most platforms
    (Discord, Slack, GitHub, Mastodon). Twitter/X require PNG — users can
    convert with any SVG→PNG tool if they need Twitter previews.
    """
    text     = BUDDY_FILE.read_text(encoding='utf-8')
    col      = read_collection()
    tr_stats = read_stats()

    def g(pat, default='?'):
        m = re.search(pat, text)
        return m.group(1).strip() if m else default

    trainer   = g(r'\*\*Trainer\*\*:\s*(.+)')
    stage     = g(r'\*\*Stage\*\*:\s*(\w+)')
    level     = int(g(r'\*\*Level\*\*:\s*(\d+)', '1'))
    specialty = g(r'\*\*Specialty\*\*:\s*(.+)')
    title     = get_trainer_title(tr_stats, col)
    streak    = tr_stats.get('streak', 0)
    total_xp  = tr_stats.get('total_xp_ever', 0)
    n_caught  = len(col['pokemon'])
    n_total   = sum(len(v) for v in POKEMON_POOL.values())
    spr       = sprite_url(stage) or ''

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0b0d1a"/>
      <stop offset="1" stop-color="#1a1033"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="40" y="40" width="1120" height="550" rx="24" fill="#101220" stroke="#a78bfa" stroke-width="2" opacity="0.9"/>
  <text x="90" y="130" fill="#a78bfa" font-family="monospace" font-size="24" font-weight="700">POKÉMON TRAINER CARD</text>
  <text x="90" y="210" fill="#dde1f5" font-family="sans-serif" font-size="72" font-weight="800">{_he(trainer)}</text>
  <text x="90" y="260" fill="#f59e0b" font-family="sans-serif" font-size="30" font-weight="600">{_he(title)}</text>
  <text x="90" y="300" fill="#4e5580" font-family="sans-serif" font-size="24">{_he(specialty)}</text>
  <image href="{spr}" x="820" y="140" width="300" height="300"/>
  <text x="820" y="470" fill="#dde1f5" font-family="sans-serif" font-size="42" font-weight="700">{_he(stage)}</text>
  <text x="820" y="510" fill="#a78bfa" font-family="monospace" font-size="28">Lv. {level}</text>
  <g font-family="sans-serif" fill="#dde1f5">
    <text x="90" y="440" font-size="22" fill="#4e5580">POKÉDEX</text>
    <text x="90" y="480" font-size="40" font-weight="700">{n_caught}<tspan fill="#4e5580" font-size="24"> / {n_total}</tspan></text>
    <text x="340" y="440" font-size="22" fill="#4e5580">STREAK</text>
    <text x="340" y="480" font-size="40" font-weight="700" fill="#f97316">{streak}<tspan fill="#4e5580" font-size="24">d</tspan></text>
    <text x="570" y="440" font-size="22" fill="#4e5580">TOTAL XP</text>
    <text x="570" y="480" font-size="40" font-weight="700" fill="#a78bfa">{total_xp:,}</text>
  </g>
  <text x="90" y="560" fill="#4e5580" font-family="monospace" font-size="18">/poke — a Pokémon companion for Claude Code</text>
</svg>
'''


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


def render_dex(filter_arg=None):
    """Render Pokédex — all caught Pokémon grouped by rarity.

    filter_arg: optional — a rarity tier name (common/uncommon/rare/legendary/
    mythical/starter/shiny) or a Pokémon type (fire/water/grass/etc.) to
    narrow the view. Case-insensitive.
    """
    col = read_collection()
    if not col['pokemon']:
        return ' No Pokémon caught yet. Earn XP to encounter wild Pokémon!'

    n_total  = sum(len(v) for v in POKEMON_POOL.values())
    n_caught = len(col['pokemon'])

    filter_mode = None  # 'tier' | 'type' | 'shiny' | None
    filter_key  = None
    if filter_arg:
        key = filter_arg.strip().lower()
        if key == 'shiny':
            filter_mode, filter_key = 'shiny', None
        elif key in RARITY_TIER_ORDER:
            filter_mode, filter_key = 'tier', key
        else:
            filter_mode, filter_key = 'type', key

    pool = col['pokemon']
    if filter_mode == 'shiny':
        pool = [p for p in pool if p.get('shiny')]
    elif filter_mode == 'tier':
        pool = [p for p in pool if p.get('rarity') == filter_key]
    elif filter_mode == 'type':
        pool = [p for p in pool if p.get('type', '').lower() == filter_key]

    grouped = _group_by_tier(pool)

    W = 54
    SEP = f' ╠{"═" * (W + 3)}╣'

    def row(content=''):
        pad = W - 1 - visual_len(content)
        return f' ║  {content}{" " * max(0, pad)}  ║'

    if filter_mode == 'shiny':
        header = f'📖  POKÉDEX · SHINY  ·  {len(pool)} / {n_caught} caught'
    elif filter_mode:
        header = f'📖  POKÉDEX · {filter_key.upper()}  ·  {len(pool)} / {n_caught} caught'
    else:
        header = f'📖  POKÉDEX  ·  {n_caught} / {n_total} caught'

    out = [
        f' ╔{"═" * (W + 3)}╗',
        row(header),
        SEP,
    ]

    if not pool:
        out += [
            row(f'No Pokémon match "{filter_arg}".'),
            row('Try: common, uncommon, rare, legendary, mythical,'),
            row('     starter, shiny, or a type (fire, water, ...).'),
            f' ╚{"═" * (W + 3)}╝',
        ]
        return '\n'.join(out)

    for tier in RARITY_TIER_ORDER:
        members = grouped.get(tier)
        if not members:
            continue
        out.append(row(RARITY_LABELS_ASCII.get(tier, tier.upper())))
        row_buf = []
        for p in members:
            mark  = '✨' if p.get('shiny') else ''
            dn, de = displayed_form(p)
            entry = f'{mark}{de} {dn}{"*" if p["name"] == col["active"] else ""} Lv.{p["level"]}'
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
                        encounter_info=None, active_quest=None, quest_done=False,
                        exp_share=None, streak_mult=1.0, lucky_mult=1.0,
                        item_drop=None):
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

    xp_mults = [m for m in [streak_mult, lucky_mult] if m > 1.0]
    mult_tag  = ' ×' + '×'.join(f'{m:.2f}' for m in xp_mults) if xp_mults else ''
    xp_label  = f'+{add_xp} XP{mult_tag}' if mult_tag else f'+{add_xp} XP!'
    parts = [xp_label]
    if combo_mult > 1.0: parts.append(f'🔥 Combo ×{combo} ({combo_mult:.1f}× XP)!')
    if streak_bonus and streak_count:
        parts.append(f'🔥 Day {streak_count} streak (+{streak_bonus} bonus)!')
    if new_level > old_level: parts.append(f'★ LEVEL UP! Lv.{old_level} → Lv.{new_level}')
    if evolved:               parts.append(f'✨ EVOLVED into {evolved}!')
    lines.append(' ' + '   '.join(parts))
    if inventory_msg:
        lines.append(f' 🎁 Earned: {inventory_msg}')
    if item_drop and item_drop in HELD_ITEMS:
        it = HELD_ITEMS[item_drop]
        lines.append(f' 💎 Item drop! {it["emoji"]} {it["name"]} added to bag — {it["desc"]}')
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
    if exp_share:
        lines.append(f' 🔀 Exp Share ({len(exp_share)} party member{"s" if len(exp_share) != 1 else ""}, +{exp_share[0][1]} XP each):')
        for name, _gained, olv, nlv in exp_share:
            lu = f'  ★ Lv.{olv}→{nlv}' if nlv > olv else ''
            lines.append(f'    • {name} Lv.{nlv}{lu}')
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

        win_pct       = ei["win_pct"]
        eff           = ei.get("effectiveness", 1.0)
        eff_str       = (' ⚔️  super effective!' if eff >= 2.0
                         else ' ⚠️  not very effective...' if eff == 0.5
                         else ' ✗  no effect!' if eff == 0.0
                         else '')
        lines += [
            ' ⚔️   BATTLE',
            f'     {buddy_name} Lv.{new_level}  vs  {wname} Lv.{wlv}',
            f'     [{stat_bar(win_pct, 20)}]  {win_pct}% win chance{eff_str}',
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

STARTER_CHOICES = [
    ('Charmander', 'Fire',     '🔥'),
    ('Bulbasaur',  'Grass',    '🌿'),
    ('Squirtle',   'Water',    '💧'),
    ('Pikachu',    'Electric', '⚡'),
    ('Gastly',     'Ghost',    '👻'),
    ('Dratini',    'Dragon',   '🐉'),
    ('Geodude',    'Rock',     '🪨'),
    ('Abra',       'Psychic',  '🧠'),
    ('Machop',     'Fighting', '🥊'),
    ('Umbreon',    'Dark',     '🌑'),
]

def _resolve_starter(arg):
    a = (arg or '').strip()
    if a.isdigit():
        idx = int(a) - 1
        if 0 <= idx < len(STARTER_CHOICES):
            return STARTER_CHOICES[idx]
    for entry in STARTER_CHOICES:
        if entry[0].lower() == a.lower():
            return entry
    return None

def _build_buddy_content(name, ptype, emoji, trainer, level, xp):
    xp_max = xp_for_level(level + 1)
    # Stat boosts accumulate at every level divisible by 5 (+5 each time)
    total_stat_boost = sum(5 for lv in range(1, level + 1) if lv % 5 == 0)
    starter = STARTER_DATA.get(name)

    # Derive current evolution stage from level so switching back to an evolved
    # starter preserves its form (e.g. Lv.16 Charmander → Charmeleon).
    stage, stage_emoji = name, emoji
    for evo_name, threshold, evo_emoji in (starter or {}).get('evolutions', []):
        if level >= threshold:
            stage, stage_emoji = evo_name, evo_emoji

    if starter:
        base_stats = starter['stats']
        specialty  = starter['specialty']
        evos       = starter['evolutions']
        evo_parts = [f'{name} Lv.1-{evos[0][1]-1}'] + \
                    [f'{e[0]} Lv.{evos[i][1]}-{evos[i+1][1]-1 if i+1 < len(evos) else "∞"}'
                     for i, e in enumerate(evos)]
        evo_line = ' → '.join(evo_parts)
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
        specialty = f'{ptype} specialist'
        evo_line  = f'{name} Lv.1+ → ???'
        moves = [('Tackle', 'Normal', 'Lv.1', 'Basic attack'),
                 ('???',    '???',    'Lv.5',  'Learn more to unlock!')]

    stats = {k: v + total_stat_boost for k, v in base_stats.items()}
    moves_rows = '\n'.join(f'| {m[0]} | {m[1]} | {m[2]} | {m[3]} |' for m in moves)

    return BUDDY_TEMPLATE.format(
        name=name, emoji=emoji, stage=stage, stage_emoji=stage_emoji,
        ptype=ptype, trainer=trainer,
        specialty=specialty, level=level, xp=xp, xp_max=xp_max,
        evo_line=evo_line,
        hp=stats['HP'], atk=stats['Attack'], def_=stats['Defense'],
        spa=stats['Special Atk'], spd=stats['Special Def'], spe=stats['Speed'],
        moves_rows=moves_rows, today=TODAY,
    )

def do_choose(target_name, trainer=None):
    pick = _resolve_starter(target_name)
    if not pick:
        names = ', '.join(n for n, _, _ in STARTER_CHOICES)
        print(f' ❌ Unknown starter: {target_name!r}')
        print(f'    Pick one of: {names}')
        sys.exit(1)
    name, default_type, default_emoji = pick

    if BUDDY_FILE.exists():
        col = read_collection()
        if not any(p['name'].lower() == name.lower() for p in col['pokemon']):
            starter = STARTER_DATA.get(name, {})
            add_to_collection(name, starter.get('type', default_type),
                              starter.get('emoji', default_emoji), 'starter')
        do_switch(name)
        return

    if trainer is None:
        trainer = os.environ.get('USER') or 'Trainer'

    starter = STARTER_DATA.get(name)
    ptype = starter['type']  if starter else default_type
    emoji = starter['emoji'] if starter else default_emoji
    level, xp = 1, 0

    content = _build_buddy_content(name, ptype, emoji, trainer, level, xp)
    BUDDY_FILE.parent.mkdir(parents=True, exist_ok=True)
    BUDDY_FILE.write_text(content, encoding='utf-8')

    write_collection(name, [{
        'name': name, 'type': ptype, 'emoji': emoji,
        'level': level, 'xp': xp, 'caught': TODAY, 'rarity': 'starter',
    }])

    STATE_FILE.write_text(f'Starter chosen: {name}! 🎉\n', encoding='utf-8')

    print(f' 🎉 Welcome, Trainer {trainer}!')
    print(f'    {emoji} {name} is now your active buddy (Lv.{level}, {xp} XP).')
    print(f'    Earn XP with /poke:xp <task> — your journey begins now!')

def do_switch(target_name):
    col = read_collection()
    match = next((p for p in col['pokemon'] if p['name'].lower() == target_name.lower()), None)
    if not match:
        print(f"❌ {target_name} not found in your party.")
        print(f"   Party: {', '.join(p['name'] for p in col['pokemon'])}")
        sys.exit(1)

    lines, _, cur_level, cur_xp, _, cur_name = read_buddy()
    sync_active_to_collection(cur_name, cur_level, cur_xp)

    trainer = re.search(r'\*\*Trainer\*\*:\s*(.+)', BUDDY_FILE.read_text(encoding='utf-8'))
    trainer = trainer.group(1).strip() if trainer else 'Trainer'

    name, ptype, emoji = match['name'], match['type'], match['emoji']
    level, xp = match['level'], match['xp']
    # Heal legacy collection rows where xp was stored as 0 for high-level catches
    # (caused negative XP bar like -2900/150 on switch).
    xp = max(xp, xp_for_level(level))

    content = _build_buddy_content(name, ptype, emoji, trainer, level, xp)
    BUDDY_FILE.write_text(content, encoding='utf-8')

    col['active'] = name
    write_collection(col['active'], col['pokemon'])

    disp_name, disp_emj = displayed_form(match)
    STATE_FILE.write_text(f'Switched to {disp_name}! 🔄\n', encoding='utf-8')

    print(f' 🔄 Switched buddy: {cur_name} → {disp_emj} {disp_name}')
    print(f'    {disp_name} is now your active buddy! (Lv.{level}, {xp} XP)')

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: buddy-update.py status|statusline|card|html|og|readme|dex|backup|import|xp|xp-auto|badge|choose|switch|catch|purge")
        sys.exit(1)

    mode = args[0]

    if mode in ('status', 'card', 'html', 'svg', 'og', 'readme', 'dex', 'switch', 'xp', 'xp-auto', 'badge') and not BUDDY_FILE.exists():
        print(f' ❌ No buddy found at {BUDDY_FILE}')
        print(f'    Run /poke:choose to pick a starter first.')
        sys.exit(1)

    if mode == 'choose':
        do_choose(args[1] if len(args) > 1 else '')
        sys.exit(0)

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
        filter_arg = args[1] if len(args) > 1 else None
        print(render_dex(filter_arg))
        sys.exit(0)

    if mode in ('html', 'svg'):
        out_path = Path(args[1]) if len(args) > 1 else Path.cwd() / 'trainer-card.html'
        out_path.write_text(render_html_card(), encoding='utf-8')
        og_path = out_path.with_name('trainer-card-og.svg')
        og_path.write_text(render_og_svg(), encoding='utf-8')
        print(f' ✅ Trainer card saved: {out_path}')
        print(f' ✅ Social share image: {og_path}')
        print(f'    Open in a browser — full-page interactive Pokemon-themed card.')
        sys.exit(0)

    if mode == 'purge':
        import shutil
        scope = args[1].lower() if len(args) > 1 else 'all'
        claude_dir = BUDDY_FILE.parent

        plugin_targets = [
            claude_dir / 'pokemon-buddy-plugin.json',
            claude_dir / 'buddy-encounter.json',
            claude_dir / 'buddy-version',
        ]
        plugin_dirs = [claude_dir / 'buddy-v1-backup']
        data_targets = [BUDDY_FILE, COLLECTION_FILE, STATS_FILE, STATE_FILE, ARCHIVE_FILE]

        removed = []

        # Always: unwire statusLine (restore backup if present)
        settings_file = claude_dir / 'settings.json'
        if settings_file.exists():
            try:
                settings = json.loads(settings_file.read_text(encoding='utf-8'))
            except Exception:
                settings = None
            if isinstance(settings, dict):
                current = settings.get('statusLine')
                cur_cmd = current.get('command') if isinstance(current, dict) else ''
                if 'buddy-update.py' in (cur_cmd or ''):
                    if '_statusLineBackup' in settings:
                        settings['statusLine'] = settings.pop('_statusLineBackup')
                        removed.append('settings.json:statusLine (restored backup)')
                    else:
                        settings.pop('statusLine', None)
                        removed.append('settings.json:statusLine')
                # remove marketplace entry
                mps = settings.get('extraKnownMarketplaces')
                if isinstance(mps, dict) and 'pokemon-buddy-claude' in mps:
                    mps.pop('pokemon-buddy-claude')
                    if not mps:
                        settings.pop('extraKnownMarketplaces', None)
                    removed.append('settings.json:extraKnownMarketplaces.pokemon-buddy-claude')
                settings_file.write_text(json.dumps(settings, indent=2), encoding='utf-8')

        targets = list(plugin_targets)
        if scope == 'all':
            targets += data_targets

        for p in targets:
            if p.exists():
                p.unlink()
                removed.append(p.name)
        for d in plugin_dirs:
            if d.exists():
                shutil.rmtree(d)
                removed.append(d.name + '/')

        if removed:
            label = 'clean uninstall' if scope == 'all' else 'plugin uninstall (data preserved)'
            print(f' ✅ Purge complete — {label}:')
            for name in removed:
                print(f'    • {name}')
        else:
            print(' ℹ️  Nothing to purge.')

        if scope != 'all':
            kept = [p.name for p in data_targets if p.exists()]
            if kept:
                print('\n 💾 Preserved (will auto-restore on reinstall):')
                for name in kept:
                    print(f'    • {name}')
        sys.exit(0)

    if mode == 'og':
        out_path = Path(args[1]) if len(args) > 1 else Path.cwd() / 'trainer-card-og.svg'
        out_path.write_text(render_og_svg(), encoding='utf-8')
        print(f' ✅ Social share image saved: {out_path}')
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

    if mode == 'item':
        sub = args[1] if len(args) > 1 else 'list'
        tr_stats = read_stats()
        if sub == 'list':
            held = get_held_item()
            print(' 💼 Item Bag:')
            for iid, info in HELD_ITEMS.items():
                count = tr_stats.get(f'item_{iid}', 0)
                equipped = ' ← equipped' if iid == held else ''
                print(f'   {info["emoji"]} {info["name"]:<14} ×{count}  — {info["desc"]}{equipped}')
            if not held:
                print('\n No item equipped. Use: /poke:item equip <item_name>')
        elif sub == 'equip':
            item_name = args[2].lower().replace(' ', '_') if len(args) > 2 else ''
            # Accept partial name match
            match = next((iid for iid in ITEM_IDS if item_name in iid or item_name in HELD_ITEMS[iid]['name'].lower()), None)
            if not match:
                print(f' ❌ Unknown item: {args[2] if len(args) > 2 else "?"}')
                print(f'    Valid items: {", ".join(ITEM_IDS)}')
            elif tr_stats.get(f'item_{match}', 0) < 1:
                it = HELD_ITEMS[match]
                print(f' ❌ You don\'t have {it["emoji"]} {it["name"]} in your bag.')
            else:
                set_held_item(match)
                it = HELD_ITEMS[match]
                print(f' {it["emoji"]} Equipped {it["name"]}! Effect: {it["desc"]}')
        elif sub == 'unequip':
            set_held_item(None)
            print(' Item unequipped.')
        else:
            print(f' Usage: buddy-update.py item list|equip <name>|unequip')
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
    streak_bonus = 0; streak_count = 0; streak_mult = 1.0
    inventory_msg = ''; combo = 1; combo_mult = 1.0
    quest_msg = ''; lv_reward_msg = ''

    # Load stats early — needed for streak and milestone tracking
    tr_stats = read_stats()

    if mode in ('xp', 'xp-auto'):
        is_auto = (mode == 'xp-auto')
        if is_auto:
            try:    base_xp = max(0, int(args[1])) if len(args) > 1 else 0
            except ValueError: base_xp = 0
            if base_xp <= 0:
                sys.exit(0)  # no-op: don't trigger encounters or state changes
            tok_summary = args[2] if len(args) > 2 else ''
            desc     = f'Auto XP from tokens{" (" + tok_summary + ")" if tok_summary else ""}'
            log_desc = desc
        else:
            desc    = args[1] if len(args) > 1 else ''
            base_xp = detect_xp(desc)
            log_desc = desc or 'XP awarded'

        # Combo multiplier — skipped for auto (every turn shouldn't bump combo)
        if is_auto:
            combo, combo_mult = 1, 1.0
        else:
            combo, combo_mult = update_combo(tr_stats)

        # Streak: bonus XP for first award of the day + multiplier for active streak
        bonus, streak_count, is_new_day = update_streak(tr_stats)
        if is_new_day:
            streak_bonus = bonus
        streak_mult = streak_multiplier(tr_stats.get('streak', 1))
        lucky_mult  = 1.5 if get_held_item() == 'lucky_egg' else 1.0

        add_xp = int(base_xp * combo_mult * streak_mult * lucky_mult) + streak_bonus

        # Track achievement counters + daily task count (keyword-driven → auto mode skips)
        if not is_auto:
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

    # At cap, excess XP flows to party via Exp Share.
    new_level, new_xp, overflow_xp = clamp_to_cap(old_xp + add_xp)
    new_max   = xp_for_level(new_level + 1)
    stat_boost = sum(5 for lv in range(old_level + 1, new_level + 1) if lv % 5 == 0)

    # Evolution: pick the highest-threshold form the new level qualifies for,
    # across whatever evolution chain the buddy's starter defines.
    # Volcano badge unlocks evolution 1 level earlier. Everstone blocks all.
    evo_offset = -1 if has_unlock('early_evolution', tr_stats) else 0
    evolutions = STARTER_DATA.get(buddy_name, {}).get('evolutions', [])
    target_stage = buddy_name
    if get_held_item() != 'everstone':
        for evo_name, threshold, _ in evolutions:
            if new_level >= threshold + evo_offset:
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

    exp_share = distribute_overflow_xp(overflow_xp, buddy_name, tr_stats) if overflow_xp else []

    # Run wild encounter (battle + ball throw)
    if mode == 'xp':
        base_xp_for_enc = detect_xp(args[1] if len(args) > 1 else '')
    elif mode == 'xp-auto':
        base_xp_for_enc = base_xp
    else:
        base_xp_for_enc = add_xp
    col          = read_collection()
    owned        = {p['name'] for p in col['pokemon']}
    buddy_rarity = get_buddy_rarity()
    buddy_type   = STARTER_DATA.get(buddy_name, {}).get('type', 'Normal')
    # role_type biases which wild Pokémon appear — suppressed in auto mode
    enc_role = None if mode == 'xp-auto' else get_role_type()

    catch_result, encounter_info = run_encounter(
        base_xp_for_enc, owned, enc_role, buddy_rarity,
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
    quest_msg    = check_daily_quest(tr_stats, desc if mode in ('xp', 'xp-auto') else '', did_catch)
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
    if mode in ('xp', 'xp-auto'):
        if evolved:
            chatter_msg = f'Evolved to {new_stage}! 🎉'
        elif exp_share:
            chatter_msg = f'Lv.100! Exp Share → {len(exp_share)} party 🔀'
        elif new_level > old_level:
            hint = next_badge_hint(tr_stats)
            chatter_msg = f'Level {new_level}! Next: {hint}' if hint else f'Level {new_level}! Growing strong 💪'
        elif catch_result and catch_result[4]:
            chatter_msg = f'✨ Shiny {catch_result[1]}! 1 in 200!'
        elif catch_result and catch_result[0] in ('mythical', 'legendary'):
            chatter_msg = f'Caught {catch_result[1]}! 🧬'
        else:
            chatter_msg = f'+{add_xp} XP! Back to work ⚡'
        STATE_FILE.write_text(chatter_msg + '\n', encoding='utf-8')
    elif mode == 'badge':
        STATE_FILE.write_text(f'Badge earned! {b_emoji} {b_name} 🏅\n', encoding='utf-8')

    item_drop = encounter_info.get('item_drop') if encounter_info else None
    print(render_announcement(
        mode, add_xp, old_level, new_level, new_xp, new_max,
        new_stage, stat_boost, new_moves_data, evolved,
        catch_result, b_emoji, b_name, b_desc,
        streak_bonus, streak_count, new_badges,
        buddy_rarity, buddy_name,
        inventory_msg, combo, combo_mult,
        quest_msg, lv_reward_msg,
        encounter_info, active_quest, quest_done,
        exp_share, streak_mult, lucky_mult, item_drop,
    ))

if __name__ == '__main__':
    main()
