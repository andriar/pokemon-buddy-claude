# Changelog

All notable changes to Pokemon Buddy for Claude are documented here.
Format: [version] — date — description

---

## [2.28.0] — 2026-04-24

### Added
- **Argument hints** — slash commands now show inline option hints in Claude Code: `/poke:battle [brock|misty|surge|...]`, `/poke:party [list|add|remove|suggest|order]`, `/poke:dex [common|rare|fire|...]`, `/poke:switch <pokemon name>`, `/poke:item [list|equip|unequip]`. Reduces "which option?" friction.
- **Smart leader recommendation** — `/poke:battle` (no-arg) now highlights the super-effective undefeated leader as `⭐ RECOMMENDED` based on your active buddy's type, plus shows per-leader `×2/×0.5/×0` effectiveness tags. Falls back to lowest-level undefeated when no super-effective match exists.
- **`/poke:party suggest`** — auto-recommends a type-diverse trio from your collection sorted by level, prints ready-to-run `/poke:party order` command to apply.
- **2 new tests** — leader recommendation picks super-effective, excludes defeated (260 total).

### Changed
- `list_leaders()` accepts `buddy_type` + `buddy_level` for context-aware output.

---

## [2.27.0] — 2026-04-24

### Added
- **F16 Mega Evolution** — new `mega_stone` held item (💫). When equipped with Earth badge owned, gym battles get **+10 effective level** (huge win% swing vs higher-level leaders).
- Mega activation displayed in battle log: `💫 MEGA EVOLVED!` tag.
- `mega_stone` added to legendary (2%) and mythical (5%) wild-encounter drop tables.
- **3 new tests** — Earth badge gating, mega flag in log, drop-table entry (258 total).

### Changed
- **README overhauled** — added "Bond & Personality (v2.20+)" and "PvP & Mega Evolution (v2.26+)" sections surfacing Nature, Friendship, Shiny deepening, Seasonal events, Gym battles, Mega Stone.

---

## [2.26.0] — 2026-04-24

### Added
- **F14 PvP lite — Gym leader battles** — new `/poke:battle` command challenges canonical Kanto gym leaders (Brock, Misty, Lt. Surge, Erika, Koga, Sabrina, Blaine, Giovanni). Uses existing `run_battle` with TYPE_CHART effectiveness.
- **First-time win earns that leader's gym badge** (alt path to milestone-based unlocks). Rematches allowed but no duplicate badge.
- Compressed 4–6 line battle log: `⚔️ GYM BATTLE`, matchup, win% bar, flavor quote, result + XP.
- Win = +75 XP, loss = +10 XP participation. Defeated set persisted to `buddy-stats.md` under new `## Leaders Defeated` section.
- `/poke:battle` no-arg lists 8 leaders with ✓/· defeated status.
- **6 new tests** — leader table size, badge mapping, unknown-leader error, first-win awards badge, rematch dedup, loss consolation XP (255 total).

### Changed
- Stats schema: `leaders_defeated: set` added. Backwards-compatible (empty set for existing trainers).

---

## [2.25.0] — 2026-04-24

### Added
- **Friendship catch bonus** — active buddy's friendship adds up to +25% catch multiplier at max (255). Formula: `×(1.0 + friendship/255 × 0.25)`. Rewards long-term bonded buddies.
- **Riolu → Lucario** friendship evolution (daytime, friendship ≥220) added alongside existing Eevee branches.
- **2 new tests** — Riolu day evo, Riolu night no-op (249 total).

---

## [2.24.0] — 2026-04-24

### Added
- **F17b Friendship evolution** — Eevee branches based on friendship + time of day:
  - Eevee + friendship ≥220 + daytime (5:00–17:59) → **Espeon**
  - Eevee + friendship ≥220 + nighttime (18:00–4:59) → **Umbreon**
- Fires automatically during XP awards. Active buddy auto-renames to evolved form. Announcement: `💖 Bond evolution! Eevee → Espeon`.
- **4 new tests** — day evo, night evo, below-threshold no-op, active slot updates (247 total).

---

## [2.23.0] — 2026-04-24

### Added
- **F17 Friendship system** — every caught Pokémon starts at 70 friendship (canonical). Clamped 0–255.
- Active buddy earns friendship on every XP event: **+1 per award, +3 per level-up, +5 per evolution**.
- Trainer card shows `Friendship: 185/255  ♥♥♥♥♡` (5-heart bar) under ACTIVE BUDDY.
- **1 new milestone**: `friendship_max` Best Friends 💖 at 255 friendship.
- **5 new tests** — boost increments, clamps at max / min, unknown returns None, max triggers milestone (243 total).

### Changed
- **Collection schema**: table extended with `Nature` + `Friendship` columns. Old rows backfill nature='' and friendship=70 on read. Empty-cell form/nature now written as `-` to preserve column positions.

---

## [2.22.0] — 2026-04-24

### Added
- **F18 Seasonal events** — month-gated spawn boosts: Jan Ice, Feb Fairy, Mar Grass, Apr Water, May Flying, Jun Bug, Jul Fire, Aug Electric, Sep Psychic, Oct Ghost (×4), Nov Dark, Dec Ice (×4). Each month has flavor label (e.g. Halloween, Thunder Season).
- `_pick_wild` now filters to seasonal type with ~25–35% probability when pool contains a match. Pure probabilistic — no forced pick.
- Trainer card shows `🗓 Season: Halloween (Ghost ×4 spawn)`.
- **3 new tests** — all months defined, Halloween is Ghost, December Ice has ≥×4 boost (238 total).

---

## [2.21.0] — 2026-04-24

### Added
- **F11 Shiny deepening** — `shiny_count` int tracked in trainer stats, increments on every shiny catch.
- Trainer card now shows `✨×N` instead of a single `Shiny Caught` bool. Preserves prior binary flag for legacy grandfathering.
- **2 new milestones**: `shiny_5` Shiny Collector 🌟, `shiny_10` Shiny Connoisseur 🌠 — trigger at 5 and 10 shiny catches.
- **4 new tests** — milestone defs, 5/10 triggers, non-trigger at 4 (235 total).

### Changed
- Stats schema adds `**shiny_count**: N` line; existing trainers default to 0 and backfill naturally on next shiny catch.

---

## [2.20.0] — 2026-04-24

### Added
- **F13 Nature system** — every caught Pokémon gets 1 of 25 natures (Hardy, Adamant, Timid, Modest, etc.). Each nature boosts one stat and lowers another (5 neutral). Shown on trainer card under ACTIVE BUDDY as `Nature: Adamant (+ATK / -SPA)`.
- **5 new tests** — nature table size, `pick_nature` randomness, `nature_info` lookup, neutral nature count (231 total).

### Changed
- **Encounter output compressed** — token cost review cut verbose narration on high-frequency path:
  - Catch throw lines: merged ball + catch-bar into 1 line (was 2) — saves ~1 line per throw.
  - Flavor text now rare+ tiers only — common/uncommon drop the mood line.
  - Encounter dividers shortened from 54 chars to 44.
  - Dropped `"→ /poke:switch to make them your buddy"` hint on every catch.
  - Dropped shiny banner subtitle line + standalone `VICTORY!` blank line.
- Estimated ~25–40% token reduction on encounter announcements (~5–8 lines per wild catch).

---

## [2.19.0] — 2026-04-24

### Added
- **Wild level-up evolution** — 60+ Pokémon evolve automatically when they level up via Exp Share or party XP split. Full chains: Weedle→Kakuna→Beedrill, Magikarp→Gyarados, Pidgey→Pidgeot, Shinx→Luxray, Ralts→Gardevoir, Deino→Hydreigon, and more. Intermediate stages (Kakuna, Pidgeotto, etc.) keyed separately so multi-step chains complete correctly.
- **Pokédex expanded 151 → 283** — common (23→73), uncommon (29→61), rare (30→66), legendary (47→60), mythical (22→23). Regirock/Regice/Registeel, lake trio, Forces of Nature, Ogerpon, Manaphy, 130+ common/uncommon/rare Pokémon added.
- **`POKEDEX_IDS` expanded** — ~210 entries covering all new Pokémon for HTML card sprites.
- **26 new tests** — wild evolution chain logic, Pokédex pool integrity (no dupes, size), level cap display (210→226 total).

### Fixed
- **`199/200` at level cap replaced with `MAX ✦ Exp Share active`** — Arceus/Miraidon at Lv.100 showed `199/200` indefinitely (intentional cap math). Now clearly shows buddy is maxed and XP overflows to party.
- **Cross-tier duplicates** — Chandelure and Gyarados appeared in both uncommon and rare; removed from uncommon.
- **`do_choose` collection entry** — initial entry now includes `form: ''` and `party: [name]` for schema consistency.
- **Trade evo hint in `/poke:choose`** — Gastly, Abra, Machop now show their evolution trigger in the starter picker.

### Changed
- **File reads per XP call: 11x → 5x** — collection read once and passed as `col=` param through `sync_active_to_collection`, `distribute_overflow_xp`, `run_encounter`, `add_to_collection`. Held item extracted from already-read buddy text instead of 3 extra file reads.
- **Exp Share announcement: O(party) lines → 1 summary line** — was listing all 98 party members; now shows count + up to 5 level-ups.
- **`/poke:history` default: 128 lines → 13 lines** — summary mode by default; full log via `--verbose` or `--export`.
- **Gym badge display** — full names replaced with emoji strip (`🪨💧⚡...`), ~60% shorter.

---

## [2.18.0] — 2026-04-24

### Added
- **`/poke:history`** — chronological journey narrative grouped by month, sourced from buddy journal + badge rows + party snapshot
- **`/poke:history --export`** → writes `journey.html` (readable in browser)
- **`_render_journey(export_html)`** — parses journal table rows, groups by `YYYY-MM`, lists milestones by date

---

## [2.17.0] — 2026-04-24

### Added
- **Egg hatching system** — earn an egg via: 10 Pokémon caught, 7-day streak, or gym badge milestone. One egg slot at a time.
- **Egg XP ticking** — each XP gain adds progress (Soul badge required). After 200 XP → egg hatches, Lv.1 baby joins collection.
- **Baby Pokémon pool** — Pichu, Cleffa, Igglybuff, Magby, Elekid, Smoochum, Tyrogue, Togepi
- **Egg progress in `/poke:status`** — `🥚 Hatching ⚡ Pichu [████████░░] 160/200 XP (80%)`
- **Hatch announcement** — `🥚✨ Egg hatched! ⚡ Pichu (Lv.1) joined your party!`
- **`STATS_SCHEMA_VER` bumped to 5** — added egg fields to `buddy-stats.md`

---

## [2.16.0] — 2026-04-24

### Added
- **Weekly raid boss** — legendary boss auto-generated every Monday from the legendary pool (deterministic from ISO week hash). HP = 5000.
- **XP deals raid damage** — each XP gain chips `xp × 0.1` HP off the boss (Earth badge required). KO adds boss to Pokédex.
- **`/poke:raid`** — shows current boss, HP bar, status, total damage dealt, week ID
- **`buddy-raid.json`** — persistent raid state (`week_id`, `boss_name`, `hp_remaining`, `captured`, `damage_log`)
- **Raid message in XP announcement** — `🐉 Raid: Rayquaza 62% HP (-5 dmg)` shown on each XP gain when raid active

---

## [2.15.0] — 2026-04-24

### Added
- **Trade evolutions** — real events trigger evolution for trade-evo Pokémon in party:
  - `/poke:export` → Gastly→Haunter→Gengar, Abra→Kadabra→Alakazam
  - `/poke:backup` → Machop→Machoke→Machamp
- **`TRADE_EVOLUTIONS`** in `lib/data.py` — `{pre_evo: (evo_name, emoji, trigger)}` dict
- **`apply_trade_evolutions(trigger)`** — scans full collection, mutates in-place, returns list of evolution strings for announcement

---

## [2.14.0] — 2026-04-24

### Added
- **Regional variants** — repeat catches have a 15% chance to roll a regional form. Seeded forms: Alolan Vulpix (Ice ❄️), Galarian Zigzagoon (Dark 🦡)
- **`REGIONAL_FORMS` + `REGIONAL_CATCH_CHANCE`** in `lib/data.py` — dict keyed by base name, value list of `(region, display_name, emoji, type)` tuples
- **`form` column in collection** — stores region name (e.g. `Alolan`); displayed in Pokédex grouped under base

### Changed
- **`add_to_collection` rolls regional form** on repeat catch if base name is in `REGIONAL_FORMS`; regional entry gets distinct display name + emoji + type stored directly
- **`displayed_form` respects `form` field** — regional entries bypass the starter evolution chain lookup
- **Collection file schema** — new `| Form |` column (8th); backward-compatible (empty string for non-regional)

---

## [2.13.0] — 2026-04-24

### Added
- **Party battles** — up to 3 Pokémon in `active_party`; XP splits 60%/25%/15% across lead/slot2/slot3 when Thunder badge is earned
- **`/poke:party list|add|remove|order`** — manage the active trio; lead is always slot 1 (same as `active`)
- **Party XP block in announcement** — `👥 Party XP (60/25/15 split): • Pikachu +25 XP` shown when split is active
- **`**ActiveParty**:` field in collection file** — persists party order across sessions; backward-compatible (defaults to `[active]`)

### Changed
- **`write_collection` accepts `party` arg** — all call sites updated to pass `col.get('party')`
- **`read_collection` returns `party` field** — list of up to 3 names; falls back to `[active]` for old files

---

## [2.12.0] — 2026-04-24

### Added
- **Full Gen-1+ type chart** (`TYPE_CHART` in `lib/data.py`) — 18 types, all super-effective/resisted/immune interactions encoded as multipliers (2.0/0.5/0.0)
- **Effectiveness line in encounter** — battle block now shows `⚔️ super effective!` / `⚠️ not very effective...` / `✗ no effect!`

### Changed
- **`run_battle` uses multiplicative type effectiveness** — replaces flat `TYPE_ADVANTAGE +20` bonus. `win_pct = base × effectiveness`, clamped [5, 95] (floor dropped from 20 → 5 to allow immune matchups to show real consequence)
- **Electric vs Ground → immune (0.0×) → 5% win chance** instead of flat 70%
- **`TYPE_ADVANTAGE` kept** in `lib/data.py` as legacy alias for backward-compatible test imports
- **4 battle tests updated** to unpack `(won, pct, effectiveness)` and match new formula

---

## [2.11.0] — 2026-04-24

### Added
- **Held items system** — equip one item to your active buddy for passive effects:
  - 🥚 Lucky Egg → +50% XP earned
  - 🎀 Choice Band → +20% battle win chance
  - 🪙 Amulet Coin → 2× catch rate
  - ✨ Shiny Charm → 1/100 shiny rate (stacks with Cascade badge)
  - 🪨 Everstone → blocks evolution
- **`/poke:item list|equip|unequip`** — manage item bag and equip/unequip items
- **Item drop on catch** — gated behind Rainbow badge (1-3% per encounter, tier-scaled drop table)
- **Item display in `/poke:status`** — shows equipped item + effect
- **Item drop announcement** — `💎 Item drop! 🥚 Lucky Egg added to bag` on lucky catches
- **`**HeldItem**:` field in buddy file** — persists through all `patch_buddy` calls; new trainers start with `none`

### Changed
- **XP badge now shows all active multipliers** — `+N XP ×1.12×1.50` when both streak and Lucky Egg active
- **Evolution gated by Everstone** — equipping Everstone prevents all evolution regardless of level
- **`STATS_SCHEMA_VER` bumped to 4** — added per-item bag counts to `buddy-stats.md`

---

## [2.10.0] — 2026-04-24

### Added
- **Gym badge system** — 8 Kanto badges earned through in-game activity, each unlocking a feature:
  - 🪨 Boulder (first catch) → Exp Share
  - 💧 Cascade (10 caught) → Shiny rate 1/200 → 1/150
  - ⚡ Thunder (Level 10) → Party XP slot 2 (F5 dep)
  - 🌈 Rainbow (5 features) → Held items (F4 dep)
  - 💜 Soul (7-day streak) → Breeding (F9 dep)
  - 🌿 Marsh (20 caught) → Double berry drop chance
  - 🔥 Volcano (3 ships) → Evolution 1 level earlier
  - 🌍 Earth (Level 30) → Raid battles (F8 dep)
- **`has_unlock(feature, stats)`** — feature-gate helper used throughout the engine
- **`next_badge_hint(stats)`** — returns the next unearned badge + how to earn it
- **Gym badge row in `/poke:status`** — shows earned badges + next target hint
- **Level-up chatter now shows next badge hint** — statusline displays `Level N! Next: 🌿 Marsh Badge: catch 20 Pokémon`
- **Backward compat** — existing trainers auto-receive badges for milestones already earned on first read; no re-earn required

### Changed
- **Exp Share gated behind Boulder badge** — new trainers start without it; existing trainers grandfathered in
- **Shiny rate 1/150 with Cascade badge** — up from 1/200 base
- **Berry drops doubled with Marsh badge**
- **Evolution 1 level earlier with Volcano badge**
- **`STATS_SCHEMA_VER` bumped to 3** — added `## Gym Badges Earned` section to `buddy-stats.md`

---

## [2.9.0] — 2026-04-24

### Added
- **Daily streak XP multiplier** — consecutive-day coding streaks now boost XP earned. Formula: `1.0 + min(streak, 30) × 0.02` (caps at ×1.60 on a 30-day streak). Multiplier stacks with the existing combo multiplier and is applied before `clamp_to_cap`.
- **Streak multiplier in XP flash badge** — announcement shows `+25 XP ×1.10` when a streak multiplier is active, so you always see the boost.
- **`🔥N` streak tag in statusline** — when streak ≥ 3 days, statusline appends `🔥N` (e.g. `🔥7`) before the persona flag.
- **Live multiplier in status card** — streak row in `/poke:status` now shows current multiplier: `🔥 Streak: 7 days (best: 30)  ×1.14 XP`.

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
