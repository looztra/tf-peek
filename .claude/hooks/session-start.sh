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

# The container image bakes in a pinned `uv` at build time. When that build
# predates a Python GA release, `uv`'s bundled python-build-standalone catalog
# doesn't know the GA build exists, so `uv run`/`uv python install` silently
# fall back to whatever pre-release is already cached locally (e.g.
# cpython-3.14.0rc2) instead of erroring or fetching the real release --
# tripping real interpreter regressions the GA release already fixed (see
# `.python-version` and pydantic/pydantic#12544). Upgrading `uv` here, once
# per session, keeps that catalog current without pinning this repo's
# `.python-version` to an exact patch that would need manual upkeep.
pip install --user --upgrade --quiet uv
# Pre-warm the interpreter `.python-version` requests so the first `uv run`
# in the session doesn't pay the download cost mid-command.
project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
uv python install "$(cat "$project_dir/.python-version")"
