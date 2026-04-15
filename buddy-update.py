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
TODAY           = date.today().strftime('%Y-%m-%d')
LOG_CAP         = 15
ARCHIVE_FILE    = Path.home() / '.claude' / 'buddy-log-archive.md'

SHINY_RATE      = 1 / 200   # 0.5% — rarer than legendary
STREAK_BONUS_XP = 20        # bonus XP for first award of the day

# ── Pokemon data ──────────────────────────────────────────────────────────────

STARTER_DATA = {
    'Charmander': {
        'type': 'Fire', 'emoji': '🔥',
        'specialty': 'Frontend / JavaScript',
        'evolutions': [('Charmeleon', 16, '🔥'), ('Charizard', 36, '🐉')],
        'stats': {'HP': 39, 'Attack': 52, 'Defense': 43,
                  'Special Atk': 60, 'Special Def': 50, 'Speed': 65},
        'moves': [
            ('Scratch', 'Normal', 'Lv.1', 'JS fundamentals'),
            ('Ember',   'Fire',   'Lv.1', 'First components/UI'),
            ('???', '???', 'Lv.5',  'Learn more to unlock!'),
            ('???', '???', 'Lv.10', 'Learn more to unlock!'),
        ],
    },
    'Bulbasaur': {
        'type': 'Grass', 'emoji': '🌿',
        'specialty': 'Backend / Python',
        'evolutions': [('Ivysaur', 16, '🌿'), ('Venusaur', 36, '🌺')],
        'stats': {'HP': 45, 'Attack': 49, 'Defense': 49,
                  'Special Atk': 65, 'Special Def': 65, 'Speed': 45},
        'moves': [
            ('Tackle',    'Normal', 'Lv.1', 'Server basics'),
            ('Vine Whip', 'Grass',  'Lv.1', 'API endpoints'),
            ('???', '???', 'Lv.5',  'Learn more to unlock!'),
            ('???', '???', 'Lv.10', 'Learn more to unlock!'),
        ],
    },
    'Squirtle': {
        'type': 'Water', 'emoji': '💧',
        'specialty': 'Database / SQL',
        'evolutions': [('Wartortle', 16, '💧'), ('Blastoise', 36, '💦')],
        'stats': {'HP': 44, 'Attack': 48, 'Defense': 65,
                  'Special Atk': 50, 'Special Def': 64, 'Speed': 43},
        'moves': [
            ('Tackle',    'Normal', 'Lv.1', 'SQL basics'),
            ('Water Gun', 'Water',  'Lv.1', 'First queries'),
            ('???', '???', 'Lv.5',  'Learn more to unlock!'),
            ('???', '???', 'Lv.10', 'Learn more to unlock!'),
        ],
    },
}

MOVE_UNLOCKS = {
    'Charmander': {
        5:  ('Metal Claw',    'Steel',  'TypeScript & type safety'),
        10: ('Fire Spin',     'Fire',   'State management (Redux/Zustand)'),
        15: ('Dragon Breath', 'Dragon', 'Full-stack API integration'),
        20: ('Flamethrower',  'Fire',   'Performance optimization'),
    },
    'Bulbasaur': {
        5:  ('Razor Leaf',    'Grass',  'ORM & database queries'),
        10: ('Sleep Powder',  'Grass',  'Async / concurrency'),
        15: ('Leech Seed',    'Grass',  'Microservices architecture'),
        20: ('Solar Beam',    'Grass',  'System design & scaling'),
    },
    'Squirtle': {
        5:  ('Bubble Beam',   'Water',  'Joins & indexes'),
        10: ('Withdraw',      'Water',  'Transactions & ACID'),
        15: ('Hydro Pump',    'Water',  'Query optimization'),
        20: ('Blizzard',      'Ice',    'Data warehousing & analytics'),
    },
}

# Starting level for newly caught Pokemon — higher rarity = joins at higher level
RARITY_START_LEVEL = {
    'common':    1,
    'uncommon':  5,
    'rare':      15,
    'legendary': 25,
    'mythical':  30,
}

# Catch-rate multipliers granted by buddy's rarity — applied per tier probability
# Common buddy = no boost (baseline). Higher buddy rarity = better odds at rare+ tiers.
BUDDY_RARITY_BOOST = {
    'uncommon':  {'rare': 1.5},
    'rare':      {'rare': 2.0, 'legendary': 1.5},
    'legendary': {'rare': 2.5, 'legendary': 2.0, 'mythical': 1.5},
    'mythical':  {'rare': 3.0, 'legendary': 2.5, 'mythical': 2.0},
}

CATCH_RATES = {
    10:  [('common',    0.08)],
    20:  [('common',    0.10)],
    25:  [('common',    0.10)],
    30:  [('common',    0.15), ('uncommon',  0.03)],
    40:  [('common',    0.25), ('uncommon',  0.10), ('rare',      0.02)],
    50:  [('uncommon',  0.15), ('rare',      0.04)],
    75:  [('uncommon',  0.25), ('rare',      0.08)],
    100: [('uncommon',  0.20), ('rare',      0.15), ('legendary', 0.04), ('mythical', 0.01)],
}

POKEMON_POOL = {
    'common': [
        # Gen 1
        ('Pidgey',    'Normal',   '🐦'),
        ('Geodude',   'Rock',     '🗿'),
        ('Magikarp',  'Water',    '🐟'),
        ('Weedle',    'Bug',      '🐛'),
        ('Zubat',     'Poison',   '🦇'),
        ('Rattata',   'Normal',   '🐭'),
        # Gen 2
        ('Sentret',   'Normal',   '🐹'),
        ('Hoothoot',  'Normal',   '🦉'),
        ('Spinarak',  'Bug',      '🐞'),
        # Gen 3
        ('Wurmple',   'Bug',      '🐛'),
        ('Zigzagoon', 'Normal',   '🐺'),
        # Gen 4
        ('Bidoof',    'Normal',   '🐻'),
        ('Starly',    'Normal',   '🐦'),
        # Gen 5
        ('Patrat',    'Normal',   '🐭'),
        ('Pidove',    'Normal',   '🐦'),
        # Gen 6
        ('Fletchling','Normal',   '🐦'),
        ('Scatterbug','Bug',      '🐛'),
        # Gen 7
        ('Pikipek',   'Normal',   '🦜'),
        ('Yungoos',   'Normal',   '🐾'),
        # Gen 8
        ('Wooloo',    'Normal',   '🐑'),
        ('Skwovet',   'Normal',   '🐹'),
        # Gen 9
        ('Lechonk',   'Normal',   '🐷'),
        ('Tarountula','Bug',      '🐞'),
    ],
    'uncommon': [
        # Gen 1
        ('Pikachu',   'Electric', '⚡'),
        ('Eevee',     'Normal',   '🦊'),
        ('Vulpix',    'Fire',     '🦊'),
        ('Psyduck',   'Water',    '🦆'),
        ('Gastly',    'Ghost',    '👻'),
        ('Machop',    'Fighting', '💪'),
        ('Abra',      'Psychic',  '🔮'),
        # Gen 2
        ('Togepi',    'Fairy',    '🥚'),
        ('Espeon',    'Psychic',  '🔮'),
        ('Umbreon',   'Dark',     '🌑'),
        ('Heracross',  'Bug',     '🦴'),
        # Gen 3
        ('Ralts',     'Psychic',  '🔮'),
        ('Bagon',     'Dragon',   '🐲'),
        ('Beldum',    'Steel',    '🔧'),
        # Gen 4
        ('Riolu',     'Fighting', '💪'),
        ('Rotom',     'Electric', '⚡'),
        ('Gible',     'Dragon',   '🐲'),
        # Gen 5
        ('Zorua',     'Dark',     '🦊'),
        ('Deino',     'Dragon',   '🐲'),
        ('Larvesta',  'Fire',     '🦋'),
        # Gen 6
        ('Noibat',    'Dragon',   '🦇'),
        ('Espurr',    'Psychic',  '🔮'),
        # Gen 7
        ('Jangmo-o',  'Dragon',   '🐲'),
        ('Mimikyu',   'Ghost',    '👻'),
        ('Comfey',    'Fairy',    '🌺'),
        # Gen 8
        ('Dreepy',    'Dragon',   '👻'),
        ('Falinks',   'Fighting', '💪'),
        # Gen 9
        ('Frigibax',  'Dragon',   '🐲'),
        ('Pawmi',     'Electric', '⚡'),
    ],
    'rare': [
        # Gen 1
        ('Snorlax',   'Normal',   '😴'),
        ('Lapras',    'Water',    '💎'),
        ('Dratini',   'Dragon',   '🐲'),
        ('Porygon',   'Normal',   '💻'),
        ('Scyther',   'Bug',      '🔪'),
        ('Jolteon',   'Electric', '⚡'),
        # Gen 2
        ('Tyranitar', 'Rock',     '🦖'),
        ('Dragonite', 'Dragon',   '🐉'),
        ('Blissey',   'Normal',   '💗'),
        # Gen 3
        ('Flygon',    'Dragon',   '🐲'),
        ('Metagross',  'Steel',   '🔧'),
        ('Salamence', 'Dragon',   '🐉'),
        # Gen 4
        ('Garchomp',  'Dragon',   '🐉'),
        ('Lucario',   'Fighting', '💪'),
        ('Togekiss',  'Fairy',    '🐦'),
        # Gen 5
        ('Hydreigon', 'Dragon',   '🐲'),
        ('Volcarona', 'Fire',     '🦋'),
        ('Haxorus',   'Dragon',   '🔪'),
        # Gen 6
        ('Goodra',    'Dragon',   '🐲'),
        ('Aegislash', 'Steel',    '🔪'),
        ('Sylveon',   'Fairy',    '🎀'),
        # Gen 7
        ('Kommo-o',   'Dragon',   '🐲'),
        ('Toxapex',   'Poison',   '🌊'),
        ('Golisopod', 'Bug',      '🦀'),
        # Gen 8
        ('Dragapult', 'Dragon',   '👻'),
        ('Grimmsnarl','Dark',     '👺'),
        ('Corviknight','Steel',   '🦅'),
        # Gen 9
        ('Baxcalibur','Dragon',   '🐉'),
        ('Gholdengo', 'Steel',    '💰'),
        ('Kingambit', 'Dark',     '👹'),
    ],
    'legendary': [
        # Gen 1 — Birds & Psychic
        ('Articuno',  'Ice',          '💎'),
        ('Zapdos',    'Electric',     '⚡'),
        ('Moltres',   'Fire',         '🔥'),
        ('Mewtwo',    'Psychic',      '🧬'),
        # Gen 2 — Beasts & Tower
        ('Raikou',    'Electric',     '⚡'),
        ('Entei',     'Fire',         '🔥'),
        ('Suicune',   'Water',        '💧'),
        ('Lugia',     'Psychic',      '🌊'),
        ('Ho-Oh',     'Fire',         '🌈'),
        # Gen 3 — Weather & Eon
        ('Kyogre',    'Water',        '🌊'),
        ('Groudon',   'Ground',       '🌋'),
        ('Rayquaza',  'Dragon',       '🐉'),
        ('Latios',    'Dragon',       '🔵'),
        ('Latias',    'Dragon',       '🔴'),
        # Gen 4 — Dialga, Palkia, Giratina
        ('Dialga',    'Steel',        '⏰'),
        ('Palkia',    'Water',        '🌀'),
        ('Giratina',  'Ghost',        '👀'),
        ('Heatran',   'Fire',         '🌋'),
        ('Cresselia',  'Psychic',     '🌙'),
        # Gen 5 — Tao Trio
        ('Reshiram',  'Dragon',       '🌞'),
        ('Zekrom',    'Dragon',       '⚡'),
        ('Kyurem',    'Dragon',       '💎'),
        ('Cobalion',  'Steel',        '🔪'),
        ('Terrakion', 'Rock',         '🗿'),
        ('Virizion',  'Grass',        '🌿'),
        # Gen 6 — Life & Death
        ('Xerneas',   'Fairy',        '🦌'),
        ('Yveltal',   'Dark',         '🦅'),
        ('Zygarde',   'Dragon',       '🐍'),
        # Gen 7 — Sun, Moon, UBs
        ('Solgaleo',  'Psychic',      '🌞'),
        ('Lunala',    'Psychic',      '🌙'),
        ('Necrozma',  'Psychic',      '💎'),
        ('Tapu Koko', 'Electric',     '⚡'),
        ('Tapu Lele', 'Psychic',      '🔮'),
        ('Tapu Bulu', 'Grass',        '🌿'),
        ('Tapu Fini', 'Water',        '💧'),
        # Gen 8 — Galar
        ('Zacian',    'Fairy',        '🔪'),
        ('Zamazenta', 'Fighting',     '🏰'),
        ('Eternatus', 'Poison',       '💀'),
        ('Calyrex',   'Psychic',      '👑'),
        ('Glastrier', 'Ice',          '🐎'),
        ('Spectrier', 'Ghost',        '🐎'),
        # Gen 9 — Paldea
        ('Koraidon',  'Dragon',       '🦖'),
        ('Miraidon',  'Dragon',       '🤖'),
        ('Ting-Lu',   'Dark',         '📿'),
        ('Chien-Pao', 'Dark',         '🔪'),
        ('Wo-Chien',  'Dark',         '📜'),
        ('Chi-Yu',    'Dark',         '🐟'),
    ],
    'mythical': [
        # Gen 1
        ('Mew',       'Psychic',      '✨'),
        # Gen 2
        ('Celebi',    'Psychic',      '🍃'),
        # Gen 3
        ('Jirachi',   'Steel',        '⭐'),
        ('Deoxys',    'Psychic',      '🛸'),
        # Gen 4
        ('Darkrai',   'Dark',         '🌑'),
        ('Shaymin',   'Grass',        '🌸'),
        ('Arceus',    'Normal',       '👑'),
        # Gen 5
        ('Victini',   'Psychic',      '🏆'),
        ('Keldeo',    'Water',        '🔪'),
        ('Meloetta',  'Normal',       '🎵'),
        ('Genesect',  'Bug',          '🤖'),
        # Gen 6
        ('Diancie',   'Rock',         '💎'),
        ('Hoopa',     'Psychic',      '🎩'),
        ('Volcanion', 'Fire',         '💥'),
        # Gen 7
        ('Magearna',  'Steel',        '🤖'),
        ('Marshadow', 'Fighting',     '👤'),
        ('Zeraora',   'Electric',     '⚡'),
        ('Meltan',    'Steel',        '🔩'),
        ('Melmetal',  'Steel',        '🔧'),
        # Gen 8
        ('Zarude',    'Dark',         '🌿'),
        # Gen 9
        ('Pecharunt', 'Poison',       '🍒'),
        ('Terapagos', 'Normal',       '💎'),
    ],
}

# ── XP detection ──────────────────────────────────────────────────────────────
# Each entry: (xp_value, [english_keywords], [bahasa_indonesia_keywords])
# First matching rule wins (highest XP first).

XP_RULES = [
    # 100 XP — Ship / deploy
    (100,
     ['ship', 'deploy', 'production', 'prod', 'release', 'publish', 'launch', 'go live', 'rollout'],
     ['rilis', 'deploy', 'produksi', 'luncurkan', 'launching', 'publish', 'kirim ke prod']),

    # 75 XP — New tech / architecture
    (75,
     ['framework', 'library', 'new tool', 'new tech', 'architecture', 'design system',
      'infrastructure', 'infra', 'terraform', 'kubernetes', 'k8s', 'docker', 'pipeline',
      'ci/cd', 'ci cd', 'microservice'],
     ['arsitektur', 'infrastruktur', 'framework baru', 'teknologi baru', 'sistem baru',
      'microservice', 'docker', 'pipeline']),

    # 50 XP — Feature / implementation
    (50,
     ['feature', 'complete', 'implement', 'finish', 'integration', 'api', 'endpoint',
      'migration', 'schema', 'authentication', 'authorization', 'oauth',
      'dashboard', 'workflow', 'automation'],
     ['fitur', 'selesai', 'implementasi', 'integrasi', 'migrasi', 'skema',
      'autentikasi', 'otorisasi', 'dashboard', 'layanan', 'otomasi', 'alur kerja']),

    # 40 XP — Hard problem / performance / security
    (40,
     ['hard', 'complex', 'difficult', 'tricky', 'solve', 'performance', 'optimize',
      'security', 'vulnerability', 'cve', 'encrypt', 'scaling', 'bottleneck', 'memory leak',
      'race condition', 'concurrency', 'algorithm'],
     ['susah', 'kompleks', 'sulit', 'rumit', 'selesaikan', 'performa', 'optimasi',
      'keamanan', 'enkripsi', 'skalabilitas', 'algoritma', 'kebocoran memori']),

    # 35 XP — AI / ML
    (35,
     ['model', 'prompt', 'dataset', 'train', 'fine-tune', 'finetune', 'inference',
      'embedding', 'vector', 'llm', 'ai ', 'ml ', 'machine learning', 'deep learning',
      'neural', 'rag', 'agent'],
     ['model', 'prompt', 'dataset', 'latih', 'pelatihan', 'inferensi', 'kecerdasan buatan',
      'pembelajaran mesin', 'vektor', 'agen']),

    # 30 XP — Tests / QA / monitoring
    (30,
     ['test', 'spec', 'coverage', 'unit test', 'e2e', 'integration test', 'qa',
      'monitor', 'alert', 'logging', 'observability', 'metric', 'oncall'],
     ['tes', 'pengujian', 'cakupan', 'monitor', 'pemantauan', 'logging', 'metrik', 'observabilitas']),

    # 25 XP — Learning / concept / research
    (25,
     ['concept', 'learn', 'understand', 'explain', 'research', 'study', 'read',
      'document', 'readme', 'docs', 'wiki', 'writeup', 'rfc', 'adr'],
     ['konsep', 'belajar', 'pahami', 'jelaskan', 'riset', 'pelajari', 'baca',
      'dokumentasi', 'dokumen', 'tulis']),

    # 20 XP — Build / refactor / review
    (20,
     ['component', 'ui', 'build', 'create', 'widget', 'refactor', 'review', 'clean',
      'page', 'form', 'layout', 'style', 'css', 'design', 'prototype', 'wireframe',
      'query', 'index', 'database', 'db '],
     ['komponen', 'bangun', 'buat', 'refaktor', 'tinjau', 'review', 'bersihkan',
      'halaman', 'formulir', 'tampilan', 'gaya', 'desain', 'prototipe', 'kueri', 'basis data']),

    # 10 XP — Bug fix / patch
    (10,
     ['bug', 'fix', 'error', 'issue', 'patch', 'hotfix', 'typo', 'crash', 'broken'],
     ['bug', 'perbaiki', 'kesalahan', 'masalah', 'error', 'hotfix', 'rusak', 'crash']),
]

def detect_xp(description):
    m = re.search(r'\b(\d+)\s*xp\b', description.lower())
    if m: return int(m.group(1))
    desc = description.lower()
    for rule in XP_RULES:
        xp, en_keywords, id_keywords = rule
        if any(k in desc for k in en_keywords) or any(k in desc for k in id_keywords):
            return xp
    return 10

# ── Milestone & title data ────────────────────────────────────────────────────

MILESTONES = {
    'first_catch':     ('🎣', 'First Catch',       'Caught your very first wild Pokemon!'),
    'legendary_catch': ('🧬', 'Legend Seeker',     'Caught a legendary Pokemon!'),
    'mythical_catch':  ('✨', 'Myth Maker',         'Caught a mythical Pokemon — incredibly rare!'),
    'shiny_catch':     ('💫', 'Shiny Hunter',       'Caught a shiny Pokemon — 1 in 200 odds!'),
    'first_evolution': ('🆙',  'First Evolution',   'Your buddy evolved for the first time!'),
    'final_evolution': ('🐉', 'Final Form',         'Reached the final evolution stage!'),
    'level_10':        ('🥇', 'Lv.10 Reached',     'Reached Level 10 — the journey is real!'),
    'level_20':        ('💪', 'Lv.20 Reached',     'Reached Level 20 — seasoned developer!'),
    'level_30':        ('🏆', 'Lv.30 Reached',     'Reached Level 30 — elite coder!'),
    'level_50':        ('👑', 'Lv.50 Reached',     'Reached Level 50 — legendary developer!'),
    'dex_10':          ('📖', 'Budding Collector',  'Caught 10 unique Pokemon!'),
    'dex_20':          ('📚', 'Avid Collector',     'Caught 20 unique Pokemon!'),
    'dex_30':          ('📇', 'Pokedex Scholar',   'Caught 30 unique Pokemon!'),
    'streak_7':        ('🔥', '7-Day Streak',       'Coded 7 days in a row!'),
    'streak_30':       ('⚡', '30-Day Streak',      'Coded 30 days in a row — unstoppable!'),
}

# First matching rule wins (highest prestige first)
TITLE_RULES = [
    ('caught_mythical',  'Mythical Master'),
    ('caught_legendary', 'Legend Hunter'),
    ('caught_shiny',     'Shiny Chaser'),
    ('dex_30',           'Pokedex Scholar'),
    ('ships_3',          'Elite Deployer'),
    ('ships_1',          'Shipmaster'),
    ('streak_30',        'Relentless'),
    ('streak_7',         'Dedicated'),
    ('bug_20',           'Bug Slayer'),
    ('features_10',      'Feature Forge'),
    ('dex_10',           'Collector'),
]

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
        'streak': 0, 'last_xp_date': '', 'longest_streak': 0,
        'total_xp_ever': 0, 'bug_fixes': 0, 'features': 0, 'ships': 0,
        'caught_legendary': False, 'caught_mythical': False, 'caught_shiny': False,
        'milestones': set(),
    }
    if not STATS_FILE.exists():
        return defaults
    text = STATS_FILE.read_text(encoding='utf-8')
    def gi(key):
        m = re.search(rf'\*\*{key}\*\*:\s*(\d+)', text)
        return int(m.group(1)) if m else defaults.get(key, 0)
    def gb(key):
        m = re.search(rf'\*\*{key}\*\*:\s*(true|false)', text)
        return (m.group(1) == 'true') if m else defaults.get(key, False)
    def gs(key):
        m = re.search(rf'\*\*{key}\*\*:\s*(\S+)', text)
        return m.group(1) if m else defaults.get(key, '')
    ms_section = re.search(r'## Milestones Awarded\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    milestones = set(re.findall(r'^- (\S+)', ms_section.group(1), re.MULTILINE)) if ms_section else set()
    return {
        'streak':          gi('streak'),
        'last_xp_date':    gs('last_xp_date'),
        'longest_streak':  gi('longest_streak'),
        'total_xp_ever':   gi('total_xp_ever'),
        'bug_fixes':       gi('bug_fixes'),
        'features':        gi('features'),
        'ships':           gi('ships'),
        'caught_legendary': gb('caught_legendary'),
        'caught_mythical':  gb('caught_mythical'),
        'caught_shiny':     gb('caught_shiny'),
        'milestones':       milestones,
    }

def write_stats(s):
    b = lambda v: 'true' if v else 'false'
    ms_lines = '\n'.join(f'- {m}' for m in sorted(s['milestones'])) or '*(none yet)*'
    STATS_FILE.write_text(
        f'# Trainer Stats\n\n'
        f'**streak**: {s["streak"]}\n'
        f'**last_xp_date**: {s["last_xp_date"]}\n'
        f'**longest_streak**: {s["longest_streak"]}\n'
        f'**total_xp_ever**: {s["total_xp_ever"]}\n'
        f'**bug_fixes**: {s["bug_fixes"]}\n'
        f'**features**: {s["features"]}\n'
        f'**ships**: {s["ships"]}\n'
        f'**caught_legendary**: {b(s["caught_legendary"])}\n'
        f'**caught_mythical**: {b(s["caught_mythical"])}\n'
        f'**caught_shiny**: {b(s["caught_shiny"])}\n\n'
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

def roll_catch(add_xp, owned_names, role_type=None, buddy_rarity=None):
    """Returns (tier, name, type, emoji, is_shiny) or None.
    role_type: if set, matching-type Pokemon are 3× more likely to be chosen.
    buddy_rarity: if set, boosts catch probabilities for higher-rarity tiers.
    """
    rates = CATCH_RATES.get(add_xp, [('common', 0.05)])
    boosts = BUDDY_RARITY_BOOST.get(buddy_rarity, {}) if buddy_rarity else {}
    caught_tier = None
    for tier, prob in sorted(rates, key=lambda x: list(POKEMON_POOL.keys()).index(x[0])):
        boosted_prob = min(1.0, prob * boosts.get(tier, 1.0))
        if random.random() < boosted_prob:
            caught_tier = tier
    if not caught_tier:
        return None
    pool = POKEMON_POOL[caught_tier]
    available = [p for p in pool if p[0] not in owned_names]
    if not available:
        available = pool
    if role_type:
        weights = [3 if p[1] == role_type else 1 for p in available]
        chosen = random.choices(available, weights=weights, k=1)[0]
    else:
        chosen = random.choice(available)
    is_shiny = random.random() < SHINY_RATE
    return (caught_tier, chosen[0], chosen[1], chosen[2], is_shiny)

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
    stats_str   = f'🔥 ×{streak}  ·  🏅 {badge_count}  ·  👥 {party_count}'

    # ── Section 4: Buddy chatter (right side) ────────────────────────────────
    chatter_str = f'💭 {get_chatter(pct)}'

    sep = '  ┃  ' if plugin_mode else '  │  '
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

    # Build party rows (2 per line)
    party_rows = []
    row_buf = []
    for p in col['pokemon']:
        mark = '✨' if p.get('shiny') else ''
        entry = f'{mark}{p["emoji"]}{p["name"]}{"*" if p["name"] == col["active"] else ""} Lv.{p["level"]}'
        row_buf.append(entry)
        if len(row_buf) == 2:
            party_rows.append(f'{row_buf[0]:<28}{row_buf[1]}')
            row_buf = []
    if row_buf:
        party_rows.append(row_buf[0])

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
        SEP,
    ]

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

    if col['pokemon']:
        out.append(row(f'PARTY  ({n_caught} Pokemon)'))
        for pr in party_rows:
            out.append(row(pr))
        out.append(SEP)

    out += [
        row(f'Total XP earned: {tr_stats.get("total_xp_ever", 0)}'),
        row(f'Bugs fixed: {tr_stats.get("bug_fixes",0)}   '
            f'Features: {tr_stats.get("features",0)}   '
            f'Ships: {tr_stats.get("ships",0)}'),
        f' ╚{"═" * (W + 3)}╝',
    ]

    return '\n'.join(out)

# ── SVG trainer card (shareable — GitHub README, Discord, Twitter) ────────────

def _svg_escape(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;')
                  .replace('>', '&gt;').replace('"', '&quot;'))

def render_svg_card():
    """Render a shareable SVG trainer card — pure Python, no deps.
    Width fixed at 620; height grows with content."""
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

    badges_section = re.search(r'## Badges Earned\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    badges_raw = re.findall(r'^- (.+)$', badges_section.group(1), re.MULTILINE) if badges_section else []
    badge_entries = []
    for b in badges_raw:
        if 'No badges yet' in b: continue
        em = re.match(r'^\s*([^\s\w])', b)
        nm = re.search(r'\*\*(.+?)\*\*', b)
        if nm:
            badge_entries.append((em.group(1) if em else '🏅', nm.group(1)))

    rarity_order = ['mythical', 'legendary', 'rare', 'uncommon', 'common']
    rarest = None
    for tier in rarity_order:
        for p in col['pokemon']:
            if tier in p.get('rarity', ''):
                rarest = p; break
        if rarest: break

    n_caught = len(col['pokemon'])
    n_total  = sum(len(v) for v in POKEMON_POOL.values())
    streak   = tr_stats.get('streak', 0)
    longest  = tr_stats.get('longest_streak', 0)
    total_xp = tr_stats.get('total_xp_ever', 0)

    # Layout constants
    W = 620
    PAD = 24
    # Dark theme colors
    BG1, BG2 = '#1a1b26', '#24283b'
    FG, MUTED = '#c0caf5', '#7982a9'
    ACCENT, GOLD = '#7aa2f7', '#e0af68'
    RED, GREEN = '#f7768e', '#9ece6a'

    pct = xp_disp / xp_max_disp if xp_max_disp else 0
    bar_w = W - PAD * 2
    fill_w = int(bar_w * max(0, min(1, pct)))

    # Build sections into list, track current y
    parts = []
    y = 0

    # ---- Header ----
    header_h = 96
    parts.append(f'<rect x="0" y="{y}" width="{W}" height="{header_h}" fill="url(#hdr)"/>')
    parts.append(f'<text x="{PAD}" y="{y+38}" font-size="22" font-weight="700" fill="{FG}">🏆 TRAINER CARD</text>')
    parts.append(f'<text x="{PAD}" y="{y+66}" font-size="18" fill="{GOLD}">{_svg_escape(trainer)}</text>')
    parts.append(f'<text x="{PAD}" y="{y+86}" font-size="13" fill="{MUTED}">· {_svg_escape(title)} ·</text>')
    y += header_h

    # ---- Active buddy ----
    buddy_h = 118
    parts.append(f'<rect x="0" y="{y}" width="{W}" height="{buddy_h}" fill="{BG2}"/>')
    parts.append(f'<text x="{PAD}" y="{y+24}" font-size="11" letter-spacing="2" fill="{MUTED}">ACTIVE BUDDY</text>')
    parts.append(f'<text x="{PAD}" y="{y+58}" font-size="26" font-weight="700" fill="{FG}">'
                 f'{_svg_escape(stage)} <tspan fill="{ACCENT}">Lv.{_svg_escape(level)}</tspan></text>')
    parts.append(f'<text x="{PAD}" y="{y+78}" font-size="12" fill="{MUTED}">{_svg_escape(specialty)}</text>')
    # XP bar
    by = y + 92
    parts.append(f'<rect x="{PAD}" y="{by}" width="{bar_w}" height="10" rx="5" fill="#2f3350"/>')
    parts.append(f'<rect x="{PAD}" y="{by}" width="{fill_w}" height="10" rx="5" fill="{GREEN}"/>')
    parts.append(f'<text x="{W-PAD}" y="{by-4}" text-anchor="end" font-size="11" fill="{MUTED}">'
                 f'{xp_disp}/{xp_max_disp} XP</text>')
    y += buddy_h

    # ---- Achievements row ----
    ach_h = 72
    parts.append(f'<rect x="0" y="{y}" width="{W}" height="{ach_h}" fill="{BG1}"/>')
    cells = [
        ('🏅', str(len(badge_entries)), 'Badges'),
        ('📖', f'{n_caught}/{n_total}', 'Dex'),
        ('🔥', f'{streak}d', f'Best {longest}d'),
        ('⚡', str(total_xp), 'Total XP'),
    ]
    cw = W / len(cells)
    for i, (em, val, lbl) in enumerate(cells):
        cx = int(i * cw + cw / 2)
        parts.append(f'<text x="{cx}" y="{y+26}" text-anchor="middle" font-size="16">{em}</text>')
        parts.append(f'<text x="{cx}" y="{y+48}" text-anchor="middle" font-size="16" font-weight="700" fill="{FG}">{_svg_escape(val)}</text>')
        parts.append(f'<text x="{cx}" y="{y+63}" text-anchor="middle" font-size="10" fill="{MUTED}">{_svg_escape(lbl)}</text>')
    y += ach_h

    # ---- Badges ----
    if badge_entries:
        row_h = 28
        per_row = 3
        rows = (len(badge_entries) + per_row - 1) // per_row
        sec_h = 36 + rows * row_h + 10
        parts.append(f'<rect x="0" y="{y}" width="{W}" height="{sec_h}" fill="{BG2}"/>')
        parts.append(f'<text x="{PAD}" y="{y+24}" font-size="11" letter-spacing="2" fill="{MUTED}">BADGES</text>')
        bw = (W - PAD * 2) / per_row
        for i, (em, nm) in enumerate(badge_entries):
            r, c = divmod(i, per_row)
            bx = PAD + int(c * bw)
            byy = y + 36 + r * row_h
            parts.append(f'<text x="{bx}" y="{byy+14}" font-size="13" fill="{FG}">{em} {_svg_escape(nm)}</text>')
        y += sec_h

    # ---- Party ----
    if col['pokemon']:
        per_row = 3
        row_h = 26
        rows = (len(col['pokemon']) + per_row - 1) // per_row
        sec_h = 36 + rows * row_h + 10
        parts.append(f'<rect x="0" y="{y}" width="{W}" height="{sec_h}" fill="{BG1}"/>')
        parts.append(f'<text x="{PAD}" y="{y+24}" font-size="11" letter-spacing="2" fill="{MUTED}">PARTY  ({n_caught})</text>')
        pw = (W - PAD * 2) / per_row
        for i, p in enumerate(col['pokemon']):
            r, c = divmod(i, per_row)
            bx = PAD + int(c * pw)
            byy = y + 36 + r * row_h
            shiny = '✨' if p.get('shiny') else ''
            active = '★' if p['name'] == col['active'] else ' '
            entry = f"{active}{shiny}{p['emoji']} {p['name']} Lv.{p['level']}"
            color = GOLD if p['name'] == col['active'] else FG
            parts.append(f'<text x="{bx}" y="{byy+14}" font-size="12" fill="{color}">{_svg_escape(entry)}</text>')
        y += sec_h

    # ---- Footer ----
    ft_h = 52
    rarest_str = (f"{p.get('emoji','')} {p['name']} ({p['rarity']})"
                  if (p := rarest) else 'None yet')
    parts.append(f'<rect x="0" y="{y}" width="{W}" height="{ft_h}" fill="{BG2}"/>')
    parts.append(f'<text x="{PAD}" y="{y+22}" font-size="11" fill="{MUTED}">Rarest catch</text>')
    parts.append(f'<text x="{PAD}" y="{y+42}" font-size="13" fill="{ACCENT}">{_svg_escape(rarest_str)}</text>')
    parts.append(f'<text x="{W-PAD}" y="{y+42}" text-anchor="end" font-size="10" fill="{MUTED}">pokemon-buddy-claude</text>')
    y += ft_h

    total_h = y
    header = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{total_h}" '
        f'viewBox="0 0 {W} {total_h}" font-family="\'Segoe UI Emoji\',\'Apple Color Emoji\','
        f'\'Noto Color Emoji\',system-ui,sans-serif">'
        f'<defs><linearGradient id="hdr" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="#1f2335"/><stop offset="1" stop-color="#2d3250"/>'
        f'</linearGradient></defs>'
    )
    return header + ''.join(parts) + '</svg>'

def render_readme_snippet(svg_path='trainer-card.svg'):
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
        f'  <img src="./{svg_path}" alt="{trainer} — {stage} Lv.{level}" width="620"/>\n'
        f'</p>\n'
        f'<p align="center">\n'
        f'  <sub>Powered by '
        f'<a href="https://github.com/anthropics/claude-code">Claude Code</a> · '
        f'<a href="https://github.com/andriar/pokemon-buddy-claude">pokemon-buddy-claude</a></sub>\n'
        f'</p>\n'
    )

def render_announcement(mode, add_xp, old_level, new_level, new_xp, new_max,
                        new_stage, stat_boost, new_moves_data, evolved,
                        catch_result=None, b_emoji='', b_name='', b_desc='',
                        streak_bonus=0, streak_count=0, new_badges=None,
                        buddy_rarity=None, buddy_name=''):
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
    if streak_bonus and streak_count:
        parts.append(f'🔥 Day {streak_count} streak (+{streak_bonus} bonus)!')
    if new_level > old_level: parts.append(f'★ LEVEL UP! Lv.{old_level} → Lv.{new_level}')
    if evolved:               parts.append(f'✨ EVOLVED into {evolved}!')
    lines.append(' ' + '   '.join(parts))
    lines += [
        f' 🔥 {new_stage.upper():<12} Lv.{new_level:<4}',
        ' ' + '─' * 52,
        f' XP  [{xp_b}]  {xp_disp} / {xp_max_disp}',
    ]
    if stat_boost > 0:
        lines.append(f' All stats +{stat_boost}!')
    for _, name, mtype, desc in new_moves_data:
        lines.append(f' New move: {name} [{mtype}] — {desc}')

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

    if catch_result:
        tier, cname, ctype, cemoji, is_shiny = catch_result
        display_tier = tier.upper()
        if is_shiny:
            lines += [
                '',
                f' ╔{"═"*54}╗',
                f' ║  ✨✨✨  SHINY {cemoji} {cname} appeared!  ✨✨✨{" " * max(0, 20 - len(cname))}║',
                f' ║  AN INCREDIBLY RARE SHINY POKEMON!  1 in 200!{" " * 7}║',
                f' ║  You threw a Pokéball...  ★ GOTCHA!  {cname} caught!{" " * max(0, 14 - len(cname))}║',
                f' ║  [Added to party — use /pokemon-switch to buddy up]{" " * 4}║',
                f' ╚{"═"*54}╝',
            ]
        else:
            boosted_tiers = set(BUDDY_RARITY_BOOST.get(buddy_rarity, {}).keys())
            show_aura = (buddy_rarity in BUDDY_RARITY_BOOST
                         and tier in boosted_tiers)
            if show_aura:
                aura_flavor = {
                    'mythical':  ('🌌', 'THE COSMOS ALIGNED',   f'{buddy_name.upper()} CALLED ACROSS DIMENSIONS!'),
                    'legendary': ('⚡', 'LEGENDARY AURA SURGE', f'{buddy_name.upper()}\'S POWER SHOOK THE WILD!'),
                    'rare':      ('🔮', 'AURA RESONANCE',       f'{buddy_name.upper()}\'S PRESENCE DREW IT NEAR!'),
                    'uncommon':  ('✨', 'BUDDY AURA ACTIVE',    f'{buddy_name.upper()}\'S AURA ATTRACTED IT!'),
                }.get(tier, ('✨', 'AURA ACTIVE', f'{buddy_name.upper()}\'S AURA RESONATED!'))
                aura_icon, aura_title, aura_msg = aura_flavor
                divider = ' ◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆◆'
                lines += [
                    '',
                    divider,
                    f'   {aura_icon}  {aura_title}  {aura_icon}',
                    f'   🎉 Wild {cemoji} {cname} appeared!  ({display_tier})',
                    f'   {aura_msg}',
                    f'   You hurled a Pokéball...  ★ GOTCHA!  {cname} caught!',
                    divider,
                ]
            else:
                lines += [
                    '',
                    f' ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
                    f' 🎉 Wild {cemoji} {cname} appeared!  ({display_tier})',
                    f'    You threw a Pokéball...  ★ Gotcha!  {cname} was caught!',
                    f'    [{cname} added to your party — use /pokemon-switch to buddy up]',
                    f' ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
                ]

    return '\n'.join(lines)

# ── Switch buddy ─────────────────────────────────────────────────────────────

BUDDY_TEMPLATE = """\
# Buddy Pokemon: {name} {emoji}

**Name**: {name}
**Type**: {ptype}
**Trainer**: {trainer}
**Specialty**: {specialty}
**Level**: {level}
**XP**: {xp} / {xp_max}
**Stage**: {name} {emoji}

## Evolution Path

**Current Stage**: {name} {emoji}

```
{evo_line}
```

## Stats

| Stat | Value |
|---|---|
| HP | {hp} |
| Attack | {atk} |
| Defense | {def_} |
| Special Atk | {spa} |
| Special Def | {spd} |
| Speed | {spe} |

## Moves

| Move | Type | Unlocked At | Description |
|---|---|---|---|
{moves_rows}

## Badges Earned

*No badges yet — the journey begins now!*

## Journey Log

| Date | Event | XP Gained |
|---|---|---|
| {today} | Switched to active buddy | — |

## Trainer Info

- **Trainer**: {trainer}
- **Journey Started**: {today}
"""

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
        print("Usage: buddy-update.py status|statusline|card|svg|readme|backup|import|xp|badge|switch|catch")
        sys.exit(1)

    mode = args[0]

    # Modes that read/render the buddy file need it to exist. statusline has
    # its own empty-state fallback; import/backup/catch handle absence themselves.
    if mode in ('status', 'card', 'svg', 'readme', 'switch', 'xp', 'badge') and not BUDDY_FILE.exists():
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

    if mode == 'svg':
        out_path = Path(args[1]) if len(args) > 1 else Path.cwd() / 'trainer-card.svg'
        out_path.write_text(render_svg_card(), encoding='utf-8')
        print(f' ✅ Trainer card saved: {out_path}')
        print(f'    Share it on GitHub, Discord, Twitter — or paste into your README.')
        sys.exit(0)

    if mode == 'readme':
        svg_rel = args[1] if len(args) > 1 else 'trainer-card.svg'
        print(render_readme_snippet(svg_rel))
        sys.exit(0)

    if mode == 'backup':
        import json
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
        import json, shutil
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

    # Load stats early — needed for streak and milestone tracking
    tr_stats = read_stats()

    if mode == 'xp':
        desc     = args[1] if len(args) > 1 else ''
        base_xp  = detect_xp(desc)
        log_desc = desc or 'XP awarded'

        # Streak: bonus XP for first award of the day
        bonus, streak_count, is_new_day = update_streak(tr_stats)
        if is_new_day:
            streak_bonus = bonus
        add_xp = base_xp + streak_bonus

        # Track achievement counters
        dl = desc.lower()
        if any(k in dl for k in ['ship','deploy','production','prod','release']):
            tr_stats['ships'] = tr_stats.get('ships', 0) + 1
        if any(k in dl for k in ['feature','complete','implement','finish']):
            tr_stats['features'] = tr_stats.get('features', 0) + 1
        if any(k in dl for k in ['bug','fix','error','issue','patch']):
            tr_stats['bug_fixes'] = tr_stats.get('bug_fixes', 0) + 1

        tr_stats['total_xp_ever'] = tr_stats.get('total_xp_ever', 0) + add_xp

    elif mode == 'badge':
        add_xp  = 50
        b_emoji = args[1] if len(args) > 1 else '🏅'
        b_name  = args[2] if len(args) > 2 else 'New Badge'
        b_desc  = args[3] if len(args) > 3 else 'Achievement unlocked'
        log_desc  = f'Earned {b_emoji} {b_name}'
        badge_line = f'- {b_emoji} **{b_name}** — *{b_desc}* `{TODAY}`'
        tr_stats['total_xp_ever'] = tr_stats.get('total_xp_ever', 0) + add_xp

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

    # Roll for wild encounter (use base XP for catch rates, not streak-boosted)
    base_xp_for_catch = detect_xp(args[1] if len(args) > 1 and mode == 'xp' else '') if mode == 'xp' else add_xp
    col = read_collection()
    owned = {p['name'] for p in col['pokemon']}
    buddy_rarity = get_buddy_rarity()
    catch_result = roll_catch(base_xp_for_catch, owned, get_role_type(), buddy_rarity)
    if catch_result:
        tier, cname, ctype, cemoji, is_shiny = catch_result
        add_to_collection(cname, ctype, cemoji, tier, is_shiny)
        # Update stats flags
        base_tier = tier.replace('-shiny', '')
        if base_tier == 'legendary': tr_stats['caught_legendary'] = True
        if base_tier == 'mythical':  tr_stats['caught_mythical']  = True
        if is_shiny:                 tr_stats['caught_shiny']      = True
        # Re-read collection after adding new catch for milestone checks
        col = read_collection()

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
    ))

if __name__ == '__main__':
    main()
