#!/bin/sh
# Run one /explore-app scenario in a fresh, non-interactive Claude Code session.
# Sonnet orchestrates; the bot itself runs on Haiku (see .claude/agents/app-explorer.md).
# Usage: scripts/run.sh <app> <scenario>
set -eu
if [ $# -ne 2 ]; then
  echo "Usage: $0 <app> <scenario>" >&2
  exit 1
fi
cd "$(dirname "$0")/.."
CLAUDE=$(command -v claude || echo "$HOME/.local/bin/claude")
exec "$CLAUDE" -p --model sonnet "/explore-app $1 $2"
