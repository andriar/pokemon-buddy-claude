# Pokemon Buddy for Claude — Repo Guide

This repo is a distributable Claude Code companion system. It is NOT a coding project — there is no app to run, no tests, no build step.

## What each file does

| File | Purpose |
|---|---|
| `install.sh` | Interactive installer — copies files to `~/.claude/`, patches CLAUDE.md + settings.json |
| `buddy-update.py` | Core engine: XP math, level-ups, evolution, wild catches, collection, status rendering |
| `statusline-buddy.sh` | One-liner delegating to Python for Claude Code status bar |
| `pokemon-persona.md` | Pokemon Master Coach persona (loaded by user's CLAUDE.md) |
| `commands/` | Slash commands: `/buddy`, `/buddy-xp`, `/buddy-badge`, `/pokemon-switch` |

## Do not read files at startup

All runtime data lives in `~/.claude/` after install — not here. When working on this repo, only read files when directly asked to modify them.

## How to contribute

1. Edit files here
2. Test by copying to `~/.claude/` manually or re-running `install.sh`
3. Keep `buddy-update.py` as the single source of truth for all logic
