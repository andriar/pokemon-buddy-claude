# Pokemon Buddy — Next-Level Features Roadmap

Status: **COMPLETE** — all 10 features shipped in v2.9.0–v2.18.0 (2026-04-24).

Core files to know:
- `buddy-update.py` — single source of truth for all logic
- `buddy-pokedex.py` — static data (STARTER_DATA, MOVE_UNLOCKS, RARITY_START_LEVEL, BUDDY_RARITY_BOOST)
- `~/.claude/buddy-stats.md` — per-trainer persistent stats
- `~/.claude/buddy-collection.md` — party + pokedex
- `~/.claude/buddy-pokemon.md` — active buddy state (XP, level, journal)

---

## F1 — Daily streak multiplier 🔥

**Goal**: reward consecutive-day XP activity. Skip day → reset.

**Data**:
- `buddy-stats.md`: add `streak_days`, `last_xp_date`, `best_streak`

**Logic** (`buddy-update.py`):
- On XP gain, compare `TODAY` vs `last_xp_date`:
  - same day → no change
  - yesterday → `streak_days += 1`
  - older → reset to 1
- Multiplier curve: `1.0 + min(streak_days, 30) * 0.02` (cap +60% at 30 days)
- Apply to `add_xp` before `clamp_to_cap`

**UI**:
- Statusline: append `🔥N` when streak ≥ 3
- `/poke:status` card: streak row with best-ever

**Acceptance**:
- Two XP gains same day → streak unchanged
- XP yesterday + today → streak = 2
- Skip 48h → reset to 1
- Multiplier visible in XP flash badge (`+25 XP ×1.10`)

---

## F2 — Type matchup combat overhaul ⚔️

**Goal**: replace flat `buddy_level/wild_level*70` with type chart.

**Data** (`buddy-pokedex.py`):
- `TYPE_CHART`: `{attacker_type: {defender_type: multiplier}}` (2.0 / 1.0 / 0.5 / 0.0)
- Real Gen-1 chart suffices for 151 dex

**Logic**:
- `run_battle`: `effectiveness = TYPE_CHART[buddy_type][wild_type]`
- `win_pct = base * effectiveness` clamped [5, 95]
- Existing `TYPE_ADVANTAGE` (line ~518) → replace with full chart lookup

**UI**:
- Encounter line: `⚔️ super effective!` / `not very effective...` / `no effect!`
- Flash badge on crit win

**Acceptance**:
- Water buddy vs Fire wild → 2× win chance
- Electric vs Ground → 0× (auto-lose)
- Neutral matchup ≈ current behavior

---

## F3 — Gym badges unlock features 🎖️

**Goal**: gate mechanics behind badges. Progression reward.

**Data** (`buddy-stats.md`):
- `gym_badges_earned`: list of badge IDs (Boulder, Cascade, …)

**Unlock map**:
| Badge | Unlock |
|---|---|
| Boulder | Exp Share active (currently always-on) |
| Cascade | Shiny rate 1/200 → 1/150 |
| Thunder | 2nd party slot gains XP too |
| Rainbow | Held items drop enabled (F4 dep) |
| Soul | Breeding (F9 dep) |
| Marsh | Double berry drop |
| Volcano | Evolution 1 level earlier |
| Earth | Raid battles (F8 dep) |

**Logic**:
- Existing `check_milestones` earns badges by activity
- Add `has_unlock(feature)` guard wherever gated feature runs
- Backward compat: grandfather existing trainers (no re-earn)

**Acceptance**:
- New trainer without Boulder → no Exp Share on cap
- Statusline shows next-badge hint on lv-up

---

## F4 — Held items 💎

**Goal**: consumable/equippable items modify buddy stats.

**Data** (`buddy-collection.md` or new `buddy-inventory.md`):
- `held_item` on active buddy
- `item_bag`: `{item_id: count}`

**Items** (MVP set):
- Lucky Egg → +50% XP
- Choice Band → +20% win_pct
- Amulet Coin → 2× catch rate
- Shiny Charm → 1/100 shiny (stacks with F3)
- Everstone → block evolution

**Logic**:
- Drop table in `run_encounter` (1-3% per encounter)
- Apply modifiers in XP math, battle math, catch math
- New command `/poke:item <equip|use|list>`

**Acceptance**:
- Lucky Egg equipped → flash badge shows `+25 XP ×1.5 = 37`
- Everstone blocks lv evolution even at threshold

---

## F5 — Party battles (active trio) 👥

**Goal**: top 3 buddies share XP on all tasks.

**Data** (`buddy-collection.md`):
- `active_party`: list of up to 3 names (first = front/statusline)

**Logic**:
- `/poke:switch` keeps legacy 1-buddy semantics
- New `/poke:party add|remove|order`
- XP award: split 60% / 25% / 15% across trio
- Encounter: lead buddy fights, others bench-boost
- Exp Share waterfall (existing) still handles overflow

**Acceptance**:
- `+100 XP` task → lead 60, 2nd 25, 3rd 15
- Only lead shown in statusline, `/poke:status` shows all 3

---

## F6 — Regional variants 🌍

**Goal**: repeat catches can roll regional form. Same dex slot, different emoji + type.

**Data** (`buddy-pokedex.py`):
- `REGIONAL_FORMS`: `{base_name: [(region, emoji, type_override), …]}`
- Seed: Alolan (Raticate, Meowth, Vulpix), Galarian (Zigzagoon, Meowth, Ponyta)

**Logic**:
- On catch, if `name` already owned: 15% roll for regional variant
- Store as `form` field on collection entry
- `displayed_form` already exists — extend

**Acceptance**:
- 2nd Meowth caught → possible Alolan form with Dark type
- Dex shows variants grouped under base

---

## F7 — Trade evolutions 🔄

**Goal**: tie evolutions to real external actions.

**Triggers**:
- `/poke:export` (HTML trainer card) → trigger Haunter→Gengar, Kadabra→Alakazam
- `/poke:backup` generated → Machoke→Machamp
- PR merged (detect via git? optional) → Graveler→Golem

**Data**:
- `trade_evolution_pending`: names queued for evo on next qualifying event

**Logic**:
- Hook into existing export / backup / ship commands
- Check qualifying party members, apply evolution, flash badge

**Acceptance**:
- Catch Haunter → run `/poke:export` → evolves to Gengar with fanfare

---

## F8 — Weekly raid boss 🐉

**Goal**: shared multi-session boss. XP chips damage. Capture on KO.

**Data** (new `buddy-raid.json`):
- `week_id` (ISO week), `boss_name`, `boss_hp`, `hp_remaining`
- `damage_log`: list of `{date, xp_applied, damage}`

**Logic**:
- Auto-generate weekly boss from legendary pool (Mon 00:00)
- Each XP gain: `damage = add_xp * 0.1`, subtract from `hp_remaining`
- On KO: add boss to pokedex, bonus XP, flash badge

**UI**:
- Statusline during raid: `🐉 Rayquaza 62% HP`
- `/poke:raid` shows progress

**Acceptance**:
- Sun night KO without finish → new boss next Mon
- Same boss persists across terminal sessions

---

## F9 — Breeding / egg hatching 🥚

**Goal**: long-arc reward. Egg earned on milestone, hatch after N XP.

**Data**:
- `egg`: `{species_hint, xp_needed, xp_progress}`

**Logic**:
- Earn egg on: 10 catches / gym badge / streak 7
- Each XP gain: `egg.xp_progress += add_xp`
- On hatch: add Lv.1 baby pokemon (Pichu, Cleffa, Magby, etc) to collection
- Only 1 egg slot at a time

**Acceptance**:
- Streak hits 7 → egg awarded
- After ~200 XP → hatch animation in flash badge

---

## F10 — Journey timeline 📜

**Goal**: `/poke:history` — narrative of trainer's pokemon-buddy journey.

**Data source**:
- Existing `buddy-pokemon.md` journal rows
- `buddy-stats.md` first-date fields
- Optional: git log from user's projects (date-aligned)

**Render**:
- Markdown timeline grouped by month
- Milestones: first catch, first evolution, each gym badge, legendaries
- `/poke:history --export` → shareable `journey.html`

**Acceptance**:
- Output readable chronological story
- Regenerable anytime from existing state files (no extra tracking)

---

## Execution order recommendation

1. **F1** (streak) — small, high retention impact, no deps
2. **F3** (badge unlocks) — structural; do before F4/F8/F9 that depend on it
3. **F4** (held items) — deepens every other system
4. **F2** (type matchup) — combat feels real
5. **F5** (party battles) — complements Exp Share waterfall already shipped
6. F6 → F7 → F8 → F9 → F10 as time allows

Each PR: bump version, update CHANGELOG.md, update README feature list.
