# /ship — Pre-commit checklist for pokemon-buddy-claude

Run this before every commit. Follow every step in order. Do not skip steps.

## Step 1 — Simplify changed code

Run `/simplify` — it works from `git diff HEAD` only, no full file reads.

The skill will fix issues and report a one-line summary. Wait for it to complete before continuing.

## Step 2 — Syntax check all Python files

Run:
```
python3 -m py_compile buddy-update.py lib/data.py hooks/session-start.py scripts/check-legendaries.py scripts/migrate_from_legacy.py
```

Fix any compile errors before continuing.

## Step 3 — Run the full test suite

Run:
```
python3 -m pytest tests/ -v
```

**If any test fails:**
- Read the failure output carefully
- Fix the root cause in the source code (do NOT weaken the test)
- Re-run until all tests pass

**Do not proceed to Step 4 until tests are green.**

## Step 4 — Add tests for new features

Look at what changed in this session. For each new function, new command argument, or new behaviour:
- Check if a test already covers it in `tests/test_engine.py`
- If not, add one. Tests go in the appropriate existing class or a new class if warranted
- Re-run `pytest tests/ -v` after adding tests

If nothing new was added (pure fix / refactor), skip to Step 5.

## Step 5 — Run the LEGENDARIES check

```
python3 scripts/check-legendaries.py
```

If new legendaries/mythicals were added to `POKEMON_POOL` in `lib/data.py` but not to `LEGENDARIES.md`, add them now.

## Step 6 — Determine version bump type

Review the changes and pick one:

| Change type | Bump |
|---|---|
| Bug fixes only, no new behaviour | **patch** (2.0.8 → 2.0.9) |
| New feature, new command, new Pokemon tier, new rule | **minor** (2.0.8 → 2.1.0) |
| Breaking change to file formats, install, or command API | **major** (2.0.8 → 3.0.0) |

When in doubt, use patch.

## Step 7 — Update VERSION and plugin.json

1. Edit `VERSION` — replace the version string with the new version
2. Edit `.claude-plugin/plugin.json` — update the `"version"` field to match

## Step 8 — Update CHANGELOG.md

Add a new section at the top (below the `---` separator after the header) in this exact format:

```
## [NEW_VERSION] — YYYY-MM-DD

### Added        ← only if features were added
- **Feature name** — one-line description of what it does and why

### Fixed        ← only if bugs were fixed
- **What was broken** — what the symptom was and what the fix does

### Changed      ← only if existing behaviour changed without it being a bug fix
- **What changed** — what it was before and what it is now now

---
```

Rules:
- Use only the sections that apply (omit `### Added` if nothing was added, etc.)
- Each bullet describes the user-visible impact, not the implementation detail
- Be specific — "fixed crash when collection empty" not "fixed bug"

## Step 9 — Final smoke test

Run the engine directly to confirm it still works end-to-end:
```
python3 buddy-update.py statusline
python3 buddy-update.py status
```

Both should produce output without errors.

## Done

Report back:
- Version bumped: old → new
- Tests: N passed
- CHANGELOG entry added
- Any simplifications made
