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
    REGIONAL_FORMS, REGIONAL_CATCH_CHANCE,
    TRADE_EVOLUTIONS, WILD_EVOLUTIONS,
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
RAID_FILE       = Path.home() / '.claude' / 'buddy-raid.json'
UPDATE_CACHE    = Path.home() / '.claude' / 'buddy-update-status.json'
UPDATE_CHECK_TTL = 86400      # 24h between GitHub release polls
UPDATE_REPO      = 'andriar/pokemon-buddy-claude'
AUTH_FILE       = Path.home() / '.claude' / 'buddy-auth.json'
HUB_API_BASE    = os.environ.get('POKE_HUB_API', 'https://pokehub-api.andriar.com')
HUB_WEB_BASE    = os.environ.get('POKE_HUB_WEB', 'https://pokehub.andriar.com')
TODAY           = date.today().strftime('%Y-%m-%d')
LOG_CAP         = 15
LEVEL_CAP       = 100         # max Pokémon level; XP past cap → Exp Share
ARCHIVE_FILE    = Path.home() / '.claude' / 'buddy-log-archive.md'

SHINY_RATE        = 1 / 200   # 0.5% base (Cascade badge raises to 1/150)
STREAK_BONUS_XP   = 20        # bonus XP for first award of the day
STATS_SCHEMA_VER  = 7         # bumped: PoGo-style XP curve (v2.32)

# ── Anti-cheat (F17) ─────────────────────────────────────────────────────────
DAILY_XP_CAP_FLOOR = 2000   # baseline daily cap for new trainers
DAILY_XP_CAP_PER_LV = 100   # cap += per highest-level Pokémon in collection
DAILY_XP_CAP       = DAILY_XP_CAP_FLOOR  # legacy export — actual cap is dynamic via daily_cap_for()
XP_DEDUP_WINDOW    = 300    # 5 min — same desc rejected
BATTLE_STAMINA_MAX = 3      # gym battles allowed before regen required
BATTLE_REGEN_SECS  = 1800   # 30 min per stamina point

# ── Natures (F13) ────────────────────────────────────────────────────────────
# (name, up_stat, down_stat). 5 neutral natures (up == down) have no effect.
NATURES = [
    ('Hardy','ATK','ATK'),  ('Lonely','ATK','DEF'), ('Brave','ATK','SPE'),
    ('Adamant','ATK','SPA'),('Naughty','ATK','SPD'),
    ('Bold','DEF','ATK'),   ('Docile','DEF','DEF'), ('Relaxed','DEF','SPE'),
    ('Impish','DEF','SPA'), ('Lax','DEF','SPD'),
    ('Timid','SPE','ATK'),  ('Hasty','SPE','DEF'),  ('Serious','SPE','SPE'),
    ('Jolly','SPE','SPA'),  ('Naive','SPE','SPD'),
    ('Modest','SPA','ATK'), ('Mild','SPA','DEF'),   ('Quiet','SPA','SPE'),
    ('Bashful','SPA','SPA'),('Rash','SPA','SPD'),
    ('Calm','SPD','ATK'),   ('Gentle','SPD','DEF'), ('Sassy','SPD','SPE'),
    ('Careful','SPD','SPA'),('Quirky','SPD','SPD'),
]

def pick_nature():
    return random.choice(NATURES)[0]

def nature_info(name):
    for n, up, down in NATURES:
        if n == name:
            return (up, down)
    return ('', '')

# ── Held items ────────────────────────────────────────────────────────────────
HELD_ITEMS = {
    'lucky_egg':   {'emoji': '🥚', 'name': 'Lucky Egg',   'desc': '+50% XP earned'},
    'choice_band': {'emoji': '🎀', 'name': 'Choice Band', 'desc': '+20% battle win chance'},
    'amulet_coin': {'emoji': '🪙', 'name': 'Amulet Coin', 'desc': '2× catch rate'},
    'shiny_charm': {'emoji': '✨', 'name': 'Shiny Charm',  'desc': '1/100 shiny rate'},
    'everstone':   {'emoji': '🪨', 'name': 'Everstone',   'desc': 'Blocks evolution'},
    'mega_stone':  {'emoji': '💫', 'name': 'Mega Stone',  'desc': '+20% gym battle win (Earth badge)'},
}
ITEM_IDS = list(HELD_ITEMS)

# Drop chances per wild tier — gated behind Rainbow badge
ITEM_DROP_TABLE = {
    'common':    [('lucky_egg', 0.01),  ('choice_band', 0.01)],
    'uncommon':  [('lucky_egg', 0.015), ('choice_band', 0.015), ('amulet_coin', 0.01)],
    'rare':      [('lucky_egg', 0.02),  ('choice_band', 0.02),  ('amulet_coin', 0.015), ('shiny_charm', 0.005)],
    'legendary': [('shiny_charm', 0.02), ('everstone', 0.02), ('amulet_coin', 0.03), ('mega_stone', 0.02)],
    'mythical':  [('shiny_charm', 0.05), ('everstone', 0.03), ('mega_stone', 0.05)],
}

# ── Breeding / egg ────────────────────────────────────────────────────────────
EGG_HATCH_XP = 200   # XP needed to hatch an egg
EGG_BABIES = [
    ('Pichu',    'Electric', '⚡'), ('Cleffa',  'Fairy',    '✨'),
    ('Igglybuff','Normal',   '🎤'), ('Magby',   'Fire',     '🔥'),
    ('Elekid',   'Electric', '⚡'), ('Smoochum','Ice',      '💋'),
    ('Tyrogue',  'Fighting', '👊'), ('Togepi',  'Fairy',    '🥚'),
]

def award_egg(stats, reason=''):
    """Give trainer an egg if they don't already have one."""
    if stats.get('egg_species'):
        return ''
    baby = random.choice(EGG_BABIES)
    stats['egg_species']  = baby[0]
    stats['egg_type']     = baby[1]
    stats['egg_emoji']    = baby[2]
    stats['egg_xp_need']  = EGG_HATCH_XP
    stats['egg_xp_prog']  = 0
    hint = f'({baby[2]} {baby[0]} hint)' if random.random() < 0.5 else '(mystery)'
    return f'🥚 Egg received! {hint}{" — " + reason if reason else ""}'

def tick_egg(stats, xp_gained):
    """Add XP progress to egg. Returns hatch message if hatched, else ''."""
    if not stats.get('egg_species'):
        return ''
    stats['egg_xp_prog'] = stats.get('egg_xp_prog', 0) + xp_gained
    if stats['egg_xp_prog'] < stats.get('egg_xp_need', EGG_HATCH_XP):
        return ''
    name, ptype, emoji = stats['egg_species'], stats['egg_type'], stats['egg_emoji']
    add_to_collection(name, ptype, emoji, 'common')
    stats['egg_species'] = ''
    stats['egg_type']    = ''
    stats['egg_emoji']   = ''
    stats['egg_xp_prog'] = 0
    stats['egg_xp_need'] = 0
    return f'🥚✨ Egg hatched! {emoji} {name} (Lv.1) joined your party!'

# ── Weekly raid ────────────────────────────────────────────────────────────────
RAID_BASE_HP = 5000   # total HP pool for the weekly boss

def _current_week_id():
    return date.today().strftime('%Y-W%W')

def read_raid():
    if not RAID_FILE.exists():
        return None
    try:
        return json.loads(RAID_FILE.read_text(encoding='utf-8'))
    except Exception:
        return None

def write_raid(data):
    RAID_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

def get_weekly_raid():
    """Return current raid dict; auto-generates new boss on week change."""
    raid = read_raid()
    week_id = _current_week_id()
    if raid and raid.get('week_id') == week_id:
        return raid
    # New week — pick a new legendary boss
    pool = POKEMON_POOL.get('legendary', [])
    if not pool:
        return None
    idx  = hash(week_id) % len(pool)
    boss_name, boss_type, boss_emoji = pool[idx]
    raid = {
        'week_id':      week_id,
        'boss_name':    boss_name,
        'boss_type':    boss_type,
        'boss_emoji':   boss_emoji,
        'boss_hp':      RAID_BASE_HP,
        'hp_remaining': RAID_BASE_HP,
        'captured':     False,
        'damage_log':   [],
    }
    write_raid(raid)
    return raid

def apply_raid_damage(xp_gained):
    """Deal damage to weekly boss equal to xp * 0.1. Returns (raid, damage, ko'd)."""
    raid = get_weekly_raid()
    if not raid or raid.get('captured'):
        return raid, 0, False
    damage = max(1, int(xp_gained * 0.1))
    raid['hp_remaining'] = max(0, raid['hp_remaining'] - damage)
    raid['damage_log'].append({'date': TODAY, 'xp': xp_gained, 'damage': damage})
    ko = raid['hp_remaining'] == 0
    if ko:
        raid['captured'] = True
    write_raid(raid)
    return raid, damage, ko

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
    evolutions of starter species and regional form overrides."""
    # Regional form: name already stored as display name (e.g. "Alolan Vulpix")
    if p.get('form'):
        return p['name'], p.get('emoji', '?')
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
    # Pokémon GO-style escalating bands. Early levels stay fast (onboarding
    # dopamine), endgame deliberately steep. Lv100 ≈ 340k XP cumulative.
    if n <= 1:  return 0
    if n <= 10: return (n - 1)  * 100
    if n <= 20: return 900      + (n - 10) * 300
    if n <= 35: return 3900     + (n - 20) * 800
    if n <= 60: return 15900    + (n - 35) * 2000
    if n <= 85: return 65900    + (n - 60) * 5000
    return                190900 + (n - 85) * 10000

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


# ── XP curve migration (v2.32) ────────────────────────────────────────────────
# Schema v6 → v7 bumped curve from quadratic-ish to PoGo-style escalating bands.
# Old XP values mean different levels under the new curve. Strategy: level-lock —
# preserve each Pokémon's level, reset XP to the new curve floor for that level.
XP_CURVE_VERSION = 7

def migrate_xp_curve(stats, col_dict, old_buddy_level, old_buddy_xp):
    """Level-lock migration. Returns adjusted (old_buddy_xp, message).
    Mutates col_dict['pokemon'] in place; caller must write_collection."""
    if stats.get('schema_version', 0) >= XP_CURVE_VERSION:
        return old_buddy_xp, ''
    party_changes = 0
    for p in col_dict.get('pokemon', []):
        lv = max(1, min(LEVEL_CAP, p.get('level', 1)))
        new_xp = xp_for_level(lv) if lv < LEVEL_CAP else CAP_XP
        if p.get('xp') != new_xp:
            p['xp'] = new_xp
            party_changes += 1
    new_buddy_xp = (xp_for_level(old_buddy_level)
                    if old_buddy_level < LEVEL_CAP else CAP_XP)
    msg = (
        '\n┌─────────────────────────────────────────────────────────────┐\n'
        '│ 🔔 XP curve updated (v2.32) — Pokémon GO-style escalation    │\n'
        '├─────────────────────────────────────────────────────────────┤\n'
        '│ Endgame leveling now meaningfully steeper. Early game        │\n'
        '│ unchanged. Lv100 = ~340k XP (was ~17k).                      │\n'
        '│                                                              │\n'
        f'│ Your buddy stays at Lv {old_buddy_level:<3} — XP reset to new floor.   │\n'
        f'│ {party_changes:<3} party/box Pokémon migrated.                          │\n'
        '│ Stack multiplier (combo×streak×lucky) now capped at 3.0×.    │\n'
        '└─────────────────────────────────────────────────────────────┘\n'
    )
    stats['schema_version'] = XP_CURVE_VERSION
    return new_buddy_xp, msg

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

def tier_color(tier):
    """ANSI color code for rarity tier."""
    colors = {
        'common':    '\033[37m',      # white
        'uncommon':  '\033[36m',      # cyan
        'rare':      '\033[35m',      # magenta
        'legendary': '\033[33m',      # yellow
        'mythical':  '\033[95m',      # bright magenta
    }
    return colors.get(tier, '\033[37m')

def colored_tier_badge(tier):
    """Tier badge with color."""
    color = tier_color(tier)
    reset = '\033[0m'
    badge = _TIER_BADGE.get(tier, tier.upper())
    return f'{color}{badge}{reset}'

def effectiveness_color(eff):
    """ANSI color for battle effectiveness."""
    if eff >= 2.0:    return '\033[32m'    # green — super effective
    elif eff == 0.5:  return '\033[33m'    # yellow — not very effective
    elif eff == 0.0:  return '\033[31m'    # red — no effect
    else:             return '\033[37m'    # white — neutral

def catch_pct_color(pct):
    """Color bar for catch percentage (red low → green high)."""
    if pct >= 80:     return '\033[32m'    # green
    elif pct >= 60:   return '\033[33m'    # yellow
    else:             return '\033[31m'    # red

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
        'shiny_count': 0,
        'milestones': set(),
        'gym_badges': set(),
        'leaders_defeated': set(),
        # Item bag
        **{f'item_{iid}': 0 for iid in ITEM_IDS},
        # Egg
        'egg_species': '', 'egg_type': '', 'egg_emoji': '',
        'egg_xp_need': 0, 'egg_xp_prog': 0,
        # Inventory (new trainers start with 5 Poké Balls)
        'balls_poke': 5, 'balls_great': 0, 'balls_ultra': 0, 'balls_master': 0,
        'master_shards': 0,
        'berry_razz': 0, 'berry_nanab': 0, 'berry_pinap': 0, 'berry_golden': 0,
        # Combo
        'combo': 0, 'combo_ts': '',
        # Daily quest
        'daily_quest_date': '', 'daily_quest_id': '', 'daily_quest_done': False,
        'tasks_today': 0,
        # Anti-cheat
        'daily_xp': 0, 'daily_xp_date': '',
        'last_xp_hash': '', 'last_xp_ts': 0,
        'battle_stamina': BATTLE_STAMINA_MAX, 'battle_stamina_ts': 0,
        # Elite Four (F18)
        'elite_defeated': set(), 'beat_elite_four': False,
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
    ld_section = re.search(r'## Leaders Defeated\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    leaders_defeated = set(re.findall(r'^- (\S+)', ld_section.group(1), re.MULTILINE)) if ld_section else set()
    ef_section = re.search(r'## Elite Four Defeated\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    elite_defeated = set(re.findall(r'^- (\S+)', ef_section.group(1), re.MULTILINE)) if ef_section else set()
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
        'shiny_count':       gi('shiny_count'),
        'milestones':        milestones,
        'gym_badges':        gym_badges,
        'leaders_defeated':  leaders_defeated,
        **{f'item_{iid}': gi(f'item_{iid}') for iid in ITEM_IDS},
        'egg_species':       gs('egg_species'),
        'egg_type':          gs('egg_type'),
        'egg_emoji':         gs('egg_emoji'),
        'egg_xp_need':       gi('egg_xp_need'),
        'egg_xp_prog':       gi('egg_xp_prog'),
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
        'daily_xp':          gi('daily_xp'),
        'daily_xp_date':     gs('daily_xp_date'),
        'last_xp_hash':      gs('last_xp_hash'),
        'last_xp_ts':        gi('last_xp_ts'),
        'battle_stamina':    gi('battle_stamina') if '**battle_stamina**' in text else defaults['battle_stamina'],
        'battle_stamina_ts': gi('battle_stamina_ts'),
        'elite_defeated':    elite_defeated,
        'beat_elite_four':   gb('beat_elite_four'),
    }
    return stats

def write_stats(s):
    b = lambda v: 'true' if v else 'false'
    ms_lines = '\n'.join(f'- {m}' for m in sorted(s['milestones'])) or '*(none yet)*'
    gb_lines = '\n'.join(f'- {bid}' for bid in _BADGE_ORDER if bid in s.get('gym_badges', set())) or '*(none yet)*'
    ld_lines = '\n'.join(f'- {lid}' for lid in sorted(s.get('leaders_defeated', set()))) or '*(none yet)*'
    ef_lines = '\n'.join(f'- {eid}' for eid in _ELITE_ORDER if eid in s.get('elite_defeated', set())) or '*(none yet)*'
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
        f'**shiny_count**: {s.get("shiny_count", 0)}\n'
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
        f'**daily_xp**: {s.get("daily_xp", 0)}\n'
        f'**daily_xp_date**: {s.get("daily_xp_date", "")}\n'
        f'**last_xp_hash**: {s.get("last_xp_hash", "")}\n'
        f'**last_xp_ts**: {s.get("last_xp_ts", 0)}\n'
        f'**battle_stamina**: {s.get("battle_stamina", BATTLE_STAMINA_MAX)}\n'
        f'**battle_stamina_ts**: {s.get("battle_stamina_ts", 0)}\n'
        f'**beat_elite_four**: {b(s.get("beat_elite_four", False))}\n'
        + ''.join(f'**item_{iid}**: {s.get(f"item_{iid}", 0)}\n' for iid in ITEM_IDS)
        + f'**egg_species**: {s.get("egg_species", "")}\n'
        + f'**egg_type**: {s.get("egg_type", "")}\n'
        + f'**egg_emoji**: {s.get("egg_emoji", "")}\n'
        + f'**egg_xp_need**: {s.get("egg_xp_need", 0)}\n'
        + f'**egg_xp_prog**: {s.get("egg_xp_prog", 0)}\n'
        + '\n'
        f'## Milestones Awarded\n\n'
        f'{ms_lines}\n\n'
        f'## Gym Badges Earned\n\n'
        f'{gb_lines}\n\n'
        f'## Leaders Defeated\n\n'
        f'{ld_lines}\n\n'
        f'## Elite Four Defeated\n\n'
        f'{ef_lines}\n'
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

# ── Anti-cheat helpers ────────────────────────────────────────────────────────

import hashlib

def _desc_hash(desc):
    norm = re.sub(r'\s+', ' ', (desc or '').strip().lower())
    return hashlib.sha1(norm.encode('utf-8')).hexdigest()[:12] if norm else ''

def check_xp_dedup(stats, desc):
    """True if desc is a near-duplicate of the last award within window."""
    h = _desc_hash(desc)
    if not h:
        return False
    last_h = stats.get('last_xp_hash', '')
    last_ts = int(stats.get('last_xp_ts', 0) or 0)
    now = int(time.time())
    return bool(last_h) and h == last_h and (now - last_ts) < XP_DEDUP_WINDOW

def daily_cap_for(col):
    """Dynamic daily XP cap — anchored to highest-level Pokémon ever caught.
    Anti-cheat scales with progression, no penalty when switching buddies.
    Floor of 2000 keeps new trainers safe; +100 per highest level in dex.
    """
    if not col or not col.get('pokemon'):
        return DAILY_XP_CAP_FLOOR
    max_lv = max((p.get('level', 1) for p in col['pokemon']), default=1)
    return max(DAILY_XP_CAP_FLOOR, max_lv * DAILY_XP_CAP_PER_LV)

def apply_daily_cap(stats, add_xp, col=None):
    """Clip add_xp to remaining daily budget. Returns (clipped, was_clipped, remaining_before)."""
    if stats.get('daily_xp_date', '') != TODAY:
        stats['daily_xp_date'] = TODAY
        stats['daily_xp'] = 0
    spent = int(stats.get('daily_xp', 0) or 0)
    cap = daily_cap_for(col) if col is not None else DAILY_XP_CAP
    remaining = max(0, cap - spent)
    clipped = max(0, min(add_xp, remaining))
    return clipped, (clipped < add_xp), remaining

def regen_stamina(stats):
    """Regenerate battle stamina based on elapsed time. Returns current value."""
    now = int(time.time())
    cur = int(stats.get('battle_stamina', BATTLE_STAMINA_MAX))
    last = int(stats.get('battle_stamina_ts', 0) or 0)
    if cur >= BATTLE_STAMINA_MAX:
        stats['battle_stamina'] = BATTLE_STAMINA_MAX
        stats['battle_stamina_ts'] = now
        return BATTLE_STAMINA_MAX
    if last == 0:
        stats['battle_stamina_ts'] = now
        return cur
    gained = (now - last) // BATTLE_REGEN_SECS
    if gained > 0:
        cur = min(BATTLE_STAMINA_MAX, cur + gained)
        stats['battle_stamina'] = cur
        stats['battle_stamina_ts'] = last + gained * BATTLE_REGEN_SECS
    return cur

def stamina_eta(stats):
    """Seconds until next stamina point regenerates."""
    last = int(stats.get('battle_stamina_ts', 0) or 0)
    if not last:
        return BATTLE_REGEN_SECS
    elapsed = int(time.time()) - last
    return max(0, BATTLE_REGEN_SECS - (elapsed % BATTLE_REGEN_SECS))

def fmt_duration(secs):
    secs = max(0, int(secs))
    if secs < 60: return f'{secs}s'
    if secs < 3600: return f'{secs // 60}m {secs % 60}s'
    return f'{secs // 3600}h {(secs % 3600) // 60}m'

# ── Milestone & title logic ───────────────────────────────────────────────────

def pokedex_count(col):
    """Unique species count for Pokédex completion. Duplicates of the same name
    (e.g. catching multiple Pidgey) register only once. Regional variants are
    stored under distinct names (e.g. 'Vulpix' vs 'Alolan Vulpix') so they
    naturally count as separate dex entries."""
    return len({p['name'] for p in col.get('pokemon', [])})


def get_trainer_title(stats, col):
    n = pokedex_count(col)
    checks = {
        'beat_elite_four':  stats.get('beat_elite_four'),
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

    n_caught = pokedex_count(col)

    # Dex milestones
    if n_caught >= 1:  new_ms += maybe('first_catch')
    if n_caught >= 10:
        new_ms += maybe('dex_10')
        if not stats.get('egg_species'): award_egg(stats, '10 Pokémon caught')
    if n_caught >= 20: new_ms += maybe('dex_20')
    if n_caught >= 30: new_ms += maybe('dex_30')

    # Catch tier milestones
    if catch_result:
        base_tier = catch_result[0].replace('-shiny', '')
        if base_tier == 'legendary': new_ms += maybe('legendary_catch')
        if base_tier == 'mythical':  new_ms += maybe('mythical_catch')
        if catch_result[4]:          new_ms += maybe('shiny_catch')  # is_shiny flag

    shiny_n = stats.get('shiny_count', 0)
    if shiny_n >= 5:  new_ms += maybe('shiny_5')
    if shiny_n >= 10: new_ms += maybe('shiny_10')

    active = next((p for p in col['pokemon'] if p.get('name') == col.get('active')), None)
    if active and active.get('friendship', 0) >= FRIENDSHIP_MAX:
        new_ms += maybe('friendship_max')

    # Evolution milestones
    if evolved:
        new_ms += maybe('first_evolution')
        if new_level >= 36: new_ms += maybe('final_evolution')

    # Level milestones
    for lv, key in [(10,'level_10'),(20,'level_20'),(30,'level_30'),(50,'level_50')]:
        if old_level < lv <= new_level: new_ms += maybe(key)

    # Streak milestones
    streak = stats.get('streak', 0)
    if streak >= 7:
        new_ms += maybe('streak_7')
        if not stats.get('egg_species'): award_egg(stats, '7-day streak')
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
        return {'active': None, 'party': [], 'pokemon': []}
    text = COLLECTION_FILE.read_text(encoding='utf-8')
    active_m = re.search(r'\*\*Active\*\*:\s*(\S+)', text)
    active = active_m.group(1).strip() if active_m else None
    party_m = re.search(r'\*\*ActiveParty\*\*:\s*(.+)', text)
    if party_m:
        party = [n.strip() for n in party_m.group(1).split(',') if n.strip()]
    else:
        # Extract name from active (format: name or name:id)
        active_name = active.split(':')[0] if active and ':' in active else active
        party = [active_name] if active_name else []
    pokemon = []
    for line in text.splitlines():
        if not line.startswith('|'): continue
        cols = [c.strip() for c in line.split('|')]
        cols = [c for c in cols if c]
        if len(cols) < 6: continue

        # Check if first column is an 8-char ID
        has_id = cols[0] and len(cols[0]) == 8 and all(c in '0123456789abcdef-' for c in cols[0])
        if has_id:
            pokemon_id = cols[0]
            name_idx = 1
        else:
            pokemon_id = None
            name_idx = 0

        if cols[name_idx] == 'Name': continue  # Skip header

        try:
            name       = cols[name_idx]
            ptype      = cols[name_idx + 1] if len(cols) > name_idx + 1 else ''
            emoji      = cols[name_idx + 2] if len(cols) > name_idx + 2 else ''
            level      = int(cols[name_idx + 3]) if len(cols) > name_idx + 3 else 1
            xp         = int(cols[name_idx + 4]) if len(cols) > name_idx + 4 else 0
            caught     = cols[name_idx + 5] if len(cols) > name_idx + 5 else ''
            rarity     = cols[name_idx + 6] if len(cols) > name_idx + 6 else 'common'
            form       = cols[name_idx + 7] if len(cols) > name_idx + 7 and cols[name_idx + 7] != '-' else ''
            nature     = cols[name_idx + 8] if len(cols) > name_idx + 8 and cols[name_idx + 8] != '-' else ''
            friendship = int(cols[name_idx + 9]) if len(cols) > name_idx + 9 and cols[name_idx + 9].isdigit() else 70

            entry = {
                'name':       name,
                'type':       ptype,
                'emoji':      emoji,
                'level':      level,
                'xp':         xp,
                'caught':     caught,
                'rarity':     rarity,
                'shiny':      rarity.endswith('-shiny'),
                'form':       form,
                'nature':     nature,
                'friendship': friendship,
            }
            if pokemon_id:
                entry['id'] = pokemon_id
            pokemon.append(entry)
        except (ValueError, IndexError):
            continue
    return {'active': active, 'party': party, 'pokemon': pokemon}

def write_collection(active, pokemon_list, party=None):
    if party is None:
        # Extract name from active (format: name or name:id)
        active_name = active.split(':')[0] if active and ':' in active else active
        party = [active_name] if active_name else []
    party_str = ','.join(party[:3])
    lines = [
        '# Pokemon Collection\n\n',
        f'**Active**: {active}\n',
        f'**ActiveParty**: {party_str}\n\n',
        '| ID | Name | Type | Emoji | Level | XP | Caught | Rarity | Form | Nature | Friendship |\n',
        '|---|---|---|---|---|---|---|---|---|---|---|\n',
    ]
    for p in pokemon_list:
        pokemon_id = p.get('id', '')
        lines.append(
            f"| {pokemon_id} | {p['name']} | {p['type']} | {p['emoji']} | "
            f"{p['level']} | {p['xp']} | {p['caught']} | {p['rarity']} | {p.get('form', '') or '-'} | "
            f"{p.get('nature', '') or '-'} | {p.get('friendship', 70)} |\n"
        )
    COLLECTION_FILE.write_text(''.join(lines), encoding='utf-8')

FRIENDSHIP_MAX = 255

# ── Gym leaders (F14 PvP lite) ───────────────────────────────────────────────
# (id, name, type, level, signature, emoji, badge_id, flavor)
GYM_LEADERS = [
    ('brock',    'Brock',     'Rock',     12, 'Onix',     '🗿', 'boulder', 'Rock-hard defense!'),
    ('misty',    'Misty',     'Water',    20, 'Starmie',  '⭐', 'cascade', 'Tidal strike!'),
    ('surge',    'Lt. Surge', 'Electric', 24, 'Raichu',   '⚡', 'thunder', 'Lightning reflexes!'),
    ('erika',    'Erika',     'Grass',    29, 'Vileplume','🌸', 'rainbow', 'Pollen storm!'),
    ('koga',     'Koga',      'Poison',   40, 'Muk',      '☠️', 'soul',    'Venomous cloud!'),
    ('sabrina',  'Sabrina',   'Psychic',  43, 'Alakazam', '🔮', 'marsh',   'Psychic assault!'),
    ('blaine',   'Blaine',    'Fire',     45, 'Arcanine', '🔥', 'volcano', 'Scorching heat!'),
    ('giovanni', 'Giovanni',  'Ground',   50, 'Rhydon',   '🦏', 'earth',   'Seismic slam!'),
]
_LEADER_BY_ID = {L[0]: L for L in GYM_LEADERS}

# ── Elite Four (F18) ──────────────────────────────────────────────────────────
# (id, name, type, level, signature, emoji, flavor)
ELITE_FOUR = [
    ('lorelei',  'Lorelei',  'Ice',       55, 'Lapras',      '🧊', 'Frozen fury!'),
    ('bruno',    'Bruno',    'Fighting',  58, 'Machamp',     '💪', 'Four-arm crush!'),
    ('agatha',   'Agatha',   'Ghost',     60, 'Gengar',      '👻', 'Shadow veil!'),
    ('lance',    'Lance',    'Dragon',    62, 'Dragonite',   '🐉', 'Dragon rage!'),
    ('champion', 'Blue',     'Normal',    65, 'Pidgeot',     '🦅', 'Champion gambit!'),
]
_ELITE_BY_ID  = {E[0]: E for E in ELITE_FOUR}
_ELITE_ORDER  = [E[0] for E in ELITE_FOUR]

def _elite_gate(stats):
    """Returns (allowed, reason). Requires all 8 gym badges."""
    earned = stats.get('gym_badges', set())
    missing = [b for b in _BADGE_ORDER if b not in earned]
    if missing:
        return False, f'Need all 8 gym badges. Missing: {", ".join(missing)}'
    return True, ''

def _next_elite(stats):
    """Next trainer to face, or None if all defeated."""
    beaten = stats.get('elite_defeated', set())
    for eid in _ELITE_ORDER:
        if eid not in beaten:
            return eid
    return None

def battle_elite(eid, buddy_level, buddy_type, stats, held_item=None):
    """Run PvP vs an Elite Four trainer. Returns (won, xp_reward, log, champion_flag)."""
    trainer = _ELITE_BY_ID.get(eid)
    if not trainer:
        return False, 0, [f'Unknown Elite Four trainer: {eid}'], False
    _, tname, ttype, tlv, sig, emoji, flavor = trainer
    ok, reason = _elite_gate(stats)
    if not ok:
        return False, 0, [f' 🔒 Elite Four locked — {reason}'], False
    expected = _next_elite(stats)
    if expected is None:
        return False, 0, [' 🏆 Already defeated the Elite Four.'], False
    if eid != expected:
        exp_name = _ELITE_BY_ID[expected][1]
        return False, 0, [f' 🔒 Face {exp_name} first — Elite Four is sequential.'], False
    mega = (held_item == 'mega_stone') and ('earth' in stats.get('gym_badges', set()))
    effective_level = buddy_level + (10 if mega else 0)
    won, win_pct, eff = run_battle(effective_level, buddy_type, tlv, ttype)
    xp_reward = 150 if won else 20
    eff_tag = ' super effective!' if eff >= 2.0 else ' not very effective...' if eff == 0.5 else ''
    mega_tag = '  💫 MEGA EVOLVED!' if mega else ''
    rank = _ELITE_ORDER.index(eid) + 1
    log = [
        f' 👑 ELITE FOUR #{rank} — {tname} ({ttype}) Lv.{tlv}',
        f'   {emoji} {sig}  vs  YOU Lv.{buddy_level} [{buddy_type}]{mega_tag}',
        f'   [{stat_bar(win_pct, 20)}]  {win_pct}% win{eff_tag}',
        f'   "{flavor}"',
    ]
    champion_flag = False
    if won:
        stats.setdefault('elite_defeated', set()).add(eid)
        log.append(f'   ✓  VICTORY! +{xp_reward} XP')
        if _next_elite(stats) is None:
            stats['beat_elite_four'] = True
            champion_flag = True
            log.append('   🏆 YOU ARE THE CHAMPION!  +500 bonus XP')
            xp_reward += 500
    else:
        log.append(f'   ✗  DEFEAT. +{xp_reward} XP (keep training)')
    return won, xp_reward, log, champion_flag

def list_elite(stats):
    """Render Elite Four roster + progression state."""
    beaten = stats.get('elite_defeated', set())
    ok, reason = _elite_gate(stats)
    lines = [' 👑 ELITE FOUR', ' ' + '─' * 48]
    if not ok:
        lines.append(f' 🔒 Locked — {reason}')
        lines.append('')
    nxt = _next_elite(stats)
    for eid, name, ttype, tlv, sig, emoji, _ in ELITE_FOUR:
        if eid in beaten:
            mark = '✓'
        elif eid == nxt and ok:
            mark = '▶'
        else:
            mark = '·'
        star = '  ⭐ NEXT' if eid == nxt and ok else ''
        lines.append(f'   {mark} {emoji} {name:<9} Lv.{tlv:<3} [{ttype:<8}] {sig:<12}{star}')
    lines.append('')
    if stats.get('beat_elite_four'):
        lines.append(' 🏆 CHAMPION — you have defeated the Elite Four.')
    elif ok and nxt:
        lines.append(f' Next → /poke:elite {nxt}')
    return '\n'.join(lines)

def battle_leader(leader_id, buddy_level, buddy_type, stats, held_item=None):
    """Run PvP vs a gym leader. Returns (won, xp_reward, log_lines, badge_awarded)."""
    leader = _LEADER_BY_ID.get(leader_id)
    if not leader:
        return False, 0, [f'Unknown leader: {leader_id}'], None
    lid, lname, ltype, llv, sig, lemoji, badge_id, flavor = leader
    # Mega evolution: mega_stone + Earth badge = +20% win
    mega = (held_item == 'mega_stone') and ('earth' in stats.get('gym_badges', set()))
    effective_level = buddy_level + (10 if mega else 0)
    won, win_pct, eff = run_battle(effective_level, buddy_type, llv, ltype)
    xp_reward = 75 if won else 10
    eff_tag = ' super effective!' if eff >= 2.0 else ' not very effective...' if eff == 0.5 else ''
    mega_tag = '  💫 MEGA EVOLVED!' if mega else ''
    log = [
        f' ⚔️  GYM BATTLE — {lname} ({ltype}) Lv.{llv}',
        f'   {lemoji} {sig}  vs  YOU Lv.{buddy_level} [{buddy_type}]{mega_tag}',
        f'   [{stat_bar(win_pct, 20)}]  {win_pct}% win{eff_tag}',
        f'   "{flavor}"',
    ]
    badge_awarded = None
    defeated = stats.setdefault('leaders_defeated', set())
    if won:
        log.append(f'   ✓  VICTORY! +{xp_reward} XP')
        if lid not in defeated:
            defeated.add(lid)
            gym_badges = stats.setdefault('gym_badges', set())
            if badge_id not in gym_badges:
                gym_badges.add(badge_id)
                badge_awarded = _BADGE_BY_ID.get(badge_id)
                if badge_awarded:
                    log.append(f'   🏅 Earned {badge_awarded[1]} {badge_awarded[2]}!')
    else:
        log.append(f'   ✗  DEFEAT. +{xp_reward} XP (participation)')
    return won, xp_reward, log, badge_awarded

def list_leaders(stats, buddy_type=None, buddy_level=None):
    """Render leader list + win status + recommendation (super-effective match not yet defeated)."""
    defeated = stats.get('leaders_defeated', set())
    recommended = None
    if buddy_type:
        best_eff = 1.0
        for lid, _, ltype, llv, *_ in GYM_LEADERS:
            if lid in defeated: continue
            eff = TYPE_CHART.get(buddy_type, {}).get(ltype, 1.0)
            if eff > best_eff:
                best_eff = eff
                recommended = lid
        # If no super-effective, pick lowest-level undefeated
        if not recommended:
            undefeated = [(lid, llv) for lid, _, _, llv, *_ in GYM_LEADERS if lid not in defeated]
            if undefeated:
                recommended = min(undefeated, key=lambda x: x[1])[0]
    lines = [' 🏛  GYM LEADERS', ' ' + '─' * 48]
    for lid, lname, ltype, llv, sig, lemoji, _, _ in GYM_LEADERS:
        mark = '✓' if lid in defeated else '·'
        star = '  ⭐ RECOMMENDED' if lid == recommended else ''
        eff = TYPE_CHART.get(buddy_type, {}).get(ltype, 1.0) if buddy_type else 1.0
        eff_tag = (' ×2 super-eff' if eff >= 2.0
                   else ' ×0.5 weak' if eff == 0.5
                   else ' ×0 null' if eff == 0.0 else '')
        lines.append(f'   {mark} {lemoji} {lname:<11} Lv.{llv:<3} [{ltype:<8}] {sig:<10}{eff_tag}{star}')
    lines.append('')
    if recommended:
        lines.append(f' Best matchup → /poke:battle {recommended}')
    else:
        lines.append(' /poke:battle <leader> to challenge')
    return '\n'.join(lines)

# F17b: friendship-gated evolutions. (source, target_name, target_type, target_emoji, min_friendship, hours_range_or_None)
FRIENDSHIP_EVOLUTIONS = [
    ('Eevee', 'Espeon',  'Psychic',  '🔮', 220, ('day',   range(5, 18))),
    ('Eevee', 'Umbreon', 'Dark',     '🌑', 220, ('night', set(range(18, 24)) | set(range(0, 5)))),
    ('Riolu', 'Lucario', 'Fighting', '💪', 220, ('day',   range(5, 18))),
]

def _time_is_day(hour=None):
    h = datetime.now().hour if hour is None else hour
    return 5 <= h < 18

def apply_friendship_evolutions(col=None, hour=None):
    """Evolve any party Pokémon that crossed friendship threshold. Returns list of 'old→new' strings."""
    own_col = col is None
    if own_col:
        col = read_collection()
    day = _time_is_day(hour)
    evolved = []
    for p in col['pokemon']:
        for src, tgt_name, tgt_type, tgt_emoji, min_f, (when, _) in FRIENDSHIP_EVOLUTIONS:
            if p.get('name') != src: continue
            if p.get('friendship', 0) < min_f: continue
            if when == 'day' and not day: continue
            if when == 'night' and day: continue
            p['name']  = tgt_name
            p['type']  = tgt_type
            p['emoji'] = tgt_emoji
            evolved.append(f'{src} → {tgt_name}')
            if col.get('active') == src:
                col['active'] = tgt_name
            party = col.get('party')
            if party:
                col['party'] = [tgt_name if n == src else n for n in party]
            break
    if evolved and own_col:
        write_collection(col['active'], col['pokemon'], col.get('party'))
    return evolved

def boost_friendship(name, amount, col=None):
    """Add `amount` to a Pokemon's friendship, clamped [0, 255]. Returns new value or None."""
    own_col = col is None
    if own_col:
        col = read_collection()
    for p in col['pokemon']:
        if p['name'] == name:
            cur = p.get('friendship', 70)
            new = max(0, min(FRIENDSHIP_MAX, cur + amount))
            p['friendship'] = new
            if own_col:
                write_collection(col['active'], col['pokemon'], col.get('party'))
            return new
    return None

def sync_active_to_collection(name, level, xp, col=None, pokemon_id=None):
    if col is None:
        col = read_collection()
    # Extract ID from "name:id" format if not explicitly provided
    if pokemon_id is None and ':' in str(name):
        name, pokemon_id = name.split(':', 1)
    for p in col['pokemon']:
        # Match by name; if pokemon_id provided, also match by ID
        if p['name'] == name:
            if pokemon_id and p.get('id') != pokemon_id:
                continue  # Skip if ID doesn't match
            p['level'] = level
            p['xp']    = xp
            # Preserve rarity/shiny from collection (don't overwrite)
            write_collection(col['active'], col['pokemon'], col.get('party'))
            return
    starter = STARTER_DATA.get(name, {})
    entry = {
        'name': name, 'type': starter.get('type', '?'),
        'emoji': starter.get('emoji', '?'), 'level': level,
        'xp': xp, 'caught': TODAY, 'rarity': 'starter', 'form': '',
    }
    if pokemon_id:
        entry['id'] = pokemon_id
    col['pokemon'].append(entry)
    write_collection(col['active'], col['pokemon'], col.get('party'))

def _get_active_name(active):
    """Extract name from active field (format: 'name' or 'name:id'). Returns just the name."""
    if not active:
        return None
    return active.split(':')[0] if ':' in str(active) else active

def _generate_pokemon_id():
    """Generate an 8-character ID for duplicate Pokemon tracking."""
    import hashlib
    import time
    seed = f"{time.time()}{random.random()}".encode()
    return hashlib.md5(seed).hexdigest()[:8]

def _bump_friendship_inline(p, amount):
    """Mutate p['friendship'] by amount, clamped [0, FRIENDSHIP_MAX]."""
    cur = p.get('friendship', 70)
    p['friendship'] = max(0, min(FRIENDSHIP_MAX, cur + amount))

def distribute_overflow_xp(overflow, active_name, stats=None, col=None):
    """Exp Share: split overflow XP evenly across non-active party members
    under level 100. Returns list of (name, gained, old_lv, new_lv) for
    announcement. Remainder XP (too small to split) is dropped.
    Requires Boulder Badge (gated by has_unlock)."""
    if overflow <= 0:
        return []
    if stats is not None and not has_unlock('exp_share', stats):
        return []
    if col is None:
        col = read_collection()
    # Extract name from active_name (format: 'name' or 'name:id')
    active_base_name = _get_active_name(active_name)
    eligible = [p for p in col['pokemon']
                if p['name'] != active_base_name and p.get('level', 1) < LEVEL_CAP]
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
        _bump_friendship_inline(p, 1 + 3 * max(0, new_lv - old_lv))
        try_wild_evolve(p)
        results.append((p['name'], share, old_lv, new_lv))
    apply_friendship_evolutions(col)
    write_collection(col['active'], col['pokemon'], col.get('party'))
    return results

# Party XP split: 60% lead / 25% slot2 / 15% slot3 (Thunder badge required)
_PARTY_SPLITS = [0.60, 0.25, 0.15]

def distribute_party_xp(full_xp, active_name, col):
    """Split XP across active_party (Thunder badge must be checked by caller).
    Returns (lead_xp, list of (name, gained, old_lv, new_lv))."""
    party = [n for n in col.get('party', []) if n][:3]
    if len(party) < 2:
        return full_xp, []
    results = []
    lead_xp = int(full_xp * _PARTY_SPLITS[0])
    for i, name in enumerate(party[1:], 1):
        bench_xp = int(full_xp * _PARTY_SPLITS[i])
        if bench_xp <= 0:
            continue
        p = next((x for x in col['pokemon'] if x['name'] == name), None)
        if not p or p.get('level', 1) >= LEVEL_CAP:
            continue
        old_lv = p['level']
        new_lv, new_xp, _ = clamp_to_cap(p.get('xp', xp_for_level(old_lv)) + bench_xp)
        p['level'] = new_lv
        p['xp']    = new_xp
        _bump_friendship_inline(p, 1 + 3 * max(0, new_lv - old_lv))
        try_wild_evolve(p)
        results.append((p['name'], bench_xp, old_lv, new_lv))
    if results:
        apply_friendship_evolutions(col)
        write_collection(col['active'], col['pokemon'], col.get('party'))
    return lead_xp, results

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

SEASONAL_BOOSTS = {
    # month (1-12) -> (boosted_type, weight, flavor_label)
    1:  ('Ice',       3, 'Winter Festival'),
    2:  ('Fairy',     3, 'Lovers\' Season'),
    3:  ('Grass',     3, 'Spring Bloom'),
    4:  ('Water',     3, 'April Showers'),
    5:  ('Flying',    3, 'Migration Month'),
    6:  ('Bug',       3, 'Bug-Catching Contest'),
    7:  ('Fire',      3, 'Summer Heatwave'),
    8:  ('Electric',  3, 'Thunder Season'),
    9:  ('Psychic',   3, 'Harvest Moon'),
    10: ('Ghost',     4, 'Halloween'),
    11: ('Dark',      3, 'Shadow Nights'),
    12: ('Ice',       4, 'Snow Festival'),
}

def current_seasonal_boost(today=None):
    """Returns (type, weight, label) for current month, or None."""
    d = today or date.today()
    return SEASONAL_BOOSTS.get(d.month)

def _pick_wild(tier, owned_names, role_type):
    """Pick a wild Pokémon from the pool, preferring unseen, role-type, and seasonal types."""
    pool      = POKEMON_POOL[tier]
    available = [p for p in pool if p[0] not in owned_names] or pool
    season    = current_seasonal_boost()
    if season:
        season_matches = [p for p in available if p[1] == season[0]]
        if season_matches and random.random() < (0.15 + 0.05 * season[1]):
            available = season_matches
    if role_type:
        role_matches = [p for p in available if p[1] == role_type]
        if role_matches and random.random() < 0.5:
            available = role_matches
    return random.choice(available)

def run_battle(buddy_level, buddy_type, wild_level, wild_type, choice_band=False):
    """Returns (won: bool, win_pct: int, effectiveness: float)."""
    effectiveness = TYPE_CHART.get(buddy_type or 'Normal', {}).get(wild_type, 1.0)
    base = buddy_level / max(1, wild_level) * 70 * effectiveness
    if choice_band: base += 20
    win_pct = max(5, min(95, int(base)))
    return random.randint(1, 100) <= win_pct, win_pct, effectiveness

def _compute_catch_pct(tier, ball_key, stats, with_berry=None):
    """Compute catch% for a ball, optionally applying a berry boost.
    Held item + friendship still apply regardless of berry."""
    if ball_key == 'master':
        return 100
    base = BASE_CATCH_RATES.get(tier, 0.5)
    mult = POKEBALL_TYPES.get(ball_key, {}).get('multiplier', 1.0)
    if with_berry == 'golden':
        mult *= BERRY_TYPES['golden'].get('catch_boost', 1.5)
    elif with_berry == 'razz':
        mult *= BERRY_TYPES['razz'].get('catch_boost', 1.2)
    if get_held_item() == 'amulet_coin':
        mult *= 2.0
    buddy_friendship = _active_buddy_friendship()
    mult *= 1.0 + (buddy_friendship / FRIENDSHIP_MAX) * 0.25
    return min(95, int(base * mult * 100))


def _pick_berry(tier, base_pct, stats):
    """Smart berry decision. PoGo-style — only throw when it matters.
    Returns berry key (golden/razz/pinap) or None."""
    has_golden = stats.get('berry_golden', 0) > 0
    has_razz   = stats.get('berry_razz', 0) > 0
    has_pinap  = stats.get('berry_pinap', 0) > 0
    base_tier  = (tier or '').replace('-shiny', '')

    # High-tier wild → always burn golden if available
    if base_tier in ('legendary', 'mythical') and has_golden:
        return 'golden'
    # Low catch chance — boost as much as possible
    if base_pct < 60:
        if has_golden: return 'golden'
        if has_razz:   return 'razz'
    # Mid chance + non-common — razz worth it
    if base_pct < 80 and base_tier != 'common':
        if has_razz: return 'razz'
    # Easy catch + has pinap → grab the bonus instead of wasting boost berry
    if base_pct >= 80 and has_pinap:
        return 'pinap'
    return None


def attempt_catch(tier, ball_key, stats):
    """Roll the catch. Returns (caught, final_pct, base_pct, berry_used).
    Smart berry selection — only consumes berry when it changes the outcome
    meaningfully, or when extra reward (pinap) is wanted."""
    if ball_key == 'master':
        return True, 100, 100, None
    base_pct = _compute_catch_pct(tier, ball_key, stats, with_berry=None)
    berry    = _pick_berry(tier, base_pct, stats)
    if berry:
        stats[f'berry_{berry}'] = max(0, stats.get(f'berry_{berry}', 0) - 1)
    # Pinap is a reward berry, not a boost — final % unchanged
    if berry in ('golden', 'razz'):
        final_pct = _compute_catch_pct(tier, ball_key, stats, with_berry=berry)
    else:
        final_pct = base_pct
    return random.randint(1, 100) <= final_pct, final_pct, base_pct, berry

def _active_buddy_friendship():
    try:
        col = read_collection()
        active = next((p for p in col['pokemon'] if p.get('name') == col.get('active')), None)
        return active.get('friendship', 70) if active else 0
    except Exception:
        return 0

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
                  buddy_level, buddy_type, stats, col=None):
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
    pinap_used_on_catch = False
    for ball in BALL_BY_RARITY.get(tier, ['poke']):
        key       = f'balls_{ball}'
        ball_info = POKEBALL_TYPES.get(ball, {})
        while stats.get(key, 0) > 0:
            stats[key] -= 1
            c, catch_pct, base_pct, berry_used = attempt_catch(tier, ball, stats)
            berry_info = BERRY_TYPES.get(berry_used or '', {})
            info['throws'].append({
                'ball_key':    ball,
                'ball_emoji':  ball_info.get('emoji', '🔴'),
                'ball_name':   ball_info.get('name', 'Ball'),
                'catch_pct':   catch_pct,
                'base_pct':    base_pct,
                'berry_used':  berry_used,
                'berry_emoji': berry_info.get('emoji', ''),
                'berry_name':  berry_info.get('name', ''),
                'caught':      c,
                'rem_poke':    stats.get('balls_poke', 0),
                'rem_great':   stats.get('balls_great', 0),
                'rem_ultra':   stats.get('balls_ultra', 0),
            })
            if c:
                caught = True
                if berry_used == 'pinap':
                    pinap_used_on_catch = True
                break
        if caught:
            break
    info['pinap_bonus'] = pinap_used_on_catch

    if not info['throws']:
        info['no_balls'] = True
        return None, info

    info['caught'] = caught
    info['balls_poke']   = stats.get('balls_poke', 0)
    info['balls_great']  = stats.get('balls_great', 0)
    info['balls_ultra']  = stats.get('balls_ultra', 0)
    info['balls_master'] = stats.get('balls_master', 0)

    if caught:
        add_to_collection(wild_name, wild_type, wild_emoji, tier, is_shiny, col=col)
        # Pinap reward: bump newly added Pokémon's level by 1 (PoGo "double candy"
        # equivalent — accelerates leveling instead of giving raw XP)
        if pinap_used_on_catch and col is not None:
            # Apply to the last (most recently added) matching Pokemon
            newly_added = next((p for p in reversed(col.get('pokemon', [])) if p['name'] == wild_name), None)
            if newly_added and newly_added.get('level', 1) < LEVEL_CAP:
                newly_added['level'] += 1
                newly_added['xp'] = xp_for_level(newly_added['level'])
            write_collection(col['active'], col['pokemon'], col.get('party'))
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

def add_to_collection(name, ptype, emoji, rarity, is_shiny=False, col=None):
    if col is None:
        col = read_collection()
    owned_names = {p['name'] for p in col['pokemon']}
    stored_rarity = (rarity + '-shiny') if is_shiny else rarity
    start_level = RARITY_START_LEVEL.get(rarity, 1)

    # Regional variant roll: 15% on repeat catch if forms exist
    form = ''
    if name in owned_names and name in REGIONAL_FORMS:
        if random.random() < REGIONAL_CATCH_CHANCE:
            region, disp_name, r_emoji, r_type = random.choice(REGIONAL_FORMS[name])
            form  = region
            emoji = r_emoji
            ptype = r_type
            name  = disp_name

    col['pokemon'].append({
        'name': name, 'type': ptype, 'emoji': emoji,
        'level': start_level, 'xp': xp_for_level(start_level), 'caught': TODAY,
        'rarity': stored_rarity, 'shiny': is_shiny, 'form': form,
        'nature': pick_nature(), 'friendship': 70,
        'id': _generate_pokemon_id(),  # UUID for duplicate tracking
    })
    write_collection(col['active'], col['pokemon'], col.get('party'))

def try_wild_evolve(p):
    """Check if a collection Pokémon should level-up evolve. Mutates p in-place.
    Returns evo description string like 'Weedle → Beedrill' or ''."""
    chain = WILD_EVOLUTIONS.get(p['name'])
    if not chain:
        return ''
    level = p.get('level', 1)
    for min_lv, evo_name, evo_emoji, evo_type in reversed(chain):
        if level >= min_lv:
            if p['name'] == evo_name:
                return ''
            old_name = p['name']
            p['name']  = evo_name
            p['emoji'] = evo_emoji
            p['type']  = evo_type
            return f'{old_name} → {evo_name}'
    return ''

def apply_trade_evolutions(trigger_event):
    """Evolve any party members whose trade-evo trigger matches. Returns list of (old→new) strings."""
    col = read_collection()
    evolved = []
    changed = False
    for p in col['pokemon']:
        te = TRADE_EVOLUTIONS.get(p['name'])
        if te and te[2] == trigger_event:
            evo_name, evo_emoji, _ = te
            p['name']  = evo_name
            p['emoji'] = evo_emoji
            evolved.append(f'{p["name"]} → {evo_name}')  # note: already mutated
            changed = True
    if changed:
        write_collection(col['active'], col['pokemon'], col.get('party'))
    return evolved

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

_ENC_DIV  = ' ' + '━' * 44
_ENC_DIV2 = ' ' + '· ' * 22
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
    """Compact badge row: emoji-strip when ≥4 earned, full names when few."""
    earned = stats.get('gym_badges', set())
    n = len(earned)
    if n == 0:
        return f'0/8  →  {next_badge_hint(stats)}'
    emojis = ''.join(_BADGE_BY_ID[bid][1] for bid in _BADGE_ORDER if bid in earned)
    hint   = next_badge_hint(stats)
    next_str = f'  →  {hint}' if hint and n < 8 else ''
    return f'{n}/8  {emojis}{next_str}'

def _egg_display(stats):
    species = stats.get('egg_species', '')
    if not species:
        return 'none'
    prog = stats.get('egg_xp_prog', 0)
    need = stats.get('egg_xp_need', EGG_HATCH_XP)
    emoji = stats.get('egg_emoji', '🥚')
    pct   = int(prog / need * 100) if need else 0
    filled = int(10 * pct / 100)
    bar = '█' * filled + '░' * (10 - filled)
    return f'🥚 Hatching {emoji} {species}  [{bar}] {prog}/{need} XP ({pct}%)'

def _guards_display(stats):
    """Anti-cheat status: battle stamina + daily XP budget."""
    stamina = regen_stamina(stats)
    # Daily XP: reset display if date rolled
    daily_date = stats.get('daily_xp_date', '')
    daily_xp   = stats.get('daily_xp', 0) if daily_date == TODAY else 0
    cap = daily_cap_for(read_collection())
    pct = int(daily_xp * 100 / cap) if cap else 0
    filled = int(10 * min(pct, 100) / 100)
    xp_bar = '█' * filled + '░' * (10 - filled)
    return (f'💪 Stamina {stamina}/{BATTLE_STAMINA_MAX}  ·  '
            f'🎯 XP today [{xp_bar}] {daily_xp}/{cap}')

def _held_item_display():
    held = get_held_item()
    if not held or held not in HELD_ITEMS:
        return 'none'
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
    n_dex = pokedex_count(col)
    n_total = sum(len(v) for v in POKEMON_POOL.values())
    streak  = trainer_stats.get('streak', 0)
    longest = trainer_stats.get('longest_streak', 0)

    lv_int   = int(level) if str(level).isdigit() else 1
    at_cap   = lv_int >= LEVEL_CAP
    xp_b     = bar(xp_max_disp if at_cap else xp_disp, xp_max_disp, 24)
    xp_label = 'MAX✦ Exp Share' if at_cap else f'{xp_disp} / {xp_max_disp}'
    sep  = '─' * 52

    streak_icon = '🔥' if streak >= 7 else '📅'
    out = [
        f' 🔥 {stage.upper():<12} Lv.{level:<4}      Trainer: {trainer}',
        f'    · {title} ·',
        f' {sep}',
        f' XP  [{xp_b}]  {xp_label}',
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
        f' EGG: {_egg_display(trainer_stats)}',
        f' GUARDS: {_guards_display(trainer_stats)}',
    ]

    if col['pokemon']:
        def _party_entry(p):
            dn, de = displayed_form(p)
            active_name = _get_active_name(col['active'])
            mark = '*' if p['name'] == active_name else ''
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


# ── Update check ──────────────────────────────────────────────────────────────

def _semver_tuple(v):
    """'2.33.2' or 'v2.33.2' → (2, 33, 2). Non-numeric parts coerce to 0."""
    parts = (v or '').lstrip('v').split('.')
    return tuple(int(p) if p.isdigit() else 0 for p in (parts + ['0', '0', '0'])[:3])


def is_outdated(current, latest):
    return _semver_tuple(latest) > _semver_tuple(current)


def read_update_cache():
    """Returns dict with current/latest/outdated/checked_ts, or {} if missing."""
    if not UPDATE_CACHE.exists():
        return {}
    try:
        return json.loads(UPDATE_CACHE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def run_update_check(force=False):
    """Poll GitHub releases, write cache. Skips if cache fresh (within TTL).
    Network call is best-effort — silent on failure."""
    cached = read_update_cache()
    now    = int(time.time())
    if not force and (now - int(cached.get('checked_ts', 0))) < UPDATE_CHECK_TTL:
        return cached
    try:
        import urllib.request
        url = f'https://api.github.com/repos/{UPDATE_REPO}/releases/latest'
        req = urllib.request.Request(url, headers={'User-Agent': 'pokemon-buddy-claude'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        latest  = (data.get('tag_name') or '').lstrip('v')
        current = get_plugin_version()
        result  = {
            'current':    current,
            'latest':     latest,
            'outdated':   is_outdated(current, latest),
            'checked_ts': now,
        }
        UPDATE_CACHE.write_text(json.dumps(result), encoding='utf-8')
        return result
    except Exception:
        # Stamp the timestamp anyway so we don't retry every session
        if cached:
            cached['checked_ts'] = now
            try: UPDATE_CACHE.write_text(json.dumps(cached), encoding='utf-8')
            except Exception: pass
        return cached

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

def render_statusline(plugin_mode=False, mode='normal'):
    col = read_collection()
    prefix = ''  # version removed v2.33.2 — use /poke:status or trainer card
    persona_suffix = '  🎭' if is_persona_on() else ''
    if not col['pokemon']:
        return f'{prefix}🎮 No buddy yet{persona_suffix}'

    # ── Section 1: Active buddy ──────────────────────────────────────────────
    # Parse active (format: name or name:id)
    active_str = col['active'] or ''
    if ':' in active_str:
        active_name, active_id = active_str.split(':', 1)
        active = next((p for p in col['pokemon'] if p.get('id') == active_id), None)
        if not active:
            active = next((p for p in col['pokemon'] if p['name'] == active_name), col['pokemon'][0] if col['pokemon'] else None)
    else:
        active_name = active_str
        active = next((p for p in col['pokemon'] if p['name'] == active_name), col['pokemon'][0] if col['pokemon'] else None)

    if not active:
        return f'{prefix}🎮 No buddy yet{persona_suffix}'

    rarity     = active.get('rarity', '').replace('-shiny', '')
    is_shiny   = active.get('shiny') or '-shiny' in active.get('rarity', '')
    shiny_mark = '✨' if is_shiny else ''
    shiny_legendary = ''
    if is_shiny and rarity in ('legendary', 'mythical'):
        shiny_legendary = f' 🌟{rarity.upper()}'
    disp_name, disp_emj = displayed_form(active)
    buddy_str  = f"{shiny_mark}{disp_emj} {disp_name} Lv.{active['level']}{shiny_legendary}"

    if mode == 'compact':
        return f'{prefix}{buddy_str}{persona_suffix}'

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
    if active['level'] >= LEVEL_CAP:
        xp_str = f'{colored_bar(xp_max_disp, xp_max_disp, 10)} MAX✦'
    else:
        xp_str = f'{colored_bar(xp_disp, xp_max_disp, 10)} {xp_disp}/{xp_max_disp}'

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

    if mode == 'normal':
        return f'{prefix}{buddy_str}{sep}{xp_str}{sep}{state_str}{persona_suffix}'

    # ── Section 4: Tags (combo, streak, stamina, update) — full mode only ────
    tr_stats  = read_stats()
    streak    = tr_stats.get('streak', 0)
    streak_tag = f'  🔥{streak}' if streak >= 3 else ''

    # Combo: show when active (within window) and ≥ 2
    combo_tag = ''
    combo_n   = tr_stats.get('combo', 0)
    if combo_n >= 2:
        try:
            last = datetime.fromisoformat(tr_stats.get('combo_ts', ''))
            if (datetime.now() - last).total_seconds() <= COMBO_WINDOW_SECS:
                combo_tag = f'  ⚡×{combo_n}'
        except (ValueError, TypeError):
            pass

    # Anti-cheat guards: surface stamina when drained
    stamina = regen_stamina(tr_stats)
    stamina_tag = f'  💪{stamina}/{BATTLE_STAMINA_MAX}' if stamina < BATTLE_STAMINA_MAX else ''

    # Update available — read cache only, never blocks statusline render
    update_tag = ''
    upd = read_update_cache()
    if upd.get('outdated'):
        update_tag = f'  🔔v{upd.get("latest", "")}'

    badge_count = len(tr_stats.get('badges', []))
    badges_tag = f'  🏅×{badge_count}' if badge_count > 0 else ''
    party_count = len(col.get('party', []))
    party_tag = f'  👥{party_count}' if party_count > 0 else ''

    return f'{prefix}{buddy_str}{sep}{xp_str}{sep}{state_str}{combo_tag}{streak_tag}{stamina_tag}{badges_tag}{party_tag}{update_tag}{persona_suffix}'

def _active_nature(col):
    active = next((p for p in col['pokemon'] if p['name'] == col.get('active')), None)
    if not active:
        return '—'
    n = active.get('nature', '')
    if not n:
        return '—'
    up, down = nature_info(n)
    if up and down and up != down:
        return f'{n} (+{up} / -{down})'
    return f'{n} (neutral)'

def _active_friendship(col):
    active = next((p for p in col['pokemon'] if p['name'] == col.get('active')), None)
    if not active:
        return ''
    f = active.get('friendship', 70)
    filled = int(f / FRIENDSHIP_MAX * 5 + 0.5)
    hearts = '♥' * filled + '♡' * (5 - filled)
    return f'{f}/{FRIENDSHIP_MAX}  {hearts}'

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

    n_caught = pokedex_count(col)
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
    shiny_n   = tr_stats.get('shiny_count', 0)
    shiny_str = f'  ✨×{shiny_n}' if shiny_n else ('  ✨ Shiny' if tr_stats.get('caught_shiny') else '')

    grouped = _group_by_tier(col['pokemon'])

    balls_parts = []
    for emoji, key in [('🔴','balls_poke'),('🔵','balls_great'),('🟡','balls_ultra'),('🟣','balls_master')]:
        n = tr_stats.get(key, 0)
        if n: balls_parts.append(f'{emoji}×{n}')
    balls_str = '  '.join(balls_parts) if balls_parts else 'No balls'

    berries_parts = []
    for emoji, key in [('🍓','berry_razz'),('🍍','berry_pinap'),('🌟','berry_golden')]:
        n = tr_stats.get(key, 0)
        if n: berries_parts.append(f'{emoji}×{n}')
    berries_str = '  '.join(berries_parts) if berries_parts else 'None'

    active_quest = get_daily_quest(tr_stats)
    quest_done   = tr_stats.get('daily_quest_done', False)
    quest_line   = (f'Quest: {active_quest["desc"]}  {"✓ DONE" if quest_done else "[active]"}'
                    if active_quest else '')

    season = current_seasonal_boost()
    season_line = (f'Season: {season[2]} ({season[0]} ×{season[1]} spawn)' if season else '')

    out = [
        f' ╔{"═" * (W + 3)}╗',
        row(f'🏆  TRAINER CARD  ·  {trainer}'),
        row(f'     · {title} ·'),
        SEP,
        row('ACTIVE BUDDY'),
        row(f'{buddy_emoji} {stage.upper():<14} Lv.{level}'),
        row(f'[{xp_b}]  {xp_disp}/{xp_max_disp} XP'),
        row(f'Specialty: {specialty}'),
        row(f'Nature: {_active_nature(col)}'),
        row(f'Friendship: {_active_friendship(col)}'),
        SEP,
        row('ACHIEVEMENTS'),
        row(f'Badges: {len(badges)}   Dex: {n_caught}/{n_total} caught'),
        row(f'Streak: 🔥{streak} days  (best: {longest}){shiny_str}'),
        row(f'Rarest: {rarest_str}'),
        row(f'Balls:   {balls_str}'),
        row(f'Berries: {berries_str}'),
    ]
    if quest_line:
        out.append(row(f'📋 {quest_line}'))
    if season_line:
        out.append(row(f'🗓  {season_line}'))
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

# ── Type palette (canonical Pokémon type colors) ─────────────────────────────
TYPE_COLORS = {
    'Normal':   ('#a8a77a', '#6d6c4e'),  'Fire':     ('#ee8130', '#8b3a10'),
    'Water':    ('#6390f0', '#23416f'),  'Electric': ('#f7d02c', '#8a7106'),
    'Grass':    ('#7ac74c', '#2f5d1a'),  'Ice':      ('#96d9d6', '#2d6e6b'),
    'Fighting': ('#c22e28', '#6e0f0c'),  'Poison':   ('#a33ea1', '#4e1b4d'),
    'Ground':   ('#e2bf65', '#7a6020'),  'Flying':   ('#a98ff3', '#43308d'),
    'Psychic':  ('#f95587', '#8d1639'),  'Bug':      ('#a6b91a', '#546009'),
    'Rock':     ('#b6a136', '#5c5110'),  'Ghost':    ('#735797', '#2d1e48'),
    'Dragon':   ('#6f35fc', '#2e0d8a'),  'Dark':     ('#705746', '#2f2118'),
    'Steel':    ('#b7b7ce', '#5f5f74'),  'Fairy':    ('#d685ad', '#70253f'),
}

def _type_palette(ptype):
    """Returns (hex_primary, hex_dark) for a given type; defaults to Normal."""
    return TYPE_COLORS.get(ptype, TYPE_COLORS['Normal'])

_RARITY_FX = {
    # tier: (class_name, glow_color)
    'mythical':  ('fx-mythical',  '#c084fc'),
    'legendary': ('fx-legendary', '#ffd700'),
    'rare':      ('fx-rare',      '#60a5fa'),
    'uncommon':  ('fx-uncommon',  '#4ade80'),
    'common':    ('',             ''),
    'starter':   ('',             ''),
}

def _rarity_fx_class(rarity, shiny=False):
    base = _RARITY_FX.get((rarity or '').replace('-shiny', ''), ('', ''))[0]
    return f'{base} fx-shiny' if shiny else base

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

    n_caught   = pokedex_count(col)
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

    # ── New sections (post-v2.17 features) ───────────────────────────────────
    active_buddy = next((p for p in col['pokemon'] if p.get('name') == col.get('active')), None)
    buddy_type   = (active_buddy or {}).get('type') or STARTER_DATA.get(stage, {}).get('type', 'Normal')
    buddy_rarity = (active_buddy or {}).get('rarity', '').replace('-shiny', '')
    buddy_shiny  = bool((active_buddy or {}).get('shiny'))
    type_hi, type_dk = _type_palette(buddy_type)
    rarity_fx_cls = _rarity_fx_class(buddy_rarity, buddy_shiny)

    held_item_key = get_held_item()
    held_item_info = HELD_ITEMS.get(held_item_key) if held_item_key else None
    nature_name = (active_buddy or {}).get('nature', '')
    nature_tag = ''
    if nature_name:
        up, down = nature_info(nature_name)
        nature_tag = f'{nature_name} (+{up} / -{down})' if up and down and up != down else f'{nature_name} (neutral)'

    shiny_count = tr_stats.get('shiny_count', 0)
    mega_active = held_item_key == 'mega_stone' and 'earth' in tr_stats.get('gym_badges', set())

    # Gym badges (canonical 8)
    earned_gym = tr_stats.get('gym_badges', set())
    gym_chips_html = ''.join(
        f'<span class="gym-chip {"gym-on" if bid in earned_gym else "gym-off"}">'
        f'{_he(emj)} <span class="gym-name">{_he(bname)}</span></span>'
        for bid, emj, bname, *_ in GYM_BADGE_DATA
    )
    gym_n_earned = sum(1 for bid, *_ in GYM_BADGE_DATA if bid in earned_gym)

    # Elite Four progress
    ef_defeated = tr_stats.get('elite_defeated', set())
    ef_chips_html = ''.join(
        f'<span class="ef-chip {"ef-on" if eid in ef_defeated else "ef-off"}">'
        f'{_he(emj)} {_he(tname)}</span>'
        for eid, tname, _, _, _, emj, _ in ELITE_FOUR
    )
    is_champion = tr_stats.get('beat_elite_four', False)

    # Guards
    stamina = regen_stamina(dict(tr_stats))  # copy — don't mutate on export
    daily_xp_today = tr_stats.get('daily_xp', 0) if tr_stats.get('daily_xp_date') == TODAY else 0
    daily_xp_cap   = daily_cap_for(read_collection())
    daily_xp_pct = int(min(100, daily_xp_today * 100 / daily_xp_cap)) if daily_xp_cap else 0

    buddy_spr_url  = sprite_url(stage, shiny=buddy_shiny)
    buddy_img_html = (f'<img src="{buddy_spr_url}" class="buddy-sprite" alt="{_he(stage)}">'
                      if buddy_spr_url else '')

    party_rows_html = []
    for tier in RARITY_TIER_ORDER:
        members = grouped.get(tier)
        if not members:
            continue
        label, color, bg = rarity_labels_html.get(tier, ('?', '#fff', '#222'))
        for p in members:
            active_name = _get_active_name(col['active'])
            is_active = p['name'] == active_name
            is_shiny  = bool(p.get('shiny'))
            mark      = ' ★' if is_active else ''
            row_cls   = 'active-row' if is_active else ''
            dn, de    = displayed_form(p)
            spr       = sprite_url(dn, shiny=is_shiny)
            shiny_sfx = ' ✨' if is_shiny else ''
            fx_cls    = _rarity_fx_class(tier, is_shiny)
            icon_inner = (f'<img src="{spr}" class="poke-sprite" alt="{_he(dn)}">'
                         if spr else _he(de))
            icon      = f'<span class="poke-icon-wrap {fx_cls}" style="position:relative;display:inline-block;border-radius:8px">{icon_inner}</span>'
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

  /* ── Type-themed accent (buddy) ── */
  .type-accent {{
    --type-hi: {type_hi};
    --type-dk: {type_dk};
  }}
  .buddy-card {{
    border-color: var(--type-dk) !important;
    box-shadow: 0 0 32px color-mix(in srgb, var(--type-hi) 18%, transparent), inset 0 1px 0 rgba(255,255,255,.06);
  }}
  .buddy-sprite-bg {{
    background: radial-gradient(circle at 50% 55%, color-mix(in srgb, var(--type-hi) 22%, transparent) 0%, transparent 68%) !important;
  }}
  .type-pill {{
    display: inline-flex; align-items: center;
    background: color-mix(in srgb, var(--type-hi) 20%, transparent);
    border: 1px solid var(--type-hi);
    color: var(--type-hi);
    border-radius: 6px; padding: 2px 10px; font-size: 10px; font-weight: 700;
    letter-spacing: .5px; text-transform: uppercase;
  }}

  /* ── Rarity special effects ── */
  .fx-uncommon {{ box-shadow: 0 0 14px rgba(74,222,128,.35); }}
  .fx-rare     {{ box-shadow: 0 0 18px rgba(96,165,250,.45); animation: rare-pulse 2.8s ease-in-out infinite; }}
  .fx-legendary {{
    box-shadow: 0 0 28px rgba(255,215,0,.55);
    animation: legendary-shimmer 3.2s ease-in-out infinite;
  }}
  .fx-mythical {{
    box-shadow: 0 0 32px rgba(192,132,252,.55);
    animation: mythical-holo 4s linear infinite;
    background: linear-gradient(135deg, rgba(192,132,252,.10), rgba(244,114,182,.10), rgba(99,102,241,.10)) !important;
  }}
  .fx-shiny::after {{
    content: ''; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
    background: linear-gradient(120deg, transparent 40%, rgba(255,255,255,.25) 50%, transparent 60%);
    animation: shiny-sweep 3s linear infinite; mix-blend-mode: overlay;
  }}
  @keyframes rare-pulse      {{ 0%,100% {{ box-shadow: 0 0 14px rgba(96,165,250,.35); }} 50% {{ box-shadow: 0 0 26px rgba(96,165,250,.65); }} }}
  @keyframes legendary-shimmer {{ 0%,100% {{ filter: drop-shadow(0 0 8px rgba(255,215,0,.55)); }} 50% {{ filter: drop-shadow(0 0 18px rgba(255,215,0,.9)); }} }}
  @keyframes mythical-holo   {{ 0% {{ filter: hue-rotate(0deg); }} 100% {{ filter: hue-rotate(360deg); }} }}
  @keyframes shiny-sweep     {{ 0% {{ transform: translateX(-100%); }} 100% {{ transform: translateX(100%); }} }}

  /* ── Gym badges canonical row ── */
  .gym-row {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .gym-chip {{
    display: inline-flex; align-items: center; gap: 6px;
    border-radius: 10px; padding: 6px 12px; font-size: 11px; font-weight: 600;
    border: 1px solid var(--bdr); transition: all .2s;
  }}
  .gym-on  {{ background: rgba(255,215,0,.08); border-color: rgba(255,215,0,.32); color: #fcd34d; }}
  .gym-off {{ background: rgba(255,255,255,.02); color: var(--muted); opacity: .55; filter: grayscale(.8); }}
  .gym-name {{ font-weight: 500; }}

  /* ── Elite Four ribbon ── */
  .ef-row {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
  .ef-chip {{
    display: inline-flex; align-items: center; gap: 4px;
    border-radius: 8px; padding: 5px 10px; font-size: 11px;
    border: 1px solid var(--bdr);
  }}
  .ef-on  {{ background: rgba(167,139,250,.15); border-color: rgba(167,139,250,.45); color: #c4b5fd; font-weight: 700; }}
  .ef-off {{ background: rgba(255,255,255,.02); color: var(--muted); opacity: .6; }}
  .champion-crown {{
    display: inline-flex; align-items: center; gap: 6px;
    background: linear-gradient(135deg, #fbbf24, #f59e0b);
    color: #1f1205; border-radius: 8px; padding: 5px 12px;
    font-weight: 800; font-size: 11px; letter-spacing: .8px;
    box-shadow: 0 0 18px rgba(245,158,11,.45);
  }}

  /* ── Guards meters ── */
  .guard-row {{ display: flex; gap: 24px; flex-wrap: wrap; align-items: center; }}
  .guard-meter {{ flex: 1; min-width: 220px; }}
  .guard-label {{ font-size: 10px; color: var(--muted); margin-bottom: 5px; letter-spacing: 1px; text-transform: uppercase; }}
  .stamina-dots {{ display: inline-flex; gap: 4px; }}
  .stam-dot {{ width: 14px; height: 14px; border-radius: 50%; border: 1px solid var(--bdr); }}
  .stam-on  {{ background: radial-gradient(circle, #4ade80 40%, #14532d); box-shadow: 0 0 8px rgba(74,222,128,.6); }}
  .stam-off {{ background: rgba(255,255,255,.04); }}

  /* ── Item + Nature chips ── */
  .meta-pill {{
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(255,255,255,.04); border: 1px solid var(--bdr);
    border-radius: 6px; padding: 3px 10px; font-size: 11px; font-weight: 500;
  }}
  .meta-pill .meta-ico {{ font-size: 14px; }}
  .mega-flag {{
    background: linear-gradient(135deg, rgba(239,68,68,.25), rgba(167,139,250,.25));
    border: 1px solid rgba(244,114,182,.5); color: #f472b6;
    font-weight: 700; letter-spacing: 1px;
  }}

  /* ── Motion initial states ── */
  .header, .quest-card, .grid-2 .card,
  .card.balls-card, .card.party-card, .card.badges-card,
  .card.gym-card, .card.ef-card, .card.guards-card,
  .footer, .sbar-row, tbody tr, .badge-chip {{ opacity: 0; }}
  @media (prefers-reduced-motion: reduce) {{
    .header, .quest-card, .grid-2 .card,
    .card.balls-card, .card.party-card, .card.badges-card,
    .card.gym-card, .card.ef-card, .card.guards-card,
    .footer, .sbar-row, tbody tr, .badge-chip {{ opacity: 1 !important; transform: none !important; }}
    .buddy-sprite {{ animation: none; }}
    .pokeball-svg {{ animation: none; }}
    .xp-fill::after {{ animation: none; }}
    .fx-rare, .fx-legendary, .fx-mythical, .fx-shiny::after {{ animation: none; }}
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
    <div class="card buddy-card type-accent">
      <div class="sec-lbl">Active Buddy</div>
      <div class="buddy-sprite-bg {rarity_fx_cls}" style="position:relative">{buddy_img_html}</div>
      <div class="buddy-name">{'✨ ' if buddy_shiny else ''}{_he(stage)}</div>
      <div class="buddy-lv-row" style="flex-wrap:wrap">
        <span class="lv-chip">Lv. {level}</span>
        <span class="type-pill">{_he(buddy_type)}</span>
        {'<span class="meta-pill mega-flag">💫 MEGA READY</span>' if mega_active else ''}
      </div>
      <div class="buddy-spec">{_he(specialty)}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px">
        {f'<span class="meta-pill"><span class="meta-ico">{_he(held_item_info["emoji"])}</span> {_he(held_item_info["name"])}</span>' if held_item_info else ''}
        {f'<span class="meta-pill"><span class="meta-ico">🧬</span> {_he(nature_tag)}</span>' if nature_tag else ''}
        {f'<span class="meta-pill"><span class="meta-ico">✨</span> {shiny_count} shiny</span>' if shiny_count > 0 else ''}
      </div>
      <div class="xp-lbl"><span>XP Progress</span><span>{xp_disp} / {xp_max_disp}</span></div>
      <div class="xp-track"><div class="xp-fill" data-xp="{pct}" style="width:0%;background:linear-gradient(90deg,{type_hi},{type_dk})"></div></div>
    </div>
    <div class="card">
      <div class="sec-lbl">Trainer Stats</div>
      {stats_html}
    </div>
  </div>

  <!-- Gym Badges (canonical 8) -->
  <div class="card gym-card" style="margin-bottom:16px">
    <div class="sec-lbl">Gym Badges · {gym_n_earned}/8</div>
    <div class="gym-row">{gym_chips_html}</div>
  </div>

  <!-- Elite Four progression -->
  <div class="card ef-card" style="margin-bottom:16px">
    <div class="sec-lbl">Elite Four{' · 🏆 CHAMPION' if is_champion else ''}</div>
    <div class="ef-row">
      {ef_chips_html}
      {'<span class="champion-crown">🏆 Champion</span>' if is_champion else ''}
    </div>
  </div>

  <!-- Guards (anti-cheat meters) -->
  <div class="card guards-card" style="margin-bottom:16px">
    <div class="sec-lbl">Guards</div>
    <div class="guard-row">
      <div class="guard-meter">
        <div class="guard-label">Battle Stamina</div>
        <div class="stamina-dots">
          {''.join(f'<span class="stam-dot {"stam-on" if i < stamina else "stam-off"}"></span>' for i in range(BATTLE_STAMINA_MAX))}
          <span style="margin-left:8px;font-size:11px;color:var(--muted)">{stamina}/{BATTLE_STAMINA_MAX}</span>
        </div>
      </div>
      <div class="guard-meter">
        <div class="guard-label">XP Today · {daily_xp_today:,} / {daily_xp_cap:,}</div>
        <div class="sbar-track"><div class="sbar-fill" style="width:{daily_xp_pct}%;background:#22d3ee"></div></div>
      </div>
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
    animate('.card.gym-card, .card.ef-card, .card.guards-card, .card.balls-card, .card.party-card, .card.badges-card', {{ opacity: [0,1], y: [16,0] }}, {{ easing: ease, duration:0.4, delay: stagger(0.08, {{ start:0.5 }}) }});
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
    n_caught  = pokedex_count(col)
    n_total   = sum(len(v) for v in POKEMON_POOL.values())

    active = next((p for p in col['pokemon'] if p.get('name') == col.get('active')), None)
    buddy_type = (active or {}).get('type') or STARTER_DATA.get(stage, {}).get('type', 'Normal')
    is_shiny   = bool((active or {}).get('shiny'))
    type_hi, type_dk = _type_palette(buddy_type)
    spr       = sprite_url(stage, shiny=is_shiny) or ''

    earned_gym = tr_stats.get('gym_badges', set())
    gym_n = sum(1 for bid, *_ in GYM_BADGE_DATA if bid in earned_gym)
    ef_n  = len(tr_stats.get('elite_defeated', set()))
    is_champ = tr_stats.get('beat_elite_four', False)

    # Gym badges row: 8 dots filled based on earned
    gym_dots = ''
    for i, (bid, emj, *_) in enumerate(GYM_BADGE_DATA):
        x = 90 + i * 56
        on = bid in earned_gym
        fill = '#fcd34d' if on else '#2a2d40'
        opacity = '1' if on else '0.5'
        gym_dots += (f'<circle cx="{x}" cy="540" r="18" fill="{fill}" opacity="{opacity}" '
                     f'stroke="#1a1a1a" stroke-width="2"/>'
                     f'<text x="{x}" y="547" text-anchor="middle" font-size="18" opacity="{opacity}">{emj}</text>')

    champ_banner = (
        '<rect x="850" y="520" width="260" height="48" rx="10" fill="url(#champ-grad)"/>'
        '<text x="980" y="553" text-anchor="middle" fill="#1f1205" font-family="sans-serif" font-size="22" font-weight="900" letter-spacing="2">🏆 CHAMPION</text>'
    ) if is_champ else (
        f'<text x="850" y="545" fill="#a78bfa" font-family="monospace" font-size="18">ELITE FOUR: {ef_n}/5</text>'
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0b0d1a"/>
      <stop offset="0.5" stop-color="{type_dk}" stop-opacity="0.55"/>
      <stop offset="1" stop-color="#1a1033"/>
    </linearGradient>
    <linearGradient id="type-glow" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{type_hi}" stop-opacity="0.0"/>
      <stop offset="0.5" stop-color="{type_hi}" stop-opacity="0.9"/>
      <stop offset="1" stop-color="{type_hi}" stop-opacity="0.0"/>
    </linearGradient>
    <linearGradient id="champ-grad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#fbbf24"/>
      <stop offset="1" stop-color="#f59e0b"/>
    </linearGradient>
    <radialGradient id="buddy-halo" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="{type_hi}" stop-opacity="0.45"/>
      <stop offset="1" stop-color="{type_hi}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="40" y="40" width="1120" height="550" rx="24" fill="#101220" stroke="{type_hi}" stroke-width="3" opacity="0.95"/>
  <rect x="40" y="38" width="1120" height="4" fill="url(#type-glow)"/>

  <text x="90" y="130" fill="{type_hi}" font-family="monospace" font-size="24" font-weight="700" letter-spacing="4">POKÉMON TRAINER CARD</text>
  <text x="90" y="210" fill="#dde1f5" font-family="sans-serif" font-size="72" font-weight="800">{_he(trainer)}</text>
  <text x="90" y="260" fill="#fbbf24" font-family="sans-serif" font-size="30" font-weight="700">{_he(title)}</text>
  <text x="90" y="300" fill="#4e5580" font-family="sans-serif" font-size="22">{_he(specialty)}</text>

  <circle cx="970" cy="240" r="180" fill="url(#buddy-halo)"/>
  <image href="{spr}" x="820" y="100" width="300" height="300"/>
  <rect x="820" y="415" width="300" height="56" rx="12" fill="#1a1d2e" stroke="{type_hi}" stroke-width="2"/>
  <text x="970" y="452" text-anchor="middle" fill="#fff" font-family="sans-serif" font-size="30" font-weight="700">{'✨ ' if is_shiny else ''}{_he(stage)} · Lv. {level}</text>
  <rect x="830" y="480" width="90" height="26" rx="5" fill="{type_dk}" opacity="0.9"/>
  <text x="875" y="498" text-anchor="middle" fill="#fff" font-family="sans-serif" font-size="14" font-weight="700" letter-spacing="1">{_he(buddy_type.upper())}</text>

  <g font-family="sans-serif" fill="#dde1f5">
    <text x="90" y="400" font-size="20" fill="#4e5580" letter-spacing="2">POKÉDEX</text>
    <text x="90" y="448" font-size="44" font-weight="800">{n_caught}<tspan fill="#4e5580" font-size="24"> / {n_total}</tspan></text>
    <text x="290" y="400" font-size="20" fill="#4e5580" letter-spacing="2">STREAK</text>
    <text x="290" y="448" font-size="44" font-weight="800" fill="#f97316">{streak}<tspan fill="#4e5580" font-size="24">d</tspan></text>
    <text x="490" y="400" font-size="20" fill="#4e5580" letter-spacing="2">TOTAL XP</text>
    <text x="490" y="448" font-size="44" font-weight="800" fill="#a78bfa">{total_xp:,}</text>
    <text x="90" y="490" font-size="18" fill="#4e5580" letter-spacing="2">GYM BADGES {gym_n}/8</text>
  </g>
  {gym_dots}
  {champ_banner}

  <text x="90" y="595" fill="#4e5580" font-family="monospace" font-size="16">/poke — a Pokémon companion for Claude Code</text>
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
    n_caught = pokedex_count(col)

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
                        item_drop=None, party_xp_log=None, raid_msg='', egg_msg=''):
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
    if raid_msg:
        lines.append(f' {raid_msg}')
    if egg_msg:
        lines.append(f' {egg_msg}')
    if item_drop and item_drop in HELD_ITEMS:
        it = HELD_ITEMS[item_drop]
        lines.append(f' 💎 Item drop! {it["emoji"]} {it["name"]} added to bag — {it["desc"]}')
    if lv_reward_msg:
        lines.append(f' 🎁 Level reward: {lv_reward_msg}')
    at_cap    = new_level >= LEVEL_CAP
    xp_label  = 'MAX ✦ Exp Share active' if at_cap else f'{xp_disp} / {xp_max_disp}'
    lines += [
        f' 🔥 {new_stage.upper():<12} Lv.{new_level:<4}',
        ' ' + '─' * 52,
        f' XP  [{xp_b}]  {xp_label}',
    ]
    if stat_boost > 0:
        lines.append(f' All stats +{stat_boost}!')
    for _, name, mtype, desc in new_moves_data:
        lines.append(f' New move: {name} [{mtype}] — {desc}')
    if party_xp_log:
        lines.append(f' 👥 Party XP (60/25/15 split):')
        for name, gained, olv, nlv in party_xp_log:
            lu = f'  ★ Lv.{olv}→{nlv}' if nlv > olv else ''
            lines.append(f'    • {name} +{gained} XP  Lv.{nlv}{lu}')
    if exp_share:
        leveled = [(n, ol, nl) for n, _, ol, nl in exp_share if nl > ol]
        lines.append(f' 🔀 Exp Share → {len(exp_share)} party members +{exp_share[0][1]} XP each'
                     + (f'  ({len(leveled)} leveled up)' if leveled else ''))
        for name, olv, nlv in leveled[:5]:
            lines.append(f'    • {name} Lv.{olv}→{nlv}')
        if len(leveled) > 5:
            lines.append(f'    • ... and {len(leveled) - 5} more level-ups')
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

        shiny_tag = f'  {"✨ SHINY ✨" if is_shiny else ""}' if is_shiny else ''
        tier_badge = colored_tier_badge(wtier)
        tier_line = f' {tier_badge}{shiny_tag}'
        if wtier in ('legendary', 'mythical'):
            flavor = _TIER_FLAVOR.get(wtier, '')
            tier_line += f'  {flavor}'
        lines += [
            tier_line,
            f'   {wemoji}  {wname}  ·  Lv.{wlv}',
            _ENC_DIV2,
        ]

        win_pct       = ei["win_pct"]
        eff           = ei.get("effectiveness", 1.0)
        eff_color = effectiveness_color(eff)
        reset = '\033[0m'
        eff_str       = (f'{eff_color}⚔️  super effective!{reset}' if eff >= 2.0
                         else f'{eff_color}⚠️  not very effective{reset}' if eff == 0.5
                         else f'{eff_color}✗  no effect{reset}' if eff == 0.0
                         else '')
        lines += [
            f' ⚔️   {buddy_name} Lv.{new_level} vs {wname} Lv.{wlv}  [{stat_bar(win_pct, 16)}] {win_pct}%  {eff_str}',
        ]

        if not ei['battle_won']:
            lines += [
                f'     ✗  DEFEAT — {wname} fled into the wild!',
                _ENC_DIV,
            ]
        else:
            lines.append('     ✓  VICTORY!')

            if ei.get('no_balls'):
                lines += [
                    ' 🎯  CATCH PHASE',
                    f'     No Pokéballs left!  {wname} slipped away...',
                    _ENC_DIV,
                ]
            else:
                lines.append(' 🎯  CATCH PHASE')
                throws = ei.get('throws', [])
                reset = '\033[0m'
                for i, t in enumerate(throws):
                    pct_str = f'{t["catch_pct"]}%'
                    pct_color = catch_pct_color(t["catch_pct"])
                    if t.get('berry_used') in ('golden', 'razz'):
                        base = t.get("base_pct", t["catch_pct"])
                        pct_str = f'{base}% → {pct_color}{t["catch_pct"]}%{reset}'
                    else:
                        pct_str = f'{pct_color}{pct_str}{reset}'
                    berry_str = f' {t["berry_emoji"]} {t["berry_name"]}' if t.get('berry_used') else ''
                    pinap_note = ' +1 Lv' if t['berry_used'] == 'pinap' else ''
                    lines.append(
                        f'     #{i+1} {t["ball_emoji"]} [{stat_bar(t["catch_pct"], 14)}] {pct_str}{berry_str}{pinap_note}'
                    )
                    if t['caught']:
                        if is_shiny:
                            shiny_color = '\033[95m'  # bright magenta
                            reset = '\033[0m'
                            lines.append(f'     {shiny_color}✨✨✨ SHINY {wemoji} {wname.upper()} CAUGHT! ✨✨✨{reset}')
                        else:
                            lines.append(f'     ★ GOTCHA! {wname} caught!')
                        break
                    else:
                        lines.append(
                            f'     💨 broke free (🔴×{t["rem_poke"]} 🔵×{t["rem_great"]} 🟡×{t["rem_ultra"]})'
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

def _render_journey(export_html=False, verbose=False):
    """Render /poke:history. Default: summary only. --verbose or --export: full log."""
    from collections import defaultdict
    col        = read_collection()
    stats      = read_stats()
    buddy_text = BUDDY_FILE.read_text(encoding='utf-8') if BUDDY_FILE.exists() else ''

    journal_rows = []
    for line in buddy_text.splitlines():
        m = re.match(r'\| (\d{4}-\d{2}-\d{2}) \| (.+?) \| \+(\d+) XP \|', line)
        if m:
            journal_rows.append({'date': m.group(1), 'desc': m.group(2).strip(), 'xp': int(m.group(3))})

    badge_rows = re.findall(r'- (.+?) \*\*(.+?)\*\* — \*(.+?)\* `(\d{4}-\d{2}-\d{2})`', buddy_text)
    trainer_m  = re.search(r'\*\*Trainer\*\*:\s*(.+)', buddy_text)
    trainer    = trainer_m.group(1).strip() if trainer_m else 'Trainer'

    total_xp   = stats.get('total_xp_ever', 0)
    streak     = stats.get('streak', 0)
    n_caught   = pokedex_count(col)

    lines = [
        f'🗺️  {trainer} — Pokémon Journey\n',
        f'Pokédex: {n_caught}  |  Streak: {streak} days  |  Total XP: {total_xp}\n',
        f'Tasks logged: {len(journal_rows)}  |  Badges: {len(badge_rows)}\n',
    ]

    if verbose or export_html:
        by_month = defaultdict(list)
        for row in journal_rows:
            by_month[row['date'][:7]].append(row)
        for month in sorted(by_month):
            try:    month_label = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
            except ValueError: month_label = month
            lines.append(f'\n## {month_label}\n')
            for row in sorted(by_month[month], key=lambda r: r['date']):
                lines.append(f'- `{row["date"]}` {row["desc"]} (+{row["xp"]} XP)\n')
        lines.append('\n## Badges & Milestones\n')
        for emoji_b, name_b, desc_b, date_b in badge_rows:
            lines.append(f'- `{date_b}` {emoji_b.strip()} **{name_b}** — {desc_b}\n')
        lines.append('\n## Party\n')
        for p in col['pokemon']:
            dn, de = displayed_form(p)
            shiny = '✨' if p.get('shiny') else ''
            lines.append(f'- {shiny}{de} {dn} Lv.{p["level"]} · {p.get("rarity","").replace("-shiny","")}\n')
    else:
        # Summary: last 5 tasks + recent badges
        lines.append('\nRecent tasks:\n')
        for row in journal_rows[-5:]:
            lines.append(f'  {row["date"]}  {row["desc"]} (+{row["xp"]} XP)\n')
        if badge_rows:
            lines.append('\nRecent badges:\n')
            for emoji_b, name_b, _, date_b in badge_rows[-3:]:
                lines.append(f'  {date_b}  {emoji_b.strip()} {name_b}\n')
        lines.append('\nUse /poke:history --verbose for full log.\n')

    output = ''.join(lines)
    print(output)

    if export_html:
        html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>Journey</title></head><body><pre style="font-family:monospace;white-space:pre-wrap">{output}</pre></body></html>'
        out_path = Path.cwd() / 'journey.html'
        out_path.write_text(html, encoding='utf-8')
        print(f'\n ✅ Exported: {out_path}')

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
        'level': level, 'xp': xp, 'caught': TODAY, 'rarity': 'starter', 'form': '',
        'nature': pick_nature(), 'friendship': 70,
    }], party=[name])

    STATE_FILE.write_text(f'Starter chosen: {name}! 🎉\n', encoding='utf-8')

    print(f' 🎉 Welcome, Trainer {trainer}!')
    print(f'    {emoji} {name} is now your active buddy (Lv.{level}, {xp} XP).')
    print(f'    Earn XP with /poke:xp <task> — your journey begins now!')

def do_shiny_rare():
    """List shiny mythical & legendary Pokémon."""
    col = read_collection()
    shiny_rares = [p for p in col['pokemon']
                   if (p.get('shiny') or '-shiny' in p.get('rarity', ''))
                   and p.get('rarity', '').replace('-shiny', '') in ('legendary', 'mythical')]
    if not shiny_rares:
        print('No shiny mythical or legendary Pokémon yet.')
        print('Keep grinding encounters — they\'re extremely rare!')
        return

    print(f' 🌟 SHINY MYTHICAL & LEGENDARY ({len(shiny_rares)})')
    print(' ─────────────────────────────────────────────')
    for p in shiny_rares:
        rarity = p.get('rarity', '').replace('-shiny', '')
        rarity_badge = tier_color(rarity) + f'{rarity.upper()}' + '\033[0m'
        print(f' ✨ {p["emoji"]} {p["name"]:<20} Lv.{p["level"]:<3} {rarity_badge}')
        print(f'    💬 /poke:switch {p["name"]}')

def do_switch(target_name, index=None):
    col = read_collection()
    matches = [p for p in col['pokemon'] if p['name'].lower() == target_name.lower()]

    if not matches:
        print(f"❌ {target_name} not found in your collection.")
        # Show shiny mythical/legendary first, then rest
        shiny_rare = []
        others = []
        for p in col['pokemon']:
            rarity = p.get('rarity', '').replace('-shiny', '')
            is_shiny = p.get('shiny') or '-shiny' in p.get('rarity', '')
            if is_shiny and rarity in ('legendary', 'mythical'):
                shiny_rare.append(p)
            else:
                others.append(p)

        all_sorted = shiny_rare + others
        print(f"\n   Available Pokémon ({len(all_sorted)} total):")
        for p in all_sorted[:20]:  # show first 20
            rarity = p.get('rarity', '').replace('-shiny', '')
            is_shiny = p.get('shiny') or '-shiny' in p.get('rarity', '')
            mark = '🌟' if is_shiny and rarity in ('legendary', 'mythical') else '✨' if is_shiny else ' '
            print(f"     {mark} {p['emoji']} {p['name']:<15} Lv.{p['level']:<3} ({rarity})")
        if len(all_sorted) > 20:
            print(f"     ... and {len(all_sorted) - 20} more")
        sys.exit(1)

    # Multiple matches: show menu + ask for clarification
    if len(matches) > 1:
        if index is None:
            print(f' 🔀 Found {len(matches)} {target_name}. Pick one:')
            for i, p in enumerate(matches, 1):
                rarity = p.get('rarity', '').replace('-shiny', '')
                is_shiny = p.get('shiny') or '-shiny' in p.get('rarity', '')
                shiny_tag = ' ✨ SHINY' if is_shiny else ''
                print(f'    {i}. {p["emoji"]} Lv.{p["level"]:<3} ({rarity}){shiny_tag}')
            print(f'\n    Run: /poke:switch {target_name} <number>')
            print(f'    Example: /poke:switch {target_name} 2')
            sys.exit(0)
        else:
            try:
                idx = int(index) - 1  # convert to 0-based
                if 0 <= idx < len(matches):
                    match = matches[idx]
                else:
                    print(f'❌ Invalid choice. Must be 1-{len(matches)}.')
                    sys.exit(1)
            except (ValueError, IndexError):
                print(f'❌ Invalid choice: {index}')
                sys.exit(1)
    else:
        match = matches[0]
    lines, _, cur_level, cur_xp, _, cur_name = read_buddy()
    # Extract current buddy's ID from active field (format: name:id or just name)
    cur_id = None
    if ':' in col['active']:
        _, cur_id = col['active'].split(':', 1)
    sync_active_to_collection(cur_name, cur_level, cur_xp, pokemon_id=cur_id)

    trainer = re.search(r'\*\*Trainer\*\*:\s*(.+)', BUDDY_FILE.read_text(encoding='utf-8'))
    trainer = trainer.group(1).strip() if trainer else 'Trainer'

    name, ptype, emoji = match['name'], match['type'], match['emoji']
    level, xp = match['level'], match['xp']
    rarity = match.get('rarity', '').replace('-shiny', '')
    is_shiny = match.get('shiny') or '-shiny' in match.get('rarity', '')
    # Heal legacy collection rows where xp was stored as 0 for high-level catches
    # (caused negative XP bar like -2900/150 on switch).
    xp = max(xp, xp_for_level(level))

    content = _build_buddy_content(name, ptype, emoji, trainer, level, xp)
    BUDDY_FILE.write_text(content, encoding='utf-8')

    # Store active as name:id to handle duplicates (fallback to name only if no ID)
    active_id = match.get('id', '')
    if active_id:
        col['active'] = f"{name}:{active_id}"
    else:
        col['active'] = name
    write_collection(col['active'], col['pokemon'], col.get('party'))

    disp_name, disp_emj = displayed_form(match)
    shiny_mark = '✨ SHINY ' if is_shiny else ''
    legendary_mark = f'🌟 {rarity.upper()}' if rarity in ('legendary', 'mythical') else ''
    STATE_FILE.write_text(f'Switched to {disp_name}! 🔄\n', encoding='utf-8')

    print(f' 🔄 Switched buddy: {cur_name} → {disp_emj} {disp_name}')
    print(f'    {shiny_mark}{disp_name} is now your active buddy! (Lv.{level}, {xp} XP) {legendary_mark}')

# ── Hub publish (pokemon-buddy-hub) ──────────────────────────────────────────

HUB_USER_AGENT = 'pokemon-buddy-cli/2.35.3 (+https://github.com/andriar/pokemon-buddy-claude)'

def _hub_request(method, path, *, token=None, payload=None, timeout=15):
    import urllib.request, urllib.error
    url = f'{HUB_API_BASE}{path}'
    data = None
    headers = {'Accept': 'application/json', 'User-Agent': HUB_USER_AGENT}
    if payload is not None:
        data = json.dumps(payload, default=lambda o: list(o) if isinstance(o, (set, frozenset)) else str(o)).encode()
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode() or '{}'
            return resp.status, json.loads(body) if body.strip().startswith(('{', '[')) else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        return e.code, {'error': body}
    except urllib.error.URLError as e:
        return 0, {'error': str(e.reason)}

def _read_auth():
    if not AUTH_FILE.exists():
        return None
    try:
        return json.loads(AUTH_FILE.read_text())
    except Exception:
        return None

def _write_auth(data):
    AUTH_FILE.write_text(json.dumps(data, indent=2))
    try:
        AUTH_FILE.chmod(0o600)
    except Exception:
        pass

def _build_publish_payload():
    col   = read_collection()
    stats = read_stats()
    _, _, level, xp, stage, name = read_buddy()
    active = next((p for p in col['pokemon'] if p.get('name') == col.get('active')), {}) or {}
    party_names = col.get('party') or []
    party = [p for n in party_names for p in col['pokemon'] if p.get('name') == n][:3]
    badges = []
    raw_badges = stats.get('gym_badges_earned') or stats.get('badges') or ''
    if isinstance(raw_badges, str):
        badges = [b.strip() for b in raw_badges.split(',') if b.strip()]
    elif isinstance(raw_badges, list):
        badges = list(raw_badges)
    buddy = {
        'name':       active.get('name', name),
        'level':      active.get('level', level),
        'xp':         active.get('xp', xp),
        'type':       active.get('type'),
        'emoji':      active.get('emoji'),
        'rarity':     active.get('rarity', 'common').replace('-shiny', ''),
        'shiny':      bool(active.get('shiny')),
        'nature':     active.get('nature'),
        'stage':      stage,
        'friendship': active.get('friendship'),
    }
    moves = MOVE_UNLOCKS.get(buddy['name'], {})
    buddy_moves = [
        {'level': lv, 'name': mv[0], 'type': mv[1], 'desc': mv[2], 'unlocked': buddy['level'] >= lv}
        for lv, mv in sorted(moves.items())
    ]
    raid = None
    if RAID_FILE.exists():
        try:
            raid = json.loads(RAID_FILE.read_text(encoding='utf-8'))
        except Exception:
            raid = None
    extras = {
        'leaders_defeated': stats.get('leaders_defeated', ''),
        'elite_defeated':   stats.get('elite_defeated', ''),
        'champion':         bool(stats.get('champion')),
        'caught_legendary': bool(stats.get('caught_legendary')),
        'caught_mythical':  bool(stats.get('caught_mythical')),
        'caught_shiny':     bool(stats.get('caught_shiny')),
        'shiny_count':      int(stats.get('shiny_count', 0) or 0),
        'milestones':       stats.get('milestones', ''),
        'daily_quest': {
            'date': stats.get('daily_quest_date'),
            'id':   stats.get('daily_quest_id'),
            'done': bool(stats.get('daily_quest_done')),
        },
        'combo':            int(stats.get('combo', 0) or 0),
        'longest_streak':   int(stats.get('longest_streak', 0) or 0),
        'bug_fixes':        int(stats.get('bug_fixes', 0) or 0),
        'features':         int(stats.get('features', 0) or 0),
        'ships':            int(stats.get('ships', 0) or 0),
    }
    journal = []
    if BUDDY_FILE.exists():
        for line in BUDDY_FILE.read_text(encoding='utf-8').splitlines():
            m = re.match(r'\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*([+\-]?\d+)?\s*(?:XP)?\s*\|', line)
            if m:
                journal.append({'date': m.group(1), 'event': m.group(2).strip(), 'xp': int(m.group(3)) if m.group(3) else 0})
    journal = journal[-15:]
    return {
        'buddy':       {**buddy, 'moves': buddy_moves},
        'party':       party,
        'collection':  col['pokemon'],
        'stats':       {k: v for k, v in stats.items() if not k.startswith('_')},
        'badges':      badges,
        'raid':        raid,
        'extras':      extras,
        'journal':     journal,
    }

def cmd_bio(args):
    """Usage: /poke:bio set <text> | title <text> | clear"""
    auth = _read_auth()
    if not auth:
        print(' 🔐 Not signed in. Run /poke:auth first.')
        sys.exit(1)
    if not args:
        print(' Usage: /poke:bio set <text>  |  title <text>  |  clear')
        sys.exit(1)
    sub = args[0].lower()
    payload = {}
    rest = ' '.join(args[1:]).strip()
    if sub == 'set':
        payload['bio'] = rest
    elif sub == 'title':
        payload['title'] = rest
    elif sub == 'clear':
        payload = {'bio': '', 'title': ''}
    else:
        print(' ❌ Unknown sub-command. Use: set | title | clear')
        sys.exit(1)
    code, body = _hub_request('PATCH', '/me', token=auth['token'], payload=payload)
    if code != 200:
        print(f' ❌ Failed ({code}): {body.get("error", "")}')
        sys.exit(1)
    if 'bio' in payload:
        print(f' ✏️  Bio updated: {payload["bio"] or "(cleared)"}')
    if 'title' in payload:
        print(f' 🏷️  Title updated: {payload["title"] or "(cleared)"}')

def cmd_follow(args, action='follow'):
    auth = _read_auth()
    if not auth:
        print(' 🔐 Not signed in. Run /poke:auth first.')
        sys.exit(1)
    if not args:
        print(f' Usage: /poke:{action} <username>')
        sys.exit(1)
    target = args[0].lstrip('@').strip()
    method = 'POST' if action == 'follow' else 'DELETE'
    code, body = _hub_request(method, f'/follow/{target}', token=auth['token'])
    if code not in (200, 204):
        print(f' ❌ {action.title()} failed ({code}): {body.get("error", "")}')
        sys.exit(1)
    icon = '🤝' if action == 'follow' else '👋'
    print(f' {icon} {action.title()}ed @{target}')

def cmd_auth():
    code, body = _hub_request('POST', '/auth/cli/start')
    if code != 200:
        print(f' ❌ Hub unreachable ({HUB_API_BASE}): {body.get("error", code)}')
        sys.exit(1)
    device_code = body['device_code']
    verify_url  = body['verification_url']
    print(' 🔐 Pokemon Buddy Hub — device login')
    print(f'    Open: {verify_url}')
    print('    Sign in with GitHub. Waiting…')
    import time
    deadline = time.time() + body.get('expires_in', 600)
    while time.time() < deadline:
        time.sleep(3)
        c, b = _hub_request('GET', f'/auth/cli/poll?code={device_code}')
        if c != 200:
            print(f' ❌ Poll failed: {b.get("error", c)}')
            sys.exit(1)
        if b.get('status') == 'ok':
            _write_auth({'token': b['token'], 'username': b['username'], 'api': HUB_API_BASE})
            print(f' ✅ Linked as @{b["username"]} — token saved to {AUTH_FILE}')
            return
    print(' ⏰ Login timed out. Try again.')
    sys.exit(1)

def cmd_publish():
    auth = _read_auth()
    if not auth:
        print(' 🔐 Not signed in. Run /poke:auth first.')
        sys.exit(1)
    payload = _build_publish_payload()
    code, body = _hub_request('POST', '/sync', token=auth['token'], payload=payload)
    if code != 200:
        print(f' ❌ Publish failed ({code}): {body.get("error", "")}')
        sys.exit(1)
    print(f' 📡 Published as @{auth["username"]}')
    print(f'    Profile: {body.get("profile_url", HUB_WEB_BASE + "/t/" + auth["username"])}')
    print(f'    Note: profile is PUBLIC. Run /poke:unpublish to remove.')

def cmd_unpublish():
    auth = _read_auth()
    if not auth:
        print(' 🔐 Not signed in.')
        sys.exit(1)
    code, body = _hub_request('DELETE', '/sync', token=auth['token'])
    if code not in (200, 204):
        print(f' ❌ Unpublish failed ({code}): {body.get("error", "")}')
        sys.exit(1)
    print(' 🗑️  Profile removed from hub.')

def cmd_profile_url():
    auth = _read_auth()
    if not auth:
        print(' 🔐 Not signed in. Run /poke:auth first.')
        sys.exit(1)
    print(f'{HUB_WEB_BASE}/t/{auth["username"]}')

def cmd_doctor(args):
    """Diagnose collection drift: stuck evolutions, friendship gaps, XP/level mismatch.

    --fix: also bump friendship of stuck evolution candidates to the threshold.
    """
    fix = '--fix' in args
    col = read_collection()
    fixed_any = False

    # Build evolved-name set so we can ignore final-stage entries listed as base
    final_stage_names = set()
    for chain in WILD_EVOLUTIONS.values():
        for _, evo_name, *_ in chain:
            final_stage_names.add(evo_name)

    wild_stuck = []
    friendship_ready = []
    friendship_close = []
    trade_pending = []
    xp_drift = []
    name_set = {p['name'] for p in col['pokemon']}

    for p in col['pokemon']:
        nm = p.get('name')
        lv = int(p.get('level', 1))
        xp = int(p.get('xp', 0))
        fr = int(p.get('friendship', 70))

        # Wild level evolutions
        chain = WILD_EVOLUTIONS.get(nm)
        if chain:
            best = None
            for min_lv, evo_name, *_ in chain:
                if lv >= min_lv:
                    best = (min_lv, evo_name)
            if best:
                wild_stuck.append((nm, lv, best[1], best[0]))

        # Trade evolutions (export/backup-gated)
        te = TRADE_EVOLUTIONS.get(nm)
        if te:
            trade_pending.append((nm, te[0], te[2]))

        # Friendship evolutions
        for src, tgt_name, _t, _e, min_f, (when, _hours) in FRIENDSHIP_EVOLUTIONS:
            if nm != src:
                continue
            if fr >= min_f:
                friendship_ready.append((nm, tgt_name, fr, min_f, when))
                if fix:
                    fixed_any = True
            else:
                friendship_close.append((nm, tgt_name, fr, min_f, when))
                if fix:
                    p['friendship'] = min_f
                    fixed_any = True

        # XP / level integrity
        try:
            expected_lv, _expected_xp, _ = clamp_to_cap(xp)
            if abs(expected_lv - lv) >= 2:
                xp_drift.append((nm, lv, expected_lv, xp))
        except Exception:
            pass

    active = col.get('active')
    party  = [n for n in col.get('party', []) if n]
    missing_active = active and active not in name_set
    missing_party  = [n for n in party if n not in name_set]

    # ── Render report
    print(' 🩺 Pokemon Buddy Doctor')
    print(f'    Collection: {len(col["pokemon"])} entries · active: {active} · party: {", ".join(party) or "—"}')
    print()

    if wild_stuck:
        print(f' 🟥 Wild evolution stuck ({len(wild_stuck)}):')
        for nm, lv, evo, min_lv in wild_stuck:
            print(f'    {nm} Lv.{lv} → should be {evo} (min Lv.{min_lv}) — try /poke:xp to trigger evolution check')
        print()

    if friendship_ready:
        print(f' 💖 Friendship evolution READY ({len(friendship_ready)}):')
        for nm, tgt, fr, mf, when in friendship_ready:
            print(f'    {nm} (friendship {fr}/{mf}) → {tgt} during {when} — next /poke:xp at correct hour evolves')
        print()

    if friendship_close:
        print(f' 💛 Friendship evolution PENDING ({len(friendship_close)}):')
        for nm, tgt, fr, mf, when in friendship_close:
            gap = mf - fr
            print(f'    {nm} (friendship {fr}/{mf}, need +{gap}) → {tgt} during {when}')
        print()

    if trade_pending:
        print(f' 📦 Trade evolution candidates ({len(trade_pending)}):')
        for nm, tgt, method in trade_pending:
            print(f'    {nm} → {tgt} via /poke:{method}')
        print()

    if xp_drift:
        print(f' ⚠️  XP/level drift ({len(xp_drift)}):')
        for nm, lv, expected_lv, xp in xp_drift:
            print(f'    {nm}: stored Lv.{lv}, XP {xp} → expected Lv.{expected_lv}')
        print()

    if missing_active or missing_party:
        print(' ⚠️  Active/party drift:')
        if missing_active:
            print(f'    active "{active}" not in collection')
        for n in missing_party:
            print(f'    party slot "{n}" not in collection')
        print()

    if fix and fixed_any:
        write_collection(col['active'], col['pokemon'], col.get('party'))
        evos = apply_friendship_evolutions(col)
        if evos:
            write_collection(col['active'], col['pokemon'], col.get('party'))
            print(f' 💖 Triggered evolutions: {", ".join(evos)}')
        print(' ✅ --fix applied: friendship bumped to threshold; re-run /poke:doctor to verify')
    elif not (wild_stuck or friendship_ready or friendship_close or trade_pending or xp_drift or missing_active or missing_party):
        print(' ✅ All clear — no drift detected')
    elif not fix and (friendship_close or friendship_ready):
        print(' 💡 Run with --fix to bump friendship to threshold (does NOT skip daytime/nighttime gate)')

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: buddy-update.py status|statusline|card|html|og|readme|dex|backup|import|xp|xp-auto|badge|choose|switch|catch|battle|elite|purge")
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
        mode_pref = os.environ.get('POKE_STATUSLINE_MODE', 'normal')
        print(render_statusline(plugin_mode=plugin_mode, mode=mode_pref))
        sys.exit(0)

    if mode == 'update-check':
        # Background mode — silent unless --verbose, never blocks
        force  = '--force' in args
        result = run_update_check(force=force)
        if '--verbose' in args:
            print(json.dumps(result, indent=2))
        sys.exit(0)

    if mode == 'auth':
        cmd_auth(); sys.exit(0)
    if mode == 'publish':
        cmd_publish(); sys.exit(0)
    if mode == 'unpublish':
        cmd_unpublish(); sys.exit(0)
    if mode == 'profile-url':
        cmd_profile_url(); sys.exit(0)
    if mode == 'doctor':
        cmd_doctor(args[1:]); sys.exit(0)
    if mode == 'bio':
        cmd_bio(args[1:]); sys.exit(0)
    if mode == 'follow':
        cmd_follow(args[1:], 'follow'); sys.exit(0)
    if mode == 'unfollow':
        cmd_follow(args[1:], 'unfollow'); sys.exit(0)

    if mode == 'card':
        print(render_card())
        sys.exit(0)

    if mode == 'dex':
        filter_arg = args[1] if len(args) > 1 else None
        print(render_dex(filter_arg))
        sys.exit(0)

    if mode == 'moves':
        col = read_collection()
        active = next((p for p in col['pokemon'] if p.get('name') == col.get('active')), None)
        if not active:
            print(' ❌ No active buddy.')
            sys.exit(1)
        name, level = active['name'], active['level']
        moves = MOVE_UNLOCKS.get(name, {})
        print(f' 📖 {active["emoji"]} {name} Lv.{level} — MOVE LEARNSET')
        print(' ' + '─' * 48)
        if not moves:
            print(f'   No learnset data for {name} yet.')
            print(f'   Shipped species: {", ".join(sorted(MOVE_UNLOCKS))}')
        else:
            for lv in sorted(moves):
                mname, mtype, desc = moves[lv]
                mark = '✓' if level >= lv else '·'
                lock = '' if level >= lv else f'  (unlock Lv.{lv})'
                print(f'   {mark} Lv.{lv:<3} {mname:<14} [{mtype}]  {desc}{lock}')
        sys.exit(0)

    if mode == 'battle':
        tr_stats = read_stats()
        col = read_collection()
        active = next((p for p in col['pokemon'] if p.get('name') == col.get('active')), None)
        if len(args) < 2:
            btype = active['type'] if active else None
            blv = active['level'] if active else None
            print(list_leaders(tr_stats, buddy_type=btype, buddy_level=blv))
            sys.exit(0)
        leader_id = args[1].lower()
        if not active:
            print(' ❌ No active buddy. Pick one with /poke:switch.')
            sys.exit(1)
        # Anti-cheat: battle stamina gate
        stamina = regen_stamina(tr_stats)
        if stamina <= 0:
            wait = stamina_eta(tr_stats)
            print(' 💤 Out of battle stamina. Rest and try again.')
            print(f'    Next point regenerates in {fmt_duration(wait)} '
                  f'(max {BATTLE_STAMINA_MAX}, +1 per {BATTLE_REGEN_SECS // 60}min).')
            write_stats(tr_stats)
            sys.exit(0)
        tr_stats['battle_stamina'] = stamina - 1
        if tr_stats.get('battle_stamina_ts', 0) == 0 or stamina == BATTLE_STAMINA_MAX:
            tr_stats['battle_stamina_ts'] = int(time.time())
        won, xp_reward, log, badge = battle_leader(
            leader_id, active['level'], active['type'], tr_stats, held_item=get_held_item()
        )
        print('\n'.join(log))
        print(f'    💪 Stamina: {tr_stats["battle_stamina"]}/{BATTLE_STAMINA_MAX}'
              + (f'  (next +1 in {fmt_duration(stamina_eta(tr_stats))})'
                 if tr_stats['battle_stamina'] < BATTLE_STAMINA_MAX else ''))
        tr_stats['total_xp_ever'] = tr_stats.get('total_xp_ever', 0) + xp_reward
        write_stats(tr_stats)
        if badge:
            append_badge(f'- {badge[1]} **{badge[2]}** — *earned by defeating {_LEADER_BY_ID[leader_id][1]}* `{TODAY}`')
        sys.exit(0)

    if mode == 'elite':
        tr_stats = read_stats()
        col = read_collection()
        active = next((p for p in col['pokemon'] if p.get('name') == col.get('active')), None)
        if len(args) < 2:
            print(list_elite(tr_stats))
            sys.exit(0)
        eid = args[1].lower()
        if not active:
            print(' ❌ No active buddy. Pick one with /poke:switch.')
            sys.exit(1)
        stamina = regen_stamina(tr_stats)
        if stamina <= 0:
            wait = stamina_eta(tr_stats)
            print(' 💤 Out of battle stamina. Rest and try again.')
            print(f'    Next point regenerates in {fmt_duration(wait)}.')
            write_stats(tr_stats)
            sys.exit(0)
        tr_stats['battle_stamina'] = stamina - 1
        if tr_stats.get('battle_stamina_ts', 0) == 0 or stamina == BATTLE_STAMINA_MAX:
            tr_stats['battle_stamina_ts'] = int(time.time())
        won, xp_reward, log, champion = battle_elite(
            eid, active['level'], active['type'], tr_stats, held_item=get_held_item()
        )
        print('\n'.join(log))
        print(f'    💪 Stamina: {tr_stats["battle_stamina"]}/{BATTLE_STAMINA_MAX}')
        tr_stats['total_xp_ever'] = tr_stats.get('total_xp_ever', 0) + xp_reward
        write_stats(tr_stats)
        if champion:
            append_badge(f'- 🏆 **Champion** — *defeated the Elite Four* `{TODAY}`')
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

    if mode == 'history':
        export_html = '--export' in args
        verbose     = '--verbose' in args or '--export' in args
        _render_journey(export_html, verbose)
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
        # Trade evolutions: /poke:export triggers Gastly→Haunter→Gengar, Abra chain
        evos = apply_trade_evolutions('export')
        if evos:
            print(f' ✨ Trade evolution! {", ".join(evos)}')
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
        # Trade evolutions: /poke:backup triggers Machop→Machoke→Machamp
        evos = apply_trade_evolutions('backup')
        if evos:
            print(f' ✨ Trade evolution! {", ".join(evos)}')
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
        name = args[1] if len(args) > 1 else ''
        idx = args[2] if len(args) > 2 else None
        do_switch(name, idx)
        sys.exit(0)

    if mode == 'shiny-rare':
        do_shiny_rare()
        sys.exit(0)

    if mode == 'raid':
        raid = get_weekly_raid()
        if not raid:
            print(' 🐉 No raid boss available.')
        else:
            hp_pct  = int(raid['hp_remaining'] / raid['boss_hp'] * 100)
            bar_len = 30
            filled  = int(bar_len * hp_pct / 100)
            hp_bar  = '█' * filled + '░' * (bar_len - filled)
            status  = '✅ CAPTURED' if raid.get('captured') else f'{hp_pct}% HP remaining'
            total_dmg = sum(e['damage'] for e in raid.get('damage_log', []))
            print(f' 🐉 Weekly Raid Boss — Week {raid["week_id"]}')
            print(f'    {raid["boss_emoji"]} {raid["boss_name"]} [{raid["boss_type"]}]')
            print(f'    [{hp_bar}]  {raid["hp_remaining"]} / {raid["boss_hp"]} HP')
            print(f'    Status: {status}')
            print(f'    Your total damage dealt: {total_dmg}')
            print(f'    New boss spawns every Monday.')
        sys.exit(0)

    if mode == 'party':
        sub = args[1] if len(args) > 1 else 'list'
        col = read_collection()
        party = col.get('party', [col['active']] if col['active'] else [])
        if sub == 'list':
            print(' 👥 Active Party (lead = slot 1):')
            for i, name in enumerate(party, 1):
                p = next((x for x in col['pokemon'] if x['name'] == name), None)
                tag = ' ← LEAD' if i == 1 else ''
                lvl = p['level'] if p else '?'
                print(f'   Slot {i}: {name} Lv.{lvl}{tag}')
            if len(party) < 3:
                print(f'\n   Add more: /poke:party add <name>')
        elif sub == 'add':
            name = args[2] if len(args) > 2 else ''
            match = next((p for p in col['pokemon'] if p['name'].lower() == name.lower()), None)
            if not match:
                print(f' ❌ {name} not in collection.')
            elif match['name'] in party:
                print(f' ❌ {match["name"]} already in party.')
            elif len(party) >= 3:
                print(f' ❌ Party full (3/3). Remove one first.')
            else:
                party.append(match['name'])
                write_collection(col['active'], col['pokemon'], party)
                print(f' ✅ {match["name"]} added to party (slot {len(party)}).')
        elif sub == 'remove':
            name = args[2] if len(args) > 2 else ''
            if name.lower() == col['active'].lower():
                print(f' ❌ Cannot remove lead buddy. Use /poke:switch first.')
            else:
                match = next((n for n in party if n.lower() == name.lower()), None)
                if not match:
                    print(f' ❌ {name} not in party.')
                else:
                    party.remove(match)
                    write_collection(col['active'], col['pokemon'], party)
                    print(f' ✅ {match} removed from party.')
        elif sub == 'suggest':
            # Recommend a type-diverse trio from collection, highest levels first
            sorted_pool = sorted(col['pokemon'], key=lambda p: p.get('level', 1), reverse=True)
            picks, seen_types = [], set()
            for p in sorted_pool:
                t = p.get('type', '?')
                if t not in seen_types:
                    picks.append(p)
                    seen_types.add(t)
                if len(picks) == 3: break
            if len(picks) < 3:
                for p in sorted_pool:
                    if p['name'] not in {x['name'] for x in picks}:
                        picks.append(p)
                    if len(picks) == 3: break
            print(' 🎯 SUGGESTED PARTY (type diversity + highest level):')
            for i, p in enumerate(picks, 1):
                tag = ' ← LEAD' if i == 1 else ''
                print(f'   Slot {i}: {p["emoji"]} {p["name"]} [{p.get("type","?")}] Lv.{p.get("level",1)}{tag}')
            print('')
            print(f' Apply → /poke:party order {",".join(p["name"] for p in picks)}')
        elif sub == 'order':
            # /poke:party order name1,name2,name3
            names = [n.strip() for n in (args[2] if len(args) > 2 else '').split(',')]
            valid = [n for n in names if any(p['name'].lower() == n.lower() for p in col['pokemon'])]
            if not valid:
                print(' ❌ No valid names provided.')
            else:
                canonical = [next(p['name'] for p in col['pokemon'] if p['name'].lower() == n.lower()) for n in valid]
                party = canonical[:3]
                col['active'] = party[0]
                write_collection(col['active'], col['pokemon'], party)
                print(f' ✅ Party reordered: {" → ".join(party)}')
        else:
            print(' Usage: buddy-update.py party list|add <name>|remove <name>|order <n1,n2,n3>')
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

    # Extract held item once from already-read buddy text (avoids 3 extra file reads)
    _held_m     = re.search(r'\*\*HeldItem\*\*:\s*(\S+)', text)
    _held_item  = _held_m.group(1) if _held_m and _held_m.group(1) != 'none' else None

    add_xp = 0; log_desc = ''; badge_line = ''
    b_emoji = b_name = b_desc = ''
    streak_bonus = 0; streak_count = 0; streak_mult = 1.0
    inventory_msg = ''; combo = 1; combo_mult = 1.0
    quest_msg = ''; lv_reward_msg = ''; raid_msg = ''
    cap_msg = ''

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

        # Anti-cheat: dedup near-identical descriptions within window (manual mode only)
        if not is_auto and check_xp_dedup(tr_stats, desc):
            wait = XP_DEDUP_WINDOW - (int(time.time()) - int(tr_stats.get('last_xp_ts', 0) or 0))
            print(f' ⚠️  Duplicate XP rejected — same task within {XP_DEDUP_WINDOW // 60} min.')
            print(f'    Describe a different task or retry in {fmt_duration(wait)}.')
            sys.exit(0)

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
        lucky_mult  = 1.5 if _held_item == 'lucky_egg' else 1.0

        # Cap stacked multipliers to prevent 6×+ spikes that broke the old curve
        stack_mult = min(combo_mult * streak_mult * lucky_mult, 3.0)
        add_xp = int(base_xp * stack_mult) + streak_bonus

        # Anti-cheat: clip to daily cap (level-scaled), record dedup fingerprint
        col = read_collection()
        _cap_for_msg = daily_cap_for(col)
        add_xp, was_capped, _ = apply_daily_cap(tr_stats, add_xp, col)
        if was_capped:
            cap_msg = f'🛑 Daily XP cap ({_cap_for_msg}) reached — clipped to +{add_xp} XP. Resets 00:00.'
        tr_stats['daily_xp'] = int(tr_stats.get('daily_xp', 0) or 0) + add_xp
        if not is_auto:
            tr_stats['last_xp_hash'] = _desc_hash(desc)
            tr_stats['last_xp_ts']   = int(time.time())

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

    # Egg hatching: tick progress on every XP gain (Soul badge required)
    egg_msg = ''
    if mode in ('xp', 'xp-auto') and has_unlock('breeding', tr_stats):
        egg_msg = tick_egg(tr_stats, add_xp)

    # Raid boss damage (Earth badge): XP chips boss HP
    raid_msg = ''
    if mode in ('xp', 'xp-auto') and has_unlock('raid_battles', tr_stats):
        raid, raid_dmg, raid_ko = apply_raid_damage(add_xp)
        if raid and raid_dmg:
            hp_pct = int(raid['hp_remaining'] / raid['boss_hp'] * 100)
            if raid_ko:
                raid_msg = (f'🐉 RAID KO! {raid["boss_emoji"]} {raid["boss_name"]} defeated! '
                            f'Added to Pokédex! Bonus XP incoming!')
                # Add boss to collection
                add_to_collection(raid['boss_name'], raid['boss_type'], raid['boss_emoji'], 'legendary')
            else:
                raid_msg = (f'🐉 Raid: {raid["boss_emoji"]} {raid["boss_name"]} '
                            f'{hp_pct}% HP  (-{raid_dmg} dmg)')

    # Read collection once — reused for party split, sync, exp share, encounter
    col = read_collection()

    # Lazy XP-curve migration (v2.32): level-lock buddy + party to new curve floors
    old_xp, _migrate_msg = migrate_xp_curve(tr_stats, col, old_level, old_xp)
    if _migrate_msg:
        write_collection(col['active'], col['pokemon'], col.get('party'))
        print(_migrate_msg)

    # Party XP split (Thunder badge): bench members get share before lead is banked.
    party_xp_log = []
    if mode in ('xp', 'xp-auto') and has_unlock('party_xp', tr_stats):
        add_xp, party_xp_log = distribute_party_xp(add_xp, buddy_name, col)

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
    if _held_item != 'everstone':
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

    # Friendship tick: +1 per XP award, +3 per level-up, +5 per evolution
    friendship_evo_msg = ''
    if mode in ('xp', 'xp-auto', 'badge'):
        gained_friendship = 1
        if new_level > old_level: gained_friendship += 3 * (new_level - old_level)
        if evolved:               gained_friendship += 5
        boost_friendship(buddy_name, gained_friendship, col)
        f_evos = apply_friendship_evolutions(col)
        if f_evos:
            friendship_evo_msg = ' 💖 Bond evolution! ' + ', '.join(f_evos)
            if col.get('active') and col['active'] != buddy_name:
                buddy_name = col['active']

    # Sync collection (reuses col in-place)
    sync_active_to_collection(buddy_name, new_level, new_xp, col)

    exp_share = distribute_overflow_xp(overflow_xp, buddy_name, tr_stats, col) if overflow_xp else []

    # Run wild encounter (battle + ball throw)
    if mode == 'xp':
        base_xp_for_enc = detect_xp(args[1] if len(args) > 1 else '')
    elif mode == 'xp-auto':
        base_xp_for_enc = base_xp
    else:
        base_xp_for_enc = add_xp
    owned        = {p['name'] for p in col['pokemon']}
    buddy_rarity = next((p.get('rarity','').replace('-shiny','') for p in col['pokemon'] if p['name'] == col.get('active')), None)
    buddy_type   = STARTER_DATA.get(buddy_name, {}).get('type', 'Normal')
    enc_role = None if mode == 'xp-auto' else get_role_type()

    catch_result, encounter_info = run_encounter(
        base_xp_for_enc, owned, enc_role, buddy_rarity,
        new_level, buddy_type, tr_stats, col,
    )

    if catch_result:
        base_tier = catch_result[0].replace('-shiny', '')
        if base_tier == 'legendary': tr_stats['caught_legendary'] = True
        if base_tier == 'mythical':  tr_stats['caught_mythical']  = True
        if catch_result[4]:
            tr_stats['caught_shiny'] = True
            tr_stats['shiny_count']  = tr_stats.get('shiny_count', 0) + 1

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
        exp_share, streak_mult, lucky_mult, item_drop, party_xp_log, raid_msg, egg_msg,
    ))
    if friendship_evo_msg:
        print(friendship_evo_msg)
    if cap_msg:
        print(f' {cap_msg}')

if __name__ == '__main__':
    main()
