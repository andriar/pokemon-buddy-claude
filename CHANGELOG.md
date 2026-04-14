# Changelog

All notable changes to Pokemon Buddy for Claude are documented here.
Format: [version] — date — description

---

## [2.0.0] — 2026-04-14

### Breaking — architectural rewrite

Pokemon Buddy is now distributed as a native **Claude Code plugin** (`.claude-plugin/` manifest) instead of a shell-installed script. One-command install on any OS, one-command uninstall, zero CLAUDE.md mutation by default.

### Added
- **Plugin manifest** — `.claude-plugin/plugin.json` + `marketplace.json`. Installable via `/plugin marketplace add` / `/plugin install`
- **SessionStart hook** — registers the statusline on first run, shows a welcome message if no buddy exists yet, nudges migration if a v1.x install is detected
- **Namespaced slash commands** — `/poke:status`, `:card`, `:xp`, `:badge`, `:switch`, `:choose`, `:migrate`, `:enable-persona`, `:disable-persona`
- **`/poke:choose`** — interactive in-chat starter picker (replaces the old shell-install Q&A)
- **`/poke:migrate`** — one-shot migration from v1.x shell install; preserves all state (buddy, XP, level, streak, collection, badges), removes only install artifacts, backs everything up to `~/.claude/buddy-v1-backup/`
- **Opt-in Pokémon Coach persona** — moved from CLAUDE.md import to `skills/pokemon-coach/SKILL.md`; users explicitly enable via `/poke:persona on` with clear token-cost disclosure
- **`docs/MIGRATION.md`** — full upgrade guide for v1.x users

### Changed
- **Default token cost is now zero** — status bar renders locally (free), slash commands only cost tokens when invoked, persona is opt-in. Pre-v2, the persona was loaded into every Claude conversation across every project (~150–250 tokens/turn, always-on).
- **Install works identically on Windows, macOS, and Linux** — no more bash/bat/emoji-encoding bug farm
- **README** — install section now leads with plugin install, shell installer marked as legacy

### Preserved
- **All state files** (`buddy-pokemon.md`, `pokemon-collection.md`, `buddy-stats.md`) keep their existing location and format. The plugin reads the same paths as v1.x.
- **buddy-update.py** engine — identical CLI surface (`status | statusline | card | xp | badge | switch | catch`), same XP math, same evolution, same catch mechanics, same shiny rates
- **Legacy shell installer files** (`install.sh`, `install.py`, `install.bat`, `uninstall.*`, `update.*`) — still in-tree for users pinned to v1.x tags, but no longer the recommended path

### Migration
Run `/poke:migrate` after installing the plugin. See `docs/MIGRATION.md`.

---

## [1.3.2] — 2026-04-14

### Fixed
- `/buddy-card`: off-by-one in row padding — box border is W+6 wide but row formula produced W+7 visual columns, shifting the right `║` 1 column right on every non-emoji line. Fixed: `pad = W - 1 - visual_len(content)` so all rows are exactly 60 visual columns regardless of emoji content.

---

## [1.3.1] — 2026-04-14

### Fixed
- `/buddy-card`: box borders now align correctly when content contains emoji — `visual_len()` counts wide chars (emoji) as 2 columns instead of 1, fixing the ragged right `║` border

---

## [1.3.0] — 2026-04-14

### Added
- **Role-type weighted catches** — Pokemon matching your trainer role type appear 3× more often in wild encounters. Frontend (Electric ⚡) attracts Pikachu/Zapdos; Mobile/Android (Dragon 🐉) attracts Bagon/Dragonite; Security (Dark 🌑) attracts Umbreon/Grimmsnarl, etc.
- **Rarity-based starting levels** — Caught Pokemon now join your party at a level reflecting their rarity: Common Lv.1 · Uncommon Lv.5 · Rare Lv.15 · Legendary Lv.25 · Mythical Lv.30
- **QA Engineer role** — New trainer role: QA Engineer (Bug 🐛 type), option 9
- **Mobile / Android role** — New trainer role: Mobile / Android (Dragon 🐉 type), option 10

### Fixed
- `install.sh` / `install.py`: `settings.json` now written with required `{"type": "command", "command": "..."}` format — Claude Code was rejecting the previous format missing `type`
- `install.py`: sync'd QA Engineer and Mobile/Android roles (were missing after `install.sh` was updated)
- `buddy-update.py` / `install.py`: added UTF-8 stdout reconfiguration on Windows so emoji output doesn't crash or garble on cp1252 terminals
- `install.sh`: `BASH_SOURCE[0]` unbound variable crash on piped bash execution — fallback to `$0`
- `install.sh`: 5 edge cases hardened — curl\|bash detection, preflight file check, write permission check, missing command file warnings, malformed/empty `settings.json` recovery

---

## [1.2.1] — 2026-04-14

### Changed
- **Statusline redesign** — four clearly separated sections with `│` dividers:
  `🔥 Charmander Lv.7  │  [colored bar] 630/700  │  🔥 ×1  ·  🏅 1  ·  👥 1  │  💭 chatter`
- **Colored XP bar** — green < 70%, yellow 70–90%, red ≥ 90% (ANSI codes)
- **Buddy chatter** (right side) — shows context-specific message after XP/badge awards for 5 min, then switches to XP-aware or time-of-day idle messages
- **Stats spacing** — streak, badge count, party count now separated by `  ·  ` for readability
- Party members removed from statusline (show in `/buddy` only); compact `👥 N` count shown instead
- New `buddy-state.txt` — written after each XP/badge award, read by statusline, auto-expires

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
