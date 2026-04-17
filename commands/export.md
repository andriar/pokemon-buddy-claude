---
description: Export your trainer card as a shareable HTML page + README snippet
---

Generate a shareable trainer card the user can post on GitHub, Discord, Twitter, etc.

1. Run:

`python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" html`

This writes `trainer-card.html` to the current working directory. Print the output verbatim.

2. Then run:

`python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" readme`

Print the output inside a fenced ```markdown code block so the user can copy-paste it straight into their GitHub profile README.

3. Briefly tell the user:
   - The HTML card is at `./trainer-card.html` — open in any browser for the full interactive experience.
   - Drag into Discord/Slack as a file attachment, or host it on GitHub Pages.
   - The markdown snippet links to the card in a GitHub README.
   - Re-run `/poke:export` any time to refresh the card with their latest progress.
