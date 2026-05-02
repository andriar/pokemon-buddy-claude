---
description: Diagnose collection drift — stuck evolutions, friendship gaps, XP/level mismatches. Usage — /poke:doctor [--fix]
---

Run `python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" doctor $ARGUMENTS` and print the output verbatim.

`--fix` bumps friendship of pending evolutions up to the threshold so the next `/poke:xp` (during the correct day/night window) triggers the evolution.
