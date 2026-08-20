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

project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

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
uv python install "$(cat "$project_dir/.python-version")"

# `pre-commit run --all-files` needs pre-commit itself plus the system
# binaries a few hooks shell out to (shellcheck, shfmt, editorconfig-checker
# aka `ec`). CI gets all of these from mise (jdx/mise-action), which reads
# .mise.toml as the single source of truth for versions. mise itself isn't
# usable here: its installer (mise.run) and most of its tool backends fetch
# prebuilt binaries straight from GitHub Releases, and that path is blocked
# by this sandbox's network policy -- only pypi.org/files.pythonhosted.org,
# registry.npmjs.org and the Go module proxy are reachable without going
# through it. So each tool below is installed from one of those reachable
# backends instead, with the version read out of .mise.toml so these pins
# can't drift from what CI actually uses.
mise_tool_version() {
  python3 -c "
import sys, tomllib
with open('$project_dir/.mise.toml', 'rb') as f:
    v = tomllib.load(f)['tools'][sys.argv[1]]
print(v['version'] if isinstance(v, dict) else v)
" "$1"
}

uv tool install --quiet "pre-commit==$(mise_tool_version 'pipx:pre-commit')" --with pre-commit-uv
# The shellcheck-py package version is the upstream ShellCheck version plus a
# packaging suffix (e.g. 0.11.0.1 for ShellCheck 0.11.x); .mise.toml only
# pins the ShellCheck minor version, so match on that prefix.
uv tool install --quiet "shellcheck-py==$(mise_tool_version shellcheck).*"

export GOBIN="$HOME/.local/bin"
go install "mvdan.cc/sh/v3/cmd/shfmt@v$(mise_tool_version shfmt)"
# .mise.toml only pins the editorconfig-checker major version; `go install`
# has no wildcard match, so track latest within that major (the import path
# is already major-version-locked to v3).
go install "github.com/editorconfig-checker/editorconfig-checker/v3/cmd/editorconfig-checker@latest"
ln -sf "$GOBIN/editorconfig-checker" "$GOBIN/ec"
