---
description: Publish your trainer profile to Pokemon Buddy Hub (public showcase)
---

Push the user's current buddy, party, Pokédex, stats, and badges to the hub.

1. Run:

`python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" publish`

Print the output verbatim. The output includes the public profile URL.

2. Briefly remind the user:
   - Profile is public — anyone with the URL can see it.
   - Re-run `/poke:publish` any time to refresh.
   - `/poke:unpublish` removes the profile.
   - `/poke:profile-url` prints the URL again.

If the command prints "Not signed in", run `/poke:auth` first.
