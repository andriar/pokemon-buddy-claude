---
description: Back up your buddy + stats + collection as a transferable JSON file
---

Write a full party backup (buddy, stats, collection) the user can transfer to another machine or share with another trainer.

Run:

`python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" backup $ARGUMENTS`

Print the output verbatim. If the user passed a path as `$ARGUMENTS`, it's used as the output file — otherwise the backup is written to `./buddy-export.json`.

Briefly remind the user they can restore it on any machine with `/poke:import <path>`.
