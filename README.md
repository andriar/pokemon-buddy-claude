# 🎮 Pokemon Buddy for Claude

A Pokemon companion system for [Claude Code](https://claude.ai/code) — your coding progress earns XP, wild Pokemon appear as rewards, and a live status bar tracks your buddy at all times.

## Features

### Core
- **Choose your starter** — Charmander 🔥, Bulbasaur 🌿, Squirtle 💧, and 7 more starters, each with unique stats and move unlocks
- **Auto XP from token usage** — every completed turn awards XP via a local Stop hook (no persona required)
- **Manual XP** — Claude awards XP after bug fixes, features, deployments, and more
- **Level up & evolve** — Lv.16 → Charmeleon · Lv.36 → Charizard (Volcano badge unlocks 1 level earlier)
- **285-Pokémon Pokédex** — catch all gens from common to mythical; role-type affinity weights matching types 3×
- **Shiny Pokémon** — 1/200 base chance; Cascade badge raises it to 1/150, Shiny Charm item to 1/100

### Combat & Catching
- **Full type chart** — 18-type Gen-1+ chart with 2×/0.5×/0× multipliers; effectiveness shown in battle block
- **Multi-throw catch** — throws continue until caught or balls exhausted; Poké/Great/Ultra/Master Balls + berries
- **Pokéball inventory** — earned per level-up and XP milestone; berry drops boost catch rates
- **Combo multiplier** — tasks within the same hour stack up to ×2.0

### Progression
- **Daily streak XP multiplier** — consecutive-day coding multiplies XP: `1.0 + min(streak, 30) × 0.02` (caps at ×1.60 on day 30); `🔥N` shown in statusline when streak ≥ 3
- **8 Gym Badges** — earned through in-game activity, each unlocking a feature:

  | Badge | Earn by | Unlocks |
  |---|---|---|
  | 🪨 Boulder | First catch | Exp Share |
  | 💧 Cascade | 10 Pokémon caught | Shiny rate 1/200 → 1/150 |
  | ⚡ Thunder | Level 10 | Party XP slot 2 |
  | 🌈 Rainbow | 5 features shipped | Held item drops |
  | 💜 Soul | 7-day streak | Egg hatching |
  | 🌿 Marsh | 20 Pokémon caught | Double berry drop |
  | 🔥 Volcano | Ship 3 times | Evolve 1 level earlier |
  | 🌍 Earth | Level 30 | Weekly raid battles |

- **Held items** — equip one item to your active buddy:
  - 🥚 Lucky Egg → +50% XP
  - 🎀 Choice Band → +20% battle win chance
  - 🪙 Amulet Coin → 2× catch rate
  - ✨ Shiny Charm → 1/100 shiny rate
  - 🪨 Everstone → blocks evolution
  - 💫 Mega Stone → +10 effective level in gym battles (Earth badge)

- **Party battles** — up to 3 Pokémon in your active trio; XP splits 60%/25%/15% (Thunder badge)
- **Regional variants** — repeat catches roll 15% chance for Alolan/Galarian forms (Vulpix, Zigzagoon)
- **Trade evolutions** — `/poke:export` triggers Gastly→Gengar, Abra→Alakazam; `/poke:backup` triggers Machop→Machamp
- **Weekly raid boss** — legendary spawns every Monday; each XP gain chips HP; KO adds boss to collection (Earth badge)
- **Egg hatching** — earn an egg via 10 catches or 7-day streak; 200 XP to hatch a baby Pokémon (Soul badge)
- **Exp Share** — overflow XP from a capped buddy splits evenly across non-maxed party members (Boulder badge)

### Bond & Personality (v2.20+)
- **Natures** — every caught Pokémon rolls 1 of 25 canonical natures (Adamant, Timid, Modest, etc.). Each boosts one stat / lowers another; 5 are neutral.
- **Friendship (0–255)** — every Pokémon starts at 70; active buddy earns +1/XP, +3/level-up, +5/evolution. Max friendship grants **Best Friends 💖** milestone and **+25% wild catch rate**.
- **Friendship evolutions** — Eevee → Espeon (day, friendship ≥220) / Umbreon (night). Riolu → Lucario (day). Fires automatically during XP awards.
- **Shiny deepening** — `shiny_count` tracked on trainer card (`✨×N`). Milestones at 5 (Shiny Collector 🌟) and 10 (Shiny Connoisseur 🌠) catches.
- **Seasonal events** — monthly type spawn boosts: Halloween Ghost ×4, December Ice ×4, and 10 other themed months. Current season shown on trainer card.

### PvP & Mega Evolution (v2.26+)
- **Gym leader battles** — `/poke:battle <leader>` challenges Brock, Misty, Lt. Surge, Erika, Koga, Sabrina, Blaine, Giovanni. First win earns that leader's gym badge. Uses TYPE_CHART + buddy stats.
- **Mega Stone** — rare drop from legendary/mythical encounters. Equipped buddy with Earth badge gets **+10 effective level** in gym battles (`💫 MEGA EVOLVED!` flash in log).

### Trainer Card & History
- **Live status bar** — buddy · XP bar · streak tag · encounter state · persona flag
- **`/poke:status`** — full status card with stats, moves, badges, gym badges, held item, egg progress, party
- **`/poke:card`** — shareable ASCII trainer card
- **`/poke:export`** — full-page HTML trainer card + OpenGraph social share SVG
- **`/poke:history`** — chronological journey narrative grouped by month; `--export` flag writes `journey.html`
- **Trainer titles** — *Mythical Master*, *Legend Hunter*, *Shiny Chaser*, *Elite Deployer*, and more

## Trainer Roles

Choose your role during setup — each maps to a Pokémon type that weights wild encounters 3×:

| # | Role | Type |
|---|---|---|
| 1 | Frontend | Electric ⚡ |
| 2 | Backend | Rock 🪨 |
| 3 | Database | Water 💧 |
| 4 | DevOps | Steel ⚙️ |
| 5 | Security | Dark 🌑 |
| 6 | Testing | Fighting 🥊 |
| 7 | AI / ML | Psychic 🧠 |
| 8 | Full-stack | Normal ⭐ |
| 9 | QA Engineer | Bug 🐛 |
| 10 | Mobile / Android | Dragon 🐉 |

## Install

Inside Claude Code:

```
/plugin marketplace add andriar/pokemon-buddy-claude
/plugin install poke
```

No shell scripts, no admin prompts. Works on Windows, macOS, and Linux.

After install, restart your session and pick a starter:

```
/poke:choose
```

### Upgrading from v1.x?

Your Pokémon, XP, level, streak, and collection are preserved:

```
/poke:migrate
```

See [docs/MIGRATION.md](docs/MIGRATION.md) for details.

## Commands

| Command | Description |
|---|---|
| `/poke:status` | Full status card — stats, moves, gym badges, held item, egg, party |
| `/poke:card` | Shareable ASCII trainer card |
| `/poke:export` | Generate HTML trainer card + OpenGraph social image |
| `/poke:history` | Journey timeline grouped by month; `--export` → `journey.html` |
| `/poke:dex` | Browse your Pokédex; filter by type or rarity |
| `/poke:xp <what you did>` | Award XP manually |
| `/poke:badge <description>` | Award a badge + 50 XP |
| `/poke:switch <name>` | Switch active buddy |
| `/poke:party list\|add\|remove\|order` | Manage active party trio (up to 3) |
| `/poke:item list\|equip\|unequip` | Manage and equip held items |
| `/poke:raid` | Show weekly raid boss HP bar and your damage |
| `/poke:choose` | Pick your starter (first-time setup) |
| `/poke:backup` | Export buddy state to `buddy-export.json` |
| `/poke:import <file>` | Restore buddy state from a backup |
| `/poke:persona on\|off` | Toggle Pokémon Master Coach voice (opt-in, costs tokens) |
| `/poke:migrate` | One-shot migration from v1.x shell install |
| `/poke:uninstall` | Uninstall plugin; choose to keep or wipe buddy data |

## XP auto-award

Two independent systems run side-by-side:

### Per-turn from token usage (always on, free)

After every Claude Code turn, a Stop hook awards XP based on token counts:

| Token type | Rate |
|---|---|
| Output tokens | 1 XP / 100 |
| Input tokens | 1 XP / 1,000 |
| Cache write | 1 XP / 500 |
| Cache read | 1 XP / 5,000 |

### Task-keyword detection (requires Coach persona)

| Achievement | Base XP |
|---|---|
| Fix a bug | +10 |
| Build a component | +20 |
| Learn a new concept | +25 |
| Write tests | +30 |
| Refactor / code review | +20 |
| Solve a hard problem | +40 |
| Complete a feature | +50 |
| Learn a new framework | +75 |
| Ship to production | +100 |
| **Daily streak bonus** (first award of day) | **+20** |

All XP is then multiplied by the streak multiplier (`×1.02` per consecutive day, max `×1.60`), combo multiplier (up to `×2.0`), and Lucky Egg (`×1.5`) if equipped. The flash badge shows all active multipliers: `+56 XP ×1.12×1.50`.

## Wild Pokémon encounters

| Rarity | Trigger example | Chance |
|---|---|---|
| Common | Bug fix | 8% |
| Uncommon | Hard problem | 10% |
| Rare | Feature complete | 4% |
| Legendary | Ship to production | 4% |
| Mythical | Ship to production | 1% |
| **Shiny** | Any catch | **1/200** base (up to **1/100** with Shiny Charm) |

Full catalogue of all legendaries + mythicals: **[LEGENDARIES.md](LEGENDARIES.md)**

## Evolution paths

```
Charmander Lv.1  ──>  Charmeleon Lv.16  ──>  Charizard Lv.36
Bulbasaur  Lv.1  ──>  Ivysaur    Lv.16  ──>  Venusaur  Lv.36
Squirtle   Lv.1  ──>  Wartortle  Lv.16  ──>  Blastoise Lv.36
```

Trade evolutions (triggered by real events):
- `/poke:export` → Gastly→Haunter→Gengar, Abra→Kadabra→Alakazam
- `/poke:backup` → Machop→Machoke→Machamp

Volcano badge unlocks evolution 1 level earlier. Everstone item blocks all evolution.

## Files installed

**Plugin files** (managed by Claude Code):

```
<plugin-root>/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── buddy-update.py         ← Core engine
├── lib/data.py             ← Static Pokémon data, type chart, XP rules
├── hooks/
│   ├── session-start.py   ← Welcome + migration nudge
│   └── stop-xp.py         ← Per-turn token XP
├── skills/pokemon-coach/  ← Coach persona (opt-in)
└── commands/              ← Slash commands (/poke:*)
    ├── status.md    card.md    xp.md      badge.md
    ├── switch.md    party.md   item.md    raid.md
    ├── history.md   dex.md     export.md  backup.md
    ├── import.md    choose.md  persona.md migrate.md
    └── uninstall.md
```

**State files** (yours — never touched by updates):

```
~/.claude/
├── buddy-pokemon.md        ← Active buddy (level, XP, moves, badges, held item)
├── pokemon-collection.md   ← Full party + active party trio
├── buddy-stats.md          ← Streak, gym badges, item bag, egg, inventory, milestones
└── buddy-raid.json         ← Weekly raid boss state
```

## Token cost

| Component | Cost |
|---|---|
| Status bar | **0 tokens** — local shell command |
| Slash commands | **~200 tokens** — only when invoked |
| Session hook | **~50 tokens** — once per session |
| Stop hook (token XP) | **0 tokens** — local Python subprocess |
| Pokémon Coach persona | **opt-in** — ~150–250 tokens/turn |

## Development / Testing

### Local dev workflow

```bash
bash dev.sh           # sync repo → plugin cache
bash dev.sh status    # show sync state
bash dev.sh restore   # print reinstall instructions
```

### Run the test suite

210 tests covering XP math, streak multiplier, type chart, gym badges, held items, regional forms, trade evolutions, weekly raid, egg hatching, party XP splits, file round-trips, and catch system:

```bash
python3 -m unittest discover tests/
# or
pytest tests/ -v
```

### Tuning XP formula

Edit `TIERS` in `hooks/stop-xp.py`, then `bash dev.sh` and restart your session.

## Updating

```
/plugin update poke
```

State files in `~/.claude/` are never touched. See [CHANGELOG.md](CHANGELOG.md) for what changed.

## Uninstalling

```
/poke:uninstall keep    # preserves buddy data; reinstall resumes where you left off
/poke:uninstall clean   # wipes all state for a fresh start
/plugin uninstall poke
```

## Requirements

- [Claude Code](https://claude.ai/code) CLI (with plugin support)
- Python 3.6+

## License

MIT
