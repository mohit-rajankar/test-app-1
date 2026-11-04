#!/usr/bin/env bash
# ==============================================================================
# Helper Script: Get Developer Username & Build Compliant Branch Name
# ==============================================================================
# Usage:
#   .githooks/get_developer_username.sh
#   .githooks/get_developer_username.sh feature add-login-form
#   .githooks/get_developer_username.sh --create feature add-login-form
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/get_developer_username.py"

PYTHON_BIN=""
if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
fi

# Verify functional Python interpreter
if [ -n "$PYTHON_BIN" ]; then
    if ! "$PYTHON_BIN" -c "import sys" >/dev/null 2>&1; then
        PYTHON_BIN=""
    fi
fi

if [ -n "$PYTHON_BIN" ] && [ -f "$PYTHON_SCRIPT" ]; then
    exec "$PYTHON_BIN" "$PYTHON_SCRIPT" "$@"
fi

# Pure Bash Fallback if Python is unavailable
DETECTED_USER=""

# Strategy 1: Git config github.user
if [ -z "$DETECTED_USER" ]; then
    DETECTED_USER=$(git config --get github.user 2>/dev/null || echo "")
fi

# Strategy 2: Remote origin URL owner
if [ -z "$DETECTED_USER" ]; then
    ORIGIN_URL=$(git config --get remote.origin.url 2>/dev/null || echo "")
    DETECTED_USER=$(echo "$ORIGIN_URL" | sed -nE 's#.*github\.com[:/]([^/]+)/.*#\1#p')
fi

# Strategy 3: Git config user.name
if [ -z "$DETECTED_USER" ]; then
    DETECTED_USER=$(git config --get user.name 2>/dev/null || echo "")
fi

# Strategy 4: Environment variable
if [ -z "$DETECTED_USER" ]; then
    DETECTED_USER="${GITHUB_USER:-${USERNAME:-${USER:-developer}}}"
fi

# Sanitize username
CLEAN_USER=$(echo "$DETECTED_USER" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9_-]//g')
CLEAN_USER="${CLEAN_USER:-developer}"

if [ $# -eq 0 ]; then
    echo "$CLEAN_USER"
    exit 0
fi

BRANCH_TYPE="${1:-feature}"
DESCRIPTION="${2:-update}"
TODAY=$(date +%Y-%m-%d)
CLEAN_DESC=$(echo "$DESCRIPTION" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9._-]//g')
BRANCH_NAME="${BRANCH_TYPE}/${CLEAN_USER}/${TODAY}/${CLEAN_DESC}"

echo "$BRANCH_NAME"
