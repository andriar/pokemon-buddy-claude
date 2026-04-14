# Migrating from v1.x (shell install) to v2.x (plugin)

The v2.x plugin keeps all your existing progress — Pokémon, XP, level, streak, collection, badges, and trainer stats. The migration only removes v1.x **install artifacts** (the engine script, statusline wrapper, persona file, CLAUDE.md imports). Your state files are untouched.

## TL;DR

```
/plugin marketplace add andriar/pokemon-buddy-claude
/plugin install poke
/poke:migrate
```

Restart Claude Code. Done.

## What stays

| File | Contents | Action |
|---|---|---|
| `~/.claude/buddy-pokemon.md` | Your buddy — species, level, XP, moves | ✅ Kept |
| `~/.claude/pokemon-collection.md` | Your caught Pokémon party / Pokédex | ✅ Kept |
| `~/.claude/buddy-stats.md` | Trainer stats, streak, lifetime XP, milestone flags | ✅ Kept |

The plugin reads these exact same files — no data migration needed.

## What gets removed

| Artifact | Why |
|---|---|
| `~/.claude/buddy-update.py` | Replaced by plugin-local copy |
| `~/.claude/statusline-buddy.sh` | Replaced by plugin-registered statusline |
| `~/.claude/pokemon-persona.md` | Persona is now an opt-in skill |
| `~/.claude/commands/buddy*.md` `pokemon-switch.md` | Replaced by `/poke:*` plugin commands |
| CLAUDE.md `@buddy-pokemon.md` / `@pokemon-persona.md` imports | Persona is opt-in now (saves ~200 tokens/turn) |
| `settings.json` statusLine pointing at legacy script | Plugin registers its own statusLine |

All removed files are backed up to `~/.claude/buddy-v1-backup/` in case you want to roll back.

## Step-by-step

1. **Install the plugin** — inside Claude Code:
   ```
   /plugin marketplace add andriar/pokemon-buddy-claude
   /plugin install poke
   ```

2. **Restart Claude Code** so the plugin loads.

3. **Run the migration** — it's interactive and will ask before each destructive step:
   ```
   /poke:migrate
   ```

   You'll see prompts for:
   - Removing persona imports from CLAUDE.md (y/n)
   - Clearing the legacy statusline from settings.json (y/n)
   - Deleting legacy files (y/n — files go to `buddy-v1-backup/` first)

4. **Restart one more time** so the new plugin-registered statusline takes over.

5. **(Optional)** If you loved the Pokémon Master Coach voice, turn it back on:
   ```
   /poke:persona on
   ```
   This is opt-in now because it adds tokens to every conversation turn. If you skip it, your buddy is silent and cheap — status bar still animates, XP commands still work manually.

## Rolling back to v1.x

If something goes wrong:

1. `/plugin uninstall poke`
2. Copy files from `~/.claude/buddy-v1-backup/` back to `~/.claude/`
3. Re-add the statusLine and CLAUDE.md imports (see backup files)
4. Pin to the v1.3.2 release: https://github.com/andriar/pokemon-buddy-claude/releases/tag/v1.3.2

## FAQ

**Q: Will I lose my Charizard?**
A: No. Your `buddy-pokemon.md` is never touched. Same Pokémon, same level, same moves.

**Q: Why is the persona opt-in now?**
A: It was loaded into every Claude conversation in every project via CLAUDE.md import — ~150–250 tokens/turn, always on. That's real API cost. The plugin default keeps your buddy visible (status bar, XP commands) but silent. Opt in when you want the flavor, opt out when you want cheap.

**Q: Do slash command names change?**
A: Yes. `/buddy` → `/poke:status`. `/buddy-xp` → `/poke:xp`. The namespacing is a plugin requirement. Your muscle memory will catch up fast.

**Q: Can I run both v1 and v2 at the same time?**
A: No — both would fight over the statusline. Migrate or stay on v1.x.
