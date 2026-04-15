#!/usr/bin/env python3
"""CI lint: verify every legendary/mythical in POKEMON_POOL is listed in LEGENDARIES.md.

Usage:
    python3 scripts/check-legendaries.py

Exit 0 = all present. Exit 1 = missing entries (prints diff).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.data import POKEMON_POOL

LEGENDARIES_MD = ROOT / 'LEGENDARIES.md'

def main():
    if not LEGENDARIES_MD.exists():
        print(f'ERROR: {LEGENDARIES_MD} not found')
        sys.exit(1)

    doc = LEGENDARIES_MD.read_text(encoding='utf-8')

    missing = []
    for tier in ('legendary', 'mythical'):
        for name, ptype, emoji in POKEMON_POOL[tier]:
            if name not in doc:
                missing.append((tier, name))

    if missing:
        print(f'FAIL: {len(missing)} Pokemon in POKEMON_POOL are missing from LEGENDARIES.md:')
        for tier, name in missing:
            print(f'  [{tier}] {name}')
        print()
        print('Fix: add an entry for each missing Pokemon to LEGENDARIES.md.')
        sys.exit(1)

    total = len(POKEMON_POOL['legendary']) + len(POKEMON_POOL['mythical'])
    print(f'OK: all {total} legendary/mythical Pokemon are documented in LEGENDARIES.md')


if __name__ == '__main__':
    main()
