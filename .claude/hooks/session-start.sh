#!/bin/bash
set -euo pipefail

# Claude Code on the web only: local sessions are expected to install tools
# themselves via their own package manager of choice.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

project_dir="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

# This repo's openspec-*/opsx:* skills (.claude/skills/openspec-*) shell out
# to a bare `openspec` command. The real CLI is published as
# @fission-ai/openspec on npm -- the unscoped `openspec` package on npm is an
# unrelated, unmaintained placeholder and must not be installed instead.
# Pinned to the major version verified against these skills; bump deliberately.
npm install -g "@fission-ai/openspec@^1.9.0"

# .pre-commit-config.yaml's editorconfig-checker/shellcheck/shfmt hooks and
# `pre-commit` itself expect the binaries `.mise.toml` pins to already be on
# PATH, the same way CI gets them via jdx/mise-action. Install mise itself
# (once per session), then that subset of .mise.toml's [tools].
#
# `uv`/`uvx` are deliberately left out of this pass: they're kept fresh by
# the pip-based step below instead of mise's pin, and mixing the two would
# reintroduce the exact staleness problem that step fixes. `bats` is skipped
# too -- it installs via mise's aqua backend, which fetches the upstream
# bats-core/bats-core release through a GitHub *API* tarball endpoint rather
# than a plain release-asset download, and Claude Code on the web only
# allows GitHub API access to repos explicitly attached to the session. That
# install 403s here regardless of mise/network access; bats isn't wired
# into this repo's poe/Makefile/pre-commit gates, so skipping it costs
# nothing.
if ! command -v mise >/dev/null 2>&1; then
  curl -fsS https://mise.run | sh
fi
mise_bin="$HOME/.local/bin/mise"
"$mise_bin" trust "$project_dir"
"$mise_bin" install -C "$project_dir" editorconfig-checker shellcheck shfmt "pipx:pre-commit"
# mise's usual activation relies on shell-rc sourcing, which Claude Code's
# non-interactive Bash tool doesn't trigger (~/.bashrc bails out early for
# non-interactive shells). Symlink the installed tools' real shim names --
# which don't always match the tool name, e.g. editorconfig-checker -> `ec`
# -- straight into ~/.local/bin, which is already on PATH for every Bash
# call.
for shim in "$HOME"/.local/share/mise/shims/*; do
  name="$(basename "$shim")"
  case "$name" in
  uv | uvx) continue ;;
  esac
  ln -sf "$mise_bin" "$HOME/.local/bin/$name"
done

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
