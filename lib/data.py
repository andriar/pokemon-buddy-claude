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

# Encounter rates — chance a wild Pokémon appears per XP tier (increased; catching is no longer auto)
ENCOUNTER_RATES = {
    10:  [('common',    0.25)],
    20:  [('common',    0.35)],
    25:  [('common',    0.40)],
    30:  [('common',    0.50), ('uncommon',  0.12)],
    35:  [('common',    0.45), ('uncommon',  0.12)],
    40:  [('common',    0.60), ('uncommon',  0.28), ('rare',      0.06)],
    50:  [('uncommon',  0.40), ('rare',      0.12)],
    75:  [('uncommon',  0.50), ('rare',      0.22)],
    100: [('uncommon',  0.45), ('rare',      0.35), ('legendary', 0.10), ('mythical', 0.03)],
}

# ── Pokéball system ───────────────────────────────────────────────────────────

POKEBALL_TYPES = {
    'master': {'emoji': '🟣', 'name': 'Master Ball', 'multiplier': 999.0},
    'ultra':  {'emoji': '🟡', 'name': 'Ultra Ball',  'multiplier': 2.0},
    'great':  {'emoji': '🔵', 'name': 'Great Ball',  'multiplier': 1.5},
    'poke':   {'emoji': '🔴', 'name': 'Poké Ball',   'multiplier': 1.0},
}

# Auto-select priority per wild Pokémon rarity (first available wins)
BALL_BY_RARITY = {
    'mythical':  ['master', 'ultra', 'great', 'poke'],
    'legendary': ['master', 'ultra', 'great', 'poke'],
    'rare':      ['ultra', 'great', 'poke'],
    'uncommon':  ['great', 'poke'],
    'common':    ['poke', 'great'],
}

# Balls earned alongside XP (by base XP value)
BALL_EARN_BY_XP = {
    10:  {'poke': 1},
    20:  {'poke': 1},
    25:  {'poke': 1},
    30:  {'poke': 2},
    35:  {'poke': 1, 'great': 1},
    40:  {'poke': 1, 'great': 1},
    50:  {'great': 1},
    75:  {'great': 1, 'ultra': 1},
    100: {'ultra': 2},
}

# ── Berry system ──────────────────────────────────────────────────────────────

BERRY_TYPES = {
    'razz':   {'emoji': '🍓', 'name': 'Razz Berry',        'catch_boost': 1.2},
    'nanab':  {'emoji': '🍌', 'name': 'Nanab Berry',       'flee_reduce': 0.5},
    'pinap':  {'emoji': '🍍', 'name': 'Pinap Berry',       'xp_boost': 2.0},
    'golden': {'emoji': '🌟', 'name': 'Golden Razz Berry', 'catch_boost': 1.5},
}

# Berry drop chances by base XP (rolled independently after task)
BERRY_DROP_RATES = {
    10:  [('razz', 0.05)],
    20:  [('razz', 0.08)],
    25:  [('razz', 0.10)],
    30:  [('razz', 0.12), ('nanab', 0.04)],
    35:  [('razz', 0.12), ('nanab', 0.04)],
    40:  [('razz', 0.15), ('nanab', 0.08), ('pinap', 0.03)],
    50:  [('nanab', 0.10), ('pinap', 0.05)],
    75:  [('pinap', 0.10), ('golden', 0.03)],
    100: [('pinap', 0.15), ('golden', 0.08)],
}

# ── Battle system ─────────────────────────────────────────────────────────────

# Wild Pokémon level range per tier (min, max)
WILD_LEVELS = {
    'common':    (1,  5),
    'uncommon':  (5,  15),
    'rare':      (15, 30),
    'legendary': (30, 50),
    'mythical':  (40, 60),
}

# Base catch probability per tier (post-battle, pre-ball multiplier)
BASE_CATCH_RATES = {
    'common':    0.85,
    'uncommon':  0.65,
    'rare':      0.40,
    'legendary': 0.12,
    'mythical':  0.05,
}

# Type advantage: buddy_type → wild types it's strong against (+20% win chance)
# Legacy alias kept for tests that import it directly
TYPE_ADVANTAGE = {
    'Fire':     ['Grass', 'Bug', 'Steel', 'Ice'],
    'Water':    ['Fire', 'Ground', 'Rock'],
    'Grass':    ['Water', 'Ground', 'Rock'],
    'Electric': ['Water', 'Flying'],
    'Normal':   [],
    'Poison':   ['Grass', 'Fairy'],
    'Rock':     ['Fire', 'Ice', 'Flying', 'Bug'],
    'Ground':   ['Fire', 'Electric', 'Poison', 'Rock', 'Steel'],
    'Bug':      ['Grass', 'Poison', 'Psychic'],
    'Ice':      ['Grass', 'Ground', 'Flying', 'Dragon'],
    'Psychic':  ['Fighting', 'Poison'],
    'Dragon':   ['Dragon'],
    'Dark':     ['Psychic', 'Ghost'],
    'Fighting': ['Normal', 'Ice', 'Rock', 'Dark', 'Steel'],
    'Ghost':    ['Psychic', 'Ghost'],
    'Steel':    ['Ice', 'Rock', 'Fairy'],
    'Fairy':    ['Fighting', 'Dragon', 'Dark'],
    'Flying':   ['Grass', 'Fighting', 'Bug'],
}

# Full type chart: attacker → {defender: multiplier}
# 2.0=super effective, 0.5=not very effective, 0.0=immune, 1.0=neutral (omitted)
_SE  = 2.0   # super effective
_NVE = 0.5   # not very effective
_IMM = 0.0   # immune
TYPE_CHART = {
    'Normal':   {'Rock': _NVE, 'Steel': _NVE, 'Ghost': _IMM},
    'Fire':     {'Fire': _NVE, 'Water': _NVE, 'Rock': _NVE, 'Dragon': _NVE,
                 'Grass': _SE, 'Ice': _SE, 'Bug': _SE, 'Steel': _SE},
    'Water':    {'Water': _NVE, 'Grass': _NVE, 'Dragon': _NVE,
                 'Fire': _SE, 'Ground': _SE, 'Rock': _SE},
    'Electric': {'Electric': _NVE, 'Grass': _NVE, 'Dragon': _NVE, 'Ground': _IMM,
                 'Water': _SE, 'Flying': _SE},
    'Grass':    {'Fire': _NVE, 'Grass': _NVE, 'Poison': _NVE, 'Flying': _NVE,
                 'Bug': _NVE, 'Dragon': _NVE, 'Steel': _NVE,
                 'Water': _SE, 'Ground': _SE, 'Rock': _SE},
    'Ice':      {'Water': _NVE, 'Ice': _NVE, 'Steel': _NVE,
                 'Grass': _SE, 'Ground': _SE, 'Flying': _SE, 'Dragon': _SE},
    'Fighting': {'Normal': _SE, 'Ice': _SE, 'Rock': _SE, 'Dark': _SE, 'Steel': _SE,
                 'Poison': _NVE, 'Flying': _NVE, 'Psychic': _NVE, 'Bug': _NVE, 'Fairy': _NVE,
                 'Ghost': _IMM},
    'Poison':   {'Grass': _SE, 'Fairy': _SE,
                 'Poison': _NVE, 'Ground': _NVE, 'Rock': _NVE, 'Ghost': _NVE, 'Steel': _IMM},
    'Ground':   {'Fire': _SE, 'Electric': _SE, 'Poison': _SE, 'Rock': _SE, 'Steel': _SE,
                 'Grass': _NVE, 'Bug': _NVE, 'Flying': _IMM},
    'Flying':   {'Grass': _SE, 'Fighting': _SE, 'Bug': _SE,
                 'Electric': _NVE, 'Rock': _NVE, 'Steel': _NVE},
    'Psychic':  {'Fighting': _SE, 'Poison': _SE,
                 'Psychic': _NVE, 'Steel': _NVE, 'Dark': _IMM},
    'Bug':      {'Grass': _SE, 'Psychic': _SE, 'Dark': _SE,
                 'Fire': _NVE, 'Fighting': _NVE, 'Flying': _NVE,
                 'Ghost': _NVE, 'Steel': _NVE, 'Fairy': _NVE},
    'Rock':     {'Fire': _SE, 'Ice': _SE, 'Flying': _SE, 'Bug': _SE,
                 'Fighting': _NVE, 'Ground': _NVE, 'Steel': _NVE},
    'Ghost':    {'Psychic': _SE, 'Ghost': _SE,
                 'Dark': _NVE, 'Normal': _IMM},
    'Dragon':   {'Dragon': _SE, 'Steel': _NVE, 'Fairy': _IMM},
    'Dark':     {'Psychic': _SE, 'Ghost': _SE,
                 'Fighting': _NVE, 'Dark': _NVE, 'Fairy': _NVE},
    'Steel':    {'Ice': _SE, 'Rock': _SE, 'Fairy': _SE,
                 'Fire': _NVE, 'Water': _NVE, 'Electric': _NVE, 'Steel': _NVE},
    'Fairy':    {'Fighting': _SE, 'Dragon': _SE, 'Dark': _SE,
                 'Fire': _NVE, 'Poison': _NVE, 'Steel': _NVE},
}

# ── Trade evolutions ──────────────────────────────────────────────────────────
# {pre_evo_name: (evolved_name, evolved_emoji, trigger_event)}
# trigger_event: 'export' | 'backup' | 'ship'
TRADE_EVOLUTIONS = {
    'Gastly':  ('Haunter', '👻', 'export'),
    'Haunter': ('Gengar',  '👻', 'export'),
    'Abra':    ('Kadabra', '🔮', 'export'),
    'Kadabra': ('Alakazam','🔮', 'export'),
    'Machop':  ('Machoke', '💪', 'backup'),
    'Machoke': ('Machamp', '🥊', 'backup'),
}

# ── Regional forms ────────────────────────────────────────────────────────────
# {base_name: [(region, display_name, emoji, type_override), ...]}
REGIONAL_FORMS = {
    'Vulpix':    [('Alolan',   'Alolan Vulpix',    '🦊❄️',  'Ice')],
    'Zigzagoon': [('Galarian', 'Galarian Zigzagoon','🦡',    'Dark')],
}
REGIONAL_CATCH_CHANCE = 0.15   # 15% on repeat catch

# ── Combo & rewards ───────────────────────────────────────────────────────────

# Combo multipliers: (min_tasks_this_hour, xp_multiplier)
COMBO_MULTIPLIERS = [
    (5, 2.0),
    (3, 1.5),
    (2, 1.2),
    (1, 1.0),
]
COMBO_WINDOW_SECS = 3600  # 1 hour window for combo

# Ball rewards on level-up (every level: +2 poke; every 5: +1 great; every 10: +1 ultra)
# Milestone overrides for special levels
LEVEL_UP_MILESTONE_REWARDS = {
    50: {'ultra': 2, 'msg': '🏆 Lv.50 milestone!'},
}

# Daily quest pool — picked by hash(TODAY) % len
DAILY_QUESTS = [
    {'id': 'fix_bug',     'desc': 'Fix a bug today',        'keywords': ['bug', 'fix', 'error', 'patch', 'hotfix'],       'reward': 'ultra',  'qty': 1},
    {'id': 'learn',       'desc': 'Learn something new',    'keywords': ['learn', 'understand', 'concept', 'explain', 'study', 'research'], 'reward': 'xp', 'qty': 25},
    {'id': 'feature',     'desc': 'Implement a feature',    'keywords': ['feature', 'implement', 'complete', 'finish'],    'reward': 'great',  'qty': 2},
    {'id': 'ship',        'desc': 'Ship to production',     'keywords': ['ship', 'deploy', 'release', 'production'],       'reward': 'shard',  'qty': 1},
    {'id': 'test',        'desc': 'Write or fix tests',     'keywords': ['test', 'spec', 'coverage', 'e2e', 'unit test'],  'reward': 'great',  'qty': 1},
    {'id': 'refactor',    'desc': 'Refactor some code',     'keywords': ['refactor', 'cleanup', 'rewrite', 'clean'],       'reward': 'razz',   'qty': 2},
    {'id': 'catch',       'desc': 'Catch a wild Pokémon',   'keywords': [],                                                'reward': 'great',  'qty': 1},
    {'id': 'research',    'desc': 'Research something',     'keywords': ['research', 'explore', 'discover', 'study'],      'reward': 'pinap',  'qty': 1},
    {'id': 'three_tasks', 'desc': 'Complete 3 tasks',       'keywords': [],                                                'reward': 'ultra',  'qty': 1},
]

POKEMON_POOL = {
    'common': [
        # Gen 1
        ('Pidgey',    'Normal',   '🐦'),
        ('Caterpie',  'Bug',      '🐛'),
        ('Ekans',     'Poison',   '🐍'),
        ('Sandshrew', 'Ground',   '🪨'),
        ('Clefairy',  'Fairy',    '🌙'),
        ('Jigglypuff','Normal',   '🎤'),
        ('Meowth',    'Normal',   '😺'),
        ('Geodude',   'Rock',     '🗿'),
        ('Mankey',    'Fighting', '🐵'),
        ('Growlithe', 'Fire',     '🐶'),
        ('Poliwag',   'Water',    '💧'),
        ('Magikarp',  'Water',    '🐟'),
        ('Bellsprout','Grass',    '🌿'),
        ('Tentacool', 'Water',    '💙'),
        ('Ponyta',    'Fire',     '🐴'),
        ('Slowpoke',  'Water',    '💖'),
        ('Magnemite', 'Electric', '⚙️'),
        ('Doduo',     'Normal',   '🐦'),
        ('Seel',      'Water',    '🦭'),
        ('Weedle',    'Bug',      '🐛'),
        ('Zubat',     'Poison',   '🦇'),
        ('Rattata',   'Normal',   '🐭'),
        ('Goldeen',   'Water',    '🐟'),
        ('Voltorb',   'Electric', '💣'),
        ('Cubone',    'Ground',   '💀'),
        ('Ditto',     'Normal',   '💜'),
        # Gen 2
        ('Sentret',   'Normal',   '🐹'),
        ('Hoothoot',  'Normal',   '🦉'),
        ('Spinarak',  'Bug',      '🐞'),
        ('Marill',    'Water',    '💧'),
        ('Sunkern',   'Grass',    '🌻'),
        ('Wooper',    'Water',    '💧'),
        ('Murkrow',   'Dark',     '🐦'),
        ('Snubbull',  'Fairy',    '🐶'),
        # Gen 3
        ('Wurmple',   'Bug',      '🐛'),
        ('Zigzagoon', 'Normal',   '🐺'),
        ('Poochyena', 'Dark',     '🐺'),
        ('Lotad',     'Water',    '🍃'),
        ('Wingull',   'Water',    '🐦'),
        ('Whismur',   'Normal',   '🎵'),
        ('Gulpin',    'Poison',   '💚'),
        ('Wailmer',   'Water',    '🐋'),
        # Gen 4
        ('Bidoof',    'Normal',   '🐻'),
        ('Starly',    'Normal',   '🐦'),
        ('Shinx',     'Electric', '⚡'),
        ('Buizel',    'Water',    '🦦'),
        ('Drifloon',  'Ghost',    '💨'),
        ('Buneary',   'Normal',   '🐰'),
        # Gen 5
        ('Patrat',    'Normal',   '🐭'),
        ('Pidove',    'Normal',   '🐦'),
        ('Lillipup',  'Normal',   '🐕'),
        ('Purrloin',  'Dark',     '😈'),
        ('Blitzle',   'Electric', '⚡'),
        ('Tympole',   'Water',    '💧'),
        # Gen 6
        ('Fletchling','Normal',   '🐦'),
        ('Scatterbug','Bug',      '🐛'),
        ('Bunnelby',  'Normal',   '🐰'),
        ('Litleo',    'Fire',     '🔥'),
        # Gen 7
        ('Pikipek',   'Normal',   '🦜'),
        ('Yungoos',   'Normal',   '🐾'),
        ('Grubbin',   'Bug',      '🐛'),
        ('Fomantis',  'Grass',    '🌿'),
        # Gen 8
        ('Wooloo',    'Normal',   '🐑'),
        ('Skwovet',   'Normal',   '🐹'),
        ('Yamper',    'Electric', '⚡'),
        ('Gossifleur','Grass',    '🌸'),
        ('Rolycoly',  'Rock',     '🪨'),
        # Gen 9
        ('Lechonk',   'Normal',   '🐷'),
        ('Tarountula','Bug',      '🐞'),
        ('Smoliv',    'Grass',    '🍈'),
        ('Nacli',     'Rock',     '🧂'),
        ('Tadbulb',   'Electric', '⚡'),
        ('Wiglett',   'Water',    '🐛'),
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
        ('Onix',      'Rock',     '🗿'),
        ('Rhydon',    'Ground',   '🦏'),
        ('Kangaskhan','Normal',   '🦘'),
        ('Pinsir',    'Bug',      '🪲'),
        ('Gyarados',  'Water',    '🐲'),
        ('Flareon',   'Fire',     '🔥'),
        ('Vaporeon',  'Water',    '💧'),
        # Gen 2
        ('Togepi',    'Fairy',    '🥚'),
        ('Espeon',    'Psychic',  '🔮'),
        ('Umbreon',   'Dark',     '🌑'),
        ('Heracross',  'Bug',     '🦴'),
        ('Wobbuffet', 'Psychic',  '💙'),
        ('Girafarig', 'Normal',   '🦒'),
        ('Stantler',  'Normal',   '🦌'),
        ('Smeargle',  'Normal',   '🎨'),
        # Gen 3
        ('Ralts',     'Psychic',  '🔮'),
        ('Bagon',     'Dragon',   '🐲'),
        ('Beldum',    'Steel',    '🔧'),
        ('Altaria',   'Dragon',   '☁️'),
        ('Absol',     'Dark',     '⚡'),
        ('Castform',  'Normal',   '🌤️'),
        ('Zangoose',  'Normal',   '🐾'),
        ('Seviper',   'Poison',   '🐍'),
        ('Solrock',   'Rock',     '☀️'),
        ('Lunatone',  'Rock',     '🌙'),
        # Gen 4
        ('Riolu',     'Fighting', '💪'),
        ('Rotom',     'Electric', '⚡'),
        ('Gible',     'Dragon',   '🐲'),
        ('Pachirisu', 'Electric', '⚡'),
        ('Mismagius', 'Ghost',    '👻'),
        ('Weavile',   'Dark',     '🔪'),
        # Gen 5
        ('Zorua',     'Dark',     '🦊'),
        ('Deino',     'Dragon',   '🐲'),
        ('Larvesta',  'Fire',     '🦋'),
        ('Emolga',    'Electric', '⚡'),
        ('Cinccino',  'Normal',   '🐭'),
        ('Chandelure','Ghost',    '🕯️'),
        # Gen 6
        ('Noibat',    'Dragon',   '🦇'),
        ('Espurr',    'Psychic',  '🔮'),
        ('Pangoro',   'Fighting', '🐼'),
        ('Klefki',    'Steel',    '🔑'),
        ('Carbink',   'Rock',     '💎'),
        # Gen 7
        ('Jangmo-o',  'Dragon',   '🐲'),
        ('Mimikyu',   'Ghost',    '👻'),
        ('Comfey',    'Fairy',    '🌺'),
        ('Wishiwashi','Water',    '🐟'),
        ('Sandygast', 'Ghost',    '🏖️'),
        # Gen 8
        ('Dreepy',    'Dragon',   '👻'),
        ('Falinks',   'Fighting', '💪'),
        ('Applin',    'Dragon',   '🍎'),
        ('Eiscue',    'Ice',      '🧊'),
        # Gen 9
        ('Frigibax',  'Dragon',   '🐲'),
        ('Pawmi',     'Electric', '⚡'),
        ('Klawf',     'Rock',     '🦀'),
        ('Charcadet', 'Fire',     '🔥'),
        ('Tinkatink', 'Fairy',    '🔨'),
    ],
    'rare': [
        # Gen 1
        ('Snorlax',   'Normal',   '😴'),
        ('Lapras',    'Water',    '💎'),
        ('Dratini',   'Dragon',   '🐲'),
        ('Porygon',   'Normal',   '💻'),
        ('Scyther',   'Bug',      '🔪'),
        ('Jolteon',   'Electric', '⚡'),
        ('Gengar',    'Ghost',    '👻'),
        ('Alakazam',  'Psychic',  '🔮'),
        ('Machamp',   'Fighting', '💪'),
        ('Gyarados',  'Water',    '🐲'),
        ('Exeggutor', 'Grass',    '🌴'),
        ('Starmie',   'Water',    '⭐'),
        # Gen 2
        ('Tyranitar', 'Rock',     '🦖'),
        ('Dragonite', 'Dragon',   '🐉'),
        ('Blissey',   'Normal',   '💗'),
        ('Ampharos',  'Electric', '⚡'),
        ('Skarmory',  'Steel',    '🦅'),
        ('Steelix',   'Steel',    '🗿'),
        # Gen 3
        ('Flygon',    'Dragon',   '🐲'),
        ('Metagross',  'Steel',   '🔧'),
        ('Salamence', 'Dragon',   '🐉'),
        ('Blaziken',  'Fire',     '🔥'),
        ('Swampert',  'Water',    '💧'),
        ('Sceptile',  'Grass',    '🌿'),
        ('Aggron',    'Steel',    '⚙️'),
        ('Milotic',   'Water',    '💧'),
        # Gen 4
        ('Garchomp',  'Dragon',   '🐉'),
        ('Lucario',   'Fighting', '💪'),
        ('Togekiss',  'Fairy',    '🐦'),
        ('Luxray',    'Electric', '⚡'),
        ('Gliscor',   'Ground',   '🦂'),
        ('Magnezone', 'Electric', '⚙️'),
        # Gen 5
        ('Hydreigon', 'Dragon',   '🐲'),
        ('Volcarona', 'Fire',     '🦋'),
        ('Haxorus',   'Dragon',   '🔪'),
        ('Zoroark',   'Dark',     '🦊'),
        ('Conkeldurr','Fighting', '💪'),
        ('Chandelure','Ghost',    '🕯️'),
        # Gen 6
        ('Goodra',    'Dragon',   '🐲'),
        ('Aegislash', 'Steel',    '🔪'),
        ('Sylveon',   'Fairy',    '🎀'),
        ('Greninja',  'Water',    '💧'),
        ('Talonflame','Fire',     '🔥'),
        ('Noivern',   'Dragon',   '🐉'),
        ('Hawlucha',  'Fighting', '🦅'),
        # Gen 7
        ('Kommo-o',   'Dragon',   '🐲'),
        ('Toxapex',   'Poison',   '🌊'),
        ('Golisopod', 'Bug',      '🦀'),
        ('Decidueye', 'Grass',    '🦉'),
        ('Incineroar','Fire',     '🔥'),
        ('Primarina', 'Water',    '🎤'),
        # Gen 8
        ('Dragapult', 'Dragon',   '👻'),
        ('Grimmsnarl','Dark',     '👺'),
        ('Corviknight','Steel',   '🦅'),
        ('Cinderace', 'Fire',     '🔥'),
        ('Rillaboom', 'Grass',    '🥁'),
        ('Inteleon',  'Water',    '💧'),
        # Gen 9
        ('Baxcalibur','Dragon',   '🐉'),
        ('Gholdengo', 'Steel',    '💰'),
        ('Kingambit', 'Dark',     '👹'),
        ('Meowscarada','Grass',   '🌿'),
        ('Skeledirge','Fire',     '🔥'),
        ('Quaquaval', 'Water',    '💃'),
        ('Tinkaton',  'Fairy',    '🔨'),
        ('Iron Valiant','Fairy',  '⚔️'),
        ('Roaring Moon','Dragon', '🌙'),
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
        # Gen 3 — Weather, Eon & Regis
        ('Kyogre',    'Water',        '🌊'),
        ('Groudon',   'Ground',       '🌋'),
        ('Rayquaza',  'Dragon',       '🐉'),
        ('Latios',    'Dragon',       '🔵'),
        ('Latias',    'Dragon',       '🔴'),
        ('Regirock',  'Rock',         '🗿'),
        ('Regice',    'Ice',          '❄️'),
        ('Registeel', 'Steel',        '⚙️'),
        # Gen 4 — Dialga, Palkia, Giratina, Lake trio
        ('Dialga',    'Steel',        '⏰'),
        ('Palkia',    'Water',        '🌀'),
        ('Giratina',  'Ghost',        '👀'),
        ('Heatran',   'Fire',         '🌋'),
        ('Cresselia',  'Psychic',     '🌙'),
        ('Uxie',      'Psychic',      '🧠'),
        ('Mesprit',   'Psychic',      '💗'),
        ('Azelf',     'Psychic',      '💥'),
        ('Regigigas', 'Normal',       '🤝'),
        # Gen 5 — Tao Trio & Forces of Nature
        ('Reshiram',  'Dragon',       '🌞'),
        ('Zekrom',    'Dragon',       '⚡'),
        ('Kyurem',    'Dragon',       '💎'),
        ('Cobalion',  'Steel',        '🔪'),
        ('Terrakion', 'Rock',         '🗿'),
        ('Virizion',  'Grass',        '🌿'),
        ('Tornadus',  'Flying',       '🌪️'),
        ('Thundurus', 'Electric',     '⚡'),
        ('Landorus',  'Ground',       '🌍'),
        # Gen 6 — Life & Death
        ('Xerneas',   'Fairy',        '🦌'),
        ('Yveltal',   'Dark',         '🦅'),
        ('Zygarde',   'Dragon',       '🐍'),
        # Gen 7 — Sun, Moon, Tapus
        ('Solgaleo',  'Psychic',      '🌞'),
        ('Lunala',    'Psychic',      '🌙'),
        ('Necrozma',  'Psychic',      '💎'),
        ('Tapu Koko', 'Electric',     '⚡'),
        ('Tapu Lele', 'Psychic',      '🔮'),
        ('Tapu Bulu', 'Grass',        '🌿'),
        ('Tapu Fini', 'Water',        '💧'),
        # Gen 8 — Galar & Regis
        ('Zacian',    'Fairy',        '🔪'),
        ('Zamazenta', 'Fighting',     '🏰'),
        ('Eternatus', 'Poison',       '💀'),
        ('Calyrex',   'Psychic',      '👑'),
        ('Glastrier', 'Ice',          '🐎'),
        ('Spectrier', 'Ghost',        '🐎'),
        ('Regieleki', 'Electric',     '⚡'),
        ('Regidrago', 'Dragon',       '🐉'),
        # Gen 9 — Paldea
        ('Koraidon',  'Dragon',       '🦖'),
        ('Miraidon',  'Dragon',       '🤖'),
        ('Ting-Lu',   'Dark',         '📿'),
        ('Chien-Pao', 'Dark',         '🔪'),
        ('Wo-Chien',  'Dark',         '📜'),
        ('Chi-Yu',    'Dark',         '🐟'),
        ('Ogerpon',   'Grass',        '🎭'),
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
        ('Manaphy',   'Water',        '💧'),
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

# ── National Dex IDs (for PokéAPI sprites) ────────────────────────────────────
POKEDEX_IDS = {
    # Starters & evolutions
    'Bulbasaur': 1, 'Ivysaur': 2, 'Venusaur': 3,
    'Charmander': 4, 'Charmeleon': 5, 'Charizard': 6,
    'Squirtle': 7, 'Wartortle': 8, 'Blastoise': 9,
    # Common
    'Weedle': 13, 'Pidgey': 16, 'Rattata': 19, 'Zubat': 41,
    'Geodude': 74, 'Magikarp': 129,
    'Sentret': 161, 'Hoothoot': 163, 'Spinarak': 167,
    'Wurmple': 265, 'Zigzagoon': 263,
    'Bidoof': 399, 'Starly': 396,
    'Patrat': 504, 'Pidove': 519,
    'Fletchling': 661, 'Scatterbug': 664,
    'Pikipek': 731, 'Yungoos': 734,
    'Wooloo': 831, 'Skwovet': 819,
    'Lechonk': 924, 'Tarountula': 917,
    # Uncommon
    'Pikachu': 25, 'Vulpix': 37, 'Abra': 63, 'Machop': 66,
    'Gastly': 92, 'Psyduck': 54, 'Eevee': 133,
    'Togepi': 175, 'Espeon': 196, 'Umbreon': 197, 'Heracross': 214,
    'Ralts': 280, 'Bagon': 371, 'Beldum': 374,
    'Gible': 443, 'Riolu': 447, 'Rotom': 479,
    'Zorua': 570, 'Deino': 633, 'Larvesta': 636,
    'Espurr': 677, 'Noibat': 714,
    'Comfey': 764, 'Mimikyu': 778, 'Jangmo-o': 782,
    'Falinks': 870, 'Dreepy': 885,
    'Pawmi': 921, 'Frigibax': 999,
    # Rare
    'Scyther': 123, 'Lapras': 131, 'Porygon': 137, 'Snorlax': 143,
    'Dratini': 147, 'Dragonite': 149, 'Jolteon': 135,
    'Blissey': 242, 'Tyranitar': 248,
    'Flygon': 330, 'Salamence': 373, 'Metagross': 376,
    'Garchomp': 445, 'Lucario': 448, 'Togekiss': 468,
    'Haxorus': 612, 'Hydreigon': 635, 'Volcarona': 637,
    'Aegislash': 681, 'Sylveon': 700, 'Goodra': 706,
    'Toxapex': 748, 'Golisopod': 768, 'Kommo-o': 784,
    'Corviknight': 823, 'Grimmsnarl': 861, 'Dragapult': 887,
    'Kingambit': 983, 'Baxcalibur': 998, 'Gholdengo': 1000,
    # Legendary
    'Articuno': 144, 'Zapdos': 145, 'Moltres': 146, 'Mewtwo': 150,
    'Raikou': 243, 'Entei': 244, 'Suicune': 245, 'Lugia': 249, 'Ho-Oh': 250,
    'Latias': 380, 'Latios': 381, 'Kyogre': 382, 'Groudon': 383, 'Rayquaza': 384,
    'Dialga': 483, 'Palkia': 484, 'Heatran': 485, 'Giratina': 487, 'Cresselia': 488,
    'Cobalion': 638, 'Terrakion': 639, 'Virizion': 640, 'Reshiram': 643,
    'Zekrom': 644, 'Kyurem': 646,
    'Xerneas': 716, 'Yveltal': 717, 'Zygarde': 718,
    'Tapu Koko': 785, 'Tapu Lele': 786, 'Tapu Bulu': 787, 'Tapu Fini': 788,
    'Solgaleo': 791, 'Lunala': 792, 'Necrozma': 800,
    'Zacian': 888, 'Zamazenta': 889, 'Eternatus': 890,
    'Glastrier': 896, 'Spectrier': 897, 'Calyrex': 898,
    'Wo-Chien': 1001, 'Ting-Lu': 1002, 'Chien-Pao': 1003, 'Chi-Yu': 1004,
    'Koraidon': 1007, 'Miraidon': 1008,
    # Mythical
    'Mew': 151, 'Celebi': 251,
    'Jirachi': 385, 'Deoxys': 386,
    'Darkrai': 491, 'Shaymin': 492, 'Arceus': 493,
    'Victini': 494, 'Keldeo': 647, 'Meloetta': 648, 'Genesect': 649,
    'Diancie': 719, 'Hoopa': 720, 'Volcanion': 721,
    'Magearna': 801, 'Marshadow': 802, 'Zeraora': 807, 'Meltan': 808, 'Melmetal': 809,
    'Zarude': 893,
    'Terapagos': 1024, 'Pecharunt': 1025,
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
# Buddy Pokemon: {stage} {stage_emoji}

**Name**: {name}
**Type**: {ptype}
**Trainer**: {trainer}
**Specialty**: {specialty}
**Level**: {level}
**XP**: {xp} / {xp_max}
**Stage**: {stage} {stage_emoji}
**HeldItem**: none

## Evolution Path

**Current Stage**: {stage} {stage_emoji}

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
