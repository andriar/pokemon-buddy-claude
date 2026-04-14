---
description: Migrate from legacy v1.x shell install to plugin v2.x (preserves your buddy)
---

The user wants to migrate their v1.x Pokémon Buddy install to the plugin version. Run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/migrate_from_legacy.py"
```

Print the script's output verbatim. The script is interactive and will ask the user to confirm each destructive step (CLAUDE.md edits, file deletion). Do NOT bypass prompts — the user must approve each.

After the script finishes, remind the user to **restart their Claude Code session** for the plugin statusline to take over.
