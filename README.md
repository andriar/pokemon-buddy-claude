# 🎮 Pokemon Buddy for Claude

A Pokemon companion system for [Claude Code](https://claude.ai/code) — your AI coding assistant becomes a Pokemon Master Coach, your progress earns XP, and wild Pokemon appear as rewards.

## Features

- **Choose your starter** — Charmander 🔥, Bulbasaur 🌿, or Squirtle 💧, each with unique stats and move unlocks
- **Auto XP from token usage** — every completed turn awards XP via a tiered formula (no persona required, runs in a local Stop hook)
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

## XP auto-award

Two independent systems run side-by-side:

### Per-turn from token usage (always on)

After every Claude Code turn, a Stop hook reads the transcript, extracts the turn's token counts, and awards XP via a tiered divisor formula. No persona, no keywords, no Claude tokens spent — the hook is a local Python subprocess.

| Token type | Rate |
|---|---|
| Output tokens | 1 XP / 100 |
| Input tokens | 1 XP / 1,000 |
| Cache write | 1 XP / 500 |
| Cache read | 1 XP / 5,000 |

The hook is idempotent per `session_id` (stored in `~/.claude/pokemon-buddy-plugin.json`) and never back-awards on a resumed/compacted session. In auto-mode XP awards, the encounter roll is unbiased (role type does not weight wild picks) and daily-quest `tasks_today` is not incremented — those remain driven by manual `/poke:xp` descriptions.

To tune, edit the `TIERS` dict in `hooks/stop-xp.py` and run `bash dev.sh` (see [Development / Testing](#development--testing)).

### Task-keyword detection (requires Coach persona)

When the Coach persona is enabled, Claude detects completed tasks and auto-runs `/poke:xp <description>`:

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

The plugin lives in your Claude Code plugin directory. Your buddy data stays in `~/.claude/`.

**Plugin files** (managed by Claude Code, don't touch):

```
<plugin-root>/
├── .claude-plugin/
│   ├── plugin.json         ← Plugin manifest
│   └── marketplace.json    ← Marketplace listing
├── buddy-update.py         ← Core engine (XP, evolution, catches)
├── statusline-buddy.sh     ← Status bar script
├── hooks/
│   ├── session-start.py    ← Session hook (welcome, migration nudge)
│   └── stop-xp.py          ← Stop hook (per-turn token-based XP)
├── skills/
│   └── pokemon-coach/
│       └── SKILL.md        ← Coach persona (opt-in)
└── commands/               ← Slash commands (/poke:*)
    ├── status.md
    ├── card.md
    ├── xp.md
    ├── badge.md
    ├── switch.md
    ├── choose.md
    ├── persona.md
    ├── migrate.md
    ├── backup.md
    ├── export.md
    └── import.md
```

**State files** (yours — never touched by updates):

```
~/.claude/
├── buddy-pokemon.md        ← Active buddy data
├── pokemon-collection.md   ← Full party roster
└── buddy-stats.md          ← Streak, counters, milestones
```

## Token cost

Every token spent on the buddy system is a token taken from your actual coding work. This system was designed to be as cheap as possible.

### Default install: zero ongoing cost

The v2.x plugin is **free by default**:

| Component | Cost |
|---|---|
| Status bar | **0 tokens** — runs as a shell command outside Claude context |
| Slash commands | **~200 tokens** — only when you invoke one |
| Session hook | **~50 tokens** — one-time on session start, skipped if no buddy |
| Stop hook (per-turn XP) | **0 tokens** — local Python subprocess, output is shown but not re-ingested |
| Pokémon Coach persona | **opt-in** — ~150–250 tokens/turn when enabled |

There is no always-on CLAUDE.md import in v2.x. The coach persona that previously loaded into every conversation (~380 tokens/session always) is now fully opt-in via `/poke:persona on`.

### Per-command cost

Each command runs a single Python script via one `Bash` tool call.

| Command | Tokens | What happens |
|---|---|---|
| `/poke:status` | ~200 | Script reads files, renders full status card |
| `/poke:xp` | ~200 | Script detects XP, patches file, prints announcement |
| `/poke:badge` | ~250 | Script patches file, prints badge box + announcement |
| `/poke:switch` | ~150 | Script swaps active buddy, regenerates buddy file |
| Auto XP (persona on) | ~200 | Same as `/poke:xp`, triggered after task completion |

### Why it's cheap: the design decisions

Most Claude Code customizations are expensive because they make Claude do the work in-context. This system offloads everything to a Python script:

| Approach | Tool calls | Tokens per XP award |
|---|---|---|
| ❌ Naive (Claude reads + edits file) | Read + 3× Edit | ~1,200 |
| ✅ This system (script does everything) | 1× Bash | ~200 |

**6× cheaper** than the naive approach. Key decisions:

1. **Script renders output** — Claude never formats the status card. Python outputs final text verbatim.
2. **Script detects XP** — keyword matching in Python; Claude doesn't reason about XP tiers.
3. **Single Bash call** — read + calculate + patch + output in one tool call.
4. **No runtime API calls** — PokeAPI (or any external data) is never fetched.

## Updating

Inside Claude Code:

```
/plugin update poke
```

Your state files (`buddy-pokemon.md`, `pokemon-collection.md`, `buddy-stats.md`) are never touched — they live in `~/.claude/` outside the plugin directory.

See [CHANGELOG.md](CHANGELOG.md) for what changed between versions.

## Development / Testing

If you're hacking on the plugin itself (not just using it), this section is for you.

### Local dev workflow — edit the repo, test in Claude Code

The plugin you run inside Claude Code lives in a cache directory, *not* this repo. Use `dev.sh` to sync your local edits into the cache without reinstalling:

```bash
bash dev.sh           # sync repo → plugin cache (default: deploy)
bash dev.sh status    # show which engine files are in sync
bash dev.sh restore   # print plugin reinstall instructions
```

Files covered: `buddy-update.py`, `lib/*.py`, `hooks/*.py`, `hooks.json`. After syncing `hooks.json` or hook files, **restart your Claude Code session** so hooks are re-registered.

### Run the unit test suite

152 tests cover XP math, streak, evolution, milestones, file round-trips, and catch system:

```bash
python3 -m unittest discover tests/
# or, if you have pytest:
pytest tests/ -v
```

Tests use temp dirs via `tempfile` — they never touch your real `~/.claude/` buddy state.

### Test the Stop hook manually

The hook expects the Claude Code Stop payload on stdin. Simulate it with a real transcript:

```bash
# 1. Find a transcript for this project
TRANSCRIPT=$(ls -t ~/.claude/projects/-Users-<you>-*/*.jsonl | head -1)

# 2. Fire the hook end-to-end (awards XP if anchor is stale)
echo "{\"transcript_path\":\"$TRANSCRIPT\",\"session_id\":\"TEST\",\"hook_event_name\":\"Stop\"}" \
  | python3 hooks/stop-xp.py
```

The hook is idempotent per `session_id`, so re-running with the same `session_id` gives no output until new turns appear in the transcript. To reset: delete the entry under `xp_sessions.TEST` in `~/.claude/pokemon-buddy-plugin.json`.

Edge cases that should exit silently with code 0:

```bash
echo ''                                           | python3 hooks/stop-xp.py  # empty stdin
echo '{"transcript_path":"/nope","session_id":"x"}' | python3 hooks/stop-xp.py  # missing file
echo 'not json'                                   | python3 hooks/stop-xp.py  # malformed
```

All failures are logged to `~/.claude/pokemon-buddy-error.log` and never crash the hook.

### Test `xp-auto` directly

The subcommand invoked by the Stop hook:

```bash
python3 buddy-update.py xp-auto 25 "250o+100i"   # award 25 XP with a token summary tag
python3 buddy-update.py xp-auto 0                # silent no-op
python3 buddy-update.py xp-auto not_a_number     # silent no-op (parses to 0)
```

Manual XP path (unchanged) still works the same way:

```bash
python3 buddy-update.py xp "fixed a bug"
```

### Tuning the XP formula

Edit `TIERS` in `hooks/stop-xp.py`:

```python
TIERS = {
    'output':       100,    # ← lower = more generous
    'input':        1000,
    'cache_write':  500,
    'cache_read':   5000,
}
```

Then `bash dev.sh` to push to the plugin cache, and restart your Claude Code session.

## Uninstalling

Run `/poke:uninstall` inside Claude Code and pick a mode:

- `/poke:uninstall keep` — preserves buddy state (`buddy-pokemon.md`, `pokemon-collection.md`, `buddy-stats.md`). Reinstalling later resumes exactly where you left off.
- `/poke:uninstall clean` — purges all state files for a fresh start.

Then remove the plugin:

```
/plugin uninstall poke
```

## Requirements

- [Claude Code](https://claude.ai/code) CLI (with plugin support)
- Python 3.6+

## License

MIT
