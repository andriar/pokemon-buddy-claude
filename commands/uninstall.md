---
description: Uninstall the poke plugin — choose to keep buddy data or clean everything
argument-hint: [keep|clean]
---

Two uninstall modes:

- **keep** (default) — wipe ALL plugin traces but preserve `buddy-pokemon.md`, `pokemon-collection.md`, and `buddy-stats.md`. Reinstalling later auto-restores your buddy, collection, and streak.
- **clean** — purge everything including buddy data. Reinstalling starts from `/poke:choose`.

Both modes reverse the plugin-side changes: unwire statusLine (restore backup if any), drop marketplace entry, remove plugin state files (`pokemon-buddy-plugin.json`, `buddy-encounter.json`, `buddy-version`, `buddy-v1-backup/`).

## Step 1 — Detect mode from `$ARGUMENTS`

- If the argument is `clean` (case-insensitive): **clean uninstall**.
- If the argument is `keep`, empty, or anything else: **keep-data uninstall**.

If no argument was given, briefly ask the user which mode they want before continuing. Do not proceed destructively by default.

## Step 2 — Run purge

For **keep** mode:

```
python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" purge keep
```

For **clean** mode:

```
python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" purge all
```

Print the output verbatim.

## Step 3 — Tell the user to remove the plugin

The plugin package itself can only be removed by Claude Code's plugin manager. Instruct the user to run:

```
/plugin uninstall poke
```

Also remind them: if their global `~/.claude/CLAUDE.md` has "Auto XP" or "Active Persona — Pokémon Master Coach" sections from an older install, they should manually delete those lines — the plugin cannot safely edit the user's personal CLAUDE.md.

## Step 4 — Confirm

- **keep mode**: tell them their buddy data is safe and will auto-restore on reinstall.
- **clean mode**: tell them a fresh install will start at `/poke:choose` again.

Keep the final message short (3–4 lines).
