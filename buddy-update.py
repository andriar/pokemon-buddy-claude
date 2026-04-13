#!/usr/bin/env python3
"""
buddy-update.py — Pokemon Buddy engine for Claude Code.

Commands:
  status                     Full status card (read-only)
  statusline                 Compact one-liner for status bar
  xp "<description>"         Award XP (auto-detects amount), may trigger catch
  badge "<emoji>" "<n>" "<d>"  Award badge + 50 XP
  switch "<name>"            Switch active buddy
  catch "<name>"             Manually add a Pokemon to collection
"""

import sys, re, random
from datetime import date
from pathlib import Path

BUDDY_FILE      = Path.home() / '.claude' / 'buddy-pokemon.md'
COLLECTION_FILE = Path.home() / '.claude' / 'pokemon-collection.md'
TODAY           = date.today().strftime('%Y-%m-%d')
LOG_CAP         = 15
ARCHIVE_FILE    = Path.home() / '.claude' / 'buddy-log-archive.md'

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
        ('Geodude',   'Rock',     '🪨'),
        ('Magikarp',  'Water',    '🐟'),
        ('Weedle',    'Bug',      '🐛'),
        ('Zubat',     'Poison',   '🦇'),
        ('Rattata',   'Normal',   '🐭'),
        # Gen 2
        ('Sentret',   'Normal',   '🦔'),
        ('Hoothoot',  'Normal',   '🦉'),
        ('Spinarak',  'Bug',      '🕷️'),
        # Gen 3
        ('Wurmple',   'Bug',      '🐛'),
        ('Zigzagoon', 'Normal',   '🦡'),
        # Gen 4
        ('Bidoof',    'Normal',   '🦫'),
        ('Starly',    'Normal',   '🐦'),
        # Gen 5
        ('Patrat',    'Normal',   '🐭'),
        ('Pidove',    'Normal',   '🕊️'),
        # Gen 6
        ('Fletchling','Normal',   '🐦'),
        ('Scatterbug','Bug',      '🐛'),
        # Gen 7
        ('Pikipek',   'Normal',   '🦜'),
        ('Yungoos',   'Normal',   '🐾'),
        # Gen 8
        ('Wooloo',    'Normal',   '🐑'),
        ('Skwovet',   'Normal',   '🐿️'),
        # Gen 9
        ('Lechonk',   'Normal',   '🐷'),
        ('Tarountula','Bug',      '🕷️'),
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
        ('Beldum',    'Steel',    '⚙️'),
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
        ('Lapras',    'Water',    '🧊'),
        ('Dratini',   'Dragon',   '🐲'),
        ('Porygon',   'Normal',   '💻'),
        ('Scyther',   'Bug',      '⚔️'),
        ('Jolteon',   'Electric', '⚡'),
        # Gen 2
        ('Tyranitar', 'Rock',     '🦖'),
        ('Dragonite', 'Dragon',   '🐉'),
        ('Blissey',   'Normal',   '💗'),
        # Gen 3
        ('Flygon',    'Dragon',   '🐲'),
        ('Metagross',  'Steel',   '⚙️'),
        ('Salamence', 'Dragon',   '🐉'),
        # Gen 4
        ('Garchomp',  'Dragon',   '🐉'),
        ('Lucario',   'Fighting', '💪'),
        ('Togekiss',  'Fairy',    '🕊️'),
        # Gen 5
        ('Hydreigon', 'Dragon',   '🐲'),
        ('Volcarona', 'Fire',     '🦋'),
        ('Haxorus',   'Dragon',   '⚔️'),
        # Gen 6
        ('Goodra',    'Dragon',   '🐲'),
        ('Aegislash', 'Steel',    '⚔️'),
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
        ('Kingambit', 'Dark',     '♟️'),
    ],
    'legendary': [
        # Gen 1 — Birds & Psychic
        ('Articuno',  'Ice',          '❄️'),
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
        ('Dialga',    'Steel',        '⏱️'),
        ('Palkia',    'Water',        '🌀'),
        ('Giratina',  'Ghost',        '👁️'),
        ('Heatran',   'Fire',         '🌋'),
        ('Cresselia',  'Psychic',     '🌙'),
        # Gen 5 — Tao Trio
        ('Reshiram',  'Dragon',       '☀️'),
        ('Zekrom',    'Dragon',       '⚡'),
        ('Kyurem',    'Dragon',       '❄️'),
        ('Cobalion',  'Steel',        '⚔️'),
        ('Terrakion', 'Rock',         '🪨'),
        ('Virizion',  'Grass',        '🌿'),
        # Gen 6 — Life & Death
        ('Xerneas',   'Fairy',        '🦌'),
        ('Yveltal',   'Dark',         '🦅'),
        ('Zygarde',   'Dragon',       '🐍'),
        # Gen 7 — Sun, Moon, UBs
        ('Solgaleo',  'Psychic',      '☀️'),
        ('Lunala',    'Psychic',      '🌙'),
        ('Necrozma',  'Psychic',      '💎'),
        ('Tapu Koko', 'Electric',     '⚡'),
        ('Tapu Lele', 'Psychic',      '🔮'),
        ('Tapu Bulu', 'Grass',        '🌿'),
        ('Tapu Fini', 'Water',        '💧'),
        # Gen 8 — Galar
        ('Zacian',    'Fairy',        '⚔️'),
        ('Zamazenta', 'Fighting',     '🛡️'),
        ('Eternatus', 'Poison',       '☠️'),
        ('Calyrex',   'Psychic',      '👑'),
        ('Glastrier', 'Ice',          '🐎'),
        ('Spectrier', 'Ghost',        '🐎'),
        # Gen 9 — Paldea
        ('Koraidon',  'Dragon',       '🦖'),
        ('Miraidon',  'Dragon',       '🤖'),
        ('Ting-Lu',   'Dark',         '🏺'),
        ('Chien-Pao', 'Dark',         '🗡️'),
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
        ('Keldeo',    'Water',        '⚔️'),
        ('Meloetta',  'Normal',       '🎵'),
        ('Genesect',  'Bug',          '🤖'),
        # Gen 6
        ('Diancie',   'Rock',         '💎'),
        ('Hoopa',     'Psychic',      '🪄'),
        ('Volcanion', 'Fire',         '♨️'),
        # Gen 7
        ('Magearna',  'Steel',        '🤖'),
        ('Marshadow', 'Fighting',     '👤'),
        ('Zeraora',   'Electric',     '⚡'),
        ('Meltan',    'Steel',        '🔩'),
        ('Melmetal',  'Steel',        '⚙️'),
        # Gen 8
        ('Zarude',    'Dark',         '🌿'),
        # Gen 9
        ('Pecharunt', 'Poison',       '🍑'),
        ('Terapagos', 'Normal',       '💎'),
    ],
}

# ── XP detection ──────────────────────────────────────────────────────────────

XP_RULES = [
    (100, ['ship', 'deploy', 'production', 'prod', 'release']),
    ( 75, ['framework', 'library', 'new tool', 'new tech']),
    ( 50, ['feature', 'complete', 'implement', 'finish']),
    ( 40, ['hard', 'complex', 'difficult', 'tricky', 'solve']),
    ( 30, ['test', 'spec', 'coverage']),
    ( 25, ['concept', 'learn', 'understand', 'explain']),
    ( 20, ['component', 'ui ', 'build', 'create', 'widget', 'refactor', 'review', 'clean']),
    ( 10, ['bug', 'fix', 'error', 'issue', 'patch']),
]

def detect_xp(description):
    m = re.search(r'\b(\d+)\s*xp\b', description.lower())
    if m: return int(m.group(1))
    desc = description.lower()
    for xp, keywords in XP_RULES:
        if any(k in desc for k in keywords):
            return xp
    return 10

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

# ── Collection I/O ────────────────────────────────────────────────────────────

def parse_int(text):
    m = re.search(r'\d+', str(text))
    return int(m.group()) if m else 0

def read_collection():
    if not COLLECTION_FILE.exists():
        return {'active': None, 'pokemon': []}
    text = COLLECTION_FILE.read_text()
    active_m = re.search(r'\*\*Active\*\*:\s*(\S+)', text)
    active = active_m.group(1).strip() if active_m else None
    pokemon = []
    for line in text.splitlines():
        if not line.startswith('|'): continue
        cols = [c.strip() for c in line.split('|')]
        cols = [c for c in cols if c]
        if len(cols) < 6 or cols[0] == 'Name': continue
        try:
            pokemon.append({
                'name':    cols[0],
                'type':    cols[1],
                'emoji':   cols[2],
                'level':   int(cols[3]),
                'xp':      int(cols[4]),
                'caught':  cols[5],
                'rarity':  cols[6] if len(cols) > 6 else 'caught',
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
    COLLECTION_FILE.write_text(''.join(lines))

def sync_active_to_collection(name, level, xp):
    """Update the active buddy's level/xp in the collection file."""
    col = read_collection()
    for p in col['pokemon']:
        if p['name'] == name:
            p['level'] = level
            p['xp']    = xp
            break
    write_collection(col['active'], col['pokemon'])

# ── Catch system ─────────────────────────────────────────────────────────────

def roll_catch(add_xp, owned_names):
    rates = CATCH_RATES.get(add_xp, [('common', 0.05)])
    caught_tier = None
    for tier, prob in sorted(rates, key=lambda x: POKEMON_POOL.keys().__contains__(x[0])):
        if random.random() < prob:
            caught_tier = tier
    if not caught_tier:
        return None
    pool = POKEMON_POOL[caught_tier]
    available = [p for p in pool if p[0] not in owned_names]
    if not available:
        available = pool
    chosen = random.choice(available)
    return (caught_tier, *chosen)   # (tier, name, type, emoji)

def add_to_collection(name, ptype, emoji, rarity):
    col = read_collection()
    col['pokemon'].append({
        'name': name, 'type': ptype, 'emoji': emoji,
        'level': 1, 'xp': 0, 'caught': TODAY, 'rarity': rarity,
    })
    write_collection(col['active'], col['pokemon'])

# ── Buddy file I/O ────────────────────────────────────────────────────────────

def read_buddy():
    lines = BUDDY_FILE.read_text().splitlines(keepends=True)
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

    if mode == 'badge' and badge_line and '*No badges yet' not in BUDDY_FILE.read_text():
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

    stats = {}
    for stat in ('HP', 'Attack', 'Speed', 'Special Atk', 'Defense', 'Special Def'):
        m = re.search(rf'\| {re.escape(stat)} \| (\d+) \|', text)
        stats[stat] = int(m.group(1)) if m else 0

    moves = re.findall(r'\| ([^|?]+) \| ([^|?]+) \| Lv\.(\d+) \| ([^|]+) \|', text)
    locked = re.findall(r'\| \?\?\? \| \?\?\? \| Lv\.(\d+) \|', text)

    badges_section = re.search(r'## Badges Earned\n(.*?)(?=\n##|\Z)', text, re.DOTALL)
    badges_raw = re.findall(r'^- (.+)$', badges_section.group(1), re.MULTILINE) if badges_section else []
    badges = [b for b in badges_raw if 'No badges yet' not in b]

    xp_b = bar(xp_cur, xp_max, 24)
    sep  = '─' * 52

    out = [
        f' 🔥 {stage.upper():<12} Lv.{level:<4}      Trainer: {trainer}',
        f' {sep}',
        f' XP  [{xp_b}]  {xp_cur} / {xp_max}',
        '',
    ]

    move_list = [(m[0].strip(), m[1].strip(), m[3].strip()) for m in moves]
    right_items = []
    for nm, mt, desc in move_list:
        right_items.append(f'  {nm:<10} [{mt[0].upper()}]  {desc}')
    for lv in locked:
        right_items.append(f'  ? ???        [?]  unlock Lv.{lv}')

    stat_keys   = ['HP', 'Attack', 'Defense', 'Special Atk', 'Special Def', 'Speed']
    stat_labels = ['HP ', 'ATK', 'DEF', 'SPA', 'SPD', 'SPE']
    for i, (key, label) in enumerate(zip(stat_keys, stat_labels)):
        val   = stats.get(key, 0)
        b     = stat_bar(val)
        right = right_items[i] if i < len(right_items) else ''
        if i == 5 and badges:
            badge_names = ', '.join(
                re.search(r'\*\*(.+?)\*\*', b2).group(1)
                for b2 in badges if re.search(r'\*\*(.+?)\*\*', b2)
            )
            right = f'  BADGES: {len(badges)}  ({badge_names})'
        out.append(f' {label}  {b}  {val:<3}    {right}')

    out += [f' {sep}', f' PATH: {stage} ──> (Lv.16) ──> (Lv.36)']

    # Party summary from collection
    col = read_collection()
    if col['pokemon']:
        party_str = '  '.join(
            f"{p['emoji']}{p['name']}{'*' if p['name'] == col['active'] else ''} Lv.{p['level']}"
            for p in col['pokemon']
        )
        out += ['', f' PARTY: {party_str}']

    return '\n'.join(out)

def render_statusline():
    col = read_collection()
    if not col['pokemon']:
        return '🎮 No buddy yet'

    party = '  '.join(
        f"{p['emoji']}{'*' if p['name'] == col['active'] else ''}"
        f"Lv{p['level']} {p['name']}"
        for p in col['pokemon']
    )

    # Active buddy XP bar
    lines = BUDDY_FILE.read_text().splitlines()
    xp_cur = parse_int(next((l for l in lines if l.startswith('**XP**:')), '0'))
    xp_max_m = re.search(r'\*\*XP\*\*:\s*\d+\s*/\s*(\d+)',
                          next((l for l in lines if l.startswith('**XP**:')), ''))
    xp_max = int(xp_max_m.group(1)) if xp_max_m else 100

    xp_b = bar(xp_cur, xp_max, 10)
    pct  = xp_cur * 100 // xp_max if xp_max else 0
    mood = '😴' if pct < 30 else '🔥' if pct < 60 else '⚡' if pct < 90 else '💥'

    badges_section = re.search(r'## Badges Earned\n(.*?)(?=\n##|\Z)',
                                BUDDY_FILE.read_text(), re.DOTALL)
    badges_raw = re.findall(r'^- (.+)$', badges_section.group(1), re.MULTILINE) if badges_section else []
    badge_count = sum(1 for b in badges_raw if 'No badges yet' not in b)

    return f'{party} {mood} [{xp_b}] {xp_cur}/{xp_max} 🏅{badge_count}'

def render_announcement(mode, add_xp, old_level, new_level, new_xp, new_max,
                        new_stage, stat_boost, new_moves_data, evolved,
                        catch_result=None, b_emoji='', b_name='', b_desc=''):
    xp_b  = bar(new_xp, new_max, 24)
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
    if new_level > old_level: parts.append(f'★ LEVEL UP! Lv.{old_level} → Lv.{new_level}')
    if evolved:               parts.append(f'✨ EVOLVED into {evolved}!')
    lines.append(' ' + '   '.join(parts))
    lines += [
        f' 🔥 {new_stage.upper():<12} Lv.{new_level:<4}      Trainer: Andriar',
        ' ' + '─' * 52,
        f' XP  [{xp_b}]  {new_xp} / {new_max}',
    ]
    if stat_boost > 0:
        lines.append(f' All stats +{stat_boost}!')
    for _, name, mtype, desc in new_moves_data:
        lines.append(f' New move: {name} [{mtype}] — {desc}')

    if catch_result:
        tier, cname, ctype, cemoji = catch_result
        lines += [
            '',
            f' ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
            f' 🎉 Wild {cemoji} {cname} appeared!  ({tier.upper()})',
            f'    You threw a Pokéball...  ★ Gotcha!  {cname} was caught!',
            f'    [{cname} added to your party — use /pokemon-switch to set as buddy]',
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

    # Save current buddy XP back to collection
    lines, _, cur_level, cur_xp, _, cur_name = read_buddy()
    sync_active_to_collection(cur_name, cur_level, cur_xp)

    # Build new buddy file
    name    = match['name']
    ptype   = match['type']
    emoji   = match['emoji']
    level   = match['level']
    xp      = match['xp']
    xp_max  = xp_for_level(level_from_xp(xp) + 1)

    starter = STARTER_DATA.get(name)
    trainer = re.search(r'\*\*Trainer\*\*:\s*(.+)', BUDDY_FILE.read_text())
    trainer = trainer.group(1).strip() if trainer else 'Trainer'

    if starter:
        stats     = starter['stats']
        evos      = starter['evolutions']
        evo_parts = [f'{name} Lv.1-{evos[0][1]-1}'] + \
                    [f'{e[0]} Lv.{evos[i][1]}-{evos[i+1][1]-1 if i+1 < len(evos) else "∞"}'
                     for i, e in enumerate(evos)]
        evo_line  = ' → '.join(evo_parts)
        moves     = starter['moves']
        specialty = starter['specialty']
    else:
        stats    = {'HP': 40, 'Attack': 50, 'Defense': 50,
                    'Special Atk': 50, 'Special Def': 50, 'Speed': 50}
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
    BUDDY_FILE.write_text(content)

    col['active'] = name
    write_collection(col['active'], col['pokemon'])

    prev = cur_name
    print(f' 🔄 Switched buddy: {prev} → {emoji} {name}')
    print(f'    {name} is now your active buddy! (Lv.{level}, {xp} XP)')

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: buddy-update.py status|statusline|xp|badge|switch|catch")
        sys.exit(1)

    mode = args[0]

    if mode == 'status':
        print(render_status(BUDDY_FILE.read_text()))
        sys.exit(0)

    if mode == 'statusline':
        print(render_statusline())
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

    if mode == 'xp':
        desc     = args[1] if len(args) > 1 else ''
        add_xp   = detect_xp(desc)
        log_desc = desc or 'XP awarded'
    elif mode == 'badge':
        add_xp  = 50
        b_emoji = args[1] if len(args) > 1 else '🏅'
        b_name  = args[2] if len(args) > 2 else 'New Badge'
        b_desc  = args[3] if len(args) > 3 else 'Achievement unlocked'
        log_desc  = f'Earned {b_emoji} {b_name}'
        badge_line = f'- {b_emoji} **{b_name}** — *{b_desc}* `{TODAY}`'

    new_xp    = old_xp + add_xp
    new_level = level_from_xp(new_xp)
    new_max   = xp_for_level(new_level + 1)
    stat_boost = sum(5 for lv in range(old_level + 1, new_level + 1) if lv % 5 == 0)

    evolved = ''
    if   old_level < 16 <= new_level: evolved = 'Charmeleon'
    elif old_level < 36 <= new_level: evolved = 'Charizard'
    new_stage = evolved or old_stage

    move_defs     = MOVE_UNLOCKS.get(buddy_name, MOVE_UNLOCKS.get('Charmander', {}))
    new_moves_data = [(lv, *move_defs[lv]) for lv in sorted(move_defs) if old_level < lv <= new_level]

    out, last_log_idx = patch_buddy(lines, new_level, new_xp, new_max, new_stage,
                                    stat_boost, new_moves_data, mode, badge_line)

    if last_log_idx >= 0:
        out.insert(last_log_idx + 1, f'| {TODAY} | {log_desc} | +{add_xp} XP |\n')

    out = cap_journal(out)
    BUDDY_FILE.write_text(''.join(out))

    # Sync collection
    sync_active_to_collection(buddy_name, new_level, new_xp)

    # Roll for wild encounter
    col = read_collection()
    owned = {p['name'] for p in col['pokemon']}
    catch_result = roll_catch(add_xp, owned)
    if catch_result:
        tier, cname, ctype, cemoji = catch_result
        add_to_collection(cname, ctype, cemoji, tier)

    print(render_announcement(mode, add_xp, old_level, new_level, new_xp, new_max,
                              new_stage, stat_boost, new_moves_data, evolved,
                              catch_result, b_emoji, b_name, b_desc))

if __name__ == '__main__':
    main()
