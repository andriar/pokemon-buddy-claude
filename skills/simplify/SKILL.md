---
name: simplify
description: Lean code review — works only from git diff, no file reads, no subagents. Fixes reuse, quality, and efficiency issues directly inline.
---

## Goal

Review and fix the changed code for quality, reuse, and efficiency. Operate entirely from the diff — do not read whole files or spawn agents.

## Step 1 — Get the diff

Run:
```
git diff HEAD
```

If the diff is empty, check staged changes:
```
git diff --cached
```

Work only from this output. Do not read any source files beyond what the diff shows.

## Step 2 — Review the diff inline

Scan the changed lines for these issues, in priority order:

**Reuse**
- New function that duplicates an existing one visible in the diff context
- Inline logic that a function already shown in the diff could handle
- Hardcoded constant that matches one already visible in the diff

**Quality**
- `f'...'` string with no `{...}` interpolation — remove the `f` prefix
- Comment that describes WHAT the code does (not WHY) — delete it
- Local constant defined inside a function that never changes — hoist to module level
- Stale data read from a snapshot that was taken before the relevant mutations

**Efficiency**
- Dict/object lookup inside a loop where the key never changes — move it outside
- Repeated computation of the same value within a tight loop
- Unnecessary intermediate variables used only once

## Step 3 — Fix directly

Apply every fix you found by editing the file. Do not explain each fix — just make the change.

If a finding is a false positive, skip it silently.

## Step 4 — Report

One-line summary per fix made. If nothing needed fixing, say "Code is clean."
