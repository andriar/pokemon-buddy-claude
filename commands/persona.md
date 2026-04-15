---
description: Toggle the Pokémon Master Coach persona on/off (usage, /persona on | /persona off)
argument-hint: on | off
---

Parse the user's argument (`$ARGUMENTS`). It should be `on` or `off`. If missing or unrecognized, show usage: `/persona on` or `/persona off`.

---

## If `on`

Disclose the cost clearly first:

```
⚠ Enabling the Pokémon Coach persona will:
  • Add a skill import to your ~/.claude/CLAUDE.md
  • Make Claude speak as a Pokémon trainer across all projects
  • Cost roughly 150–250 extra tokens per conversation turn (always-on)
  • Trigger automatic XP awards after meaningful tasks

To keep the buddy silent and cheap, decline and just use /poke:* commands manually.
```

Ask: **"Enable the Coach persona? (yes / no)"**

If **yes**, append these two blocks to `~/.claude/CLAUDE.md` (create the file if missing). Check for duplicates before appending — skip any block already present:

```
## Auto XP
After completing a meaningful task (bug fix, feature, refactor, ship, tests, concept), automatically run `/poke:xp <brief description>`.

## Active Persona — Pokémon Master Coach
Load the `pokemon-coach` skill from the pokemon-buddy plugin whenever discussing code.
```

Use the Edit or Write tool. Confirm the edit and tell the user the persona will activate on their next Claude Code session.

If **no**, tell them they can still use the buddy silently via slash commands, and the status bar still animates — they just skip the persona voice + auto-XP. They can enable later anytime. Offer to add just the `## Auto XP` block if they still want automatic XP awards without the persona.

---

## If `off`

Use the Edit tool on `~/.claude/CLAUDE.md` to remove only the persona block:

- `## Active Persona — Pokémon Master Coach` heading and its `Load the pokemon-coach skill...` line
- Do **NOT** remove the `## Auto XP` block — auto-XP awards are independent of the persona

Also remove any legacy `@pokemon-persona.md` or `@buddy-pokemon.md` imports.

Confirm removal. Tell the user:

- Status bar, slash commands, and state files are untouched
- Claude will stop speaking in-character on next session
- Auto-XP awards will **continue** running (the `## Auto XP` block stays)
- They can re-enable the persona anytime with `/poke:persona on`
