#!/usr/bin/env bash
# dev.sh — swap between local dev and installed production
#
# Usage:
#   bash dev.sh          → deploy local repo → plugin cache (dev mode)
#   bash dev.sh restore  → restore cache from repo's install.sh (prod mode)
#   bash dev.sh status   → show which version is active

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(cat "$REPO_DIR/VERSION" 2>/dev/null || echo '2.1.0')"
CACHE_DIR="$HOME/.claude/plugins/cache/pokemon-buddy-claude/poke/$VERSION"

# Files that contain the core engine
ENGINE_FILES=(
    "buddy-update.py"
    "lib/data.py"
    "lib/__init__.py"
)

cmd="${1:-deploy}"

case "$cmd" in
# ── deploy ─────────────────────────────────────────────────────────────────
deploy)
    if [ ! -d "$CACHE_DIR" ]; then
        echo "❌ Cache not found: $CACHE_DIR"
        echo "   Install the plugin first: /plugin install poke"
        exit 1
    fi

    echo "🔧 DEV DEPLOY — repo → plugin cache (v$VERSION)"
    echo "   $REPO_DIR"
    echo "   → $CACHE_DIR"
    echo ""

    for f in "${ENGINE_FILES[@]}"; do
        src="$REPO_DIR/$f"
        dst="$CACHE_DIR/$f"
        if [ -f "$src" ]; then
            mkdir -p "$(dirname "$dst")"
            cp "$src" "$dst"
            echo "   ✅ $f"
        else
            echo "   ⚠️  skipped (not found): $f"
        fi
    done

    echo ""
    echo "✅ Done. /poke:xp and /poke:status now use your local code."
    echo "   Run 'bash dev.sh restore' to go back to the installed version."
    ;;

# ── restore ────────────────────────────────────────────────────────────────
restore)
    echo "🔄 RESTORE — reinstalling the plugin to reset cache..."
    echo ""
    echo "   Run inside Claude Code:"
    echo "     /plugin uninstall poke"
    echo "     /plugin install poke"
    echo ""
    ;;

# ── status ─────────────────────────────────────────────────────────────────
status)
    echo "📦 Version: $VERSION"
    echo "   Repo:  $REPO_DIR"
    echo "   Cache: $CACHE_DIR"
    echo ""
    if [ ! -d "$CACHE_DIR" ]; then
        echo "❌ Cache not installed. Run: /plugin install poke"
        exit 0
    fi
    echo "File sync status:"
    for f in "${ENGINE_FILES[@]}"; do
        src="$REPO_DIR/$f"
        dst="$CACHE_DIR/$f"
        if [ ! -f "$src" ] || [ ! -f "$dst" ]; then
            echo "   ⚠️  $f (missing)"
        elif diff -q "$src" "$dst" > /dev/null 2>&1; then
            echo "   ✅ $f (in sync)"
        else
            echo "   🔧 $f (repo differs from cache — run 'bash dev.sh' to deploy)"
        fi
    done
    ;;

*)
    echo "Usage: bash dev.sh [deploy|restore|status]"
    echo ""
    echo "  deploy   Sync local repo → plugin cache (default)"
    echo "  restore  Print plugin reinstall instructions"
    echo "  status   Show sync status of engine files"
    exit 1
    ;;
esac
