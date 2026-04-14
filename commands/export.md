---
description: Export your trainer card as a shareable SVG + README snippet
---

Generate a shareable trainer card the user can post on GitHub, Discord, Twitter, etc.

1. Run:

`python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" svg`

This writes `trainer-card.svg` to the current working directory. Print the output verbatim.

2. Then run:

`python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" readme`

Print the output inside a fenced ```markdown code block so the user can copy-paste it straight into their GitHub profile README.

3. Briefly tell the user:
   - The SVG is at `./trainer-card.svg` — drag into Discord/Slack, or drop into a GitHub repo.
   - The markdown snippet embeds the SVG in a GitHub README.
   - Re-run `/poke:export` any time to refresh the card with their latest progress.
