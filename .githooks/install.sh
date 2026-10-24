#!/usr/bin/env bash
# ==============================================================================
# Developer Activation Script for Git Central Hooks
# ==============================================================================
# Usage:
#   bash .githooks/install.sh
# or:
#   ./.githooks/install.sh
# ==============================================================================

set -euo pipefail

echo "================================================================="
echo "[SETUP] Configuring Local Git Hooks"
echo "================================================================="

# 1. Verify we are inside a Git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "[ERROR] Current directory is not a Git repository."
    exit 1
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

# 2. Verify .githooks directory exists
if [ ! -d ".githooks" ]; then
    echo "[ERROR] '.githooks' directory not found in $REPO_ROOT."
    echo "        Ensure this repository has received synchronized hooks from central."
    exit 1
fi

# 3. Configure core.hooksPath
git config core.hooksPath .githooks

# 4. Ensure all hooks inside .githooks are executable (for Unix/macOS/Git Bash)
if compgen -G ".githooks/*" > /dev/null; then
    chmod +x .githooks/* 2>/dev/null || true
fi

# 5. Verify the configuration
ACTIVE_HOOKS_PATH=$(git config --get core.hooksPath || echo "")

if [ "$ACTIVE_HOOKS_PATH" = ".githooks" ]; then
    echo "[SUCCESS] Git hooks path configured to '.githooks'."
    echo ""
    echo "Active hooks in .githooks/:"
    for hook in .githooks/*; do
        if [ -f "$hook" ]; then
            echo "  - $(basename "$hook")"
        fi
    done
    echo ""
    echo "Git will now execute hooks directly from .githooks on commit/push."
    echo "================================================================="
else
    echo "[ERROR] Failed to set core.hooksPath. Current value: '$ACTIVE_HOOKS_PATH'"
    exit 1
fi
