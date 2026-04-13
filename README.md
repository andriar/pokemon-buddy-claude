# 🎮 Pokemon Buddy for Claude

A Pokemon companion system for [Claude Code](https://claude.ai/code) — your AI coding assistant becomes a Pokemon Master Coach, your progress earns XP, and wild Pokemon appear as rewards.

## Features

- **Choose your starter** — Charmander 🔥, Bulbasaur 🌿, or Squirtle 💧, each with unique stats and move unlocks
- **Earn XP automatically** — Claude awards XP after bug fixes, features, deployments, and more
- **Level up & evolve** — Lv.16 → Charmeleon/Ivysaur/Wartortle · Lv.36 → Charizard/Venusaur/Blastoise
- **Catch wild Pokemon** — rare encounters triggered by hard achievements (production ship = 4% legendary chance)
- **Switch active buddy** — build a party, choose who to train
- **Live status bar** — party + XP bar + mood shown at the bottom of Claude Code

```
🔥*Lv4 Charmander  ⚡Lv1 Pikachu 💥 [█████████░] 360/400 🏅1
```

## Install

```bash
curl -sSL https://raw.githubusercontent.com/andriar/pokemon-buddy-claude/main/install.sh | bash
```

Or clone and run:

```bash
git clone https://github.com/andriar/pokemon-buddy-claude
cd pokemon-buddy-claude
bash install.sh
```

Then restart Claude Code.

## Commands

| Command | Description |
|---|---|
| `/buddy` | Full status card — stats, moves, badges, party |
| `/buddy-xp <what you did>` | Award XP manually |
| `/buddy-badge <description>` | Award a badge + 50 XP |
| `/pokemon-switch <name>` | Switch active buddy |

## XP is awarded automatically

Claude detects completed tasks and auto-runs `/buddy-xp` without being asked:

| Achievement | XP |
|---|---|
| Fix a bug | +10 |
| Build a component | +20 |
| Learn a new concept | +25 |
| Complete a feature | +50 |
| Ship to production | +100 |
| Learn a new framework | +75 |
| Solve a hard problem | +40 |
| Write tests | +30 |
| Refactor / code review | +20 |

## Wild Pokemon encounters

Triggered automatically on XP awards. Higher XP = better rarity:

| Rarity | Trigger example | Chance |
|---|---|---|
| Common 🐦 | Bug fix | 8% |
| Uncommon ⚡ | Hard problem | 10% |
| Rare 🐲 | Feature complete | 4% |
| Legendary 🧬 | Ship to production | 4% |

## Evolution path

```
Charmander Lv.1  ──>  Charmeleon Lv.16  ──>  Charizard Lv.36
Bulbasaur  Lv.1  ──>  Ivysaur    Lv.16  ──>  Venusaur  Lv.36
Squirtle   Lv.1  ──>  Wartortle  Lv.16  ──>  Blastoise Lv.36
```

## Files installed

```
~/.claude/
├── buddy-pokemon.md        ← Active buddy data
├── pokemon-collection.md   ← Full party roster
├── buddy-update.py         ← Core engine
├── statusline-buddy.sh     ← Status bar script
├── pokemon-persona.md      ← Coach persona
└── commands/
    ├── buddy.md
    ├── buddy-xp.md
    ├── buddy-badge.md
    └── pokemon-switch.md
```

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3.8+
- Bash

## License

MIT
