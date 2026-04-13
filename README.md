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

## Token cost

Every token spent on the buddy system is a token taken from your actual coding work. This system was designed to be as cheap as possible. Here's exactly what it costs.

### Per-session overhead (loaded on every Claude Code start)

These files are always loaded into context via `CLAUDE.md`:

| File | Size | Tokens |
|---|---|---|
| `buddy-pokemon.md` (active buddy data) | ~1 KB | ~250 |
| `pokemon-persona.md` (coach persona) | ~350 B | ~90 |
| `CLAUDE.md` buddy section (auto-award rules) | ~150 B | ~40 |
| **Total per session** | | **~380 tokens** |

This is a fixed cost you pay once per conversation, regardless of how many commands you run.

### Per-command cost

Each command runs a single Python script via one `Bash` tool call. No file reads, no multiple edits.

| Command | Tool calls | Tokens | What happens |
|---|---|---|---|
| `/buddy` | 1 Bash | ~200 | Script reads files, renders full status card |
| `/buddy-xp` | 1 Bash | ~200 | Script detects XP, patches file, prints announcement |
| `/buddy-badge` | 1 Bash | ~250 | Script patches file, prints badge box + announcement |
| `/pokemon-switch` | 1 Bash | ~150 | Script swaps active buddy, regenerates buddy file |
| Auto XP award | 1 Bash | ~200 | Same as `/buddy-xp`, triggered after task completion |

### Why it's cheap: the design decisions

Most Claude Code customizations are expensive because they make Claude do the work in-context. This system offloads everything to a Python script:

| Approach | Tool calls | Tokens per XP award |
|---|---|---|
| ❌ Naive (Claude reads + edits file) | Read + 3× Edit | ~1,200 |
| ✅ This system (script does everything) | 1× Bash | ~200 |

**6× cheaper** than the naive approach.

The key decisions that keep it cheap:

1. **Script renders output** — Claude never formats the status card or announcement. The Python script outputs the final text verbatim.
2. **Script detects XP** — keyword matching in Python means Claude doesn't need to reason about which XP tier applies.
3. **Single Bash call** — one tool call covers read + calculate + patch + output. No round-trips.
4. **Lazy persona loading** — `pokemon-persona.md` is referenced in `CLAUDE.md` but kept at 350 bytes (stripped from 4.7 KB original).
5. **No runtime API calls** — PokeAPI (or any external data) is never fetched during commands.

### Real-world cost estimate

A typical coding session with 5 auto XP awards and 1 `/buddy` check:

```
Session load:       380 tokens  (one-time)
5× auto XP award:  1,000 tokens (5 × 200)
1× /buddy status:   200 tokens

Total:            ~1,580 tokens per session
```

At typical Claude API pricing (~$3 per 1M input tokens), that's roughly **$0.005 per session** — less than half a cent.

### Status bar cost

The status bar (`statusline-buddy.sh`) calls Python directly via the shell — it runs **outside** the Claude context entirely. It costs **0 Claude tokens**.

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3.8+
- Bash

## License

MIT
