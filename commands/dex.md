---
description: Browse your Pokédex — all caught Pokémon, optionally filtered
argument-hint: [common|uncommon|rare|legendary|mythical|starter|shiny|fire|water|grass|...]
---

Usage:
- `/poke:dex` — all caught Pokémon grouped by rarity
- `/poke:dex <tier>` — filter by rarity: `common`, `uncommon`, `rare`, `legendary`, `mythical`, `starter`, `shiny`
- `/poke:dex <type>` — filter by Pokémon type: `fire`, `water`, `grass`, `electric`, `psychic`, `dragon`, etc.

Run `python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" dex $ARGUMENTS` and print the output verbatim.
