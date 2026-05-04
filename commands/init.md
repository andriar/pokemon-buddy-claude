---
description: Interactive Pokemon Buddy setup — pick starter, statusline mode, persona. Writes to settings.json.
argument-hint: "[--quick | --reset]"
---

# /poke:init

Interactive setup wizard for Pokemon Buddy. Collects user preferences via `AskUserQuestion`, then writes to `~/.claude/settings.json` under `env` block.

## Behavior

If user passed `--quick`: write defaults silently (Pidgeotto, normal, persona on, auto-xp on).
If user passed `--reset`: reset all Pokemon Buddy env vars to defaults.

Otherwise, ask questions one at a time, then write answers.

## Questions

1. **POKE_STARTER** — header "Starter"
   - Question: "Pick your starter Pokémon. Sets your active buddy and unlocks starter moves + type affinity."
   - Options: `Pidgeotto (Recommended)` description "Flying type — balanced stats, early flight ability" | `Charizard` description "Fire/Flying — offensive heavy, solo carry potential" | `Blastoise` description "Water type — defensive, team support focus"
   - Only ask if no active buddy exists yet (check ~/.claude/buddy-active or buddy metadata)

2. **POKE_STATUSLINE_MODE** — header "Status Bar"
   - Question: "POKE_STATUSLINE_MODE — how much detail in Claude Code status bar. 'compact' shows version + buddy name + level (minimal tokens). 'normal' adds XP bar + state (current). 'full' includes stats, badges, streak, party count (verbose)."
   - Options: `compact` description "Version · Buddy · Lv (minimal)" | `normal (Recommended)` description "^ + XP bar + state" | `full` description "^ + stats + badges + streak"

3. **POKE_COACH_ENABLED** — header "Coach"
   - Question: "Enable Pokemon Master Coach persona? Drops Pokémon battle metaphors & strategy tips into responses about code work."
   - Options: `Yes (Recommended)` description "Load pokemon-coach persona for framing" | `No` description "Disable persona (can re-enable later)"

4. **POKE_AUTO_XP** — header "Auto-XP"
   - Question: "Auto-grant XP after meaningful work? If yes, you'll be prompted to claim XP after bug fixes, features, refactors, and shipped code."
   - Options: `Yes (Recommended)` description "Remind after completion, you approve grants" | `No` description "Manual only — run /poke:xp <desc> yourself"

## Writing answers

After collecting all answers, write to `~/.claude/settings.json`:

```bash
python3 <<'PY'
import json, os
p = os.path.expanduser("~/.claude/settings.json")
with open(p) as f: s = json.load(f)
env = s.setdefault("env", {})
# Update with collected answers
env.update({
  "POKE_STATUSLINE_MODE": "normal",  # replace with user answer
  "POKE_COACH_ENABLED": "true",
  "POKE_AUTO_XP": "true",
})
with open(p, "w") as f: json.dump(s, f, indent=2)
print("Wrote Pokemon Buddy settings:", sorted(env))
PY
```

If POKE_STARTER was set, also write to `~/.claude/buddy-active`.

## Final output

Print settings confirmation and remind:

> Restart Claude Code to load new settings.
