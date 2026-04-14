---
description: Pick your starter Pokémon (first-time setup)
---

The user is picking their starter. Present this menu exactly:

```
╔═══════════════════════════════════════════════════╗
║   PICK YOUR STARTER POKÉMON                       ║
╚═══════════════════════════════════════════════════╝

  1. 🔥 Charmander   Fire       Frontend / JavaScript
  2. 🌿 Bulbasaur    Grass      Backend / Python
  3. 💧 Squirtle     Water      Database / SQL
  4. ⚡ Pikachu      Electric   Fullstack
  5. 👻 Gastly       Ghost      Security / Reverse Eng
  6. 🐉 Dratini      Dragon     Mobile / Android
  7. 🪨 Geodude      Rock       DevOps / Infra
  8. 🧠 Abra         Psychic    AI / ML
  9. 🥊 Machop       Fighting   QA / Testing
  10. 🌑 Umbreon     Dark       Cybersecurity
```

Ask the user to reply with a **number** (or the Pokémon name). Once they respond, run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/buddy-update.py" switch "<chosen name>"
```

Then print the output verbatim and welcome them as their new trainer.
