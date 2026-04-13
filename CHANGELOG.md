# Changelog

All notable changes to Pokemon Buddy for Claude are documented here.
Format: [version] — date — description

---

## [1.2.0] — 2026-04-14

### Added
- **Shiny Pokemon** — 0.5% (1 in 200) chance on any catch; shiny celebration block with `✨` markers; shinies flagged in party/card
- **Daily coding streak** — First XP award of the day earns +20 bonus XP; streak counter shown in status bar and status card; longest streak tracked
- **Auto milestone badges** — 15 milestones auto-awarded on achievement: First Catch, Legend Seeker, Myth Maker, Shiny Hunter, First/Final Evolution, Lv.10/20/30/50, Dex 10/20/30, 7-Day/30-Day Streak
- **Trainer titles** — Dynamic title computed from achievements (Mythical Master, Legend Hunter, Shiny Chaser, Pokedex Scholar, Elite Deployer, Bug Slayer, etc.); shown under trainer name in `/buddy`
- **`/buddy-card` command** — Shareable ASCII trainer card showing buddy, title, achievements, Dex count, streak, rarest catch, party, lifetime stats
- **Pokedex tracker** — `DEX: N/68 caught` shown in `/buddy` status and streak info
- **`buddy-stats.md`** — New persistent stats file tracking streak, counters (bugs/features/ships), catch flags, and milestone award history
- `commands/buddy-card.md` — new slash command file

### Changed
- `render_status()` — now shows trainer title, Dex count, and streak
- `render_statusline()` — shows streak count when ≥ 2 days (`🔥N` suffix)
- `render_announcement()` — shows streak bonus in XP line; shiny catch gets full-width celebration box; auto milestone badges get inline announcement
- Party display marks shiny Pokemon with `✨` prefix
- `roll_catch()` now returns 5-tuple `(tier, name, type, emoji, is_shiny)`

---

## [1.1.1] — 2026-04-14

### Added
- `install.py` — cross-platform Python installer for Windows, macOS, and Linux
- `update.py` — cross-platform Python updater with `--remote` flag; Windows-safe (no curl/bash required)

### Fixed
- `install.sh` / `install.py`: overwrite guard — prompts before wiping existing buddy data
- `install.sh` / `install.py`: stamps `buddy-version` on fresh install so updater detects correct installed version
- `install.py`: echoes default selection when user input falls back to Charmander/Frontend
- `install.sh`: added `python3` availability check with OS-specific install instructions (macOS/Linux)
- `install.sh`: redirects Windows (Git Bash/Cygwin) users to `install.py`
- `update.sh`: added `curl` availability check and Windows redirect to `update.py`

---

## [1.1.0] — 2026-04-13

### Added
- Full legendary pool across all 9 generations (46 legendaries)
- New **mythical** rarity tier — 1% chance on production ship only (22 mythicals including Arceus, Mew, Darkrai)
- All-generation common/uncommon/rare pools expanded
- `update.sh` — update installed files without touching user data
- `VERSION` file for version tracking
- `LEGENDARIES.md` — full legendary & mythical catalogue with dev mappings

### Changed
- `CATCH_RATES` updated: 100 XP now rolls for mythical tier (1%)

---

## [1.0.0] — 2026-04-13

### Added
- Interactive installer with starter Pokemon selection (Charmander, Bulbasaur, Squirtle)
- XP engine with auto-detection, level-ups, evolution, stat boosts
- Wild Pokemon catch system with rarity tiers (common / uncommon / rare / legendary)
- Pokemon party collection with active buddy switching
- Live status bar showing full party + mood + XP bar
- Slash commands: `/buddy`, `/buddy-xp`, `/buddy-badge`, `/pokemon-switch`
- Pokemon Master Coach persona for Claude
- Per-session token cost: ~380 tokens
- Per-command token cost: ~200 tokens
