# Changelog

All notable changes to Pokemon Buddy for Claude are documented here.
Format: [version] — date — description

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
