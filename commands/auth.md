---
description: Sign in to Pokemon Buddy Hub (one-time, links your CLI to a public profile)
---

Run:

`python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" auth`

This starts a device-code flow. The user opens the printed URL in their browser, signs in with GitHub, and the CLI receives a long-lived bearer token saved to `~/.claude/buddy-auth.json` (chmod 600). Print the output verbatim.

After auth completes, tell the user they can now run `/poke:publish` to push their trainer state to the hub.
