---
description: Import a trainer's party from a buddy-export.json backup file
---

Restore a party (buddy, stats, collection) from a JSON backup produced by `/poke:backup`.

**Warning the user first:** this overwrites the current buddy, stats, and collection. The previous files are saved alongside with a `.bak` suffix so they can be recovered manually if needed.

Run:

`python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" import $ARGUMENTS`

Print the output verbatim. If the user passed no path, the command looks for `./buddy-export.json` in the current directory.

After a successful import, suggest they run `/poke:status` to see the restored party.
