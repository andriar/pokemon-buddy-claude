"""Static data for Pokemon Buddy engine — imported by buddy-update.py.

Do NOT import from here directly in user code; always go through buddy-update.py.
"""

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
