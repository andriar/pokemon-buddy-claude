# Changelog

All notable changes to Pokemon Buddy for Claude are documented here.
Format: [version] — date — description

---

## [2.8.0] — 2026-04-22

### Added
- **Exp Share** — once your active buddy reaches Lv.100, excess XP splits evenly across non-maxed party members. Level-ups (and Lv.100 caps) propagate automatically. Announcement shows a 🔀 block listing each recipient; statusline chatter surfaces `Lv.100! Exp Share → N party 🔀`.
- **`LEVEL_CAP` + `CAP_XP` constants and `clamp_to_cap()` helper** — unified level-cap math removes magic `100`/`xp_for_level(101) - 1` duplication across the XP pipeline.

### Changed
- **XP pipeline** — cap-clamp logic now flows through `clamp_to_cap()`, returning `(level, stored_xp, overflow)`. Buddy reach cap → overflow drives Exp Share; below cap → identical behavior to v2.7.0.

---

## [2.7.0] — 2026-04-21

### Added
- **Encounter throw wobble animation** — statusline now renders Pokémon Go–style wobble frames (`·` → `· ·` → `· · ·` → `💫`) per throw, timestamp-driven from `base_ts` + `throw_secs`. Multi-throw encounters show `1/N`, `2/N` counters before the final reveal.
- **Persona flag in statusline** — appends `🎭` suffix when the Pokémon Master Coach persona is active (detected from `~/.claude/CLAUDE.md`). Absent when persona is off.

### Changed
- **Compact statusline** — dropped the stats section (streak · badges · party count). New layout: `version · buddy · XP bar · state · persona`. State slot rotates between chatter (idle) and live encounter animation.

### Fixed
- **Evolved form now displays correctly everywhere** — statusline, status card PARTY, ASCII trainer card party, HTML trainer card, Pokédex, and switch messages all showed starter form (e.g. `🔥 Charmander Lv.39`) instead of evolved stage (`🐉 Charizard Lv.39`). New `displayed_form()` helper computes display name + emoji from starter evolution thresholds by level; non-starters pass through unchanged. No schema or migration.

---

## [2.6.4] — 2026-04-21

### Added
- **Token-based auto XP** — Stop hook (`stop-xp.py`) awards XP every turn based on token usage. No more manual `/poke:xp` calls for routine work.

### Fixed
- **Negative XP bar on buddy switch** — switching to a high-level Pokémon showed values like `-2900/150` due to legacy/inconsistent XP totals. Healed on load + clamped on render.
- **Lost evolution state on switch** — evolved forms reverted to base when swapping buddies. Evolution state now persists per Pokémon in the collection.

---

## [2.6.3] — 2026-04-18

### Fixed
- **Plugin update detection** — `.claude-plugin/marketplace.json` version fields were stuck at `2.0.0`, so Claude Code never surfaced updates via `/plugin`. Both `metadata.version` and `plugins[0].version` now track the plugin version and will be bumped with every release.

---

## [2.6.2] — 2026-04-18

### Fixed
- **`/poke:choose` now works on first run** — previously it shelled into `buddy-update.py switch`, which gated on an existing buddy file and dead-ended with "run /poke:choose", leaving new trainers stuck in a circular error. Added a dedicated `choose` mode that bootstraps `buddy-pokemon.md` + `buddy-collection.json` from scratch, accepts both a number (1–10) and the Pokémon name, and delegates to `switch` when the trainer already has a party.

---

## [2.6.1] — 2026-04-18

### Fixed
- **`/poke:uninstall` now fully reverses the install** — previously only wiped buddy state files and left behind the statusLine entry in `settings.json`, the `pokemon-buddy-claude` marketplace entry, and plugin-side files (`pokemon-buddy-plugin.json`, `buddy-encounter.json`, `buddy-version`, `buddy-v1-backup/`). `keep` mode now wipes all plugin traces while preserving buddy data; `clean` mode wipes everything. StatusLine backup (`_statusLineBackup`) is restored when present.
- **SessionStart greets returning trainers** — reinstalling with preserved buddy data now prints a "welcome back" message instead of silently resuming.

### Changed
- **`buddy-update.py purge`** — accepts `keep` or `all` scope argument (defaults to `all` for backward compatibility).

---

## [2.6.0] — 2026-04-18

### Added
- **`/poke:dex` filters** — browse the Pokédex by rarity (`/poke:dex legendary`, `/poke:dex shiny`, etc.) or by Pokémon type (`/poke:dex fire`, `/poke:dex psychic`, etc.); unfiltered view unchanged
- **Social-share image** — `/poke:export` now also writes `trainer-card-og.svg` (1200×630 OpenGraph image) alongside the HTML, with `og:*` + `twitter:*` meta tags wired into `<head>` so link previews on Discord/Slack/Mastodon auto-populate when the card is hosted
- **`buddy-update.py og`** — standalone mode to regenerate just the social-share SVG
- **`/poke:uninstall`** — interactive uninstall with two modes: `keep` (default — preserves buddy state, lets reinstall pick up where you left off) or `clean` (purges all state files for a fresh start). Backed by a new `buddy-update.py purge` mode that removes `buddy-pokemon.md`, `pokemon-collection.md`, `buddy-stats.md`, and log archives.

### Changed
- **Legacy shell installers removed** — `install.{sh,py,bat}`, `uninstall.{sh,py,bat}`, `update.{sh,py}` deleted from `main`; they referenced stale command filenames and were broken. Users pinned to v1.x still have the [v1.3.2](https://github.com/andriar/pokemon-buddy-claude/releases/tag/v1.3.2) release. v2.x install path is unchanged: `/plugin install poke`
- **`trainer-card.html` gitignored** — generated output from `/poke:export`, no longer tracked
- **CI + `/ship` syntax check** — dropped references to deleted installers; now also compiles `scripts/check-legendaries.py` and `lib/data.py`

---

## [2.5.0] — 2026-04-17

### Added
- **Pokémon sprites in party table** — each party row now shows the actual PokéAPI sprite image instead of an emoji; shiny Pokémon use the shiny sprite variant
- **Pokéball image assets** — ball inventory uses real Pokéball sprites (Poké/Great/Ultra/Master) with a count badge, replacing the coloured circle emojis
- **RPG stat bars** — stats section replaced with 6 horizontal progress bars (Streak, Pokédex, Total XP, Bug Fixes, Features, Ships), each with its own accent colour and shimmer animation
- **Trainer card visual revamp** — new dark indigo theme (BRIX-inspired), Inter + Press Start 2P typography, dot-grid background, glassmorphism cards, `sprite_url` helper, `_BALL_SPRITES` constant, and `POKEDEX_IDS` national dex map in `lib/data.py`

### Fixed
- **Motion CDN `stagger` export error** — pinned to `motion@10.18.0/+esm` which correctly exports `stagger`, `spring`, and `animate`

---

## [2.4.0] — 2026-04-17

### Added
- **HTML trainer card** — `/poke:export` now generates a full-page interactive Pokemon-themed HTML card (replaces SVG); includes animated XP bar, rarity-coloured party table, ball inventory, and daily quest widget
- **`/poke:dex`** — new Pokédex command shows all caught Pokémon grouped by rarity in a 3-per-row ASCII table
- **Ball inventory on trainer card** — `/poke:card` achievements section now shows current Poké/Great/Ultra/Master Ball counts
- **Daily quest always visible** — XP output always shows the active quest and its status (`[…]` or `✓ DONE`), not only on completion
- **`RARITY_TIER_ORDER`, `RARITY_LABELS_ASCII`, `_pokemon_tier()`, `_group_by_tier()`** — module-level rarity constants and helpers; 7 new unit tests cover them

### Changed
- **Party section moved out of trainer card** — party now renders as a separate table below the main card, with columns for Pokémon, Level, and Rarity, grouped by tier with dividers

---

## [2.3.0] — 2026-04-17

### Added
- **Multi-throw catch mechanic** — When a wild Pokémon breaks free, the game keeps throwing balls in priority order (Ultra → Great → Poké) until the Pokémon is caught or all applicable balls are exhausted
- **Encounter display overhaul** — Rarity tier badges (`◌ ◈ ◆ ★ ✦`), flavor text per tier, progress bars for win chance and catch rate, and live inventory countdown on each missed throw

### Changed
- **"Broke free" counter is now accurate** — Each missed throw shows the remaining ball count at that exact moment, not the final end-of-encounter count

---

## [2.2.0] — 2026-04-17

### Added
- **Pokéball inventory** — trainers now collect Poké Balls, Great Balls, Ultra Balls, and Master Balls; stored in `buddy-stats.md` alongside XP; new trainers start with 5 Poké Balls
- **Battle mechanic** — wild encounters now require a battle before catching; win % = `clamp(buddy_lv / wild_lv × 70%, 20%, 95%)` with +20% for type advantage; losing means the Pokémon flees with no ball used
- **Wild Pokémon levels** — each wild Pokémon spawns with a random level by tier (common 1–5, uncommon 5–15, rare 15–30, legendary 30–50, mythical 40–60)
- **Ball auto-selection** — best available ball chosen automatically by rarity; Master Ball guarantees 100% catch; falls back through Ultra → Great → Poké Ball
- **Berry system** — Razz Berry (+20% catch), Nanab Berry (flavor), Pinap Berry (×2 XP), Golden Razz Berry (+50% catch); earned as random drops alongside ball rewards; best available berry auto-used on each throw
- **Combo multiplier** — tasks completed within the same hour stack a combo (×1.2 at 2, ×1.5 at 3, ×2.0 at 5); combo counter and timestamp stored in stats
- **Daily quest** — one quest per day from a pool of 9 (fix bug, learn something, ship, catch, etc.); rewards balls, berries, or Master Ball shards on completion
- **Level-up rewards** — every level awards +2 Poké Balls; every 5 levels +1 Great Ball; every 10 levels +1 Ultra Ball; Lv.50 awards 2 Ultra Balls
- **Master Ball shards** — badges each award 1 shard; collecting 3 shards automatically converts to 1 Master Ball
- **Contextual statusline** — statusbar shows encounter result (battle outcome, ball used, catch result, inventory snapshot) for 5 minutes after an encounter, then reverts to normal view
- **Increased encounter rates** — wild Pokémon now appear 2–3× more often since catching is no longer automatic
- **`dev.sh` script** — `bash dev.sh` syncs repo → plugin cache instantly for local testing; `bash dev.sh status` shows sync state; `bash dev.sh restore` reinstalls from `install.sh`
- **48 new unit tests** — covering all new systems: inventory round-trip, battle logic, ball selection, catch probability, berry consumption, combo multiplier, daily quest lifecycle, level-up rewards, and full `run_encounter` flow (122 total)

### Changed
- **`roll_catch()` replaced by `run_encounter()`** — old auto-catch is gone; new function runs the full battle → ball-select → attempt-catch pipeline and returns `(catch_result, encounter_info)` for announcement rendering
- **Announcement output** — encounter block now shows wild Pokémon level, battle win %, ball type used, catch %, and remaining inventory; combo and earned items printed above the XP bar
- **`CATCH_RATES` renamed `ENCOUNTER_RATES`** — reflects that these are spawn probabilities, not catch probabilities (separate `BASE_CATCH_RATES` dict added per tier)
- **`STATS_SCHEMA_VER` bumped to 2** — new inventory, combo, and daily quest fields added to `buddy-stats.md`

---

## [2.1.0] — 2026-04-15

### Added
- **Engine split** — static Pokémon data (pools, XP rules, milestones, BUDDY_TEMPLATE) extracted to `lib/data.py`; `buddy-update.py` shrinks from 1763 → 1322 lines and imports from `lib`
- **CI workflow** — `.github/workflows/ci.yml` with three jobs: syntax check (`py_compile`), unit tests (`pytest`), and LEGENDARIES.md sync check
- **74 unit tests** — `tests/test_engine.py` covering XP math, level-up boundaries, evolution thresholds, streak logic, trainer titles, milestones, and full I/O round-trips (stats, collection, catch system, buddy file parsing)
- **Schema versioning** — `buddy-stats.md` now writes a `schema_version` field; `read_stats` handles legacy files without it gracefully; migration hook ready for future format changes
- **LEGENDARIES sync check** — `scripts/check-legendaries.py` verifies every legendary/mythical in `POKEMON_POOL` is documented in `LEGENDARIES.md`; passes for all 69 entries
- **/ship workflow** — `.claude/commands/ship.md` project-local slash command: 9-step pre-commit checklist (simplify → syntax → tests → new feature tests → legendaries → version bump → CHANGELOG → smoke test)
- **Error logging** — `hooks/session-start.py` now writes exceptions to `~/.claude/pokemon-buddy-error.log` instead of silently swallowing them

---

## [2.0.8] — 2026-04-15

### Fixed
- **XP bar overflow after switch** — `do_switch` now stores the cumulative XP threshold (`xp_for_level(level+1)`) instead of the relative per-level delta, fixing the 160/100 overflow display.
- **XP bar shows relative progress** — all five render functions (`status`, `statusline`, `card`, `svg`, `announcement`) now subtract `xp_for_level(level)` before display, so the bar always shows progress *within* the current level (e.g. 60/100 at Lv.2 with 160 total XP).

---

## [2.0.7] — 2026-04-15

### Fixed
- **Switch: stats reset on swap** — `do_switch` now applies accumulated level-up stat boosts (+5 per level divisible by 5) so a Lv.15 buddy no longer reverts to Lv.1 base stats when switched back in.
- **Switch: moves reset on swap** — locked `???` moves are now replaced with the correct unlocked moves for the buddy's current level when switching.
- **Statusline chatter stale after switch** — `do_switch` now writes `Switched to <name>! 🔄` to `STATE_FILE` so the right-side chatter in the status bar reflects the swap immediately.

---

## [2.0.6] — 2026-04-15

### Changed
- Bump plugin.json version to 2.0.6

---

## [2.0.5] — 2026-04-15

### Added
- **Buddy rarity aura** — active buddy's rarity passively boosts wild catch odds for higher-rarity tiers. Rare buddy: rare ×2.0, legendary ×1.5. Legendary buddy: rare ×2.5, legendary ×2.0, mythical ×1.5. Mythical buddy: rare ×3.0, legendary ×2.5, mythical ×2.0.
- **Aura banner display** — when a catch is boosted by buddy aura, a `◆◆◆` banner fires with tier-scaled headline: `AURA RESONANCE` / `LEGENDARY AURA SURGE` / `THE COSMOS ALIGNED`. Banner uses fixed-width dividers (no right border) so emoji never misalign.

---

## [2.0.4] — 2026-04-15

### Added
- **Live plugin version in status bar** — statusline now reads and displays the installed plugin version

---

## [2.0.3] — 2026-04-15

### Fixed
- Pre-push hook: version bump now verified with automated test

---

## [2.0.2] — 2026-04-15

### Fixed
- **XP keyword matching** — substring collision bugs where short keywords (e.g. `fix`) would match inside longer unrelated words, awarding wrong XP amounts
- **XP rules expanded** — broader keyword coverage; added Bahasa Indonesia XP trigger support
- **Persona decoupled from auto-XP** — auto-XP now fires independently of whether Coach persona is active

---

## [2.0.1] — 2026-04-14

### Fixed
- **README** — Files installed, Token cost, Updating, Uninstalling, and Requirements sections now reflect v2.x plugin architecture (removed all v1.x shell-installer references)

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
