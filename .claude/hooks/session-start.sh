#!/bin/bash
set -euo pipefail

# Claude Code on the web only: local sessions are expected to install tools
# themselves via their own package manager of choice.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# This repo's openspec-*/opsx:* skills (.claude/skills/openspec-*) shell out
# to a bare `openspec` command. The real CLI is published as
# @fission-ai/openspec on npm -- the unscoped `openspec` package on npm is an
# unrelated, unmaintained placeholder and must not be installed instead.
# Pinned to the major version verified against these skills; bump deliberately.
npm install -g "@fission-ai/openspec@^1.9.0"
