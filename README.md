# 🎮 Pokemon Buddy for Claude

A Pokemon companion system for [Claude Code](https://claude.ai/code) — your AI coding assistant becomes a Pokemon Master Coach, your progress earns XP, and wild Pokemon appear as rewards.

## Features

- **Choose your starter** — Charmander 🔥, Bulbasaur 🌿, or Squirtle 💧, each with unique stats and move unlocks
- **Earn XP automatically** — Claude awards XP after bug fixes, features, deployments, and more
- **Daily streak bonus** — first XP award of the day gives +20 bonus XP; streak shown in status bar
- **Level up & evolve** — Lv.16 → Charmeleon/Ivysaur/Wartortle · Lv.36 → Charizard/Venusaur/Blastoise
- **Catch wild Pokemon** — rare encounters triggered by hard achievements (production ship = 4% legendary chance)
- **Role-type affinity** — Pokemon matching your trainer role type appear 3× more often in wild encounters
- **Rarity-based starting levels** — caught Pokemon join at Lv.1 (common) up to Lv.30 (mythical)
- **Shiny Pokemon** — 0.5% (1 in 200) chance on any catch — full celebration box + `✨` in party
- **Auto milestone badges** — 15 milestones awarded automatically (First Catch, Legend Seeker, Lv.10, 7-Day Streak, and more)
- **Trainer titles** — earn titles like *Legend Hunter*, *Shiny Chaser*, *Elite Deployer* based on your achievements
- **Pokedex tracker** — see how many unique Pokemon you've caught out of 68 total
- **Switch active buddy** — build a party, choose who to train
- **Live status bar** — party + XP bar + mood + streak shown at the bottom of Claude Code

```
🔥*Lv4 Charmander  ⚡Lv1 Pikachu 💥 [█████████░] 360/400 🏅1
```

## Trainer Roles

During install, choose your role — each maps to a Pokemon type that flavors your trainer profile:

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

> Your role type influences wild encounters — Pokemon of the same type appear **3× more often** in your catches.

## Install (v2.x — Claude Code plugin, works on any OS)

Inside Claude Code:

```
/plugin marketplace add andriar/pokemon-buddy-claude
/plugin install poke
```

That's the whole install. No shell scripts, no admin prompts, no emoji encoding bugs. Works identically on Windows, macOS, and Linux.

After install, restart your session, then pick a starter:

```
/poke:choose
```

The status bar animates immediately once you pick.

### Upgrading from v1.x (shell install)?

Your Pokémon, XP, level, streak, and collection are preserved. After installing the plugin:

```
/poke:migrate
```

Follow the prompts — it cleans up legacy install files and CLAUDE.md imports. State files stay put.

See [docs/MIGRATION.md](docs/MIGRATION.md) for details.

### Legacy shell install (v1.x)

Still available, but no longer recommended. See [releases/tag/v1.3.2](https://github.com/andriar/pokemon-buddy-claude/releases/tag/v1.3.2) for the last shell-installer release.

## Commands (v2.x)

All slash commands are namespaced under `/poke:*` in the plugin version.

| Command | Description |
|---|---|
| `/poke:status` | Full status card — stats, moves, badges, party, Dex, streak |
| `/poke:card` | Shareable ASCII trainer card |
| `/poke:xp <what you did>` | Award XP manually |
| `/poke:badge <description>` | Award a badge + 50 XP |
| `/poke:switch <name>` | Switch active buddy |
| `/poke:choose` | Pick your starter (first-time setup) |
| `/poke:persona on` | Turn on Pokémon Master Coach voice + auto-XP (opt-in, costs tokens) |
| `/poke:persona off` | Turn it off again — keep your buddy silent |
| `/poke:migrate` | One-shot migration from v1.x shell install |

### Cost note

**The default plugin install is free** — status bar runs locally, slash commands only cost tokens when you invoke them. The Pokémon Master Coach persona is **opt-in** because it adds ~150–250 tokens per conversation turn (always-on). Enable it if you love the flavor and can afford it; skip it for a silent buddy that still animates the status bar.

## XP auto-award (only active if persona is enabled)

When the Coach persona is enabled, Claude detects completed tasks and auto-runs `/poke:xp`:

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
| **Daily streak bonus** (first award of the day) | **+20** |

## Wild Pokemon encounters

Triggered automatically on XP awards. Higher XP = better rarity:

| Rarity | Trigger example | Chance |
|---|---|---|
| Common 🐦 | Bug fix | 8% |
| Uncommon ⚡ | Hard problem | 10% |
| Rare 🐲 | Feature complete | 4% |
| Legendary 🧬 | Ship to production | 4% |
| Mythical ✨ | Ship to production | 1% |
| **Shiny** ✨ | Any catch | **0.5%** |

Any caught Pokemon has a 0.5% (1 in 200) chance of being shiny — a special sparkling variant with a full celebration announcement.

Full catalogue of all 46 legendaries + 22 mythicals with their dev meanings: **[LEGENDARIES.md](LEGENDARIES.md)**

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
├── buddy-stats.md          ← Streak, counters, milestones
├── buddy-update.py         ← Core engine
├── statusline-buddy.sh     ← Status bar script
├── pokemon-persona.md      ← Coach persona
└── commands/
    ├── buddy.md
    ├── buddy-card.md
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

## Updating

Run the updater to get the latest version **without losing your buddy data**:

**macOS / Linux**

```bash
# From cloned repo:
bash update.sh

# Or remotely (no clone needed):
curl -sSL https://raw.githubusercontent.com/andriar/pokemon-buddy-claude/main/update.sh | bash
```

**Windows**

```powershell
# From cloned repo:
python update.py

# Or remotely (no clone needed):
python update.py --remote
```

The updater **never touches**:
- `~/.claude/buddy-pokemon.md` — your active buddy
- `~/.claude/pokemon-collection.md` — your party roster
- `~/.claude/buddy-stats.md` — your streak, counters, milestones
- `~/.claude/buddy-log-archive.md` — your history

It **only updates**: `buddy-update.py`, `statusline-buddy.sh`, `pokemon-persona.md`, and all `commands/`.

See [CHANGELOG.md](CHANGELOG.md) for what changed between versions.

## Uninstalling

Remove the engine + slash commands + status bar patch. By default, your buddy data (party, stats, journey log) is **kept** in `~/.claude/`.

**macOS / Linux**

```bash
bash uninstall.sh              # keep buddy data
bash uninstall.sh --purge      # also delete buddy/collection/stats
```

**Windows**

```powershell
python uninstall.py            # keep buddy data
python uninstall.py --purge    # also delete buddy/collection/stats
```

Or double-click `uninstall.bat` from Explorer.

The uninstaller also un-patches `CLAUDE.md` (backup saved as `CLAUDE.md.bak.<timestamp>`) and removes the `statusLine` entry from `settings.json` if it points to the buddy status script.

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3.6+
- **macOS / Linux**: Bash
- **Windows**: Windows Terminal (recommended) on Windows 10 20H1 or later — for full emoji + UTF-8 support

## License

MIT
